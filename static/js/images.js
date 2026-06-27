(function () {
  'use strict';

  function initConfidenceSlider() {
    const slider = document.getElementById('confidence-slider');
    const valueDisplay = document.getElementById('confidence-value');
    if (slider && valueDisplay) {
      slider.addEventListener('input', (e) => {
        valueDisplay.textContent = e.target.value;
      });
    }
  }

  function initDropzone() {
    const dropzone = document.querySelector('.lg\\:col-span-8');
    if (!dropzone) return;

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('border-primary-container');
      dropzone.style.background = 'rgba(255, 140, 0, 0.05)';
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('border-primary-container');
      dropzone.style.background = 'rgba(255, 255, 255, 0.04)';
    });
  }

  function initStartButton() {
    const startBtn = document.querySelector('button.bg-primary-container');
    if (!startBtn) return;

    startBtn.addEventListener('click', () => {
      startBtn.innerHTML = '<span class="material-symbols-outlined animate-spin">sync</span> Procesando...';
      startBtn.disabled = true;

      setTimeout(() => {
        startBtn.innerHTML = '<span class="material-symbols-outlined">check</span> ¡Completado!';
        setTimeout(() => {
          startBtn.innerHTML = '<span class="material-symbols-outlined">play_arrow</span> Iniciar Análisis';
          startBtn.disabled = false;
        }, 2000);
      }, 3000);
    });
  }

  function init() {
    initConfidenceSlider();
    initDropzone();
    initStartButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
