#!/usr/bin/env python3
"""
ComfyUI Advanced API CLI
Command-line interface for managing ComfyUI workflows
"""

import argparse
import sys
from pathlib import Path
import logging
import json
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from client import ComfyUIClient
from workflow_manager import WorkflowManager
from queue_manager import QueueManager, JobStatus
from utils import load_config, setup_logging, format_duration, extract_output_images

logger = logging.getLogger(__name__)


def cmd_send(args):
    """Send a workflow to ComfyUI"""
    # Load config
    config = load_config(Path(args.config))
    setup_logging(config)

    # Initialize client
    comfyui_config = config['comfyui']
    client = ComfyUIClient(
        host=comfyui_config['host'],
        port=comfyui_config['port'],
        protocol=comfyui_config['protocol'],
        timeout=comfyui_config['timeout']
    )

    # Load workflow
    workflow_mgr = WorkflowManager()
    workflow_path = Path(args.workflow)
    workflow = workflow_mgr.load_workflow(workflow_path)

    # Validate if enabled
    if config['workflow'].get('validate_before_send', True):
        is_valid, errors = workflow_mgr.validate_workflow(workflow)
        if not is_valid:
            logger.error("Workflow validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1

    # Apply modifications if specified
    if args.update:
        for update in args.update:
            parts = update.split('=', 1)
            if len(parts) != 2:
                logger.error(f"Invalid update format: {update}")
                continue

            path, value = parts
            path_parts = path.split('.')
            if len(path_parts) != 2:
                logger.error(f"Invalid path format: {path}")
                continue

            node_id, input_name = path_parts
            # Try to parse value as JSON
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass  # Keep as string

            workflow_mgr.update_node_input(workflow, node_id, input_name, value)

    # Connect WebSocket if enabled
    if config['websocket'].get('enable', True):
        try:
            client.connect_websocket()

            # Setup progress callback
            def on_progress(data):
                if 'data' in data:
                    value = data['data'].get('value', 0)
                    max_val = data['data'].get('max', 100)
                    print(f"\rProgress: {value}/{max_val}", end='', flush=True)

            client.on('progress', on_progress)
        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")

    # Send workflow
    print(f"Sending workflow: {workflow_path.name}")
    start_time = time.time()

    try:
        response = client.queue_prompt(workflow)
        prompt_id = response.get('prompt_id')

        if not prompt_id:
            logger.error("Failed to queue prompt")
            return 1

        print(f"Queued with prompt_id: {prompt_id}")

        # Wait for completion
        if args.wait:
            print("Waiting for completion...")
            history = client.wait_for_completion(prompt_id, timeout=args.timeout)

            duration = time.time() - start_time
            print(f"\nCompleted in {format_duration(duration)}")

            # Extract and download images
            images = extract_output_images(history)
            if images:
                print(f"\nGenerated {len(images)} image(s):")

                output_config = config.get('output', {})
                if output_config.get('download_results', True):
                    output_dir = Path(output_config.get('output_dir', './outputs'))
                    output_dir.mkdir(parents=True, exist_ok=True)

                    for img in images:
                        filename = img['filename']
                        print(f"  - {filename}")

                        # Download image
                        try:
                            image_data = client.get_image(
                                filename,
                                subfolder=img['subfolder'],
                                folder_type=img['type']
                            )

                            output_path = output_dir / filename
                            with open(output_path, 'wb') as f:
                                f.write(image_data)

                            print(f"    Saved to: {output_path}")
                        except Exception as e:
                            logger.error(f"Failed to download {filename}: {e}")

                    # Save metadata if enabled
                    if output_config.get('save_metadata', True):
                        metadata_path = output_dir / f"{prompt_id}_metadata.json"
                        with open(metadata_path, 'w') as f:
                            json.dump(history, f, indent=2)
                        print(f"\nMetadata saved to: {metadata_path}")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        client.disconnect_websocket()


def cmd_batch(args):
    """Process multiple workflows in batch"""
    # Load config
    config = load_config(Path(args.config))
    setup_logging(config)

    # Initialize client
    comfyui_config = config['comfyui']
    client = ComfyUIClient(
        host=comfyui_config['host'],
        port=comfyui_config['port'],
        protocol=comfyui_config['protocol'],
        timeout=comfyui_config['timeout']
    )

    # Initialize queue manager
    batch_config = config.get('batch', {})
    queue_mgr = QueueManager(
        client,
        max_concurrent=batch_config.get('max_concurrent', 3),
        retry_on_failure=batch_config.get('retry_on_failure', True),
        max_retries=batch_config.get('max_retries', 3)
    )

    # Setup callbacks
    def on_job_completed(job):
        print(f"✓ Job {job.job_id} completed")

    def on_job_failed(job):
        print(f"✗ Job {job.job_id} failed: {job.error}")

    queue_mgr.on('job_completed', on_job_completed)
    queue_mgr.on('job_failed', on_job_failed)

    # Load workflows
    workflow_mgr = WorkflowManager()
    workflows_dir = Path(args.directory)

    if not workflows_dir.exists():
        logger.error(f"Directory not found: {workflows_dir}")
        return 1

    workflow_files = list(workflows_dir.glob('*.json'))
    if not workflow_files:
        logger.error(f"No workflow files found in {workflows_dir}")
        return 1

    print(f"Found {len(workflow_files)} workflow(s)")

    # Add jobs
    for wf_path in workflow_files:
        try:
            workflow = workflow_mgr.load_workflow(wf_path)
            job_id = wf_path.stem
            queue_mgr.add_job(job_id, workflow, metadata={'source': str(wf_path)})
            print(f"  Added: {wf_path.name}")
        except Exception as e:
            logger.error(f"Failed to load {wf_path}: {e}")

    # Start processing
    print(f"\nProcessing with {batch_config.get('max_concurrent', 3)} concurrent jobs...")
    queue_mgr.start()

    try:
        queue_mgr.wait_for_completion(timeout=args.timeout)
    except TimeoutError:
        logger.error("Batch processing timed out")
        queue_mgr.stop(wait=False)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        queue_mgr.stop(wait=False)
        return 1

    # Print statistics
    stats = queue_mgr.get_statistics()
    print("\n" + "=" * 50)
    print("Batch Processing Results:")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Cancelled: {stats['cancelled']}")
    print("=" * 50)

    queue_mgr.stop()
    return 0 if stats['failed'] == 0 else 1


def cmd_validate(args):
    """Validate a workflow"""
    workflow_mgr = WorkflowManager()
    workflow_path = Path(args.workflow)

    try:
        workflow = workflow_mgr.load_workflow(workflow_path)
        is_valid, errors = workflow_mgr.validate_workflow(workflow)

        if is_valid:
            print(f"✓ Workflow is valid: {workflow_path.name}")

            # Show info
            info = workflow_mgr.get_workflow_info(workflow)
            print(f"\nWorkflow Information:")
            print(f"  Total nodes: {info['total_nodes']}")
            print(f"  Node types:")
            for node_type, count in sorted(info['node_types'].items()):
                print(f"    - {node_type}: {count}")

            return 0
        else:
            print(f"✗ Workflow validation failed: {workflow_path.name}")
            print(f"\nErrors:")
            for error in errors:
                print(f"  - {error}")
            return 1

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


def cmd_queue_status(args):
    """Get queue status"""
    # Load config
    config = load_config(Path(args.config))

    # Initialize client
    comfyui_config = config['comfyui']
    client = ComfyUIClient(
        host=comfyui_config['host'],
        port=comfyui_config['port'],
        protocol=comfyui_config['protocol']
    )

    try:
        queue_data = client.get_queue()

        print("Queue Status:")
        print(f"  Running: {len(queue_data.get('queue_running', []))}")
        print(f"  Pending: {len(queue_data.get('queue_pending', []))}")

        if args.verbose:
            print("\n" + json.dumps(queue_data, indent=2))

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='ComfyUI Advanced API Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file (default: config.yaml)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Send command
    send_parser = subparsers.add_parser('send', help='Send a workflow to ComfyUI')
    send_parser.add_argument('workflow', help='Path to workflow JSON file')
    send_parser.add_argument(
        '--wait', '-w',
        action='store_true',
        help='Wait for completion'
    )
    send_parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=None,
        help='Timeout in seconds'
    )
    send_parser.add_argument(
        '--update', '-u',
        action='append',
        help='Update node input (format: node_id.input_name=value)'
    )

    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Process workflows in batch')
    batch_parser.add_argument('directory', help='Directory containing workflow JSON files')
    batch_parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=None,
        help='Timeout in seconds'
    )

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a workflow')
    validate_parser.add_argument('workflow', help='Path to workflow JSON file')

    # Queue status command
    queue_parser = subparsers.add_parser('queue', help='Get queue status')
    queue_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == 'send':
        return cmd_send(args)
    elif args.command == 'batch':
        return cmd_batch(args)
    elif args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'queue':
        return cmd_queue_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
