/**
 * Crawl-ETL Web Client Application Logic
 */

const API_BASE = window.location.origin;
let currentJobId = null;
let ws = null;

document.addEventListener("DOMContentLoaded", () => {
    initGPUHealthCheck();
    initWebSocket();
    fetchJobsList();
    setInterval(fetchJobsList, 4000);
});

function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    
    document.getElementById(tabId).classList.add('active');
    
    const titles = {
        'launcherTab': ['Crawl Launcher', 'Configure and launch universal web, document, and GPU media extraction jobs.'],
        'opsTab': ['Live Ops & Logs', 'Monitor active crawl tasks, queue progress, and real-time GPU engine logs.'],
        'explorerTab': ['Media & Docs Explorer', 'Inspect rich scraped content, transcript timelines, and multimodal summaries.'],
        'downloadTab': ['Local Download Center', 'Directly save extracted structured datasets onto your local machine drive.']
    };

    if (titles[tabId]) {
        document.getElementById('tabTitle').innerText = titles[tabId][0];
        document.getElementById('tabSubtitle').innerText = titles[tabId][1];
    }
}

async function initGPUHealthCheck() {
    try {
        const resp = await fetch(`${API_BASE}/api/system/gpu`);
        const data = await resp.json();
        
        const badge = document.getElementById("gpuStatusBadge");
        const devName = document.getElementById("gpuDeviceName");
        
        if (data.cuda_available) {
            badge.innerText = "GPU Accelerated";
            badge.style.color = "#10b981";
            devName.innerText = data.device_name;
        } else {
            badge.innerText = "CPU Mode";
            badge.style.color = "#f59e0b";
            devName.innerText = "CPU Fallback";
        }
    } catch (e) {
        console.warn("GPU check failed:", e);
    }
}

function initWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/logs`;
    
    ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
        appendLog(event.data);
    };
    ws.onclose = () => {
        setTimeout(initWebSocket, 3000);
    };
}

function appendLog(msg, type = "info") {
    const logsDiv = document.getElementById("terminalLogs");
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    line.innerText = msg;
    logsDiv.appendChild(line);
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

function clearLogs() {
    document.getElementById("terminalLogs").innerHTML = "";
}

async function handleCrawlSubmit(event) {
    event.preventDefault();
    
    const urlsText = document.getElementById("startUrls").value.trim();
    if (!urlsText) return alert("Please enter at least one seed URL.");

    const urls = urlsText.split('\n').map(u => u.trim()).filter(Boolean);
    const payload = {
        start_urls: urls,
        max_depth: parseInt(document.getElementById("maxDepth").value),
        max_pages: parseInt(document.getElementById("maxPages").value),
        concurrency: parseInt(document.getElementById("concurrency").value),
        enable_media_ai: document.getElementById("enableMediaAi").checked,
        enable_whisper: document.getElementById("enableWhisper").checked,
        enable_javascript: document.getElementById("enableJavascript").checked,
        domain_restriction: document.getElementById("domainRestriction").checked,
        output_formats: ["json", "csv", "markdown"]
    };

    try {
        const resp = await fetch(`${API_BASE}/api/crawl`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const res = await resp.json();
        currentJobId = res.job_id;
        appendLog(`[System] Launched job #${currentJobId}`, "success");
        switchTab('opsTab');
        fetchJobsList();
    } catch (e) {
        alert("Failed to submit crawl job: " + e.message);
    }
}

async function fetchJobsList() {
    try {
        const resp = await fetch(`${API_BASE}/api/jobs`);
        const jobs = await resp.json();

        let totalPages = 0;
        let totalMedia = 0;
        let activeCount = 0;

        const tbody = document.getElementById("jobsTableBody");
        const selector = document.getElementById("jobSelector");

        if (jobs.length > 0) {
            tbody.innerHTML = "";
            
            // Retain selected job in dropdown
            const prevSelected = selector.value;
            selector.innerHTML = '<option value="">Select Job ID...</option>';

            jobs.forEach(j => {
                totalPages += j.pages_crawled || 0;
                totalMedia += j.media_processed || 0;
                if (j.status === 'running' || j.status === 'pending') activeCount++;

                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><code>#${j.job_id}</code></td>
                    <td><span class="pulse-green">${j.status.toUpperCase()}</span></td>
                    <td>${j.pages_crawled}</td>
                    <td>${j.media_processed}</td>
                    <td><button class="btn-outline" onclick="inspectJob('${j.job_id}')">Inspect</button></td>
                `;
                tbody.appendChild(tr);

                const opt = document.createElement("option");
                opt.value = j.job_id;
                opt.innerText = `Job #${j.job_id} (${j.status} - ${j.pages_crawled} pages)`;
                if (j.job_id === prevSelected) opt.selected = true;
                selector.appendChild(opt);
            });
        }

        document.getElementById("statPages").innerText = totalPages;
        document.getElementById("statMedia").innerText = totalMedia;
        document.getElementById("statActiveJobs").innerText = activeCount;
    } catch (e) {
        console.warn("Failed to fetch jobs list:", e);
    }
}

function inspectJob(jobId) {
    document.getElementById("jobSelector").value = jobId;
    switchTab("explorerTab");
    loadJobResults();
}

async function loadJobResults() {
    const jobId = document.getElementById("jobSelector").value;
    const container = document.getElementById("resultsContainer");
    if (!jobId) return;

    currentJobId = jobId;
    container.innerHTML = `<div class="empty-state">Loading results for job #${jobId}...</div>`;

    try {
        const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/results`);
        const docs = await resp.json();

        if (docs.length === 0) {
            container.innerHTML = `<div class="empty-state">No documents scraped yet for job #${jobId}.</div>`;
            return;
        }

        container.innerHTML = "";
        docs.forEach(doc => {
            const card = document.createElement("div");
            card.className = "card";
            card.style.background = "rgba(10, 13, 20, 0.4)";
            card.style.marginBottom = "16px";

            let mediaHtml = "";
            if (doc.media_assets && doc.media_assets.length > 0) {
                mediaHtml += `<h4 style="margin-top:14px;">Extracted Media Assets:</h4><ul style="padding-left:20px; color:var(--accent-cyan)">`;
                doc.media_assets.forEach(m => {
                    mediaHtml += `<li><strong>${m.media_type.toUpperCase()}</strong>: <a href="${m.url}" target="_blank" style="color:var(--accent-cyan)">${m.url}</a>`;
                    if (m.transcript) {
                        mediaHtml += `<br><em>Speech Transcript:</em> "${m.transcript}"`;
                    }
                    mediaHtml += `</li>`;
                });
                mediaHtml += `</ul>`;
            }

            card.innerHTML = `
                <h4><a href="${doc.url}" target="_blank" style="color:white; text-decoration:none;">📄 ${doc.title}</a></h4>
                <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:10px;">Domain: ${doc.domain} | Type: ${doc.content_type}</p>
                <p><strong>Summary:</strong> ${doc.summary || "N/A"}</p>
                ${mediaHtml}
                <details style="margin-top:12px;">
                    <summary style="cursor:pointer; color:var(--accent-cyan);">View Full Text Content</summary>
                    <pre style="white-space:pre-wrap; background:#05070a; padding:12px; border-radius:8px; margin-top:8px; font-size:0.85rem;">${doc.cleaned_text}</pre>
                </details>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        container.innerHTML = `<div class="empty-state" style="color:red">Failed to load results: ${e.message}</div>`;
    }
}

function triggerDownload(fmt) {
    if (!currentJobId) {
        alert("Please select or launch a crawl job first!");
        return;
    }
    const downloadUrl = `${API_BASE}/api/jobs/${currentJobId}/download/${fmt}`;
    window.location.href = downloadUrl;
}
