# ComfyUI Workflows

This directory contains example workflows for use with the ComfyUI API Interface.

## Workflow Structure

ComfyUI workflows are JSON files that define a node graph. Each node has:
- `class_type`: The type of node (e.g., "KSampler", "CheckpointLoaderSimple")
- `inputs`: Dictionary of input parameters and connections to other nodes

## Creating Workflows

The easiest way to create workflows is:

1. Use the ComfyUI web interface to build your workflow visually
2. Click "Save (API Format)" to export the workflow as JSON
3. Place the JSON file in this directory

## Example Workflow Format

```json
{
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 12345,
      "steps": 20,
      "cfg": 8.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0,
      "model": ["4", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0]
    }
  },
  "4": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "v1-5-pruned-emaonly.safetensors"
    }
  }
}
```

## Using Workflows

### Via CLI:
```bash
python comfyui_cli.py send workflows/my_workflow.json --wait
```

### Via Python:
```python
from workflow_manager import WorkflowManager
from client import ComfyUIClient

# Load workflow
mgr = WorkflowManager()
workflow = mgr.load_workflow("workflows/my_workflow.json")

# Send to ComfyUI
client = ComfyUIClient()
response = client.queue_prompt(workflow)
```

## Workflow Templates

You can create reusable templates with parameters:

```python
mgr.create_template(
    name="text_to_image",
    workflow=base_workflow,
    parameters={
        "prompt": {"node_id": "6", "input_name": "text"},
        "seed": {"node_id": "3", "input_name": "seed"}
    }
)

# Use template
workflow = mgr.instantiate_template(
    "text_to_image",
    {"prompt": "a cat", "seed": 42}
)
```
