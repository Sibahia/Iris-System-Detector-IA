let isStreaming = false;
let statusInterval = null;

const startBtn = document.getElementById('startMonitoring');
const sourceSelect = document.getElementById('sourceSelect');
const cameraContainer = document.getElementById('cameraSelectContainer');
const urlContainer = document.getElementById('urlInputContainer');
const urlInput = document.getElementById('streamUrlInput');

sourceSelect.addEventListener('change', () => {
    const isWebcam = sourceSelect.value === 'webcam';
    cameraContainer.classList.toggle('hidden', !isWebcam);
    urlContainer.classList.toggle('hidden', isWebcam);
});

startBtn.addEventListener('click', async () => {
    if (!isStreaming) {
        const config = {
            source: sourceSelect.value === 'webcam' ? document.getElementById('cameraSelect').value : urlInput.value,
            threshold: document.getElementById('sensitivitySelect').value
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
        const response = await fetch('/live/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stream_id: 'main',
                source: config.source,
                crowd_threshold: parseInt(config.threshold)
            })
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
        document.getElementById('metric-vehicles').textContent = data.vehicle_count || 0;
    } catch (e) { stopStream(); }
}