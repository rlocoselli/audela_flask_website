(function () {
  let driverLoadPromise = null;

  function getDriverScriptUrl() {
    if (window.__AUD_DRIVER_URL) return window.__AUD_DRIVER_URL;
    const current = document.querySelector('script[src*="portal/driver_tutorial.js"]');
    if (!current) return '/static/vendor/driverjs/driver.iife.js';
    try {
      const src = current.getAttribute('src') || '';
      return src.replace(/portal\/driver_tutorial\.js(?:\?.*)?$/, 'vendor/driverjs/driver.iife.js');
    } catch (_) {
      return '/static/vendor/driverjs/driver.iife.js';
    }
  }

  function ensureDriverLoaded() {
    if (getDriverFactory()) return Promise.resolve(true);
    if (driverLoadPromise) return driverLoadPromise;

    driverLoadPromise = new Promise(function (resolve) {
      const script = document.createElement('script');
      script.src = getDriverScriptUrl();
      script.async = true;
      script.onload = function () {
        resolve(!!getDriverFactory());
      };
      script.onerror = function () {
        resolve(false);
      };
      document.head.appendChild(script);
    });

    return driverLoadPromise;
  }

  function ensureFallbackStyles() {
    if (document.getElementById('audela-tour-fallback-style')) return;
    const style = document.createElement('style');
    style.id = 'audela-tour-fallback-style';
    style.textContent = [
      '.audela-tour-highlight {',
      '  outline: 3px solid #0d6efd !important;',
      '  outline-offset: 2px;',
      '  border-radius: 6px;',
      '  position: relative;',
      '  z-index: 1065;',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  function runFallbackTour(steps, labels) {
    if (!steps || !steps.length) return;
    ensureFallbackStyles();

    const modalId = 'audela-tour-fallback-modal';
    let modalEl = document.getElementById(modalId);
    if (!modalEl) {
      modalEl = document.createElement('div');
      modalEl.className = 'modal fade';
      modalEl.id = modalId;
      modalEl.tabIndex = -1;
      modalEl.setAttribute('aria-hidden', 'true');
      modalEl.innerHTML = [
        '<div class="modal-dialog modal-dialog-centered">',
        '  <div class="modal-content">',
        '    <div class="modal-header">',
        '      <h5 class="modal-title" id="audela-tour-fallback-title"></h5>',
        '      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>',
        '    </div>',
        '    <div class="modal-body">',
        '      <div id="audela-tour-fallback-progress" class="small text-secondary mb-2"></div>',
        '      <div id="audela-tour-fallback-desc"></div>',
        '    </div>',
        '    <div class="modal-footer">',
        '      <button type="button" class="btn btn-outline-secondary" id="audela-tour-fallback-prev"></button>',
        '      <button type="button" class="btn btn-primary" id="audela-tour-fallback-next"></button>',
        '    </div>',
        '  </div>',
        '</div>',
      ].join('');
      document.body.appendChild(modalEl);
    }

    const titleEl = modalEl.querySelector('#audela-tour-fallback-title');
    const descEl = modalEl.querySelector('#audela-tour-fallback-desc');
    const progressEl = modalEl.querySelector('#audela-tour-fallback-progress');
    const prevBtn = modalEl.querySelector('#audela-tour-fallback-prev');
    const nextBtn = modalEl.querySelector('#audela-tour-fallback-next');

    let currentIndex = 0;

    function clearHighlight() {
      document.querySelectorAll('.audela-tour-highlight').forEach(function (el) {
        el.classList.remove('audela-tour-highlight');
      });
    }

    function renderStep() {
      const step = steps[currentIndex];
      if (!step) return;

      clearHighlight();
      if (step.element && step.element.classList) {
        step.element.classList.add('audela-tour-highlight');
        try {
          step.element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        } catch (_) {
          step.element.scrollIntoView();
        }
      }

      const title = (step.popover && step.popover.title) || (window.t ? window.t('Tutoriel') : 'Tutorial');
      const description = (step.popover && step.popover.description) || '';

      titleEl.textContent = title;
      descEl.textContent = description;
      progressEl.textContent = (currentIndex + 1) + ' / ' + steps.length;

      prevBtn.textContent = labels.prev;
      prevBtn.disabled = currentIndex === 0;

      const isLast = currentIndex >= steps.length - 1;
      nextBtn.textContent = isLast ? labels.done : labels.next;
    }

    prevBtn.onclick = function () {
      if (currentIndex > 0) {
        currentIndex -= 1;
        renderStep();
      }
    };

    nextBtn.onclick = function () {
      const isLast = currentIndex >= steps.length - 1;
      if (isLast) {
        const inst = window.bootstrap && window.bootstrap.Modal ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;
        if (inst) inst.hide();
        clearHighlight();
        return;
      }
      currentIndex += 1;
      renderStep();
    };

    modalEl.addEventListener('hidden.bs.modal', clearHighlight, { once: true });

    renderStep();

    if (window.bootstrap && window.bootstrap.Modal) {
      window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    } else {
      alert(((titleEl && titleEl.textContent) || 'Tutorial') + '\n\n' + ((descEl && descEl.textContent) || ''));
      clearHighlight();
    }
  }

  function getDriverFactory() {
    if (window.driver && typeof window.driver.js === 'function') return window.driver.js;
    if (window.driver && typeof window.driver.driver === 'function') return window.driver.driver;
    if (typeof window.driver === 'function') return window.driver;
    if (typeof window.Driver === 'function') return window.Driver;
    return null;
  }

  function isVisible(el) {
    if (!el) return false;
    if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  }

  function toNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function cleanText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function detectTourTitle() {
    const path = (window.location && window.location.pathname ? window.location.pathname : '').toLowerCase();
    if (path.includes('/etl')) return window.t ? window.t('Tutoriel ETL') : 'ETL Tutorial';
    return window.t ? window.t('Tutoriel BI') : 'BI Tutorial';
  }

  function collectSteps() {
    const nodes = Array.from(document.querySelectorAll('[data-tour]'));
    const sorted = nodes
      .map(function (el, index) {
        return {
          el: el,
          index: index,
          order: toNumber(el.getAttribute('data-tour-order'), index + 1),
        };
      })
      .sort(function (a, b) {
        if (a.order === b.order) return a.index - b.index;
        return a.order - b.order;
      });

    return sorted
      .map(function (item) {
        const el = item.el;
        if (!isVisible(el)) return null;
        const description = (el.getAttribute('data-tour') || '').trim();
        if (!description) return null;
        const title = (el.getAttribute('data-tour-title') || '').trim();
        return {
          element: el,
          popover: {
            title: title || (window.t ? window.t('Tutoriel') : 'Tutorial'),
            description: description,
          },
        };
      })
      .filter(Boolean);
  }

  function collectAutoSteps() {
    const title = detectTourTitle();
    const selectors = [
      '[data-tip]',
      '[data-bi-tip]',
      '[data-finance-tip]',
      'h1, h2, h3, h4',
      'form .form-label',
      'form .form-control',
      '.btn.btn-primary, .btn.btn-outline-primary, .btn.btn-outline-secondary',
      '#drawflow, #etlPreview, #schema, #sql_text, #nlq-text, #source_id',
      '.card .text-muted',
    ].join(',');

    const seen = new Set();
    const maxSteps = 12;
    const out = [];

    const nodes = Array.from(document.querySelectorAll(selectors));
    for (const el of nodes) {
      if (!isVisible(el)) continue;

      const desc = cleanText(
        el.getAttribute('data-tip') ||
        el.getAttribute('data-bi-tip') ||
        el.getAttribute('data-finance-tip') ||
        el.getAttribute('aria-label') ||
        el.getAttribute('title') ||
        el.getAttribute('placeholder') ||
        el.textContent
      );

      if (!desc || desc.length < 6 || desc.length > 180) continue;
      const key = desc.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);

      out.push({
        element: el,
        popover: {
          title: title,
          description: desc,
        },
      });

      if (out.length >= maxSteps) break;
    }

    return out;
  }

  function buildFallbackSteps() {
    const anchor = document.querySelector('.js-start-tutorial') || document.querySelector('body');
    return [
      {
        element: anchor,
        popover: {
          title: window.t ? window.t('Tutoriel') : 'Tutorial',
          description: window.t
            ? window.t('Bienvenue dans le tutoriel. Cette page ne contient pas encore d\'étapes guidées détaillées.')
            : "Welcome to the tutorial. This page does not have detailed guided steps yet.",
        },
      },
    ];
  }

  async function startTour() {
    const explicitSteps = collectSteps();
    const autoSteps = explicitSteps.length ? [] : collectAutoSteps();
    const steps = explicitSteps.length ? explicitSteps : autoSteps;
    const finalSteps = steps.length ? steps : buildFallbackSteps();
    if (!explicitSteps.length && autoSteps.length && window.uiToast) {
      window.uiToast(
        window.t
          ? window.t('Tutoriel BI/ETL généré automatiquement pour cette page.')
          : 'Automatic BI/ETL tutorial generated for this page.',
        {
          variant: 'info',
          title: window.t ? window.t('Tutoriel') : 'Tutorial',
        }
      );
    }

    if (!steps.length && window.uiToast) {
      window.uiToast(
        window.t
          ? window.t('Mode tutoriel simplifié activé pour cette page.')
          : 'Simplified tutorial mode is enabled for this page.',
        {
          variant: 'info',
          title: window.t ? window.t('Tutoriel') : 'Tutorial',
        }
      );
    }

    const labels = {
      done: window.t ? window.t('Terminer') : 'Done',
      close: window.t ? window.t('Fermer') : 'Close',
      next: window.t ? window.t('Étape suivante') : 'Next',
      prev: window.t ? window.t('Étape précédente') : 'Previous',
      progressText: '{{current}} / {{total}}',
    };

    let driverFactory = getDriverFactory();
    if (!driverFactory) {
      await ensureDriverLoaded();
      driverFactory = getDriverFactory();
    }

    if (!driverFactory) {
      if (window.uiToast) {
        window.uiToast(
          window.t
            ? window.t('Mode tutoriel de compatibilité activé.')
            : 'Compatibility tutorial mode enabled.',
          {
            variant: 'info',
            title: window.t ? window.t('Tutoriel') : 'Tutorial',
          }
        );
      }
      runFallbackTour(finalSteps, labels);
      return;
    }

    const tour = driverFactory({
      showProgress: true,
      allowClose: true,
      animate: true,
      overlayOpacity: 0.55,
      nextBtnText: labels.next,
      prevBtnText: labels.prev,
      doneBtnText: labels.done,
      showButtons: ['previous', 'next', 'close'],
      steps: finalSteps,
    });

    tour.drive();
  }

  function bindTutorialButtons() {
    const buttons = Array.from(document.querySelectorAll('.js-start-tutorial'));
    if (!buttons.length) return;

    buttons.forEach(function (btn) {
      btn.disabled = false;
      btn.addEventListener('click', startTour);
    });

    const params = new URLSearchParams(window.location.search);
    if (params.get('tour') === '1') {
      startTour();
    }
  }

  window.startAudelaTutorial = startTour;

  if (window.onReady) window.onReady(bindTutorialButtons);
  else document.addEventListener('DOMContentLoaded', bindTutorialButtons);
})();
