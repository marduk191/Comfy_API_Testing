#!/usr/bin/env python3
"""
ComfyUI API Web Interface
Flask-based web server for managing ComfyUI workflows
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock
import time

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from client import ComfyUIClient
from workflow_manager import WorkflowManager
from queue_manager import QueueManager, JobStatus
from utils import load_config, extract_output_images, format_duration

# Initialize Flask app
app = Flask(__name__,
            template_folder='web/templates',
            static_folder='web/static')
app.config['SECRET_KEY'] = 'comfyui-api-interface-secret'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global instances
config = None
comfyui_client = None
workflow_mgr = None
queue_mgr = None
active_executions = {}
execution_lock = Lock()

# File upload settings
UPLOAD_FOLDER = Path('workflows')
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'json'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def init_app():
    """Initialize application components"""
    global config, comfyui_client, workflow_mgr, queue_mgr

    # Load config
    config_path = Path('config.yaml')
    config = load_config(config_path)

    # Initialize ComfyUI client
    comfyui_config = config['comfyui']
    comfyui_client = ComfyUIClient(
        host=comfyui_config['host'],
        port=comfyui_config['port'],
        protocol=comfyui_config['protocol'],
        timeout=comfyui_config['timeout']
    )

    # Initialize workflow manager
    workflow_mgr = WorkflowManager()

    # Initialize queue manager
    batch_config = config.get('batch', {})
    queue_mgr = QueueManager(
        comfyui_client,
        max_concurrent=batch_config.get('max_concurrent', 3),
        retry_on_failure=batch_config.get('retry_on_failure', True),
        max_retries=batch_config.get('max_retries', 3)
    )

    # Setup queue callbacks
    def on_job_started(job):
        socketio.emit('job_started', {
            'job_id': job.job_id,
            'status': 'running',
            'started_at': job.started_at
        })

    def on_job_completed(job):
        socketio.emit('job_completed', {
            'job_id': job.job_id,
            'status': 'completed',
            'completed_at': job.completed_at,
            'duration': job.completed_at - job.started_at if job.started_at else 0
        })

    def on_job_failed(job):
        socketio.emit('job_failed', {
            'job_id': job.job_id,
            'status': 'failed',
            'error': job.error
        })

    queue_mgr.on('job_started', on_job_started)
    queue_mgr.on('job_completed', on_job_completed)
    queue_mgr.on('job_failed', on_job_failed)

    # Start queue manager
    queue_mgr.start()

    print("✓ Application initialized")


# Routes

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get server status"""
    try:
        system_stats = comfyui_client.get_system_stats()
        queue_data = comfyui_client.get_queue()

        return jsonify({
            'status': 'connected',
            'comfyui': {
                'host': config['comfyui']['host'],
                'port': config['comfyui']['port'],
                'system_stats': system_stats,
                'queue': {
                    'running': len(queue_data.get('queue_running', [])),
                    'pending': len(queue_data.get('queue_pending', []))
                }
            },
            'local_queue': queue_mgr.get_statistics()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    """List available workflows"""
    workflows = []
    for wf_path in UPLOAD_FOLDER.glob('*.json'):
        try:
            workflow = workflow_mgr.load_workflow(wf_path)
            info = workflow_mgr.get_workflow_info(workflow)
            workflows.append({
                'filename': wf_path.name,
                'name': wf_path.stem,
                'size': wf_path.stat().st_size,
                'modified': wf_path.stat().st_mtime,
                'node_count': info['total_nodes']
            })
        except Exception as e:
            print(f"Error loading {wf_path}: {e}")

    return jsonify(workflows)


@app.route('/api/workflows/<filename>', methods=['GET'])
def get_workflow(filename):
    """Get workflow details"""
    wf_path = UPLOAD_FOLDER / secure_filename(filename)

    if not wf_path.exists():
        return jsonify({'error': 'Workflow not found'}), 404

    try:
        workflow = workflow_mgr.load_workflow(wf_path)
        info = workflow_mgr.get_workflow_info(workflow)
        is_valid, errors = workflow_mgr.validate_workflow(workflow)

        return jsonify({
            'filename': filename,
            'workflow': workflow,
            'info': info,
            'validation': {
                'is_valid': is_valid,
                'errors': errors
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflows/upload', methods=['POST'])
def upload_workflow():
    """Upload a workflow file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JSON files allowed'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = UPLOAD_FOLDER / filename

        # Save file
        file.save(str(filepath))

        # Validate workflow
        workflow = workflow_mgr.load_workflow(filepath)
        is_valid, errors = workflow_mgr.validate_workflow(workflow)

        if not is_valid:
            return jsonify({
                'warning': 'Workflow uploaded but validation failed',
                'filename': filename,
                'errors': errors
            }), 200

        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Workflow uploaded successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflows/<filename>', methods=['DELETE'])
def delete_workflow(filename):
    """Delete a workflow"""
    wf_path = UPLOAD_FOLDER / secure_filename(filename)

    if not wf_path.exists():
        return jsonify({'error': 'Workflow not found'}), 404

    try:
        wf_path.unlink()
        return jsonify({'success': True, 'message': 'Workflow deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/execute', methods=['POST'])
def execute_workflow():
    """Execute a workflow"""
    data = request.json

    if 'workflow' not in data:
        return jsonify({'error': 'No workflow provided'}), 400

    try:
        workflow = data['workflow']

        # Apply parameter updates if provided
        if 'parameters' in data:
            for param in data['parameters']:
                workflow_mgr.update_node_input(
                    workflow,
                    param['node_id'],
                    param['input_name'],
                    param['value']
                )

        # Validate if enabled
        if config['workflow'].get('validate_before_send', True):
            is_valid, errors = workflow_mgr.validate_workflow(workflow)
            if not is_valid:
                return jsonify({
                    'error': 'Workflow validation failed',
                    'validation_errors': errors
                }), 400

        # Send to ComfyUI
        response = comfyui_client.queue_prompt(workflow)
        prompt_id = response.get('prompt_id')

        if not prompt_id:
            return jsonify({'error': 'Failed to queue workflow'}), 500

        # Track execution
        execution_id = str(uuid.uuid4())
        with execution_lock:
            active_executions[execution_id] = {
                'prompt_id': prompt_id,
                'status': 'queued',
                'started_at': time.time(),
                'workflow_name': data.get('workflow_name', 'Unknown')
            }

        # Start monitoring in background
        def monitor_execution():
            try:
                history = comfyui_client.wait_for_completion(prompt_id)

                with execution_lock:
                    if execution_id in active_executions:
                        active_executions[execution_id]['status'] = 'completed'
                        active_executions[execution_id]['history'] = history
                        active_executions[execution_id]['completed_at'] = time.time()

                # Extract images
                images = extract_output_images(history)

                socketio.emit('execution_completed', {
                    'execution_id': execution_id,
                    'prompt_id': prompt_id,
                    'images': images
                })

            except Exception as e:
                with execution_lock:
                    if execution_id in active_executions:
                        active_executions[execution_id]['status'] = 'failed'
                        active_executions[execution_id]['error'] = str(e)

                socketio.emit('execution_failed', {
                    'execution_id': execution_id,
                    'error': str(e)
                })

        Thread(target=monitor_execution, daemon=True).start()

        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'prompt_id': prompt_id,
            'message': 'Workflow queued successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/execute/batch', methods=['POST'])
def execute_batch():
    """Execute multiple workflows in batch"""
    data = request.json

    if 'filenames' not in data or not data['filenames']:
        return jsonify({'error': 'No workflows provided'}), 400

    try:
        job_ids = []

        for filename in data['filenames']:
            wf_path = UPLOAD_FOLDER / secure_filename(filename)

            if not wf_path.exists():
                continue

            workflow = workflow_mgr.load_workflow(wf_path)

            job_id = f"{wf_path.stem}_{int(time.time())}"
            queue_mgr.add_job(job_id, workflow, metadata={'filename': filename})
            job_ids.append(job_id)

        return jsonify({
            'success': True,
            'job_count': len(job_ids),
            'job_ids': job_ids,
            'message': f'Queued {len(job_ids)} workflows for batch processing'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/executions/<execution_id>')
def get_execution(execution_id):
    """Get execution status"""
    with execution_lock:
        if execution_id not in active_executions:
            return jsonify({'error': 'Execution not found'}), 404

        execution = active_executions[execution_id].copy()

    # Calculate duration
    if 'started_at' in execution:
        if 'completed_at' in execution:
            execution['duration'] = execution['completed_at'] - execution['started_at']
        else:
            execution['duration'] = time.time() - execution['started_at']

    return jsonify(execution)


@app.route('/api/executions')
def list_executions():
    """List all executions"""
    with execution_lock:
        executions = []
        for exec_id, exec_data in active_executions.items():
            exec_copy = exec_data.copy()
            exec_copy['execution_id'] = exec_id

            # Calculate duration
            if 'started_at' in exec_copy:
                if 'completed_at' in exec_copy:
                    exec_copy['duration'] = exec_copy['completed_at'] - exec_copy['started_at']
                else:
                    exec_copy['duration'] = time.time() - exec_copy['started_at']

            executions.append(exec_copy)

    return jsonify(executions)


@app.route('/api/queue')
def get_queue():
    """Get queue status"""
    try:
        stats = queue_mgr.get_statistics()
        jobs = []

        for job in queue_mgr.get_all_jobs():
            jobs.append({
                'job_id': job.job_id,
                'status': job.status.value,
                'prompt_id': job.prompt_id,
                'error': job.error,
                'metadata': job.metadata,
                'created_at': job.created_at,
                'started_at': job.started_at,
                'completed_at': job.completed_at,
                'retry_count': job.retry_count
            })

        return jsonify({
            'statistics': stats,
            'jobs': jobs
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    """Clear completed jobs from queue"""
    try:
        queue_mgr.clear_completed()
        return jsonify({'success': True, 'message': 'Queue cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a job"""
    try:
        success = queue_mgr.cancel_job(job_id)
        if success:
            return jsonify({'success': True, 'message': 'Job cancelled'})
        else:
            return jsonify({'error': 'Failed to cancel job'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/send_to_node', methods=['POST'])
def send_to_node():
    """Send image and prompt to a specific node"""
    try:
        # Get form data
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image_file = request.files['image']
        node_id = request.form.get('node_id')
        prompt_text = request.form.get('prompt')
        workflow_json = request.form.get('workflow')
        workflow_name = request.form.get('workflow_name', 'Unknown')

        if not node_id:
            return jsonify({'error': 'No node ID provided'}), 400

        if not prompt_text:
            return jsonify({'error': 'No prompt provided'}), 400

        if not workflow_json:
            return jsonify({'error': 'No workflow provided'}), 400

        # Parse workflow
        workflow = json.loads(workflow_json)

        # Check if node exists
        if node_id not in workflow:
            return jsonify({'error': f'Node {node_id} not found in workflow'}), 400

        # Upload image to ComfyUI
        image_filename = secure_filename(image_file.filename)
        image_result = comfyui_client.upload_image(image_file, subfolder='', overwrite=True)

        if not image_result or 'name' not in image_result:
            return jsonify({'error': 'Failed to upload image to ComfyUI'}), 500

        uploaded_image_name = image_result['name']

        # Update the workflow node with image and prompt
        node = workflow[node_id]

        # Try to find image input parameter (common names)
        image_param_names = ['image', 'images', 'input_image', 'input', 'source_image', 'img']
        image_param_found = False

        for param_name in image_param_names:
            if param_name in node.get('inputs', {}):
                node['inputs'][param_name] = uploaded_image_name
                image_param_found = True
                break

        # If no common image parameter found, try to set any parameter that looks like it accepts images
        if not image_param_found:
            for key, value in node.get('inputs', {}).items():
                if isinstance(value, str) and (
                    key.lower().endswith('image') or
                    key.lower().startswith('image') or
                    'img' in key.lower()
                ):
                    node['inputs'][key] = uploaded_image_name
                    image_param_found = True
                    break

        # Try to find text/prompt input parameter
        text_param_names = ['text', 'prompt', 'string', 'description', 'caption', 'positive']
        text_param_found = False

        for param_name in text_param_names:
            if param_name in node.get('inputs', {}):
                node['inputs'][param_name] = prompt_text
                text_param_found = True
                break

        # If no common text parameter found, try to set any string parameter
        if not text_param_found:
            for key, value in node.get('inputs', {}).items():
                if isinstance(value, str) and not image_param_found or key != list(node['inputs'].keys())[0]:
                    node['inputs'][key] = prompt_text
                    text_param_found = True
                    break

        # If neither parameter was found, add them to inputs
        if not image_param_found:
            node['inputs']['image'] = uploaded_image_name

        if not text_param_found:
            node['inputs']['text'] = prompt_text

        # Validate workflow if enabled
        if config['workflow'].get('validate_before_send', True):
            is_valid, errors = workflow_mgr.validate_workflow(workflow)
            if not is_valid:
                return jsonify({
                    'error': 'Workflow validation failed after updating node',
                    'validation_errors': errors
                }), 400

        # Execute workflow
        response = comfyui_client.queue_prompt(workflow)
        prompt_id = response.get('prompt_id')

        if not prompt_id:
            return jsonify({'error': 'Failed to queue workflow'}), 500

        # Track execution
        execution_id = str(uuid.uuid4())
        with execution_lock:
            active_executions[execution_id] = {
                'prompt_id': prompt_id,
                'status': 'queued',
                'started_at': time.time(),
                'workflow_name': workflow_name,
                'node_id': node_id,
                'uploaded_image': uploaded_image_name
            }

        # Start monitoring in background
        def monitor_execution():
            try:
                history = comfyui_client.wait_for_completion(prompt_id)

                with execution_lock:
                    if execution_id in active_executions:
                        active_executions[execution_id]['status'] = 'completed'
                        active_executions[execution_id]['history'] = history
                        active_executions[execution_id]['completed_at'] = time.time()

                # Extract images
                images = extract_output_images(history)

                socketio.emit('execution_completed', {
                    'execution_id': execution_id,
                    'prompt_id': prompt_id,
                    'images': images
                })

            except Exception as e:
                with execution_lock:
                    if execution_id in active_executions:
                        active_executions[execution_id]['status'] = 'failed'
                        active_executions[execution_id]['error'] = str(e)

                socketio.emit('execution_failed', {
                    'execution_id': execution_id,
                    'error': str(e)
                })

        Thread(target=monitor_execution, daemon=True).start()

        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'prompt_id': prompt_id,
            'uploaded_image': uploaded_image_name,
            'node_id': node_id,
            'image_param_found': image_param_found,
            'text_param_found': text_param_found,
            'message': f'Image and prompt sent to node {node_id}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/interrupt', methods=['POST'])
def interrupt_execution():
    """Interrupt current ComfyUI execution"""
    try:
        comfyui_client.interrupt_execution()
        return jsonify({'success': True, 'message': 'Execution interrupted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/image/<path:filename>')
def get_image(filename):
    """Proxy to get image from ComfyUI"""
    try:
        subfolder = request.args.get('subfolder', '')
        folder_type = request.args.get('type', 'output')

        image_data = comfyui_client.get_image(filename, subfolder, folder_type)

        # Determine content type
        content_type = 'image/png'
        if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.webp'):
            content_type = 'image/webp'

        from flask import Response
        return Response(image_data, mimetype=content_type)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# WebSocket events

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to ComfyUI API server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")


@socketio.on('subscribe_execution')
def handle_subscribe(data):
    """Subscribe to execution updates"""
    execution_id = data.get('execution_id')
    print(f"Client subscribed to execution: {execution_id}")


# Error handlers

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='ComfyUI API Web Interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    # Initialize app
    init_app()

    print("\n" + "=" * 60)
    print("ComfyUI API Web Interface")
    print("=" * 60)
    print(f"Server: http://{args.host}:{args.port}")
    print(f"ComfyUI: {config['comfyui']['protocol']}://{config['comfyui']['host']}:{config['comfyui']['port']}")
    print("=" * 60 + "\n")

    # Run server
    socketio.run(app, host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
