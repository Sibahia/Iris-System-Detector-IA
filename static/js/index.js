(function () {
  'use strict';

  const init = () => {
    const cards = document.querySelectorAll('.glass-panel');
    cards.forEach((card, i) => {
      card.style.setProperty('--card-index', i);
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
