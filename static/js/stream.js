let isStreaming = false;
let statusInterval = null;

const startBtn = document.getElementById('startMonitoring');
const sourceSelect = document.getElementById('sourceSelect');
const cameraContainer = document.getElementById('cameraSelectContainer');
const urlContainer = document.getElementById('urlInputContainer');
const urlInput = document.getElementById('streamUrlInput');
const modelSelect = document.getElementById('model-select');
const confidenceSlider = document.getElementById('confidence-slider');
const confidenceValue = document.getElementById('confidence-value');

async function initModelSelect() {
    if (!modelSelect) return;
    try {
        const resp = await fetch('/models');
        const data = await resp.json();
        data.models.forEach(function (m) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === data.default) opt.selected = true;
            modelSelect.appendChild(opt);
        });
    } catch (e) {
        modelSelect.innerHTML = '<option value="">Models unavailable</option>';
    }
}

function initConfidenceSlider() {
    if (confidenceSlider && confidenceValue) {
        confidenceSlider.addEventListener('input', function (e) {
            confidenceValue.textContent = e.target.value;
        });
    }
}

sourceSelect.addEventListener('change', () => {
    const isWebcam = sourceSelect.value === 'webcam';
    cameraContainer.classList.toggle('hidden', !isWebcam);
    urlContainer.classList.toggle('hidden', isWebcam);
});

startBtn.addEventListener('click', async () => {
    if (!isStreaming) {
        const config = {
            source: sourceSelect.value === 'webcam' ? document.getElementById('cameraSelect').value : urlInput.value,
            threshold: document.getElementById('sensitivitySelect').value,
            confidence: confidenceSlider ? confidenceSlider.value : 0.5,
            modelName: modelSelect ? modelSelect.value : '',
        };

        if (!config.source) {
            alert("Por favor, ingresa una URL válida o selecciona una cámara.");
            return;
        }

        await startStream(config);
    } else {
        await stopStream();
    }
});

async function startStream(config) {
    const originalText = startBtn.innerHTML;
    startBtn.disabled = true;
    startBtn.innerHTML = 'Conectando...';

    try {
        const body = {
            stream_id: 'main',
            source: config.source,
            crowd_threshold: parseInt(config.threshold),
            confidence: parseFloat(config.confidence),
        };
        if (config.modelName) body.model_name = config.modelName;

        const response = await fetch('/live/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (data && data.success === true) {
            isStreaming = true;
            startBtn.innerHTML = 'Detener Monitoreo';
            startBtn.classList.replace('bg-primary-container', 'bg-red-500');
            
            const canvas = document.getElementById('streamCanvas');
            canvas.innerHTML = `<img src="/live/feed/main?t=${Date.now()}" class="w-full h-full object-contain">`;
            canvas.classList.remove('hidden');
            document.getElementById('loadingIcon').classList.add('hidden');
            
            statusInterval = setInterval(updateStatus, 1000);
        } else {
            throw new Error(data.message || data.error || 'Error desconocido al conectar');
        }
    } catch (error) {
        console.error("Error en stream:", error);
        alert('No se pudo iniciar el stream: ' + error.message);
        
        startBtn.innerHTML = originalText;
        startBtn.disabled = false;
    }
}

async function stopStream() {
    await fetch('/live/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stream_id: 'main' }) });
    isStreaming = false;
    startBtn.innerHTML = 'Iniciar Monitoreo';
    startBtn.classList.replace('bg-red-500', 'bg-primary-container');
    clearInterval(statusInterval);
}

async function updateStatus() {
    try {
        const response = await fetch('/live/status/main');
        const data = await response.json();
        document.getElementById('metric-fps').textContent = data.fps || 0;
        document.getElementById('metric-people').textContent = data.person_count || 0;

        const modelEl = document.getElementById('metric-model');
        if (modelEl) modelEl.textContent = data.model_name || 'default';

        const classContainer = document.getElementById('class-metrics');
        if (classContainer && data.class_counts) {
            const entries = Object.entries(data.class_counts);
            if (entries.length > 0) {
                function optimalGridCols(n, min, max) {
                    let best = max, bestScore = -Infinity;
                    for (let c = max; c >= min; c--) {
                        const rows = Math.ceil(n / c);
                        const fill = n / (c * rows);
                        const balance = Math.min(c, rows) / Math.max(c, rows);
                        const score = fill * 10 + balance;
                        if (score > bestScore) { bestScore = score; best = c; }
                    }
                    return best;
                }
                classContainer.style.display = 'grid';
                classContainer.style.gridTemplateColumns = `repeat(${optimalGridCols(entries.length, 2, 6)}, minmax(0, 1fr))`;
                classContainer.innerHTML = entries.map(([cls, count]) => `
                    <div class="glass-card rounded-xl p-stack-md flex flex-col items-center justify-center text-center">
                        <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">${cls}</span>
                        <div class="font-headline-md text-headline-md text-on-surface mt-1">${count}</div>
                    </div>
                `).join('');
            }
        }
    } catch (e) { stopStream(); }
}

initModelSelect();
initConfidenceSlider();