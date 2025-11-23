"""
Queue Manager for batch processing and managing multiple ComfyUI workflows
"""

import time
import threading
from queue import Queue, Empty
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a workflow job"""
    job_id: str
    workflow: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    prompt_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0


class QueueManager:
    """Manages batch processing of ComfyUI workflows with concurrency control"""

    def __init__(self, client, max_concurrent: int = 3,
                 retry_on_failure: bool = True, max_retries: int = 3):
        """
        Initialize Queue Manager

        Args:
            client: ComfyUIClient instance
            max_concurrent: Maximum number of concurrent jobs
            retry_on_failure: Retry failed jobs
            max_retries: Maximum retry attempts
        """
        self.client = client
        self.max_concurrent = max_concurrent
        self.retry_on_failure = retry_on_failure
        self.max_retries = max_retries

        self.job_queue: Queue = Queue()
        self.jobs: Dict[str, Job] = {}
        self.running_jobs: List[str] = []

        self.workers: List[threading.Thread] = []
        self.running = False
        self.paused = False

        self.callbacks: Dict[str, List[Callable]] = {
            'job_started': [],
            'job_completed': [],
            'job_failed': [],
            'job_cancelled': [],
            'queue_empty': [],
        }

        logger.info(f"Initialized Queue Manager (max_concurrent={max_concurrent})")

    def add_job(self, job_id: str, workflow: Dict[str, Any],
                metadata: Optional[Dict[str, Any]] = None) -> Job:
        """
        Add a job to the queue

        Args:
            job_id: Unique job identifier
            workflow: ComfyUI workflow dictionary
            metadata: Optional metadata for the job

        Returns:
            Created Job object
        """
        if job_id in self.jobs:
            raise ValueError(f"Job ID already exists: {job_id}")

        job = Job(
            job_id=job_id,
            workflow=workflow,
            metadata=metadata or {}
        )

        self.jobs[job_id] = job
        self.job_queue.put(job_id)

        logger.info(f"Added job to queue: {job_id}")
        return job

    def add_jobs_from_list(self, workflows: List[Dict[str, Any]],
                          job_prefix: str = "job") -> List[Job]:
        """
        Add multiple jobs from a list of workflows

        Args:
            workflows: List of workflow dictionaries
            job_prefix: Prefix for auto-generated job IDs

        Returns:
            List of created Job objects
        """
        jobs = []
        for i, workflow in enumerate(workflows):
            job_id = f"{job_prefix}_{i:04d}_{int(time.time())}"
            job = self.add_job(job_id, workflow)
            jobs.append(job)

        logger.info(f"Added {len(jobs)} jobs to queue")
        return jobs

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        return self.jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get job status"""
        job = self.get_job(job_id)
        return job.status if job else None

    def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get jobs with specific status"""
        return [job for job in self.jobs.values() if job.status == status]

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False otherwise
        """
        job = self.get_job(job_id)
        if not job:
            return False

        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            self._trigger_callbacks('job_cancelled', job)
            logger.info(f"Cancelled pending job: {job_id}")
            return True

        elif job.status == JobStatus.RUNNING:
            try:
                # Try to interrupt the execution
                self.client.interrupt_execution()
                job.status = JobStatus.CANCELLED
                self._trigger_callbacks('job_cancelled', job)
                logger.info(f"Cancelled running job: {job_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to cancel job {job_id}: {e}")
                return False

        return False

    def _process_job(self, job_id: str):
        """Process a single job"""
        job = self.get_job(job_id)
        if not job:
            return

        try:
            # Update status
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            self.running_jobs.append(job_id)

            logger.info(f"Processing job: {job_id}")
            self._trigger_callbacks('job_started', job)

            # Queue the workflow
            response = self.client.queue_prompt(job.workflow)
            job.prompt_id = response.get('prompt_id')

            # Wait for completion
            if job.prompt_id:
                history = self.client.wait_for_completion(job.prompt_id)
                job.result = history
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()

                logger.info(f"Job completed: {job_id} (prompt_id: {job.prompt_id})")
                self._trigger_callbacks('job_completed', job)
            else:
                raise RuntimeError("No prompt_id received")

        except Exception as e:
            logger.error(f"Job failed: {job_id} - {e}")
            job.error = str(e)
            job.retry_count += 1

            # Retry logic
            if self.retry_on_failure and job.retry_count <= self.max_retries:
                logger.info(f"Retrying job {job_id} (attempt {job.retry_count}/{self.max_retries})")
                job.status = JobStatus.PENDING
                self.job_queue.put(job_id)
            else:
                job.status = JobStatus.FAILED
                job.completed_at = time.time()
                self._trigger_callbacks('job_failed', job)

        finally:
            if job_id in self.running_jobs:
                self.running_jobs.remove(job_id)

    def _worker(self):
        """Worker thread function"""
        while self.running:
            try:
                # Wait if paused
                while self.paused and self.running:
                    time.sleep(0.5)

                # Check concurrent limit
                while len(self.running_jobs) >= self.max_concurrent and self.running:
                    time.sleep(0.5)

                if not self.running:
                    break

                # Get next job
                try:
                    job_id = self.job_queue.get(timeout=1)
                except Empty:
                    continue

                # Check if job was cancelled
                job = self.get_job(job_id)
                if job and job.status == JobStatus.CANCELLED:
                    self.job_queue.task_done()
                    continue

                # Process job
                self._process_job(job_id)
                self.job_queue.task_done()

            except Exception as e:
                logger.error(f"Worker error: {e}")

    def start(self, num_workers: Optional[int] = None):
        """
        Start processing jobs

        Args:
            num_workers: Number of worker threads (defaults to max_concurrent)
        """
        if self.running:
            logger.warning("Queue manager already running")
            return

        num_workers = num_workers or self.max_concurrent
        self.running = True

        for i in range(num_workers):
            worker = threading.Thread(target=self._worker, name=f"Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

        logger.info(f"Started queue manager with {num_workers} workers")

    def stop(self, wait: bool = True):
        """
        Stop processing jobs

        Args:
            wait: Wait for current jobs to complete
        """
        logger.info("Stopping queue manager...")
        self.running = False

        if wait:
            for worker in self.workers:
                worker.join()

        self.workers.clear()
        logger.info("Queue manager stopped")

    def pause(self):
        """Pause job processing"""
        self.paused = True
        logger.info("Queue manager paused")

    def resume(self):
        """Resume job processing"""
        self.paused = False
        logger.info("Queue manager resumed")

    def wait_for_completion(self, timeout: Optional[float] = None):
        """
        Wait for all jobs to complete

        Args:
            timeout: Optional timeout in seconds
        """
        start_time = time.time()

        while not self.job_queue.empty() or self.running_jobs:
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError("Queue did not complete within timeout")
            time.sleep(0.5)

        logger.info("All jobs completed")
        self._trigger_callbacks('queue_empty', None)

    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {
            'total_jobs': len(self.jobs),
            'pending': len(self.get_jobs_by_status(JobStatus.PENDING)),
            'running': len(self.get_jobs_by_status(JobStatus.RUNNING)),
            'completed': len(self.get_jobs_by_status(JobStatus.COMPLETED)),
            'failed': len(self.get_jobs_by_status(JobStatus.FAILED)),
            'cancelled': len(self.get_jobs_by_status(JobStatus.CANCELLED)),
            'queue_size': self.job_queue.qsize(),
            'is_running': self.running,
            'is_paused': self.paused,
        }

        return stats

    def on(self, event_type: str, callback: Callable):
        """
        Register a callback for events

        Args:
            event_type: Event type
            callback: Callback function
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def _trigger_callbacks(self, event_type: str, job: Optional[Job]):
        """Trigger callbacks for an event"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(job)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def clear_completed(self):
        """Remove completed jobs from history"""
        completed = [
            job_id for job_id, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
        ]

        for job_id in completed:
            del self.jobs[job_id]

        logger.info(f"Cleared {len(completed)} completed jobs")
