(function () {
  'use strict';

  let currentResult = null;

  function initFileUpload() {
    const dropzone = document.getElementById('dropzone-zone');
    const fileInput = document.getElementById('image-input');
    const dropzoneText = document.getElementById('dropzone-text');
    const fileInfo = document.getElementById('file-info');
    const preview = document.getElementById('image-preview');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      if (!file) return;
      dropzoneText.textContent = file.name;
      fileInfo.textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
      const reader = new FileReader();
      reader.onload = function (e) {
        preview.src = e.target.result;
        dropzone.style.backgroundImage = `url(${e.target.result})`;
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
      dropzone.style.backgroundColor = 'rgba(255, 255, 255, 0.04)';
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.style.borderColor = 'rgba(255, 255, 255, 0.2)';
      dropzone.style.backgroundColor = 'rgba(255, 255, 255, 0.04)';
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

    const isCritico = riskLevel === 'critico';
    const styles = isCritico
      ? 'border glass-risk-high text-on-surface-variant animate-pulse'
      : 'border bg-primary-container/5 text-on-surface';
    const textStyles = isCritico ? 'text-[#ffb4ab] font-bold' : 'text-[#ffb77d]';
    const bgStyle = isCritico
      ? 'style="background-color: color-mix(in oklab, #93000a 20%, transparent);"'
      : '';
    const labelClass = isCritico ? 'text-[#ffb4ab]/80' : 'text-on-surface-variant';

    const riskHtml = '<div class="rounded-xl p-3 flex flex-col gap-1 transition-all text-center justify-center ' + (isCritico ? '' : 'glass-panel') + ' ' + styles + '" ' + bgStyle + '>' +
      '<span class="font-label-sm text-label-sm uppercase tracking-wider opacity-80 ' + labelClass + '">Nivel de Riesgo</span>' +
      '<div class="font-headline-md text-headline-md ' + textStyles + '">' + riskPct + '% (' + riskLevel.toUpperCase() + ')</div>' +
    '</div>';

    const cards = [
      { label: 'Total Detectado', value: total, blocked: false },
      { label: 'Personas', value: persons, blocked: !persons },
      { label: 'Armas', value: weapons, blocked: !weapons },
    ];

    grid.innerHTML = cards.map(function (c) { return metricCard(c.label, c.value, c.blocked); }).join('') + riskHtml +
      metricCard('Tiempo Inferencia', time + 'ms', false) +
      metricCard('Modelo Usado', model, false);
  }

  function renderClassCards(data) {
    const container = document.getElementById('class-cards');
    if (!container) return;

    const allNames = ['persona', 'arma', 'pistola', 'rifle', 'arma de fuego', 'cuchillo', 'armas', 'Cuchillo'];
    const counts = data.class_counts || {};

    container.innerHTML = allNames.map(function (cls) {
      const count = counts[cls] || 0;
      if (count === 0) {
        return '<div class="rounded-xl p-3 flex flex-col gap-1 text-center justify-center opacity-35 border border-white/5 bg-white/[0.02] cursor-not-allowed select-none">' +
          '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center justify-center gap-1">' +
            '<span class="material-symbols-outlined text-sm">lock</span> ' + cls +
          '</span>' +
          '<div class="text-on-surface-variant/30 text-label-sm font-medium">&mdash;</div>' +
        '</div>';
      }

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

      return '<div class="glass-card p-stack-lg rounded-xl flex flex-col gap-1 ' + borderColor + '">' +
        '<span class="font-label-sm text-label-sm text-on-surface-variant uppercase flex items-center justify-center gap-2">' +
          '<span class="material-symbols-outlined text-sm ' + textColor + '">' + icon + '</span>' +
          cls +
        '</span>' +
        '<span class="font-display-lg text-headline-lg ' + textColor + ' text-center">' + count + '</span>' +
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
