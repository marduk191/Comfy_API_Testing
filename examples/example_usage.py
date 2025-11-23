#!/usr/bin/env python3
"""
Example usage of the ComfyUI API Interface
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from client import ComfyUIClient
from workflow_manager import WorkflowManager
from queue_manager import QueueManager


def example_basic_usage():
    """Basic usage example"""
    print("=" * 60)
    print("Example 1: Basic Workflow Execution")
    print("=" * 60)

    # Initialize client
    client = ComfyUIClient(host="127.0.0.1", port=8188)

    # Load workflow
    workflow_mgr = WorkflowManager()
    workflow = workflow_mgr.load_workflow(Path("workflows/example_workflow.json"))

    # Validate workflow
    is_valid, errors = workflow_mgr.validate_workflow(workflow)
    if not is_valid:
        print("Workflow validation failed:")
        for error in errors:
            print(f"  - {error}")
        return

    # Send workflow
    response = client.queue_prompt(workflow)
    prompt_id = response['prompt_id']
    print(f"Queued prompt: {prompt_id}")

    # Wait for completion
    history = client.wait_for_completion(prompt_id)
    print("Workflow completed!")


def example_websocket_progress():
    """Example with WebSocket progress monitoring"""
    print("\n" + "=" * 60)
    print("Example 2: WebSocket Progress Monitoring")
    print("=" * 60)

    client = ComfyUIClient(host="127.0.0.1", port=8188)

    # Connect WebSocket
    client.connect_websocket()

    # Setup progress callback
    def on_progress(data):
        if 'data' in data:
            value = data['data'].get('value', 0)
            max_val = data['data'].get('max', 100)
            percentage = (value / max_val * 100) if max_val > 0 else 0
            print(f"Progress: {percentage:.1f}% ({value}/{max_val})")

    def on_executing(data):
        node_id = data.get('data', {}).get('node')
        if node_id:
            print(f"Executing node: {node_id}")

    client.on('progress', on_progress)
    client.on('executing', on_executing)

    # Load and send workflow
    workflow_mgr = WorkflowManager()
    workflow = workflow_mgr.load_workflow(Path("workflows/example_workflow.json"))

    response = client.queue_prompt(workflow)
    prompt_id = response['prompt_id']
    print(f"Queued prompt: {prompt_id}")

    # Wait for completion
    history = client.wait_for_completion(prompt_id)
    print("Workflow completed!")

    client.disconnect_websocket()


def example_workflow_template():
    """Example using workflow templates"""
    print("\n" + "=" * 60)
    print("Example 3: Workflow Templates")
    print("=" * 60)

    workflow_mgr = WorkflowManager()

    # Load base workflow
    base_workflow = workflow_mgr.load_workflow(Path("workflows/example_workflow.json"))

    # Create a template with parameters
    workflow_mgr.create_template(
        name="text_to_image",
        workflow=base_workflow,
        parameters={
            "prompt": {"node_id": "6", "input_name": "text"},
            "seed": {"node_id": "3", "input_name": "seed"},
            "steps": {"node_id": "3", "input_name": "steps"},
        }
    )

    # Instantiate template with different values
    for i in range(3):
        workflow = workflow_mgr.instantiate_template(
            "text_to_image",
            {
                "prompt": f"a beautiful landscape, variation {i}",
                "seed": 12345 + i,
                "steps": 20 + i * 5
            }
        )
        print(f"Created workflow variation {i}")


def example_batch_processing():
    """Example of batch processing"""
    print("\n" + "=" * 60)
    print("Example 4: Batch Processing")
    print("=" * 60)

    client = ComfyUIClient(host="127.0.0.1", port=8188)
    workflow_mgr = WorkflowManager()

    # Create queue manager
    queue_mgr = QueueManager(
        client,
        max_concurrent=2,
        retry_on_failure=True,
        max_retries=3
    )

    # Setup callbacks
    def on_job_started(job):
        print(f"Started: {job.job_id}")

    def on_job_completed(job):
        print(f"Completed: {job.job_id}")

    def on_job_failed(job):
        print(f"Failed: {job.job_id} - {job.error}")

    queue_mgr.on('job_started', on_job_started)
    queue_mgr.on('job_completed', on_job_completed)
    queue_mgr.on('job_failed', on_job_failed)

    # Load base workflow
    base_workflow = workflow_mgr.load_workflow(Path("workflows/example_workflow.json"))

    # Add multiple jobs with variations
    for i in range(5):
        workflow = base_workflow.copy()
        workflow_mgr.update_node_input(workflow, "3", "seed", 12345 + i)

        queue_mgr.add_job(f"job_{i}", workflow)

    # Start processing
    print(f"Processing {queue_mgr.get_statistics()['total_jobs']} jobs...")
    queue_mgr.start()

    # Wait for completion
    queue_mgr.wait_for_completion()

    # Show statistics
    stats = queue_mgr.get_statistics()
    print("\nBatch Processing Complete!")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")

    queue_mgr.stop()


def example_workflow_manipulation():
    """Example of workflow manipulation"""
    print("\n" + "=" * 60)
    print("Example 5: Workflow Manipulation")
    print("=" * 60)

    workflow_mgr = WorkflowManager()

    # Load workflow
    workflow = workflow_mgr.load_workflow(Path("workflows/example_workflow.json"))

    # Get workflow info
    info = workflow_mgr.get_workflow_info(workflow)
    print(f"Total nodes: {info['total_nodes']}")
    print("Node types:")
    for node_type, count in info['node_types'].items():
        print(f"  {node_type}: {count}")

    # Find specific nodes
    ksampler_nodes = workflow_mgr.find_nodes_by_type(workflow, "KSampler")
    print(f"\nFound {len(ksampler_nodes)} KSampler node(s): {ksampler_nodes}")

    # Update node inputs
    if ksampler_nodes:
        workflow_mgr.update_node_input(workflow, ksampler_nodes[0], "seed", 99999)
        workflow_mgr.update_node_input(workflow, ksampler_nodes[0], "steps", 30)
        print(f"Updated KSampler parameters")

    # Save modified workflow
    workflow_mgr.save_workflow(workflow, Path("workflows/modified_workflow.json"))
    print("Saved modified workflow")


def example_image_upload():
    """Example of uploading images"""
    print("\n" + "=" * 60)
    print("Example 6: Image Upload")
    print("=" * 60)

    client = ComfyUIClient(host="127.0.0.1", port=8188)

    # Upload an image
    image_path = Path("examples/sample_image.png")
    if image_path.exists():
        result = client.upload_image(image_path)
        print(f"Uploaded image: {result}")
    else:
        print(f"Sample image not found: {image_path}")


def main():
    """Run all examples"""
    print("\nComfyUI API Interface - Usage Examples\n")

    try:
        # Run examples (commented out to avoid errors without ComfyUI running)
        # Uncomment the examples you want to run

        # example_basic_usage()
        # example_websocket_progress()
        example_workflow_template()
        example_workflow_manipulation()
        # example_batch_processing()
        # example_image_upload()

        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
