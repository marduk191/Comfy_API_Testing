# Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure ComfyUI Connection
Edit `config.yaml`:
```yaml
comfyui:
  host: "127.0.0.1"  # Your ComfyUI host
  port: 8188          # Your ComfyUI port
```

### 3. Get a Workflow

**Option A**: Export from ComfyUI
1. Open ComfyUI web interface
2. Create or load a workflow
3. Click "Save (API Format)"
4. Save to `workflows/my_workflow.json`

**Option B**: Use an existing workflow
Place any ComfyUI API format JSON in the `workflows/` directory

### 4. Send Your First Workflow

**Using CLI:**
```bash
python comfyui_cli.py send workflows/my_workflow.json --wait
```

**Using Python:**
```python
from src.client import ComfyUIClient
from src.workflow_manager import WorkflowManager
from pathlib import Path

client = ComfyUIClient()
mgr = WorkflowManager()

workflow = mgr.load_workflow(Path("workflows/my_workflow.json"))
response = client.queue_prompt(workflow)

print(f"Queued: {response['prompt_id']}")
```

## Common Use Cases

### Modify Parameters
```bash
python comfyui_cli.py send workflows/my_workflow.json \
  --update "3.seed=42" \
  --update "3.steps=25" \
  --wait
```

### Batch Process Multiple Workflows
```bash
# Place multiple workflow JSON files in workflows/ directory
python comfyui_cli.py batch workflows/
```

### Watch Progress in Real-Time
```python
from src.client import ComfyUIClient

client = ComfyUIClient()
client.connect_websocket()

client.on('progress', lambda d: print(f"Progress: {d}"))
client.on('executing', lambda d: print(f"Executing: {d}"))

# Send workflow and monitor...
```

### Create Variations
```python
from src.workflow_manager import WorkflowManager
from pathlib import Path

mgr = WorkflowManager()
base = mgr.load_workflow(Path("workflows/base.json"))

# Create 10 variations with different seeds
for i in range(10):
    workflow = base.copy()
    mgr.update_node_input(workflow, "3", "seed", 1000 + i)
    mgr.save_workflow(workflow, Path(f"workflows/variation_{i}.json"))
```

## Next Steps

- Read the full [README.md](README.md) for complete documentation
- Check out [examples/example_usage.py](examples/example_usage.py) for more patterns
- Explore the API reference in the README
- Customize `config.yaml` for your needs

## Troubleshooting

**"Connection refused"**
- Make sure ComfyUI is running
- Check host/port in config.yaml

**"Workflow validation failed"**
- Export workflow in "API Format" not "JSON Format"
- Check that node IDs exist in your workflow

**Need help?**
- Check the examples directory
- Review the README.md
- Validate your workflow: `python comfyui_cli.py validate workflows/my_workflow.json`
