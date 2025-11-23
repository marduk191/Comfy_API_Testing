# ComfyUI Advanced API Interface

A comprehensive, production-ready interface for sending and managing ComfyUI workflows via API. This tool provides advanced features including WebSocket support for real-time progress monitoring, batch processing, workflow templating, and queue management.

## Features

### 🚀 Core Features
- **Full API Client**: Complete implementation of ComfyUI API endpoints
- **WebSocket Support**: Real-time progress monitoring and execution updates
- **Workflow Management**: Load, validate, modify, and save workflows
- **Batch Processing**: Process multiple workflows with configurable concurrency
- **Queue Management**: Advanced job queue with retry logic and status tracking
- **Template System**: Create reusable workflow templates with parameters
- **CLI Interface**: Feature-rich command-line interface
- **Image Handling**: Upload images and download generated outputs
- **Error Handling**: Comprehensive error handling with retry mechanisms
- **Configuration**: YAML-based configuration system

### 📦 Components

- **`ComfyUIClient`**: Core API client with WebSocket support
- **`WorkflowManager`**: Workflow loading, validation, and templating
- **`QueueManager`**: Batch processing and job queue management
- **CLI Tool**: Command-line interface for common operations

## Installation

### Prerequisites
- Python 3.7 or higher
- ComfyUI instance running and accessible

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Comfy_API_Testing
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure settings in `config.yaml`:
```yaml
comfyui:
  host: "127.0.0.1"
  port: 8188
  protocol: "http"
```

## Quick Start

### Using the CLI

#### Send a single workflow:
```bash
python comfyui_cli.py send workflows/my_workflow.json --wait
```

#### Update workflow parameters:
```bash
python comfyui_cli.py send workflows/my_workflow.json \
  --update "3.seed=42" \
  --update "6.text=a beautiful landscape" \
  --wait
```

#### Process workflows in batch:
```bash
python comfyui_cli.py batch workflows/ --timeout 600
```

#### Validate a workflow:
```bash
python comfyui_cli.py validate workflows/my_workflow.json
```

#### Check queue status:
```bash
python comfyui_cli.py queue --verbose
```

### Using the Python API

#### Basic Usage:
```python
from src.client import ComfyUIClient
from src.workflow_manager import WorkflowManager
from pathlib import Path

# Initialize client
client = ComfyUIClient(host="127.0.0.1", port=8188)

# Load and send workflow
workflow_mgr = WorkflowManager()
workflow = workflow_mgr.load_workflow(Path("workflows/my_workflow.json"))

response = client.queue_prompt(workflow)
prompt_id = response['prompt_id']

# Wait for completion
history = client.wait_for_completion(prompt_id)
print("Workflow completed!")
```

#### With WebSocket Progress Monitoring:
```python
from src.client import ComfyUIClient

client = ComfyUIClient(host="127.0.0.1", port=8188)
client.connect_websocket()

# Setup progress callback
def on_progress(data):
    value = data['data'].get('value', 0)
    max_val = data['data'].get('max', 100)
    print(f"Progress: {value}/{max_val}")

client.on('progress', on_progress)

# Send workflow...
response = client.queue_prompt(workflow)
history = client.wait_for_completion(response['prompt_id'])

client.disconnect_websocket()
```

#### Batch Processing:
```python
from src.client import ComfyUIClient
from src.queue_manager import QueueManager
from src.workflow_manager import WorkflowManager

client = ComfyUIClient(host="127.0.0.1", port=8188)
workflow_mgr = WorkflowManager()

# Create queue manager
queue_mgr = QueueManager(
    client,
    max_concurrent=3,
    retry_on_failure=True,
    max_retries=3
)

# Setup callbacks
queue_mgr.on('job_completed', lambda job: print(f"✓ {job.job_id}"))
queue_mgr.on('job_failed', lambda job: print(f"✗ {job.job_id}: {job.error}"))

# Load and queue workflows
workflow = workflow_mgr.load_workflow(Path("workflows/base.json"))

for i in range(10):
    modified = workflow.copy()
    workflow_mgr.update_node_input(modified, "3", "seed", 12345 + i)
    queue_mgr.add_job(f"job_{i}", modified)

# Process
queue_mgr.start()
queue_mgr.wait_for_completion()
queue_mgr.stop()

# Get statistics
stats = queue_mgr.get_statistics()
print(f"Completed: {stats['completed']}, Failed: {stats['failed']}")
```

#### Workflow Templates:
```python
from src.workflow_manager import WorkflowManager
from pathlib import Path

workflow_mgr = WorkflowManager()

# Load base workflow
base_workflow = workflow_mgr.load_workflow(Path("workflows/base.json"))

# Create template
workflow_mgr.create_template(
    name="text_to_image",
    workflow=base_workflow,
    parameters={
        "prompt": {"node_id": "6", "input_name": "text"},
        "negative_prompt": {"node_id": "7", "input_name": "text"},
        "seed": {"node_id": "3", "input_name": "seed"},
        "steps": {"node_id": "3", "input_name": "steps"},
        "cfg": {"node_id": "3", "input_name": "cfg"}
    }
)

# Use template
workflow = workflow_mgr.instantiate_template(
    "text_to_image",
    {
        "prompt": "a beautiful sunset over mountains",
        "negative_prompt": "blurry, low quality",
        "seed": 42,
        "steps": 25,
        "cfg": 7.5
    }
)
```

## Advanced Features

### Workflow Validation
```python
workflow_mgr = WorkflowManager()
workflow = workflow_mgr.load_workflow(Path("workflow.json"))

is_valid, errors = workflow_mgr.validate_workflow(workflow)
if not is_valid:
    for error in errors:
        print(f"Error: {error}")
```

### Workflow Manipulation
```python
# Find nodes by type
ksampler_nodes = workflow_mgr.find_nodes_by_type(workflow, "KSampler")

# Update node inputs
workflow_mgr.update_node_input(workflow, "3", "seed", 99999)
workflow_mgr.update_node_input(workflow, "3", "steps", 30)

# Get workflow info
info = workflow_mgr.get_workflow_info(workflow)
print(f"Total nodes: {info['total_nodes']}")
print(f"Node types: {info['node_types']}")

# Save modified workflow
workflow_mgr.save_workflow(workflow, Path("modified.json"))
```

### Image Upload/Download
```python
from pathlib import Path

# Upload image
client = ComfyUIClient()
result = client.upload_image(Path("input_image.png"))

# Download generated images
from src.utils import extract_output_images

history = client.wait_for_completion(prompt_id)
images = extract_output_images(history)

for img in images:
    image_data = client.get_image(
        img['filename'],
        subfolder=img['subfolder'],
        folder_type=img['type']
    )

    with open(f"output_{img['filename']}", 'wb') as f:
        f.write(image_data)
```

### Context Manager Support
```python
with ComfyUIClient(host="127.0.0.1", port=8188) as client:
    client.connect_websocket()
    response = client.queue_prompt(workflow)
    history = client.wait_for_completion(response['prompt_id'])
# WebSocket automatically disconnected
```

## Configuration

Edit `config.yaml` to customize settings:

```yaml
# ComfyUI server settings
comfyui:
  host: "127.0.0.1"
  port: 8188
  protocol: "http"
  timeout: 300

# WebSocket configuration
websocket:
  enable: true
  reconnect_attempts: 5
  reconnect_delay: 2

# Workflow settings
workflow:
  validate_before_send: true
  auto_queue: true

# Output settings
output:
  download_results: true
  output_dir: "./outputs"
  save_metadata: true

# Batch processing
batch:
  max_concurrent: 3
  retry_on_failure: true
  max_retries: 3

# Logging
logging:
  level: "INFO"
  file: "./comfyui_api.log"
  console: true
```

## API Reference

### ComfyUIClient

**Methods:**
- `queue_prompt(workflow)` - Queue a workflow for execution
- `get_queue()` - Get current queue status
- `get_history(prompt_id=None)` - Get execution history
- `get_system_stats()` - Get system statistics
- `interrupt_execution()` - Interrupt current execution
- `clear_queue()` - Clear execution queue
- `upload_image(image_path, subfolder="", overwrite=False)` - Upload image
- `get_image(filename, subfolder="", folder_type="output")` - Download image
- `connect_websocket(auto_reconnect=True)` - Connect to WebSocket
- `disconnect_websocket()` - Disconnect from WebSocket
- `on(event_type, callback)` - Register event callback
- `wait_for_completion(prompt_id, timeout=None)` - Wait for prompt completion

**WebSocket Events:**
- `progress` - Progress updates
- `executing` - Node execution events
- `executed` - Node execution completed
- `execution_start` - Execution started
- `execution_cached` - Execution cached
- `execution_error` - Execution error

### WorkflowManager

**Methods:**
- `load_workflow(workflow_path)` - Load workflow from file
- `save_workflow(workflow, output_path)` - Save workflow to file
- `validate_workflow(workflow)` - Validate workflow structure
- `register_workflow(name, workflow)` - Register workflow by name
- `get_workflow(name)` - Get registered workflow
- `update_node_input(workflow, node_id, input_name, value)` - Update node input
- `find_nodes_by_type(workflow, class_type)` - Find nodes by type
- `create_template(name, workflow, parameters)` - Create template
- `instantiate_template(name, values)` - Instantiate template
- `get_workflow_info(workflow)` - Get workflow information
- `merge_workflows(workflow1, workflow2, node_id_prefix)` - Merge workflows

### QueueManager

**Methods:**
- `add_job(job_id, workflow, metadata=None)` - Add job to queue
- `add_jobs_from_list(workflows, job_prefix="job")` - Add multiple jobs
- `get_job(job_id)` - Get job by ID
- `get_job_status(job_id)` - Get job status
- `get_all_jobs()` - Get all jobs
- `get_jobs_by_status(status)` - Get jobs by status
- `cancel_job(job_id)` - Cancel a job
- `start(num_workers=None)` - Start processing
- `stop(wait=True)` - Stop processing
- `pause()` - Pause processing
- `resume()` - Resume processing
- `wait_for_completion(timeout=None)` - Wait for all jobs
- `get_statistics()` - Get queue statistics
- `on(event_type, callback)` - Register event callback
- `clear_completed()` - Clear completed jobs

**Events:**
- `job_started` - Job started
- `job_completed` - Job completed
- `job_failed` - Job failed
- `job_cancelled` - Job cancelled
- `queue_empty` - Queue is empty

## Project Structure

```
Comfy_API_Testing/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── client.py             # ComfyUI API client
│   ├── workflow_manager.py   # Workflow management
│   ├── queue_manager.py      # Queue and batch processing
│   └── utils.py              # Utility functions
├── examples/
│   ├── example_usage.py      # Comprehensive examples
│   └── simple_script.py      # Simple usage example
├── workflows/
│   └── README.md             # Workflow documentation
├── outputs/                  # Generated outputs
├── config.yaml               # Configuration file
├── comfyui_cli.py           # CLI interface
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Examples

See the `examples/` directory for comprehensive usage examples:

- `examples/example_usage.py` - Multiple usage patterns
- `examples/simple_script.py` - Minimal example

Run examples:
```bash
python examples/example_usage.py
python examples/simple_script.py
```

## Troubleshooting

### Connection Issues
- Ensure ComfyUI is running and accessible
- Check `host` and `port` in `config.yaml`
- Verify firewall settings

### WebSocket Issues
- Some networks may block WebSocket connections
- Set `websocket.enable: false` in config to disable
- Check browser console if using web interface

### Workflow Validation Errors
- Export workflow in "API Format" from ComfyUI
- Check node IDs and input names match your ComfyUI version
- Use `comfyui_cli.py validate` to check workflows

### Batch Processing
- Adjust `batch.max_concurrent` based on your system resources
- Enable `batch.retry_on_failure` for unreliable workflows
- Monitor memory usage with large batches

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is provided as-is for use with ComfyUI.

## Acknowledgments

Built for use with [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - A powerful and modular stable diffusion GUI.

## Support

For issues and questions:
- Check the examples in `examples/`
- Review the API reference above
- Check ComfyUI documentation
- Submit an issue on GitHub

---

**Happy workflow automation! 🚀**
