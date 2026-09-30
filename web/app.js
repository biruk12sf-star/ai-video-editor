// State
let selectedRatio = '9:16';
let selectedFile = null;
let activeJobId = null;
let pollInterval = null;

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));

  const activeBtn = document.getElementById(`tab-${tabId}`);
  const activePanel = document.getElementById(`panel-${tabId}`);

  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');
}

// Ratio Selector
function setRatio(ratio) {
  selectedRatio = ratio;
  document.querySelectorAll('.ratio-btn').forEach(btn => {
    if (btn.getAttribute('data-ratio') === ratio) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}

// Quick Demo URL
function loadDemoUrl(url) {
  const input = document.getElementById('video-url-input');
  input.value = url;
  input.focus();
}

// File Dropzone Handling
function triggerFileInput() {
  document.getElementById('file-input').click();
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.add('dragover');
}

function handleDragLeave(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.remove('dragover');
}

function handleFileDrop(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.remove('dragover');
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    processFile(e.dataTransfer.files[0]);
  }
}

function handleFileSelected(e) {
  if (e.target.files && e.target.files.length > 0) {
    processFile(e.target.files[0]);
  }
}

function processFile(file) {
  selectedFile = file;
  const label = document.getElementById('dropzone-label');
  label.innerHTML = `Selected: <span class="highlight">${file.name}</span> (${(file.size / (1024*1024)).toFixed(1)} MB)`;
  document.getElementById('upload-action-row').style.display = 'block';
}

// Terminal Log Helper
function logToTerminal(message, type = 'normal') {
  const box = document.getElementById('terminal-box');
  const line = document.createElement('div');
  line.className = 'terminal-line';
  
  const now = new Date();
  const timeStr = `[${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}]`;
  
  let formatted = `<span class="t-dim">${timeStr}</span> ${escapeHtml(message)}`;
  if (type === 'success') line.className += ' t-success';
  if (type === 'accent') line.className += ' t-accent';
  if (type === 'warn') line.className += ' t-warn';

  line.innerHTML = formatted;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

// Submit Video to API
async function submitVideo(mode) {
  const voice = document.getElementById('voice-select').value;
  const pacingMode = document.getElementById('mode-select').value;

  const formData = new FormData();
  formData.append('ratio', selectedRatio);
  formData.append('voice', voice);
  formData.append('mode', pacingMode);

  if (mode === 'url') {
    const url = document.getElementById('video-url-input').value.trim();
    if (!url) {
      alert('Please enter a YouTube Shorts or Reddit URL');
      return;
    }
    formData.append('type', 'url');
    formData.append('url', url);
  } else if (mode === 'upload') {
    if (!selectedFile) {
      alert('Please select or drag a video file first');
      return;
    }
    formData.append('type', 'upload');
    formData.append('file', selectedFile);
  } else if (mode === 'auto') {
    formData.append('type', 'auto');
  }

  // Show Console, Hide Results
  document.getElementById('console-card').style.display = 'block';
  document.getElementById('results-card').style.display = 'none';
  document.getElementById('terminal-box').innerHTML = '';
  document.getElementById('progress-bar-fill').style.width = '5%';
  document.getElementById('progress-pct-label').innerText = '5%';
  document.getElementById('console-status-text').innerText = 'Initializing Autonomous Director...';

  logToTerminal('Connecting to AI Director Engine...', 'accent');

  // Disable submit buttons
  setButtonsState(true);

  try {
    const resp = await fetch('/api/edit', {
      method: 'POST',
      body: formData
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to start video processing');
    }

    const data = await resp.json();
    activeJobId = data.job_id;
    logToTerminal(`Job created successfully [ID: ${activeJobId}]`, 'success');
    startJobPolling(activeJobId);

  } catch (err) {
    logToTerminal(`Error: ${err.message}`, 'warn');
    document.getElementById('console-status-text').innerText = 'Processing Failed';
    setButtonsState(false);
  }
}

function setButtonsState(disabled) {
  document.getElementById('btn-submit-url').disabled = disabled;
  const upBtn = document.getElementById('btn-submit-upload');
  if (upBtn) upBtn.disabled = disabled;
  document.getElementById('btn-submit-auto').disabled = disabled;
}

// Poll Progress
function startJobPolling(jobId) {
  if (pollInterval) clearInterval(pollInterval);

  let lastLogIndex = 0;

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/job/${jobId}`);
      if (!resp.ok) return;

      const job = await resp.json();

      // Update logs
      if (job.logs && job.logs.length > lastLogIndex) {
        for (let i = lastLogIndex; i < job.logs.length; i++) {
          const entry = job.logs[i];
          logToTerminal(entry.msg, entry.type);
        }
        lastLogIndex = job.logs.length;
      }

      // Update Progress
      const pct = Math.min(100, Math.max(5, job.progress || 5));
      document.getElementById('progress-bar-fill').style.width = `${pct}%`;
      document.getElementById('progress-pct-label').innerText = `${pct}%`;
      document.getElementById('console-status-text').innerText = job.status_text || 'Processing...';

      if (job.status === 'completed') {
        clearInterval(pollInterval);
        setButtonsState(false);
        displayCompletedResult(job.result);
        loadGallery();
      } else if (job.status === 'failed') {
        clearInterval(pollInterval);
        setButtonsState(false);
        logToTerminal(`Job failed: ${job.error || 'Unknown error'}`, 'warn');
      }

    } catch (err) {
      console.error('Polling error:', err);
    }
  }, 1500);
}

// Display Result
function displayCompletedResult(res) {
  document.getElementById('console-card').style.display = 'none';
  const resultsCard = document.getElementById('results-card');
  resultsCard.style.display = 'block';

  // Video Player
  const player = document.getElementById('result-video');
  player.src = res.video_url;
  player.load();
  player.play().catch(() => {});

  // Download Button
  const dlBtn = document.getElementById('btn-download-main');
  dlBtn.href = res.download_url;
  dlBtn.download = res.filename;

  // Metadata Kit
  document.getElementById('kit-title').innerText = res.title || 'Viral Short';
  document.getElementById('kit-desc').innerText = res.description || '';
  document.getElementById('kit-tags').innerText = res.tags || '';
  document.getElementById('kit-comment').innerText = res.pinned_comment || '';

  resultsCard.scrollIntoView({ behavior: 'smooth' });
}

// Copy to Clipboard
function copyField(elementId) {
  const el = document.getElementById(elementId);
  const text = el.innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btn = el.previousElementSibling.querySelector('.copy-btn');
    const oldText = btn.innerText;
    btn.innerText = 'Copied! ✓';
    btn.style.background = '#00FF88';
    btn.style.color = '#000';
    setTimeout(() => {
      btn.innerText = oldText;
      btn.style.background = '';
      btn.style.color = '';
    }, 2000);
  });
}

// Load Recent Gallery
async function loadGallery() {
  const grid = document.getElementById('gallery-grid');
  try {
    const resp = await fetch('/api/gallery');
    if (!resp.ok) return;
    const items = await resp.json();

    if (!items || items.length === 0) {
      grid.innerHTML = '<div class="gallery-loading">No completed videos yet. Launch your first one above!</div>';
      return;
    }

    grid.innerHTML = '';
    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      card.onclick = () => {
        displayCompletedResult(item);
      };

      card.innerHTML = `
        <div class="gallery-thumb-container">
          <video class="gallery-thumb-video" preload="metadata" muted playsinline src="${item.video_url}#t=0.5"></video>
          <div class="play-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          </div>
        </div>
        <div class="gallery-info">
          <div class="gallery-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
          <div class="gallery-meta">
            <span>${item.duration || '30s'}</span>
            <span>${item.size_mb || '15'} MB</span>
          </div>
        </div>
      `;
      grid.appendChild(card);
    });

  } catch (err) {
    console.error('Failed to load gallery:', err);
  }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  loadGallery();
});
