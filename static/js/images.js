(function () {
  'use strict';

  let currentResult = null;
  const ALLOWED_IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];

  function initFileUpload() {
    const dropzone = document.getElementById('dropzone-zone');
    const fileInput = document.getElementById('image-input');
    const dropzoneText = document.getElementById('dropzone-text');
    const fileInfo = document.getElementById('file-info');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      if (!file) return;

      var ext = '.' + file.name.split('.').pop().toLowerCase();
      if (ALLOWED_IMAGE_EXTS.indexOf(ext) === -1) {
        showError('Tipo de archivo no permitido. Formatos aceptados: JPG, PNG, GIF, BMP, WEBP.');
        return;
      }

      dropzoneText.textContent = file.name;
      fileInfo.textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
      var reader = new FileReader();
      reader.onload = function (e) {
        dropzone.style.backgroundImage = 'url(' + e.target.result + ')';
        dropzone.style.backgroundSize = 'cover';
        dropzone.style.backgroundPosition = 'center';
        dropzone.classList.add('has-image');
      };
      reader.readAsDataURL(file);
      hideError();
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

  function initAnalyzeButton() {
    const btn = document.getElementById('analyze-btn');
    if (!btn) return;
    btn.addEventListener('click', handleAnalyze);
  }

  async function handleAnalyze() {
    const fileInput = document.getElementById('image-input');
    const file = fileInput.files[0];
    if (!file) {
      showError('Por favor selecciona una imagen primero.');
      return;
    }

    const confidence = document.getElementById('confidence-slider').value;
    const modelSelect = document.getElementById('model-select');
    const modelName = modelSelect ? modelSelect.value : '';

    const btn = document.getElementById('analyze-btn');
    showLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    let url = '/analyze-image?confidence=' + confidence + '&crowd_threshold=5';
    if (modelName) url += '&model_name=' + encodeURIComponent(modelName);

    try {
      const resp = await fetch(url, { method: 'POST', body: formData });
      if (!resp.ok) {
        const errData = await resp.json().catch(function () { return {}; });
        throw new Error(errData.detail || 'Error en el análisis');
      }
      const data = await resp.json();
      currentResult = data;
      displayResults(data);
    } catch (err) {
      showError(err.message || 'Error de conexión con el servidor.');
    } finally {
      showLoading(false);
    }
  }

  function displayResults(data) {
    document.getElementById('results-section').classList.remove('hidden');
    hideError();

    renderGlobalMetrics(data);
    renderClassCards(data);
    updateStatusBadge(data);
    showAnnotatedImage(data);
  }

  function metricCard(label, value, blocked) {
    if (blocked) {
      return '<div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">' +
        '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">' +
          '<span class="material-symbols-outlined text-sm">lock</span> ' + label +
        '</span>' +
        '<div class="text-on-surface-variant/30 text-label-sm font-medium">&mdash;</div>' +
      '</div>';
    }
    return '<div class="glass-panel rounded-xl p-3 flex flex-col gap-1 transition-all text-center justify-center">' +
      '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">' + label + '</span>' +
      '<div class="font-headline-md text-headline-md text-on-surface">' + value + '</div>' +
    '</div>';
  }

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

  function renderGlobalMetrics(data) {
    const grid = document.getElementById('metrics-grid');
    if (!grid) return;

    const persons = data.persons_count || 0;
    const weapons = data.weapons_count || 0;
    const objects = data.objects_count || 0;
    const total = persons + weapons + objects;
    const riskPct = data.risk_percentage || 0;
    const riskLevel = data.risk_level || 'normal';
    const time = data.processing_time_ms || 0;
    const model = data.model_used || '—';

    const riskColors = { normal: '#4ade80', bajo: '#4ade80', medio: '#fbbf24', alto: '#f87171' };
    const color = riskColors[riskLevel] || '#4ade80';

    const riskHtml = '<div class="glass-panel rounded-xl p-3 flex flex-col gap-1 transition-all text-center justify-center border bg-primary-container/5 text-on-surface">' +
      '<span class="font-label-sm text-label-sm uppercase tracking-wider opacity-80 text-on-surface-variant">Nivel de Riesgo</span>' +
      '<div class="font-headline-md text-headline-md" style="color: ' + color + '">' + riskPct + '% (' + riskLevel.toUpperCase() + ')</div>' +
    '</div>';

    const cards = [
      { label: 'Total Detectado', value: total, blocked: false },
    ];

    var itemsHtml = cards.map(function (c) { return metricCard(c.label, c.value, c.blocked); }).join('') + riskHtml +
      metricCard('Tiempo Inferencia', time + 'ms', false) +
      metricCard('Modelo Usado', model, false);

    var totalItems = (itemsHtml.match(/<div class="rounded-xl/g) || []).length;
    var cols = optimalGridCols(totalItems, 2, 6);
    grid.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
    grid.style.justifyContent = totalItems <= 6 ? 'center' : '';
    grid.innerHTML = itemsHtml;
  }

  function renderClassCards(data) {
    const container = document.getElementById('class-cards');
    if (!container) return;

    const classGroups = data.class_groups || {};
    const classCounts = data.class_counts || {};
    const groupNames = Object.keys(classGroups);

    if (groupNames.length === 0) {
      container.innerHTML = '';
      return;
    }

    var cols = optimalGridCols(groupNames.length, 2, 6);
    container.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
    container.innerHTML = groupNames.map(function (gName) {
      var g = classGroups[gName];
      var total = g.count || 0;
      var style = getGroupStyle(gName);

      if (total === 0) {
        return '<div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">' +
          '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">' +
            '<span class="material-symbols-outlined text-sm">lock</span> ' + gName +
          '</span>' +
          '<div class="text-on-surface-variant/30 text-label-sm font-medium">&mdash;</div>' +
        '</div>';
      }

      var detectedList = g.detected_natives || {};
      var subItems = Object.keys(detectedList).map(function (n) {
        return '<div class="flex items-center justify-between gap-2">' +
          '<span class="text-label-xs text-on-surface-variant/80 truncate">' + n + '</span>' +
          '<span class="text-label-xs font-bold ' + style.textColor + '">×' + detectedList[n] + '</span>' +
        '</div>';
      }).join('');

      return '<div class="glass-card p-stack-lg rounded-xl flex flex-col gap-1 ' + style.borderColor + '">' +
        '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase flex items-center justify-center gap-2">' +
          '<span class="material-symbols-outlined text-sm ' + style.textColor + '">' + style.icon + '</span>' + gName +
        '</span>' +
        '<span class="font-display-lg text-headline-lg ' + style.textColor + ' text-center">' + total + '</span>' +
        (subItems ? '<div class="border-t border-white/10 pt-2 mt-1 flex flex-col gap-1">' + subItems + '</div>' : '') +
      '</div>';
    }).join('');
  }

  function updateStatusBadge(data) {
    const badge = document.getElementById('status-badge');
    const statusText = document.getElementById('status-text');
    if (!badge || !statusText) return;

    var dot = badge.querySelector('span:first-child');
    if (!dot) return;

    if (data.is_anomaly) {
      badge.className = 'px-3 py-1 bg-red-500/10 text-red-400 text-label-sm rounded-full border border-red-500/20 flex items-center gap-1';
      dot.className = 'w-2 h-2 bg-red-400 rounded-full animate-pulse';
      statusText.textContent = 'Anomalía detectada';
    } else {
      badge.className = 'px-3 py-1 bg-green-500/10 text-green-400 text-label-sm rounded-full border border-green-500/20 flex items-center gap-1';
      dot.className = 'w-2 h-2 bg-green-400 rounded-full animate-pulse';
      statusText.textContent = 'Procesamiento completado — Normal';
    }
  }

  function showAnnotatedImage(data) {
    const img = document.getElementById('result-image');
    if (!img) return;
    img.src = data.annotated_image_url || '';
    img.classList.remove('opacity-80');
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

  function initZoom() {
    const btn = document.getElementById('zoom-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      const img = document.getElementById('result-image');
      if (!img || !img.src) return;
      window.open(img.src, '_blank');
    });
  }

  function showError(msg) {
    const el = document.getElementById('error-message');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(function () { hideError(); }, 8000);
  }

  function hideError() {
    const el = document.getElementById('error-message');
    if (el) el.classList.add('hidden');
  }

  function showLoading(active) {
    const btn = document.getElementById('analyze-btn');
    if (!btn) return;
    if (active) {
      btn.disabled = true;
      btn.innerHTML = '<span class="material-symbols-outlined animate-spin">sync</span> Procesando...';
    } else {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined">play_arrow</span> Iniciar Análisis';
    }
  }

  function init() {
    initFileUpload();
    initModelSelect();
    initConfidenceSlider();
    initAnalyzeButton();
    initExportJSON();
    initZoom();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
