const API_BASE = window.location.origin;

// Tab switching
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');
}

// GitHub Form Submission
document.getElementById('github-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const repo = formData.get('repo');
    const filePath = formData.get('file_path') || 'mc_list.txt';
    const branch = formData.get('branch') || 'main';
    
    const statusDiv = document.getElementById('repo-status');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = 'Starting extraction...';
    statusDiv.style.display = 'block';
    
    try {
        const params = new URLSearchParams({
            repo: repo,
            file_path: filePath,
            branch: branch
        });
        
        const response = await fetch(`${API_BASE}/extract-from-github?${params}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = `
                <strong>Extraction Started!</strong><br>
                Job ID: ${data.job_id}<br>
                MC Numbers: ${data.total_mc_numbers}<br>
                <a href="#" onclick="showJobStatus('${data.job_id}'); return false;">View Status</a>
            `;
            showToast('Extraction started successfully!');
        } else {
            throw new Error(data.detail || 'Failed to start extraction');
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = `Error: ${error.message}`;
        showToast('Error starting extraction', 'error');
    }
});

// Check Repository
async function checkRepo() {
    const repo = document.getElementById('repo').value;
    const filePath = document.getElementById('file-path').value || 'mc_list.txt';
    const branch = document.getElementById('branch').value || 'main';
    
    if (!repo) {
        showToast('Please enter a repository name', 'error');
        return;
    }
    
    const statusDiv = document.getElementById('repo-status');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = 'Checking repository...';
    statusDiv.style.display = 'block';
    
    try {
        const params = new URLSearchParams({
            repo: repo,
            file_path: filePath,
            branch: branch
        });
        
        const response = await fetch(`${API_BASE}/github/check-repo?${params}`);
        const data = await response.json();
        
        if (data.file_exists) {
            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = `
                <strong>Repository Found!</strong><br>
                Repository: <a href="${data.repo_url}" target="_blank">${data.repo}</a><br>
                File: ${data.file_path}<br>
                Branch: ${data.branch}
            `;
        } else {
            statusDiv.className = 'status-message error';
            statusDiv.textContent = `File ${data.file_path} not found in repository ${data.repo}`;
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = `Error: ${error.message}`;
    }
}

// Upload CSV Form
document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('csv-file');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('Please select a file', 'error');
        return;
    }
    
    const statusDiv = document.getElementById('upload-status');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = 'Uploading and starting extraction...';
    statusDiv.style.display = 'block';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE}/extract-bulk`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = `
                <strong>Upload Successful!</strong><br>
                Job ID: ${data.job_id}<br>
                MC Numbers: ${data.total_mc_numbers}<br>
                <a href="#" onclick="showJobStatus('${data.job_id}'); return false;">View Status</a>
            `;
            showToast('File uploaded and extraction started!');
        } else {
            throw new Error(data.detail || 'Failed to upload file');
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = `Error: ${error.message}`;
        showToast('Error uploading file', 'error');
    }
});

// Job Status Form
document.getElementById('status-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const jobId = document.getElementById('job-id').value;
    showJobStatus(jobId);
});

let autoRefreshInterval = null;

function autoRefresh() {
    const btn = document.getElementById('auto-refresh-btn');
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        btn.textContent = 'Auto Refresh';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-secondary');
    } else {
        const jobId = document.getElementById('job-id').value;
        if (!jobId) {
            showToast('Please enter a Job ID first', 'error');
            return;
        }
        autoRefreshInterval = setInterval(() => {
            showJobStatus(jobId, true);
        }, 3000);
        btn.textContent = 'Stop Auto Refresh';
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-primary');
    }
}

async function showJobStatus(jobId, silent = false) {
    if (!silent) {
        document.getElementById('job-id').value = jobId;
    }
    
    const statusDiv = document.getElementById('job-status');
    statusDiv.innerHTML = '<div class="loading"></div> Checking status...';
    
    try {
        const response = await fetch(`${API_BASE}/extract-status/${jobId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Job not found');
        }
        
        const progress = data.total_mc_numbers > 0 
            ? Math.round((data.processed_count / data.total_mc_numbers) * 100) 
            : 0;
        
        statusDiv.innerHTML = `
            <div class="job-info">
                <div class="job-info-item">
                    <strong>Job ID</strong>
                    ${data.job_id}
                </div>
                <div class="job-info-item">
                    <strong>Status</strong>
                    <span class="status-badge ${data.status}">${data.status.toUpperCase()}</span>
                </div>
                <div class="job-info-item">
                    <strong>Progress</strong>
                    ${data.processed_count} / ${data.total_mc_numbers}
                </div>
                <div class="job-info-item">
                    <strong>Failed</strong>
                    ${data.failed_count}
                </div>
                <div class="job-info-item">
                    <strong>Created</strong>
                    ${new Date(data.created_at).toLocaleString()}
                </div>
                ${data.completed_at ? `
                <div class="job-info-item">
                    <strong>Completed</strong>
                    ${new Date(data.completed_at).toLocaleString()}
                </div>
                ` : ''}
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%">
                    ${progress}%
                </div>
            </div>
            ${data.error_message ? `
                <div class="status-message error" style="margin-top: 15px;">
                    Error: ${data.error_message}
                </div>
            ` : ''}
        `;
        
        // Show download buttons if job is completed
        if (data.status === 'completed') {
            document.getElementById('job-actions').style.display = 'block';
            document.getElementById('job-actions').setAttribute('data-job-id', jobId);
        } else {
            document.getElementById('job-actions').style.display = 'none';
        }
        
    } catch (error) {
        statusDiv.innerHTML = `
            <div class="status-message error">
                Error: ${error.message}
            </div>
        `;
    }
}

// Download Functions
function downloadResults(format) {
    const jobId = document.getElementById('job-actions').getAttribute('data-job-id');
    window.open(`${API_BASE}/extract-results/${jobId}?format=${format}`, '_blank');
}

function downloadFailed() {
    const jobId = document.getElementById('job-actions').getAttribute('data-job-id');
    window.open(`${API_BASE}/extract-failed/${jobId}`, '_blank');
}

// Load History
async function loadHistory() {
    const historyDiv = document.getElementById('history-list');
    historyDiv.innerHTML = '<div class="loading"></div> Loading history...';
    
    try {
        const response = await fetch(`${API_BASE}/history`);
        const jobs = await response.json();
        
        if (jobs.length === 0) {
            historyDiv.innerHTML = '<p>No extraction history found.</p>';
            return;
        }
        
        historyDiv.innerHTML = jobs.map(job => `
            <div class="history-item" onclick="showJobStatus('${job.job_id}'); showTab('status');">
                <div class="history-item-header">
                    <h3>${job.job_id}</h3>
                    <span class="status-badge ${job.status}">${job.status.toUpperCase()}</span>
                </div>
                <div class="job-info">
                    <div class="job-info-item">
                        <strong>Total MC Numbers</strong>
                        ${job.total_mc_numbers}
                    </div>
                    <div class="job-info-item">
                        <strong>Processed</strong>
                        ${job.processed_count}
                    </div>
                    <div class="job-info-item">
                        <strong>Failed</strong>
                        ${job.failed_count}
                    </div>
                    <div class="job-info-item">
                        <strong>Created</strong>
                        ${new Date(job.created_at).toLocaleString()}
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        historyDiv.innerHTML = `
            <div class="status-message error">
                Error loading history: ${error.message}
            </div>
        `;
    }
}

// Toast Notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Load history on page load
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
});

