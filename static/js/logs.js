const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let allItems = [];
let searchTimeout;

async function loadHistory() {
    const tbody = document.getElementById('history-body');
    const loadingDiv = document.getElementById('history-loading');

    if (loadingDiv) loadingDiv.style.display = 'block';
    tbody.innerHTML = '';

    const filename = document.getElementById('search-filename')?.value || '';
    const minRate = document.getElementById('filter-rate')?.value || '';
    const recordType = document.getElementById('filter-type')?.value || '';

    let url = '/combined-history?';
    if (filename) url += `filename=${encodeURIComponent(filename)}&`;
    if (minRate) url += `min_anomaly_rate=${minRate}&`;
    if (recordType) url += `record_type=${recordType}&`;

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

            const type = v.record_type || 'video';

            let icon = 'video_file';
            let iconColor = 'text-primary-container';
            if (type === 'image') {
                icon = 'image';
            } else if (type === 'stream') {
                icon = 'sensors';
                iconColor = 'text-green-400';
            }
            if (riskRate > 50) iconColor = 'text-error';

            let details = v.frame_count != null ? v.frame_count + ' f' : '—';

            let thresholdDisplay = v.threshold_used != null ? v.threshold_used : '—';

            let actionHtml = '';
            if (type === 'video') {
                actionHtml = `
                    <button onclick="viewRecord(${v.id}, 'video')" class="bg-primary-container text-on-primary-container px-4 py-2 rounded-lg flex items-center gap-2 hover:brightness-110 transition-all font-bold text-sm">
                        <span class="material-symbols-outlined text-sm">play_arrow</span> Reproducir
                    </button>`;
            } else if (type === 'image') {
                actionHtml = `
                    <button onclick="viewRecord(${v.id}, 'image')" class="bg-primary-container text-on-primary-container px-4 py-2 rounded-lg flex items-center gap-2 hover:brightness-110 transition-all font-bold text-sm">
                        <span class="material-symbols-outlined text-sm">visibility</span> Ver
                    </button>`;
            }
            actionHtml += `
                <button onclick="viewRecordJSON(${v.id}, '${type}')" title="Ver JSON" class="bg-white/10 text-on-surface px-3 py-2 rounded-lg hover:bg-white/20 transition-all flex items-center justify-center">
                    <span class="material-symbols-outlined text-sm leading-none">data_object</span>
                </button>
                <button onclick="viewRecordCards(${v.id}, '${type}')" title="Ver Cards" class="bg-white/10 text-on-surface px-3 py-2 rounded-lg hover:bg-white/20 transition-all flex items-center justify-center">
                    <span class="material-symbols-outlined text-sm leading-none">dashboard</span>
                </button>
                <button onclick="deleteRecord(${v.id}, '${type}')" class="bg-error-container/20 text-error px-3 py-2 rounded-lg hover:bg-error-container transition-all flex items-center justify-center">
                    <span class="material-symbols-outlined text-sm leading-none">delete</span>
                </button>`;

            return `
                <tr class="${rowClass}">
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">#${v.id}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <span class="material-symbols-outlined ${iconColor}">
                                ${icon}
                            </span>
                            <span class="font-body-md text-body-md text-on-surface font-semibold">${v.filename}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${v.upload_time ? new Date(v.upload_time).toLocaleDateString() : '—'}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${details}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${thresholdDisplay}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant text-xs">${v.model_used || '—'}</td>
                    <td class="px-6 py-4 font-body-md text-body-md text-on-surface-variant">${v.anomaly_count || 0} ${type === 'image' ? 'eventos' : 'eventos'}</td>
                    <td class="px-6 py-4 text-center">
                        <span class="${riskClass} px-3 py-1 rounded-full text-xs font-bold inline-block">${riskRate}% ${riskLabel}</span>
                    </td>
                    <td class="px-6 py-4 text-center">
                        <div class="flex justify-center gap-2">
                            ${actionHtml}
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

async function viewRecord(id, type) {
    try {
        if (type === 'video') {
            const response = await fetch(`/history/${id}`);
            const data = await response.json();
            if (data.output_video_path) {
                const filename = data.output_video_path.replace(/\\/g, '/').split('/').pop();
                window.open(`/static/videos/${filename}`, '_blank');
            } else {
                alert('Video no disponible.');
            }
        } else if (type === 'image') {
            const response = await fetch(`/image-history/${id}`);
            const data = await response.json();
            if (data.output_path) {
                const filename = data.output_path.replace(/\\/g, '/').split('/').pop();
                window.open(`/static/images/${filename}`, '_blank');
            } else {
                alert('Imagen no disponible.');
            }
        }
    } catch (error) {
        alert('Error al abrir el registro.');
    }
}

async function deleteRecord(id, type) {
    if (!confirm('¿Estás seguro de que deseas eliminar este registro?')) return;
    try {
        let url;
        if (type === 'video') url = `/history/${id}`;
        else if (type === 'image') url = `/image-history/${id}`;
        else if (type === 'stream') url = `/stream-history/${id}`;
        else return;

        const response = await fetch(url, { method: 'DELETE' });
        if (response.ok) loadHistory();
    } catch (error) {
        alert('Error al eliminar el registro.');
    }
}

function clearFilters() {
    document.getElementById('search-filename').value = '';
    document.getElementById('filter-rate').value = '';
    document.getElementById('filter-type').value = '';
    currentPage = 1;
    allItems = [];
    loadHistory();
}

function syntaxHighlight(json) {
    return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/:(\s*)"([^"]*)"/g, ':<span class="json-string">"$2"</span>')
        .replace(/:(\s*)(\d+(?:\.\d+)?)/g, ':<span class="json-number">$2</span>')
        .replace(/:(\s*)(true|false)/g, ':<span class="json-boolean">$2</span>')
        .replace(/:(\s*)(null)/g, ':<span class="json-null">$2</span>');
}

function optimalGridCols(n, min, max) {
    var best = max, bestScore = -Infinity;
    for (var c = max; c >= min; c--) {
        var rows = Math.ceil(n / c);
        var fill = n / (c * rows);
        var balance = Math.min(c, rows) / Math.max(c, rows);
        var score = fill * 10 + balance;
        if (score > bestScore) { bestScore = score; best = c; }
    }
    return best;
}

async function viewRecordJSON(id, type) {
    var modal = document.getElementById('json-detail-modal');
    var content = document.getElementById('json-detail-content');
    var title = document.getElementById('json-detail-title');
    if (!modal || !content) return;

    title.textContent = 'JSON del Registro #' + id + ' (' + type + ')';
    content.innerHTML = '<div class="text-center py-8 text-on-surface-variant">Cargando...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        var resp = await fetch('/record-detail/' + type + '/' + id);
        if (!resp.ok) throw new Error('Error al obtener detalle');
        var data = await resp.json();
        var formatted = JSON.stringify(data, null, 2);
        content.innerHTML = '<pre class="bg-black/50 rounded-xl p-4 text-sm leading-relaxed overflow-x-auto"><code class="font-mono">' + syntaxHighlight(formatted) + '</code></pre>';
    } catch (e) {
        content.innerHTML = '<div class="text-center py-8 text-error">Error: ' + e.message + '</div>';
    }
}

function closeJsonDetailModal() {
    var modal = document.getElementById('json-detail-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function copyJsonDetail() {
    var code = document.querySelector('#json-detail-content code');
    if (!code) return;
    var btn = document.getElementById('copy-json-detail-btn');
    navigator.clipboard.writeText(code.textContent).then(function () {
        if (!btn) return;
        var orig = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-sm">check</span> Copiado';
        setTimeout(function () { btn.innerHTML = orig; }, 2000);
    }).catch(function () {
        alert('No se pudo copiar al portapapeles');
    });
}

async function viewRecordCards(id, type) {
    var modal = document.getElementById('cards-detail-modal');
    var content = document.getElementById('cards-detail-content');
    var title = document.getElementById('cards-detail-title');
    if (!modal || !content) return;

    title.textContent = 'Class Cards — Registro #' + id + ' (' + type + ')';
    content.innerHTML = '<div class="text-center py-8 text-on-surface-variant">Cargando...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    try {
        var resp = await fetch('/record-detail/' + type + '/' + id);
        if (!resp.ok) throw new Error('Error al obtener detalle');
        var data = await resp.json();

        var classCounts = data.class_counts || {};
        var modelClasses = data.model_classes || Object.keys(classCounts);

        if (modelClasses.length === 0) {
            content.innerHTML = '<div class="text-center py-8 text-on-surface-variant">No hay clases disponibles para este registro</div>';
            return;
        }

        var cols = optimalGridCols(modelClasses.length, 2, 6);
        var html = '<div class="grid gap-3" style="grid-template-columns: repeat(' + cols + ', minmax(0, 1fr));">';

        modelClasses.forEach(function (cls) {
            var count = classCounts[cls] || 0;
            var nameLower = cls.toLowerCase();
            var borderColor = 'border-primary-container/30';
            var textColor = 'text-primary';
            var icon = 'category';

            if (nameLower.indexOf('person') !== -1 || nameLower.indexOf('persona') !== -1) {
                borderColor = 'border-blue-400/30';
                textColor = 'text-blue-400';
                icon = 'person';
            } else if (nameLower.indexOf('knife') !== -1 || nameLower.indexOf('weapon') !== -1 || nameLower.indexOf('gun') !== -1 || nameLower.indexOf('pistol') !== -1 || nameLower.indexOf('rifle') !== -1 || nameLower.indexOf('arma') !== -1 || nameLower.indexOf('cuchillo') !== -1 || nameLower.indexOf('fuego') !== -1) {
                borderColor = 'border-red-500/30';
                textColor = 'text-red-500';
                icon = 'warning';
            }

            if (count === 0) {
                html += '<div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">' +
                    '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">' +
                    '<span class="material-symbols-outlined text-sm">lock</span> ' + cls +
                    '</span>' +
                    '<div class="text-on-surface-variant/30 text-label-sm font-medium">&mdash;</div>' +
                    '</div>';
            } else {
                html += '<div class="glass-card p-stack-lg rounded-xl flex flex-col gap-1 ' + borderColor + '">' +
                    '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase flex items-center justify-center gap-2">' +
                    '<span class="material-symbols-outlined text-sm ' + textColor + '">' + icon + '</span>' + cls +
                    '</span>' +
                    '<span class="font-display-lg text-headline-lg ' + textColor + ' text-center">' + count + '</span>' +
                    '</div>';
            }
        });

        html += '</div>';
        content.innerHTML = html;
    } catch (e) {
        content.innerHTML = '<div class="text-center py-8 text-error">Error: ' + e.message + '</div>';
    }
}

function closeCardsDetailModal() {
    var modal = document.getElementById('cards-detail-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function initLiveSearch() {
    const input = document.getElementById('search-filename');
    if (!input) return;
    input.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(loadHistory, 300);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    initLiveSearch();

    const filterBtn = document.querySelector('button.bg-primary-container');
    if (filterBtn) filterBtn.onclick = loadHistory;

    const clearBtn = document.querySelector('button.bg-white\\/10');
    if (clearBtn) clearBtn.onclick = clearFilters;

    const typeSelect = document.getElementById('filter-type');
    if (typeSelect) typeSelect.addEventListener('change', loadHistory);

    const rateSelect = document.getElementById('filter-rate');
    if (rateSelect) rateSelect.addEventListener('change', loadHistory);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeJsonDetailModal();
            closeCardsDetailModal();
        }
    });

    var jsonModal = document.getElementById('json-detail-modal');
    if (jsonModal) jsonModal.addEventListener('click', closeJsonDetailModal);

    var cardsModal = document.getElementById('cards-detail-modal');
    if (cardsModal) cardsModal.addEventListener('click', closeCardsDetailModal);
});
