# ComfyUI API Web Interface

A modern, real-time web interface for managing and executing ComfyUI workflows.

## Features

### 🎨 Modern UI
- Dark theme optimized for long sessions
- Responsive design works on desktop and mobile
- Real-time updates via WebSocket
- Intuitive navigation and workflow management

### 📁 Workflow Management
- Upload workflows via drag-and-drop or file picker
- View workflow details and validation status
- Edit workflow parameters before execution
- Delete unwanted workflows

### ▶️ Execution Control
- Execute workflows with custom parameters
- Modify KSampler settings (seed, steps, CFG)
- Edit text prompts inline
- Batch execute multiple workflows
- Real-time execution monitoring

### 📋 Queue Monitoring
- Live queue statistics dashboard
- View running, pending, and completed jobs
- Cancel jobs in queue
- Retry failed jobs automatically
- Clear completed jobs

### 🕐 Execution History
- View all past executions
- See execution duration and status
- View generated images
- Access execution metadata

### 🔔 Real-time Notifications
- Job started/completed notifications
- Error alerts
- WebSocket connection status
- Success confirmations

## Installation

### Prerequisites
- Python 3.7+
- ComfyUI running and accessible
- Modern web browser (Chrome, Firefox, Edge, Safari)

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure ComfyUI connection:**

Edit `config.yaml`:
```yaml
comfyui:
  host: "127.0.0.1"  # Your ComfyUI host
  port: 8188          # Your ComfyUI port
  protocol: "http"    # or "https"
```

3. **Start the web server:**
```bash
python web_server.py
```

Default: `http://0.0.0.0:5000`

### Custom Port

```bash
python web_server.py --port 8080
```

### Debug Mode

```bash
python web_server.py --debug
```

## Usage Guide

### 1. Uploading Workflows

**Method 1: Upload Button**
1. Click the "Upload Workflow" button
2. Select a workflow JSON file exported from ComfyUI
3. The workflow will be validated and added to your library

**Method 2: From ComfyUI**
1. In ComfyUI web interface, create your workflow
2. Click "Save (API Format)" - **NOT** "Save" (workflow format)
3. Upload the JSON file to the web interface

### 2. Executing Workflows

**Quick Execute (from Workflows view):**
1. Navigate to the "Workflows" tab
2. Click "Execute" on any workflow card
3. The workflow will be queued with default parameters

**Execute with Custom Parameters:**
1. Go to the "Execute" tab
2. Select a workflow from the dropdown
3. Modify parameters (seed, steps, CFG, prompts)
4. Click "Execute Workflow"

### 3. Monitoring Executions

**Real-time Updates:**
- WebSocket connection provides live updates
- Notifications appear for job state changes
- Queue view auto-updates with job progress

**Queue View:**
- See all jobs: pending, running, completed, failed
- Statistics dashboard shows overall status
- Cancel running or pending jobs
- Clear completed jobs to declutter

### 4. Viewing Results

**From History:**
1. Go to "History" tab
2. Find completed execution
3. Click "View Results"
4. Modal shows all generated images

**Auto-popup:**
- When execution completes, results modal appears automatically
- Shows all generated images
- Images can be opened in new tab

## API Endpoints

The web server exposes a REST API:

### Status
- `GET /api/status` - Server and ComfyUI status

### Workflows
- `GET /api/workflows` - List all workflows
- `GET /api/workflows/<filename>` - Get workflow details
- `POST /api/workflows/upload` - Upload workflow
- `DELETE /api/workflows/<filename>` - Delete workflow

### Execution
- `POST /api/execute` - Execute single workflow
- `POST /api/execute/batch` - Execute multiple workflows
- `GET /api/executions` - List executions
- `GET /api/executions/<id>` - Get execution details

### Queue
- `GET /api/queue` - Get queue status and jobs
- `POST /api/queue/clear` - Clear completed jobs
- `POST /api/queue/<job_id>/cancel` - Cancel job

### Control
- `POST /api/interrupt` - Interrupt current execution

### Images
- `GET /api/image/<filename>` - Proxy to ComfyUI images

## WebSocket Events

### Server → Client
- `connected` - Connection established
- `job_started` - Job execution started
- `job_completed` - Job execution completed
- `job_failed` - Job execution failed
- `execution_completed` - Execution finished with results
- `execution_failed` - Execution error

### Client → Server
- `subscribe_execution` - Subscribe to execution updates

## Architecture

```
┌─────────────────┐
│   Web Browser   │
│   (JavaScript)  │
└────────┬────────┘
         │ HTTP/WebSocket
         ▼
┌─────────────────┐
│  Flask Server   │
│  (web_server.py)│
└────────┬────────┘
         │ Python API
         ▼
┌─────────────────┐
│  ComfyUI Client │
│  Queue Manager  │
└────────┬────────┘
         │ HTTP/WebSocket
         ▼
┌─────────────────┐
│    ComfyUI      │
│     Server      │
└─────────────────┘
```

## Customization

### Changing Theme Colors

Edit `web/static/css/style.css`:
```css
:root {
    --primary-color: #4a90e2;    /* Main accent color */
    --secondary-color: #7b68ee;  /* Secondary accent */
    --success-color: #50c878;    /* Success states */
    --danger-color: #ff6b6b;     /* Error states */
    --bg-primary: #1a1a2e;       /* Main background */
    --bg-secondary: #16213e;     /* Card backgrounds */
}
```

### Adding Custom Parameter Editors

Edit `web/static/js/app.js`, function `renderParametersEditor()`:
```javascript
// Add custom node type handling
if (nodeData.class_type === 'YourCustomNode') {
    html += `
        <div class="parameter-item">
            <label>Your Parameter:</label>
            <input type="text" data-node="${nodeId}" data-input="your_param"
                   value="${nodeData.inputs.your_param || ''}" class="form-control">
        </div>
    `;
}
```

### Server Configuration

Edit `web_server.py` to change:
- Max upload file size: `app.config['MAX_CONTENT_LENGTH']`
- CORS settings: `CORS(app, ...)`
- WebSocket settings: `SocketIO(app, ...)`

## Troubleshooting

### Web Interface Won't Start

**Error: "Address already in use"**
- Another service is using port 5000
- Solution: Use a different port: `python web_server.py --port 8080`

**Error: "Module not found"**
- Missing dependencies
- Solution: `pip install -r requirements.txt`

### Can't Connect to ComfyUI

**Status shows "Disconnected"**
- Check ComfyUI is running
- Verify `config.yaml` has correct host/port
- Check firewall settings
- Try accessing ComfyUI directly in browser

### Workflows Won't Upload

**Error: "Invalid file type"**
- Only JSON files are accepted
- Export workflow from ComfyUI in "API Format"

**Error: "Workflow validation failed"**
- Workflow may be corrupted
- Try re-exporting from ComfyUI
- Check the validation errors in the response

### WebSocket Disconnects

**Frequent disconnections:**
- Network instability
- Firewall blocking WebSocket
- Use HTTP polling as fallback (modify app.js)

### Images Don't Display

**Broken image icons:**
- ComfyUI not accessible
- Images may have been deleted
- Check browser console for errors
- Verify `/api/image/<filename>` endpoint works

## Security Considerations

### Production Deployment

**DO NOT expose to public internet without:**
1. Authentication (add Flask-Login or similar)
2. HTTPS (use reverse proxy like nginx)
3. Rate limiting (use Flask-Limiter)
4. Input validation (already included)
5. CSRF protection (use Flask-WTF)

### Recommended Setup

```nginx
# nginx reverse proxy example
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Access Control

Add authentication to `web_server.py`:
```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # Implement your authentication logic
    return username == "admin" and password == "secret"

@app.route('/api/...')
@auth.login_required
def protected_route():
    # Your endpoint
```

## Performance Tips

### Large Workflow Libraries
- Consider pagination for workflow list
- Implement search/filter functionality
- Cache workflow metadata

### Many Concurrent Users
- Use production WSGI server (gunicorn, uwsgi)
- Increase worker processes
- Use Redis for session storage

### Example Production Start

```bash
gunicorn -w 4 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker web_server:app
```

## Browser Compatibility

| Browser | Version | Support |
|---------|---------|---------|
| Chrome  | 90+     | ✅ Full |
| Firefox | 88+     | ✅ Full |
| Safari  | 14+     | ✅ Full |
| Edge    | 90+     | ✅ Full |

### Required Features
- WebSocket support
- ES6 JavaScript
- CSS Grid
- Fetch API

## Contributing

To add features to the web interface:

1. **Backend**: Edit `web_server.py`
   - Add Flask routes for new API endpoints
   - Add WebSocket events for real-time features

2. **Frontend**: Edit files in `web/`:
   - `templates/index.html` - Page structure
   - `static/css/style.css` - Styling
   - `static/js/app.js` - Application logic

3. **Test changes**:
   ```bash
   python web_server.py --debug
   ```

## Support

For issues and questions:
- Check browser console for JavaScript errors
- Check Flask server logs for backend errors
- Verify ComfyUI is running and accessible
- Review this documentation

## Screenshots

### Main Interface
- Workflows view with card layout
- Execute view with parameter editor
- Queue monitoring dashboard
- Execution history with results

### Real-time Updates
- WebSocket notifications
- Live queue statistics
- Automatic result display

---

**Enjoy your enhanced ComfyUI workflow management! 🎨✨**
