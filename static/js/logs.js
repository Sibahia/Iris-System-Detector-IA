const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let allItems = [];

async function loadHistory() {
    const tbody = document.getElementById('history-body');
    const loadingDiv = document.getElementById('history-loading');
    
    if (loadingDiv) loadingDiv.style.display = 'block';
    tbody.innerHTML = '';

    const filename = document.getElementById('search-filename')?.value || '';
    const minRate = document.getElementById('filter-rate')?.value || '';

    let url = '/history?';
    if (filename) url += `filename=${encodeURIComponent(filename)}&`;
    if (minRate) url += `min_anomaly_rate=${minRate}&`;

    try {
        const response = await fetch(url);
        allItems = await response.json();
        currentPage = 1;
        renderPage();
    } catch (e) {
        console.error("Error cargando historial:", e);
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 20px; color: var(--error);">Error al cargar el historial</td></tr>';
    } finally {
        if (loadingDiv) loadingDiv.style.display = 'none';
    }
}

function renderPage() {
    const tbody = document.getElementById('history-body');
    const totalPages = Math.ceil(allItems.length / ITEMS_PER_PAGE) || 1;

    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = allItems.slice(start, end);

    if (!allItems || allItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 40px; color: var(--on-surface-variant);">No se encontraron registros</td></tr>';
    } else {
        tbody.innerHTML = pageItems.map(v => {
            const riskRate = Math.round((v.anomaly_rate || 0) * 100);
            
            let riskClass = "risk-low";
            let riskLabel = "Bajo";
            let rowClass = "hover:bg-white/5 transition-colors group"; 

            if (riskRate > 50) { 
                riskClass = "risk-high"; 
                riskLabel = "Alto";
                rowClass += " bg-error-container/5"; 
            } else if (riskRate > 25) { 
                riskClass = "risk-medium"; 
                riskLabel = "Medio"; 
            }

            return `
                <tr class="${rowClass}">
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">#${v.id}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <span class="material-symbols-outlined ${riskRate > 50 ? 'text-error' : 'text-primary-container'}">
                                ${riskRate > 50 ? 'warning' : 'video_file'}
                            </span>
                            <span class="font-body-md text-body-md text-on-surface font-semibold">${v.filename}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${new Date(v.upload_time).toLocaleDateString()}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${v.frame_count} f</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">0.${v.threshold_used}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant font-mono text-xs">${v.model_used || '—'}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${v.anomaly_count} eventos</td>
                    <td class="px-6 py-4 text-center">
                        <span class="${riskClass} px-3 py-1 rounded-full text-xs font-bold inline-block">${riskRate}% ${riskLabel}</span>
                    </td>
                    <td class="px-6 py-4 text-center">
                        <div class="flex justify-center gap-2">
                            <button onclick="viewVideo(${v.id})" class="bg-primary-container text-on-primary-container px-4 py-2 rounded-lg flex items-center gap-2 hover:brightness-110 transition-all font-bold text-sm">
                                <span class="material-symbols-outlined text-sm">play_arrow</span> Reproducir
                            </button>
                            <button onclick="deleteVideo(${v.id})" class="bg-error-container/20 text-error px-3 py-2 rounded-lg hover:bg-error-container transition-all flex items-center justify-center">
                                <span class="material-symbols-outlined text-sm leading-none">delete</span>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    const infoEl = document.getElementById('pagination-info');
    const indicatorEl = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');

    if (infoEl) {
        if (allItems.length === 0) {
            infoEl.textContent = 'Mostrando 0 registros';
        } else {
            infoEl.textContent = `Mostrando ${start + 1}–${Math.min(end, allItems.length)} de ${allItems.length} registros`;
        }
    }

    if (indicatorEl) indicatorEl.textContent = `Página ${currentPage} de ${totalPages}`;
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
}

function changePage(delta) {
    currentPage += delta;
    renderPage();
}

async function viewVideo(videoId) {
    try {
        const response = await fetch(`/history/${videoId}`);
        const data = await response.json();
        if (data.output_video_path) {
            const filename = data.output_video_path.replace(/\\/g, '/').split('/').pop();
            window.open(`/static/videos/${filename}`, '_blank');
        } else {
            alert('Video no disponible.');
        }
    } catch (error) {
        alert('Error al intentar abrir el video.');
    }
}

async function deleteVideo(videoId) {
    if (!confirm('¿Estás seguro de que deseas eliminar este registro?')) return;
    try {
        const response = await fetch(`/history/${videoId}`, { method: 'DELETE' });
        if (response.ok) loadHistory();
    } catch (error) {
        alert('Error al eliminar el registro.');
    }
}

function clearFilters() {
    document.getElementById('search-filename').value = '';
    document.getElementById('filter-rate').value = '';
    currentPage = 1;
    allItems = [];
    loadHistory();
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    
    const filterBtn = document.querySelector('button.bg-primary-container');
    if(filterBtn) filterBtn.onclick = loadHistory;
    
    const clearBtn = document.querySelector('button.bg-white\\/10');
    if(clearBtn) clearBtn.onclick = clearFilters;
});
