(function () {
  function getCsrfToken () {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function _defaultButtonHtml (button) {
    if (!button.dataset.ttsDefaultHtml) {
      button.dataset.ttsDefaultHtml = button.innerHTML;
    }
    return button.dataset.ttsDefaultHtml;
  }

  function _setButtonIdle (button) {
    if (!button) return;
    button.disabled = false;
    button.classList.remove('btn-primary', 'active');
    button.classList.add('btn-outline-secondary');
    button.setAttribute('aria-pressed', 'false');
    button.innerHTML = _defaultButtonHtml(button);
  }

  function _setButtonLoading (button) {
    if (!button) return;
    _defaultButtonHtml(button);
    button.disabled = true;
    button.classList.remove('active');
    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
  }

  function _setButtonPlaying (button) {
    if (!button) return;
    button.disabled = false;
    button.classList.remove('btn-outline-secondary');
    button.classList.add('btn-primary', 'active');
    button.setAttribute('aria-pressed', 'true');
    button.innerHTML = '<i class="bi bi-stop-circle"></i>';
  }

  function stopCurrentAudio () {
    if (window.__audelaTtsAudio) {
      try {
        window.__audelaTtsAudio.pause();
        window.__audelaTtsAudio.currentTime = 0;
      } catch (e) {}
      window.__audelaTtsAudio = null;
    }
    if (window.__audelaTtsAudioUrl) {
      try { URL.revokeObjectURL(window.__audelaTtsAudioUrl); } catch (e) {}
      window.__audelaTtsAudioUrl = null;
    }
    if (window.__audelaTtsButton) {
      _setButtonIdle(window.__audelaTtsButton);
      window.__audelaTtsButton = null;
    }
  }

  async function speakText (button) {
    if (window.__audelaTtsButton === button && window.__audelaTtsAudio) {
      stopCurrentAudio();
      return;
    }

    const txt = (button.getAttribute('data-tts-text') || '').trim();
    if (!txt) {
      if (window.uiToast) window.uiToast(window.t('Digite um texto para ouvir.'), { variant: 'danger' });
      return;
    }

    stopCurrentAudio();
    _setButtonLoading(button);

    try {
      const resp = await fetch('/app/api/tts', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {})
        },
        body: JSON.stringify({ text: txt })
      });

      if (!resp.ok) {
        let errorText = window.t('Não foi possível gerar áudio.');
        try {
          const payload = await resp.json();
          if (payload && payload.error) errorText = payload.error;
        } catch (e) {}
        throw new Error(errorText);
      }

      const blob = await resp.blob();

      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      window.__audelaTtsAudio = audio;
      window.__audelaTtsAudioUrl = audioUrl;
      window.__audelaTtsButton = button;
      _setButtonPlaying(button);

      audio.addEventListener('ended', function () {
        stopCurrentAudio();
      }, { once: true });

      audio.addEventListener('error', function () {
        stopCurrentAudio();
      }, { once: true });

      await audio.play();
    } catch (e) {
      if (window.__audelaTtsButton === button) {
        stopCurrentAudio();
      } else {
        _setButtonIdle(button);
      }
      if (window.uiToast) window.uiToast(String(e.message || window.t('Não foi possível gerar áudio.')), { variant: 'danger' });
    }
  }

  function bootTts () {
    document.addEventListener('click', function (event) {
      const button = event.target.closest('.js-tts-speak');
      if (!button) return;
      event.preventDefault();
      speakText(button);
    });
  }

  document.addEventListener('DOMContentLoaded', bootTts);
})();
