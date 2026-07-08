let currentVideoUrl = null;

function getVideoThumbnail(file, maxTime = 0.5) {
    return new Promise((resolve) => {
        const video = document.createElement('video');
        video.muted = true;
        video.playsinline = true;
        video.preload = 'metadata';
        video.src = URL.createObjectURL(file);
        video.addEventListener('loadedmetadata', () => {
            const seekTo = Math.min(maxTime, video.duration * 0.1 || 0.5);
            video.currentTime = seekTo;
        });
        video.addEventListener('seeked', () => {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            URL.revokeObjectURL(video.src);
            resolve(canvas.toDataURL('image/jpeg', 0.7));
        });
        video.addEventListener('error', () => {
            URL.revokeObjectURL(video.src);
            resolve('');
        });
    });
}

function initVideoUpload() {
    const dropzone = document.getElementById('video-dropzone');
    const fileInput = document.getElementById('videoFile');
    const fileName = document.getElementById('fileName');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (!file) return;
        fileName.textContent = file.name;
        getVideoThumbnail(file).then(dataUrl => {
            if (dataUrl) {
                dropzone.style.backgroundImage = `url(${dataUrl})`;
                dropzone.style.backgroundSize = 'cover';
                dropzone.style.backgroundPosition = 'center';
            }
        });
        document.getElementById('results').style.display = 'none';
        document.getElementById('loading').style.display = 'none';
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#ff8c00';
        dropzone.style.backgroundColor = 'rgba(255, 140, 0, 0.05)';
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        dropzone.style.backgroundColor = '';
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        dropzone.style.backgroundColor = '';
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            fileInput.dispatchEvent(new Event('change'));
        }
    });
}

function updateFileName(input) {
    const display = document.getElementById('fileName');
    const dropzone = document.getElementById('video-dropzone');
    
    if (input.files && input.files.length > 0) {
        display.textContent = input.files[0].name;
        getVideoThumbnail(input.files[0]).then(dataUrl => {
            if (dataUrl) {
                dropzone.style.backgroundImage = `url(${dataUrl})`;
                dropzone.style.backgroundSize = 'cover';
                dropzone.style.backgroundPosition = 'center';
            }
        });
        document.getElementById('results').style.display = 'none';
        document.getElementById('loading').style.display = 'none';
    } else {
        display.textContent = 'Haz clic para buscar o arrastra el video';
        dropzone.style.backgroundImage = '';
    }
}

function resetUploadUI() {
    const dropzone = document.getElementById('video-dropzone');
    const fileName = document.getElementById('fileName');
    if (dropzone) {
        dropzone.style.backgroundImage = '';
        dropzone.style.backgroundSize = '';
        dropzone.style.backgroundPosition = '';
    }
    if (fileName) fileName.textContent = 'Haz clic para buscar o arrastra el video';
}

async function initModelSelect() {
    const select = document.getElementById('model-select');
    if (!select) return;

    try {
        const resp = await fetch('/models');
        const data = await resp.json();
        data.models.forEach(function (m) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === data.default) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (e) {
        select.innerHTML = '<option value="">Models unavailable</option>';
    }
}

function initConfidenceSlider() {
    const slider = document.getElementById('confidence-slider');
    const valueDisplay = document.getElementById('confidence-value');
    if (slider && valueDisplay) {
        slider.addEventListener('input', function (e) {
            valueDisplay.textContent = e.target.value;
        });
    }
}

async function uploadVideo() {
    const fileInput = document.getElementById('videoFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Por favor selecciona un video');
        return;
    }

    // Reset UI
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').textContent = '0%';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const threshold = document.getElementById('crowdThreshold').value;
        const confidence = document.getElementById('confidence-slider').value;
        const modelSelect = document.getElementById('model-select');
        const modelName = modelSelect ? modelSelect.value : '';
        let url = `/analyze-yolo?crowd_threshold=${threshold}&confidence=${confidence}`;
        if (modelName) url += '&model_name=' + encodeURIComponent(modelName);
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Error al iniciar el análisis');
        }
        
        // Limpiamos el input después de iniciar la carga con éxito
        fileInput.value = '';
        resetUploadUI();

        if (data.task_id) {
            pollTaskStatus(data.task_id);
        } else {
            throw new Error(data.detail || 'Error al iniciar el análisis');
        }
    } catch (error) {
        alert('Error: ' + error.message);
        document.getElementById('loading').style.display = 'none';
        // Limpiamos en caso de error para permitir reintento
        fileInput.value = '';
        resetUploadUI();
    }
}

async function pollTaskStatus(taskId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/tasks/${taskId}`);
            const task = await response.json();

            if (task.status === 'processing') {
                document.getElementById('progressBar').style.width = task.progress + '%';
                document.getElementById('progressText').textContent = task.progress + '%';
            } else if (task.status === 'completed') {
                clearInterval(pollInterval);
                document.getElementById('loading').style.display = 'none';
                displayResults(task.result);
            } else if (task.status === 'failed') {
                clearInterval(pollInterval);
                document.getElementById('loading').style.display = 'none';
                alert('Error: ' + (task.error || 'El análisis falló.'));
            }
        } catch (error) {
            clearInterval(pollInterval);
            console.error('Error polling:', error);
        }
    }, 1000);
}

function displayResults(result) {
    const metricsDiv = document.getElementById('metrics');

    const isCritico = result.risk_level === 'critico';

    const anomalyTypesCount = result.anomaly_types
        ? Object.keys(result.anomaly_types).length
        : 0;

    function metricCard(label, value, blocked) {
        if (blocked) {
            return `
                <div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">
                    <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">
                        <span class="material-symbols-outlined text-sm">lock</span> ${label}
                    </span>
                    <div class="text-on-surface-variant/30 text-label-sm font-medium">—</div>
                </div>
            `;
        }
        return `
            <div class="glass-panel rounded-xl p-3 flex flex-col gap-1 glass-panel-hover transition-all text-center justify-center">
                <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">${label}</span>
                <div class="font-headline-md text-headline-md text-on-surface">${value}</div>
            </div>
        `;
    }

    function riskCard() {
        const styles = isCritico
            ? "border glass-risk-high text-on-surface-variant animate-pulse"
            : "border bg-primary-container/5 text-on-surface";
        const textStyles = isCritico ? "text-[#ffb4ab] font-bold" : "text-[#ffb77d]";
        const bgStyle = isCritico
            ? 'style="background-color: color-mix(in oklab, #93000a 20%, transparent);"'
            : '';
        const labelClass = isCritico ? 'text-[#ffb4ab]/80' : 'text-on-surface-variant';

        return `
            <div class="rounded-xl p-3 flex flex-col gap-1 transition-all text-center justify-center ${isCritico ? '' : 'glass-panel'} ${styles}" ${bgStyle}>
                <span class="font-label-sm text-label-sm uppercase tracking-wider opacity-80 ${labelClass}">Nivel de Riesgo</span>
                <div class="font-headline-md text-headline-md ${textStyles}">
                    ${result.risk_percentage}% (${(result.risk_level || 'normal').toUpperCase()})
                </div>
            </div>
        `;
    }

    const crowdThreshold = result.crowd_threshold ?? null;
    const maxPeople = result.max_people_detected ?? 0;
    const peopleExceeded = crowdThreshold !== null && maxPeople >= crowdThreshold;
    const peopleValue = crowdThreshold !== null ? `${maxPeople} (umbral: ${crowdThreshold})` : String(maxPeople);

    const cards = [
        { label: 'Frames Totales', value: result.total_frames ?? 0, blocked: false },
        { label: 'Frames Anómalos', value: result.anomaly_frames ?? 0, blocked: !result.anomaly_frames },
        { label: 'Tasa Anomalías', value: (result.anomaly_rate != null ? (result.anomaly_rate * 100).toFixed(1) + '%' : '0%'), blocked: false },
        { label: 'Máx. Personas', value: peopleValue, blocked: !peopleExceeded },
        { label: 'Máx. Armas', value: result.max_weapons_detected ?? 0, blocked: !result.max_weapons_detected },
        { label: 'Tipos Anomalía', value: anomalyTypesCount, blocked: !anomalyTypesCount },
        { label: 'Tiempo Proc.', value: (result.processing_time != null ? result.processing_time.toFixed(1) + 's' : '—'), blocked: false },
        { label: 'Modelo', value: result.model_name || 'default', blocked: false },
    ];

    const riskHtml = riskCard();
    const metricHtml = cards.map(c => metricCard(c.label, c.value, c.blocked)).join('');

    metricsDiv.innerHTML = metricHtml + riskHtml;

    const classContainer = document.getElementById('class-cards');
    if (classContainer) {
        const allNames = result.model_classes || Object.keys(result.class_counts || {});
        const classCounts = result.class_counts || {};

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
        classContainer.style.gridTemplateColumns = `repeat(${optimalGridCols(allNames.length, 2, 6)}, minmax(0, 1fr))`;
        classContainer.innerHTML = allNames.map(cls => {
            const count = classCounts[cls] || 0;
            if (count === 0) {
                return `
                    <div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">
                        <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">
                            <span class="material-symbols-outlined text-sm">lock</span> ${cls}
                        </span>
                        <div class="text-on-surface-variant/30 text-label-sm font-medium">—</div>
                    </div>
                `;
            }
            return `
                <div class="glass-card rounded-xl p-stack-md flex flex-col items-center justify-center text-center">
                    <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">${cls}</span>
                    <div class="font-headline-md text-headline-md text-on-surface mt-1">${count}</div>
                    <span class="font-label-xs text-label-xs text-on-surface-variant/60 uppercase tracking-wider mt-0.5">frames</span>
                </div>
            `;
        }).join('');
    }

    if (result.annotated_video_url) {
        const videoEl = document.getElementById('annotated-video');
        videoEl.src = result.annotated_video_url;
        document.getElementById('video-container').style.display = 'block';
        videoEl.load();
    }

    document.getElementById('results').style.display = 'block';
}

function init() {
    initVideoUpload();
    initModelSelect();
    initConfidenceSlider();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}