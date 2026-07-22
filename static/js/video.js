let currentVideoUrl = null;
let currentResult = null;
const ALLOWED_VIDEO_EXTS = ['.mp4', '.avi', '.mov', '.mkv'];

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

        var ext = '.' + file.name.split('.').pop().toLowerCase();
        if (ALLOWED_VIDEO_EXTS.indexOf(ext) === -1) {
            showVideoError('Tipo de archivo no permitido. Formatos aceptados: MP4, AVI, MOV, MKV.');
            return;
        }

        fileName.textContent = file.name;
        getVideoThumbnail(file).then(dataUrl => {
            if (dataUrl) {
                dropzone.style.backgroundImage = 'url(' + dataUrl + ')';
                dropzone.style.backgroundSize = 'cover';
                dropzone.style.backgroundPosition = 'center';
                dropzone.classList.add('has-preview');
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
                dropzone.style.backgroundImage = 'url(' + dataUrl + ')';
                dropzone.style.backgroundSize = 'cover';
                dropzone.style.backgroundPosition = 'center';
                dropzone.classList.add('has-preview');
            }
        });
        document.getElementById('results').style.display = 'none';
        document.getElementById('loading').style.display = 'none';
    } else {
        display.textContent = 'Haz clic para buscar o arrastra el video';
        resetUploadUI();
    }
}

function resetUploadUI() {
    const dropzone = document.getElementById('video-dropzone');
    const fileName = document.getElementById('fileName');
    if (dropzone) {
        dropzone.classList.remove('has-preview');
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

    try {
        var cfgResp = await fetch('/config');
        var cfg = await cfgResp.json();
        var info = document.getElementById('file-info');
        if (info && cfg.max_file_size_mb) {
            info.textContent = 'Tamaño máximo de archivo: ' + cfg.max_file_size_mb + 'MB';
        }
    } catch (e) {}
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
        showVideoError('Por favor selecciona un video');
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
        showVideoError(error.message || 'Error de conexión con el servidor.');
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
                showVideoError(task.error || 'El análisis falló.');
            }
        } catch (error) {
            clearInterval(pollInterval);
            console.error('Error polling:', error);
        }
    }, 1000);
}

function displayResults(result) {
    currentResult = result;
    const metricsDiv = document.getElementById('metrics');

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
        const riskColors = { normal: '#4ade80', bajo: '#4ade80', medio: '#fbbf24', alto: '#f87171' };
        const color = riskColors[result.risk_level] || '#4ade80';
        const riskLabel = (result.risk_level || 'normal').toUpperCase();

        return `
            <div class="glass-panel rounded-xl p-3 flex flex-col gap-1 transition-all text-center justify-center border bg-primary-container/5 text-on-surface">
                <span class="font-label-sm text-label-sm uppercase tracking-wider opacity-80 text-on-surface-variant">Nivel de Riesgo</span>
                <div class="font-headline-md text-headline-md" style="color: ${color}">
                    ${result.risk_percentage}% (${riskLabel})
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
    const allMetricItems = metricHtml + riskHtml;
    const metricCount = (allMetricItems.match(/<div class="rounded-xl/g) || []).length;
    const metricCols = optimalGridCols(metricCount, 2, 6);
    metricsDiv.style.gridTemplateColumns = `repeat(${metricCols}, minmax(0, 1fr))`;
    metricsDiv.style.justifyContent = metricCount <= 6 ? 'center' : '';
    metricsDiv.innerHTML = allMetricItems;

    function getGroupStyle(groupName) {
        var n = groupName.toLowerCase();
        if (n.indexOf('person') !== -1 || n.indexOf('persona') !== -1) {
            return { borderColor: 'border-blue-400/30', textColor: 'text-blue-400', icon: 'person' };
        }
        if (n.indexOf('weapon') !== -1 || n.indexOf('armed') !== -1 || n.indexOf('arma') !== -1) {
            return { borderColor: 'border-red-500/30', textColor: 'text-red-500', icon: 'warning' };
        }
        if (n.indexOf('police') !== -1 || n.indexOf('autoridad') !== -1) {
            return { borderColor: 'border-cyan-400/30', textColor: 'text-cyan-400', icon: 'local_police' };
        }
        if (n.indexOf('prison') !== -1 || n.indexOf('preso') !== -1) {
            return { borderColor: 'border-purple-400/30', textColor: 'text-purple-400', icon: 'lock' };
        }
        if (n.indexOf('behavior') !== -1 || n.indexOf('assault') !== -1 || n.indexOf('fight') !== -1 || n.indexOf('kidnap') !== -1 || n.indexOf('terror') !== -1 || n.indexOf('robbery') !== -1) {
            return { borderColor: 'border-amber-400/30', textColor: 'text-amber-400', icon: 'gavel' };
        }
        return { borderColor: 'border-primary-container/30', textColor: 'text-primary', icon: 'category' };
    }

    function optimalGridCols(n, min, max) {
        if (n <= max) return n;
        return Math.min(Math.ceil(n / 2), max);
    }

    const classContainer = document.getElementById('class-cards');
    if (classContainer) {
        const classGroups = result.class_groups || {};
        const groupNames = Object.keys(classGroups);

        if (groupNames.length > 0) {
            const cols = optimalGridCols(groupNames.length, 2, 6);
            classContainer.style.display = 'grid';
            classContainer.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
            classContainer.innerHTML = groupNames.map(gName => {
                const g = classGroups[gName];
                const total = g.count || 0;
                const style = getGroupStyle(gName);

                if (total === 0) {
                    return `
                        <div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">
                            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">
                                <span class="material-symbols-outlined text-sm">lock</span> ${gName}
                            </span>
                            <div class="text-on-surface-variant/30 text-label-sm font-medium">—</div>
                        </div>
                    `;
                }

                const detectedList = g.detected_natives || {};
                const subItems = Object.keys(detectedList).map(n =>
                    `<div class="flex items-center justify-between gap-2">
                        <span class="text-label-xs text-on-surface-variant/80 truncate">${n}</span>
                        <span class="text-label-xs font-bold ${style.textColor}">×${detectedList[n]}</span>
                    </div>`
                ).join('');

                return `
                    <div class="glass-card rounded-xl p-stack-md flex flex-col items-center justify-center text-center ${style.borderColor}">
                        <span class="font-label-sm text-label-sm text-on-surface-variant uppercase flex items-center justify-center gap-2">
                            <span class="material-symbols-outlined text-sm ${style.textColor}">${style.icon}</span> ${gName}
                        </span>
                        <div class="font-headline-md text-headline-md ${style.textColor} text-center mt-1">${total}</div>
                        <span class="font-label-xs text-label-xs text-on-surface-variant/60 uppercase tracking-wider mt-0.5">detectado(s)</span>
                        ${subItems ? `<div class="border-t border-white/10 pt-2 mt-2 w-full flex flex-col gap-1">${subItems}</div>` : ''}
                    </div>
                `;
            }).join('');
        }
    }

    if (result.annotated_video_url) {
        const videoEl = document.getElementById('annotated-video');
        videoEl.src = result.annotated_video_url;
        document.getElementById('video-container').style.display = 'block';
        videoEl.load();
    }

    document.getElementById('results').style.display = 'block';
}

function initExportJSON() {
    const btn = document.getElementById('export-json-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
        if (!currentResult) return;
        var json = JSON.stringify(currentResult, null, 2);
        var blob = new Blob([json], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'analysis_result.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

function showVideoError(msg) {
    var el = document.getElementById('video-error-message');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(function () { el.classList.add('hidden'); }, 8000);
}

function init() {
    initVideoUpload();
    initModelSelect();
    initConfidenceSlider();
    initExportJSON();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}