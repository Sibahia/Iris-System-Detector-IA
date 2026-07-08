const ITEMS_PER_PAGE = 50;
let currentPage = 1;
let allLogs = [];
let refreshInterval = null;

const LEVEL_COLORS = {
    "DEBUG": "text-gray-400",
    "INFO": "text-blue-400",
    "WARNING": "text-yellow-400",
    "ERROR": "text-red-400",
    "CRITICAL": "text-red-400 font-bold",
};

const LEVEL_BG = {
    "DEBUG": "bg-gray-500/10",
    "INFO": "bg-blue-500/10",
    "WARNING": "bg-yellow-500/10",
    "ERROR": "bg-red-500/10",
    "CRITICAL": "bg-red-500/20",
};

async function loadLogs() {
    const tbody = document.getElementById('logs-body');
    const level = document.getElementById('filter-level')?.value || '';

    let url = '/api/logs?limit=200&offset=0';
    if (level) url += '&level=' + encodeURIComponent(level);

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        allLogs = data.logs || [];
        const total = data.total || 0;
        currentPage = 1;
        renderPage(total);
    } catch (e) {
        console.error("Error cargando logs:", e);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center p-8 text-error">Error al cargar logs</td></tr>';
    }
}

function renderPage(total) {
    const tbody = document.getElementById('logs-body');
    const totalPages = Math.ceil(allLogs.length / ITEMS_PER_PAGE) || 1;

    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = allLogs.slice(start, end);

    if (!allLogs || allLogs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center p-8 text-on-surface-variant">No hay logs disponibles</td></tr>';
    } else {
        tbody.innerHTML = pageItems.map(function (log, i) {
            const levelColor = LEVEL_COLORS[log.level] || 'text-on-surface';
            const levelBg = LEVEL_BG[log.level] || '';
            var idx = start + i;

            return '<tr class="hover:bg-white/5 transition-colors group font-mono text-sm">' +
                '<td class="px-6 py-3 text-on-surface-variant whitespace-nowrap">' + (log.timestamp || '--') + '</td>' +
                '<td class="px-6 py-3"><span class="px-2 py-0.5 rounded text-xs font-bold ' + levelBg + ' ' + levelColor + '">' + log.level + '</span></td>' +
                '<td class="px-6 py-3 text-on-surface-variant text-xs">' + (log.logger || log.module || '--') + '</td>' +
                '<td class="px-6 py-3 text-on-surface max-w-xl truncate" title="' + escapeHtml(log.message) + '">' + escapeHtml(log.message) + '</td>' +
                '<td class="px-6 py-3 text-on-surface-variant text-xs text-center">' + (log.line || '--') + '</td>' +
                '<td class="px-6 py-3 text-center"><button onclick="openJsonModal(' + idx + ')" class="text-xs px-2 py-1 rounded bg-white/10 hover:bg-primary-container/30 hover:text-primary-container transition-colors font-mono" title="Ver JSON completo">{ }</button></td>' +
                '</tr>';
        }).join('');
    }

    const infoEl = document.getElementById('pagination-info');
    const indicatorEl = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');

    if (infoEl) {
        if (allLogs.length === 0) {
            infoEl.textContent = 'Mostrando 0 registros (total: ' + (total || 0) + ')';
        } else {
            infoEl.textContent = 'Mostrando ' + (start + 1) + '–' + Math.min(end, allLogs.length) + ' de ' + allLogs.length + ' registros (total: ' + (total || allLogs.length) + ')';
        }
    }

    if (indicatorEl) indicatorEl.textContent = 'Pagina ' + currentPage + ' de ' + totalPages;
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
}

function changePage(delta) {
    currentPage += delta;
    renderPage();
}

function clearFilters() {
    document.getElementById('filter-level').value = '';
    currentPage = 1;
    allLogs = [];
    loadLogs();
}

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function syntaxHighlight(json) {
    return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/:(\s*)"([^"]*)"/g, ':<span class="json-string">"$2"</span>')
        .replace(/:(\s*)(\d+(?:\.\d+)?)/g, ':<span class="json-number">$2</span>')
        .replace(/:(\s*)(true|false)/g, ':<span class="json-boolean">$2</span>')
        .replace(/:(\s*)(null)/g, ':<span class="json-null">$2</span>');
}

function openJsonModal(index) {
    var log = allLogs[index];
    if (!log) return;
    var formatted = JSON.stringify(log, null, 2);
    document.getElementById('json-viewer').innerHTML = syntaxHighlight(formatted);
    var modal = document.getElementById('json-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeJsonModal() {
    var modal = document.getElementById('json-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

function initAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh');
    if (!checkbox) return;

    function toggleRefresh() {
        if (checkbox.checked) {
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(loadLogs, 2000);
        } else {
            if (refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
            }
        }
    }

    checkbox.addEventListener('change', toggleRefresh);
    toggleRefresh();
}

function initCopyLogs() {
    const btn = document.getElementById('copy-logs-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
        if (!allLogs || allLogs.length === 0) return;
        var text = allLogs.map(function (l) {
            return '[' + l.timestamp + '] [' + l.level + '] [' + (l.logger || l.module) + '] ' + l.message + (l.line ? ' (line ' + l.line + ')' : '');
        }).join('\n');
        navigator.clipboard.writeText(text).then(function () {
            var orig = btn.innerHTML;
            btn.innerHTML = '<span class="material-symbols-outlined text-sm">check</span> Copiado';
            setTimeout(function () { btn.innerHTML = orig; }, 2000);
        }).catch(function () {
            alert('No se pudo copiar al portapapeles');
        });
    });
}

function init() {
    loadLogs();
    initAutoRefresh();
    initCopyLogs();

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeJsonModal();
    });

    document.getElementById('json-modal').addEventListener('click', closeJsonModal);

    var filterSelect = document.getElementById('filter-level');
    if (filterSelect) filterSelect.addEventListener('change', loadLogs);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
