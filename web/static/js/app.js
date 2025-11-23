// ComfyUI API Interface - Client Application

class ComfyUIApp {
    constructor() {
        this.socket = null;
        this.currentView = 'workflows';
        this.workflows = [];
        this.selectedWorkflow = null;
        this.executions = [];

        this.init();
    }

    init() {
        console.log('Initializing ComfyUI App...');

        // Initialize WebSocket
        this.initWebSocket();

        // Setup event listeners
        this.setupEventListeners();

        // Load initial data
        this.loadStatus();
        this.loadWorkflows();

        // Start auto-refresh
        setInterval(() => this.loadStatus(), 5000);
    }

    // WebSocket
    initWebSocket() {
        this.socket = io();

        this.socket.on('connect', () => {
            console.log('WebSocket connected');
            this.showNotification('Connected', 'WebSocket connection established', 'success');
        });

        this.socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
            this.showNotification('Disconnected', 'WebSocket connection lost', 'warning');
        });

        this.socket.on('job_started', (data) => {
            console.log('Job started:', data);
            this.showNotification('Job Started', `Job ${data.job_id} started`, 'success');
            this.refreshQueue();
        });

        this.socket.on('job_completed', (data) => {
            console.log('Job completed:', data);
            const duration = data.duration ? data.duration.toFixed(1) + 's' : 'N/A';
            this.showNotification('Job Completed', `Job ${data.job_id} completed in ${duration}`, 'success');
            this.refreshQueue();
        });

        this.socket.on('job_failed', (data) => {
            console.log('Job failed:', data);
            this.showNotification('Job Failed', `Job ${data.job_id}: ${data.error}`, 'error');
            this.refreshQueue();
        });

        this.socket.on('execution_completed', (data) => {
            console.log('Execution completed:', data);
            this.showNotification('Execution Complete', `Prompt ${data.prompt_id} completed`, 'success');
            this.showExecutionResults(data);
            this.refreshHistory();
        });

        this.socket.on('execution_failed', (data) => {
            console.log('Execution failed:', data);
            this.showNotification('Execution Failed', data.error, 'error');
        });
    }

    // Event Listeners
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                this.switchView(view);
            });
        });

        // Upload workflow
        document.getElementById('upload-btn').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });

        document.getElementById('file-input').addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadWorkflow(e.target.files[0]);
            }
        });

        // Refresh workflows
        document.getElementById('refresh-workflows-btn').addEventListener('click', () => {
            this.loadWorkflows();
        });

        // Workflow selection
        document.getElementById('workflow-select').addEventListener('change', (e) => {
            const filename = e.target.value;
            if (filename) {
                this.loadWorkflowDetails(filename);
            } else {
                this.selectedWorkflow = null;
                document.getElementById('execute-btn').disabled = true;
                document.getElementById('workflow-preview').innerHTML = '<div class="placeholder">Select a workflow to see details</div>';
                document.getElementById('parameters-editor').innerHTML = '<div class="placeholder">No parameters to edit</div>';
            }
        });

        // Execute workflow
        document.getElementById('execute-btn').addEventListener('click', () => {
            this.executeWorkflow();
        });

        // Queue actions
        document.getElementById('refresh-queue-btn').addEventListener('click', () => {
            this.refreshQueue();
        });

        document.getElementById('clear-queue-btn').addEventListener('click', () => {
            this.clearQueue();
        });

        // History
        document.getElementById('refresh-history-btn').addEventListener('click', () => {
            this.refreshHistory();
        });

        // Send to Node button
        document.getElementById('send-to-node-btn').addEventListener('click', () => {
            this.sendToNode();
        });
    }

    // View Management
    switchView(viewName) {
        this.currentView = viewName;

        // Update navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`.nav-btn[data-view="${viewName}"]`).classList.add('active');

        // Update content
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });
        document.getElementById(`${viewName}-view`).classList.add('active');

        // Load view data
        switch(viewName) {
            case 'workflows':
                this.loadWorkflows();
                break;
            case 'execute':
                this.loadWorkflowsForSelect();
                break;
            case 'queue':
                this.refreshQueue();
                break;
            case 'history':
                this.refreshHistory();
                break;
        }
    }

    // API Calls
    async loadStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            if (data.status === 'connected') {
                document.getElementById('comfyui-status').textContent = 'Connected';
                document.getElementById('comfyui-status').style.color = 'var(--success-color)';

                const queue = data.comfyui.queue;
                document.getElementById('queue-status').textContent =
                    `${queue.running} running / ${queue.pending} pending`;
            } else {
                document.getElementById('comfyui-status').textContent = 'Disconnected';
                document.getElementById('comfyui-status').style.color = 'var(--danger-color)';
            }
        } catch (error) {
            console.error('Failed to load status:', error);
            document.getElementById('comfyui-status').textContent = 'Error';
            document.getElementById('comfyui-status').style.color = 'var(--danger-color)';
        }
    }

    async loadWorkflows() {
        try {
            const response = await fetch('/api/workflows');
            this.workflows = await response.json();
            this.renderWorkflows();
        } catch (error) {
            console.error('Failed to load workflows:', error);
            this.showNotification('Error', 'Failed to load workflows', 'error');
        }
    }

    async loadWorkflowsForSelect() {
        try {
            const response = await fetch('/api/workflows');
            const workflows = await response.json();

            const select = document.getElementById('workflow-select');
            select.innerHTML = '<option value="">-- Select a workflow --</option>';

            workflows.forEach(wf => {
                const option = document.createElement('option');
                option.value = wf.filename;
                option.textContent = wf.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load workflows:', error);
        }
    }

    async loadWorkflowDetails(filename) {
        try {
            const response = await fetch(`/api/workflows/${filename}`);
            this.selectedWorkflow = await response.json();

            document.getElementById('execute-btn').disabled = false;

            // Show preview
            const preview = document.getElementById('workflow-preview');
            preview.innerHTML = `
                <div class="info-grid">
                    <div class="info-label">Filename:</div>
                    <div class="info-value">${this.selectedWorkflow.filename}</div>

                    <div class="info-label">Total Nodes:</div>
                    <div class="info-value">${this.selectedWorkflow.info.total_nodes}</div>

                    <div class="info-label">Validation:</div>
                    <div class="info-value">
                        ${this.selectedWorkflow.validation.is_valid
                            ? '<span style="color: var(--success-color)">✓ Valid</span>'
                            : '<span style="color: var(--danger-color)">✗ Invalid</span>'}
                    </div>
                </div>
            `;

            // Show common parameters (KSampler, text prompts, etc.)
            this.renderParametersEditor();

            // Populate node selector
            this.populateNodeSelector();

        } catch (error) {
            console.error('Failed to load workflow details:', error);
            this.showNotification('Error', 'Failed to load workflow details', 'error');
        }
    }

    populateNodeSelector() {
        const nodeSelect = document.getElementById('node-select');
        const workflow = this.selectedWorkflow.workflow;

        nodeSelect.innerHTML = '<option value="">-- Select a node --</option>';

        // Add all nodes to the selector
        for (const [nodeId, nodeData] of Object.entries(workflow)) {
            const option = document.createElement('option');
            option.value = nodeId;
            const title = nodeData.title || nodeData._meta?.title || nodeData.class_type;
            option.textContent = `Node ${nodeId} (${title})`;
            nodeSelect.appendChild(option);
        }

        // Enable the node input controls
        nodeSelect.disabled = false;
        document.getElementById('node-image-input').disabled = false;
        document.getElementById('node-prompt-input').disabled = false;
        document.getElementById('send-to-node-btn').disabled = false;
    }

    renderParametersEditor() {
        const editor = document.getElementById('parameters-editor');
        const workflow = this.selectedWorkflow.workflow;

        let html = '<div class="parameters-list">';
        let hasParams = false;

        // Find common editable parameters
        for (const [nodeId, nodeData] of Object.entries(workflow)) {
            if (nodeData.class_type === 'KSampler') {
                hasParams = true;
                html += `
                    <div class="parameter-item">
                        <strong>Node ${nodeId} (KSampler)</strong>
                    </div>
                    <div class="parameter-item">
                        <label>Seed:</label>
                        <input type="number" data-node="${nodeId}" data-input="seed"
                               value="${nodeData.inputs.seed || 0}" class="form-control">
                    </div>
                    <div class="parameter-item">
                        <label>Steps:</label>
                        <input type="number" data-node="${nodeId}" data-input="steps"
                               value="${nodeData.inputs.steps || 20}" class="form-control">
                    </div>
                    <div class="parameter-item">
                        <label>CFG:</label>
                        <input type="number" step="0.1" data-node="${nodeId}" data-input="cfg"
                               value="${nodeData.inputs.cfg || 7}" class="form-control">
                    </div>
                `;
            } else if (nodeData.class_type === 'CLIPTextEncode') {
                hasParams = true;
                html += `
                    <div class="parameter-item">
                        <strong>Node ${nodeId} (Text Prompt)</strong>
                    </div>
                    <div class="parameter-item" style="grid-column: 1 / -1;">
                        <textarea data-node="${nodeId}" data-input="text"
                                  class="form-control" rows="3">${nodeData.inputs.text || ''}</textarea>
                    </div>
                `;
            }
        }

        html += '</div>';

        if (!hasParams) {
            editor.innerHTML = '<div class="placeholder">No editable parameters found</div>';
        } else {
            editor.innerHTML = html;
        }
    }

    async uploadWorkflow(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/workflows/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success || data.warning) {
                this.showNotification('Upload Success', data.message || data.warning, 'success');
                this.loadWorkflows();
            } else {
                this.showNotification('Upload Failed', data.error, 'error');
            }
        } catch (error) {
            console.error('Upload failed:', error);
            this.showNotification('Upload Failed', error.message, 'error');
        }

        // Reset file input
        document.getElementById('file-input').value = '';
    }

    async executeWorkflow() {
        if (!this.selectedWorkflow) return;

        // Gather parameter updates
        const parameters = [];
        document.querySelectorAll('#parameters-editor input, #parameters-editor textarea').forEach(input => {
            const nodeId = input.dataset.node;
            const inputName = input.dataset.input;
            let value = input.value;

            // Parse numeric values
            if (input.type === 'number') {
                value = parseFloat(value);
            }

            parameters.push({
                node_id: nodeId,
                input_name: inputName,
                value: value
            });
        });

        try {
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow: this.selectedWorkflow.workflow,
                    parameters: parameters,
                    workflow_name: this.selectedWorkflow.filename
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Execution Started',
                    `Workflow queued with ID: ${data.prompt_id}`, 'success');

                // Subscribe to execution updates
                this.socket.emit('subscribe_execution', {
                    execution_id: data.execution_id
                });
            } else {
                this.showNotification('Execution Failed', data.error, 'error');
            }
        } catch (error) {
            console.error('Execute failed:', error);
            this.showNotification('Execution Failed', error.message, 'error');
        }
    }

    async refreshQueue() {
        try {
            const response = await fetch('/api/queue');
            const data = await response.json();

            // Update statistics
            document.getElementById('stat-total').textContent = data.statistics.total_jobs;
            document.getElementById('stat-running').textContent = data.statistics.running;
            document.getElementById('stat-pending').textContent = data.statistics.pending;
            document.getElementById('stat-completed').textContent = data.statistics.completed;
            document.getElementById('stat-failed').textContent = data.statistics.failed;

            // Render jobs
            this.renderQueue(data.jobs);
        } catch (error) {
            console.error('Failed to refresh queue:', error);
        }
    }

    async clearQueue() {
        try {
            const response = await fetch('/api/queue/clear', {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Queue Cleared', 'Completed jobs removed', 'success');
                this.refreshQueue();
            }
        } catch (error) {
            console.error('Failed to clear queue:', error);
            this.showNotification('Error', 'Failed to clear queue', 'error');
        }
    }

    async refreshHistory() {
        try {
            const response = await fetch('/api/executions');
            this.executions = await response.json();
            this.renderHistory();
        } catch (error) {
            console.error('Failed to refresh history:', error);
        }
    }

    // Rendering
    renderWorkflows() {
        const container = document.getElementById('workflows-list');

        if (this.workflows.length === 0) {
            container.innerHTML = '<div class="placeholder">No workflows found. Upload a workflow to get started.</div>';
            return;
        }

        container.innerHTML = this.workflows.map(wf => `
            <div class="workflow-card" data-filename="${wf.filename}">
                <div class="workflow-card-header">
                    <div class="workflow-card-title">${wf.name}</div>
                    <div class="workflow-card-actions">
                        <button class="icon-btn delete-workflow" data-filename="${wf.filename}" title="Delete">
                            🗑️
                        </button>
                    </div>
                </div>
                <div class="workflow-card-info">
                    <div>Nodes: ${wf.node_count}</div>
                    <div>Size: ${(wf.size / 1024).toFixed(1)} KB</div>
                    <div>Modified: ${new Date(wf.modified * 1000).toLocaleString()}</div>
                </div>
                <div class="workflow-card-footer">
                    <button class="btn btn-primary btn-sm execute-workflow" data-filename="${wf.filename}">
                        Execute
                    </button>
                    <button class="btn btn-secondary btn-sm view-workflow" data-filename="${wf.filename}">
                        View Details
                    </button>
                </div>
            </div>
        `).join('');

        // Add event listeners
        container.querySelectorAll('.execute-workflow').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const filename = e.target.dataset.filename;
                this.quickExecute(filename);
            });
        });

        container.querySelectorAll('.view-workflow').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const filename = e.target.dataset.filename;
                this.showWorkflowDetails(filename);
            });
        });

        container.querySelectorAll('.delete-workflow').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const filename = e.target.dataset.filename;
                if (confirm(`Delete workflow "${filename}"?`)) {
                    await this.deleteWorkflow(filename);
                }
            });
        });
    }

    renderQueue(jobs) {
        const container = document.getElementById('queue-list');

        if (jobs.length === 0) {
            container.innerHTML = '<div class="placeholder">No jobs in queue</div>';
            return;
        }

        container.innerHTML = jobs.map(job => {
            const duration = job.started_at
                ? ((job.completed_at || Date.now()/1000) - job.started_at).toFixed(1) + 's'
                : 'N/A';

            return `
                <div class="job-card">
                    <div class="job-header">
                        <div class="job-title">${job.job_id}</div>
                        <div class="job-status status-${job.status}">${job.status.toUpperCase()}</div>
                    </div>
                    <div class="job-info">
                        <div>Prompt ID: ${job.prompt_id || 'N/A'}</div>
                        <div>Duration: ${duration}</div>
                        ${job.error ? `<div style="color: var(--danger-color)">Error: ${job.error}</div>` : ''}
                        ${job.retry_count > 0 ? `<div>Retries: ${job.retry_count}</div>` : ''}
                    </div>
                    ${job.status === 'pending' || job.status === 'running' ? `
                        <div class="job-actions">
                            <button class="btn btn-danger btn-sm cancel-job" data-job-id="${job.job_id}">
                                Cancel
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        // Add event listeners
        container.querySelectorAll('.cancel-job').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const jobId = e.target.dataset.jobId;
                await this.cancelJob(jobId);
            });
        });
    }

    renderHistory() {
        const container = document.getElementById('history-list');

        if (this.executions.length === 0) {
            container.innerHTML = '<div class="placeholder">No execution history</div>';
            return;
        }

        container.innerHTML = this.executions
            .sort((a, b) => b.started_at - a.started_at)
            .map(exec => {
                const duration = exec.duration ? exec.duration.toFixed(1) + 's' : 'N/A';

                return `
                    <div class="job-card">
                        <div class="job-header">
                            <div class="job-title">${exec.workflow_name || exec.execution_id}</div>
                            <div class="job-status status-${exec.status}">${exec.status.toUpperCase()}</div>
                        </div>
                        <div class="job-info">
                            <div>Prompt ID: ${exec.prompt_id}</div>
                            <div>Duration: ${duration}</div>
                            <div>Started: ${new Date(exec.started_at * 1000).toLocaleString()}</div>
                            ${exec.error ? `<div style="color: var(--danger-color)">Error: ${exec.error}</div>` : ''}
                        </div>
                        ${exec.status === 'completed' && exec.history ? `
                            <div class="job-actions">
                                <button class="btn btn-primary btn-sm view-results" data-execution-id="${exec.execution_id}">
                                    View Results
                                </button>
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('');

        // Add event listeners
        container.querySelectorAll('.view-results').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const execId = e.target.dataset.executionId;
                const exec = this.executions.find(ex => ex.execution_id === execId);
                if (exec) {
                    this.showExecutionResults({
                        execution_id: exec.execution_id,
                        prompt_id: exec.prompt_id,
                        images: this.extractImages(exec.history)
                    });
                }
            });
        });
    }

    async sendToNode() {
        if (!this.selectedWorkflow) {
            this.showNotification('Error', 'Please select a workflow first', 'error');
            return;
        }

        const nodeId = document.getElementById('node-select').value;
        const imageInput = document.getElementById('node-image-input');
        const promptText = document.getElementById('node-prompt-input').value;

        // Validate inputs
        if (!nodeId) {
            this.showNotification('Error', 'Please select a node', 'error');
            return;
        }

        if (!imageInput.files || imageInput.files.length === 0) {
            this.showNotification('Error', 'Please select an image file', 'error');
            return;
        }

        if (!promptText.trim()) {
            this.showNotification('Error', 'Please enter a prompt', 'error');
            return;
        }

        // Create FormData for upload
        const formData = new FormData();
        formData.append('image', imageInput.files[0]);
        formData.append('node_id', nodeId);
        formData.append('prompt', promptText);
        formData.append('workflow', JSON.stringify(this.selectedWorkflow.workflow));
        formData.append('workflow_name', this.selectedWorkflow.filename);

        try {
            const response = await fetch('/api/send_to_node', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Success',
                    `Image and prompt sent to node ${nodeId}. Execution ID: ${data.execution_id}`,
                    'success');

                // Subscribe to execution updates
                this.socket.emit('subscribe_execution', {
                    execution_id: data.execution_id
                });

                // Clear inputs
                imageInput.value = '';
                document.getElementById('node-prompt-input').value = '';
            } else {
                this.showNotification('Error', data.error || 'Failed to send to node', 'error');
            }
        } catch (error) {
            console.error('Send to node failed:', error);
            this.showNotification('Error', error.message, 'error');
        }
    }

    // Helper Functions
    async quickExecute(filename) {
        try {
            const response = await fetch(`/api/workflows/${filename}`);
            const workflowData = await response.json();

            const execResponse = await fetch('/api/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow: workflowData.workflow,
                    workflow_name: filename
                })
            });

            const data = await execResponse.json();

            if (data.success) {
                this.showNotification('Execution Started',
                    `Workflow "${filename}" queued`, 'success');
            } else {
                this.showNotification('Execution Failed', data.error, 'error');
            }
        } catch (error) {
            console.error('Quick execute failed:', error);
            this.showNotification('Execution Failed', error.message, 'error');
        }
    }

    async showWorkflowDetails(filename) {
        try {
            const response = await fetch(`/api/workflows/${filename}`);
            const data = await response.json();

            const modal = document.getElementById('workflow-modal');
            const body = document.getElementById('workflow-modal-body');

            document.getElementById('modal-workflow-title').textContent = data.filename;

            body.innerHTML = `
                <div class="info-grid">
                    <div class="info-label">Total Nodes:</div>
                    <div class="info-value">${data.info.total_nodes}</div>

                    <div class="info-label">Validation:</div>
                    <div class="info-value">
                        ${data.validation.is_valid
                            ? '<span style="color: var(--success-color)">✓ Valid</span>'
                            : '<span style="color: var(--danger-color)">✗ Invalid</span>'}
                    </div>
                </div>

                <h4 style="margin-top: 1.5rem; margin-bottom: 0.75rem;">Node Types:</h4>
                <div class="code-block">
                    ${Object.entries(data.info.node_types)
                        .map(([type, count]) => `${type}: ${count}`)
                        .join('\n')}
                </div>
            `;

            document.getElementById('modal-execute-btn').onclick = () => {
                this.quickExecute(filename);
                closeModal('workflow-modal');
            };

            modal.classList.add('active');
        } catch (error) {
            console.error('Failed to show workflow details:', error);
        }
    }

    showExecutionResults(data) {
        const modal = document.getElementById('results-modal');
        const body = document.getElementById('results-modal-body');

        if (!data.images || data.images.length === 0) {
            body.innerHTML = '<div class="placeholder">No images generated</div>';
        } else {
            body.innerHTML = `
                <h4>Generated Images (${data.images.length}):</h4>
                <div class="image-grid">
                    ${data.images.map(img => `
                        <div class="image-item">
                            <img src="/api/image/${img.filename}?subfolder=${img.subfolder}&type=${img.type}"
                                 alt="${img.filename}">
                            <div class="image-info">
                                <div>${img.filename}</div>
                                <div>Node: ${img.node_id}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        modal.classList.add('active');
    }

    async deleteWorkflow(filename) {
        try {
            const response = await fetch(`/api/workflows/${filename}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Deleted', `Workflow "${filename}" deleted`, 'success');
                this.loadWorkflows();
            } else {
                this.showNotification('Delete Failed', data.error, 'error');
            }
        } catch (error) {
            console.error('Delete failed:', error);
            this.showNotification('Delete Failed', error.message, 'error');
        }
    }

    async cancelJob(jobId) {
        try {
            const response = await fetch(`/api/queue/${jobId}/cancel`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Job Cancelled', `Job ${jobId} cancelled`, 'success');
                this.refreshQueue();
            } else {
                this.showNotification('Cancel Failed', data.error, 'error');
            }
        } catch (error) {
            console.error('Cancel failed:', error);
            this.showNotification('Cancel Failed', error.message, 'error');
        }
    }

    extractImages(history) {
        const images = [];
        if (history && history.outputs) {
            for (const [nodeId, output] of Object.entries(history.outputs)) {
                if (output.images) {
                    output.images.forEach(img => {
                        images.push({
                            node_id: nodeId,
                            filename: img.filename,
                            subfolder: img.subfolder || '',
                            type: img.type || 'output'
                        });
                    });
                }
            }
        }
        return images;
    }

    showNotification(title, message, type = 'info') {
        const container = document.getElementById('notifications');
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-title">${title}</div>
            <div class="notification-message">${message}</div>
        `;

        container.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Modal functions
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Close modals on background click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ComfyUIApp();
});
