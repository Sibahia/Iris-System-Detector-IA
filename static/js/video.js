let currentVideoUrl = null;

// Recibimos el elemento 'input' directamente desde el HTML con 'this'
function updateFileName(input) {
    const display = document.getElementById('fileName');
    
    if (input.files && input.files.length > 0) {
        display.textContent = input.files[0].name;
        // Ocultamos resultados anteriores al seleccionar un nuevo video
        document.getElementById('results').style.display = 'none';
        document.getElementById('loading').style.display = 'none';
    } else {
        display.textContent = 'Haz clic para buscar o arrastra el video';
    }
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
        
        // Limpiamos el input después de iniciar la carga con éxito
        fileInput.value = ''; 
        document.getElementById('fileName').textContent = 'Haz clic para buscar o arrastra el video';

        if (data.task_id) {
            pollTaskStatus(data.task_id);
        } else {
            throw new Error(data.message || 'Error al iniciar el análisis');
        }
    } catch (error) {
        alert('Error: ' + error.message);
        document.getElementById('loading').style.display = 'none';
        // Limpiamos en caso de error para permitir reintento
        fileInput.value = ''; 
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
                alert('El análisis falló.');
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
    
    const riskCardStyles = isCritico 
        ? "border glass-risk-high text-on-surface-variant animate-pulse" 
        : "border bg-primary-container/5 text-on-surface";
        
    const riskTextStyles = isCritico ? "text-[#ffb4ab] font-bold" : "text-[#ffb77d]";

    metricsDiv.innerHTML = `
        <div class="glass-panel rounded-xl p-stack-md flex flex-col gap-1 glass-panel-hover transition-all">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Frames</span>
            <div class="font-headline-lg text-headline-lg text-on-surface">${result.total_frames || 0}</div>
        </div>

        <div class="glass-panel rounded-xl p-stack-md flex flex-col gap-1 glass-panel-hover transition-all">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Anomalías</span>
            <div class="font-headline-lg text-headline-lg text-on-surface">${result.anomaly_frames || 0}</div>
        </div>

        <div class="rounded-xl p-stack-md flex flex-col gap-1 transition-all ${isCritico ? '' : 'glass-panel'} ${riskCardStyles}"
             ${isCritico ? 'style="background-color: color-mix(in oklab, #93000a 20%, transparent);"' : ''}>
            <span class="font-label-sm text-label-sm uppercase tracking-wider opacity-80 ${isCritico ? 'text-[#ffb4ab]/80' : 'text-on-surface-variant'}">Nivel de Riesgo</span>
            <div class="font-headline-lg text-headline-lg ${riskTextStyles}">
                ${result.risk_percentage}% (${(result.risk_level || 'normal').toUpperCase()})
            </div>
        </div>

        <div class="glass-panel rounded-xl p-stack-md flex flex-col gap-1 glass-panel-hover transition-all">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Máx. Personas</span>
            <div class="font-headline-lg text-headline-lg text-on-surface">${result.max_people_detected || 0}</div>
        </div>

        <div class="glass-panel rounded-xl p-stack-md flex flex-col gap-1 glass-panel-hover transition-all">
            <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Máx. Armas</span>
            <div class="font-headline-lg text-headline-lg text-on-surface">${result.max_weapons_detected || 0}</div>
        </div>
    `;

    if (result.annotated_video_url) {
        const videoEl = document.getElementById('annotated-video');
        videoEl.src = result.annotated_video_url;
        document.getElementById('video-container').style.display = 'block';
        videoEl.load();
    }

    document.getElementById('results').style.display = 'block';
}

function init() {
    initModelSelect();
    initConfidenceSlider();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}