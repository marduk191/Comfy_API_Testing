#!/usr/bin/env python3
"""
Simple script example for sending a workflow to ComfyUI
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from client import ComfyUIClient
from workflow_manager import WorkflowManager
from utils import extract_output_images


def main():
    # Initialize client
    client = ComfyUIClient(host="127.0.0.1", port=8188)

    # Load workflow
    workflow_mgr = WorkflowManager()
    workflow_path = Path("workflows/my_workflow.json")

    if not workflow_path.exists():
        print(f"Workflow not found: {workflow_path}")
        return 1

    workflow = workflow_mgr.load_workflow(workflow_path)

    # Optional: Modify workflow parameters
    # workflow_mgr.update_node_input(workflow, "3", "seed", 42)

    # Send workflow
    print("Sending workflow...")
    response = client.queue_prompt(workflow)
    prompt_id = response['prompt_id']
    print(f"Queued with ID: {prompt_id}")

    # Wait for completion
    print("Waiting for completion...")
    history = client.wait_for_completion(prompt_id, timeout=300)

    # Get output images
    images = extract_output_images(history)
    print(f"\nGenerated {len(images)} image(s):")

    # Download images
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    for img in images:
        filename = img['filename']
        print(f"  Downloading: {filename}")

        image_data = client.get_image(
            filename,
            subfolder=img['subfolder'],
            folder_type=img['type']
        )

        output_path = output_dir / filename
        with open(output_path, 'wb') as f:
            f.write(image_data)

        print(f"    Saved to: {output_path}")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
