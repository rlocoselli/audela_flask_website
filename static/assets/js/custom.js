(function () {
  function initAudelaCarousel(root) {
    var slides = Array.prototype.slice.call(root.querySelectorAll('.slide'));
    var dots = Array.prototype.slice.call(root.querySelectorAll('.dot'));
    var prev = root.querySelector('.arrow.prev');
    var next = root.querySelector('.arrow.next');
    var idx = 0;
    var timer = null;

    function render() {
      slides.forEach(function (s, i) { s.classList.toggle('active', i === idx); });
      dots.forEach(function (d, i) { d.classList.toggle('active', i === idx); });
    }
    function go(n) {
      idx = (n + slides.length) % slides.length;
      render();
    }
    function start() {
      stop();
      timer = setInterval(function () { go(idx + 1); }, 6000);
    }
    function stop() {
      if (timer) { clearInterval(timer); timer = null; }
    }

    dots.forEach(function (d, i) {
      d.addEventListener('click', function () { go(i); start(); });
    });
    if (prev) prev.addEventListener('click', function () { go(idx - 1); start(); });
    if (next) next.addEventListener('click', function () { go(idx + 1); start(); });

    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);

    render();
    start();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var c = document.querySelector('.audela-carousel');
    if (c) initAudelaCarousel(c);

    // Cookie information banner (for essential cookies; hides once acknowledged)
    try {
      var banner = document.getElementById('cookie-banner');
      var btn = document.getElementById('cookie-banner-accept');
      var key = 'audela_cookie_consent_v1';
      if (banner && btn) {
        var existing = localStorage.getItem(key);
        if (!existing) {
          banner.style.display = 'block';
        }
        btn.addEventListener('click', function(){
          try { localStorage.setItem(key, 'ack'); } catch(e) {}
          banner.style.display = 'none';
        });
      }
    } catch (e) {
      // ignore
    }
  });
})();
