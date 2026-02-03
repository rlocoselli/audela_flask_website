(function(){
  const PRESETS = {
    default: {
      '--brand-color': '#1f6feb',
      '--brand-contrast': '#ffffff',
      '--accent-color': '#2563eb',
      '--accent-hover': '#1e40af',
      '--bg-primary': '#ffffff',
      '--bg-secondary': '#f8f9fa',
      '--bg-tertiary': '#f0f2f5',
      '--bg-hover': '#e8eaed',
      '--card-bg': '#ffffff',
      '--card-border': '#d1d5db',
      '--card-shadow': '0 2px 8px rgba(0, 0, 0, 0.08)',
      '--card-shadow-hover': '0 4px 16px rgba(0, 0, 0, 0.12)',
      '--sidebar-bg': '#ffffff',
      '--sidebar-border': '#e5e7eb',
      '--sidebar-text': '#374151',
      '--sidebar-hover-bg': '#f3f4f6',
      '--sidebar-active-bg': '#eff6ff',
      '--sidebar-active-text': '#1f6feb',
      '--text-primary': '#111827',
      '--text-secondary': '#6b7280',
      '--text-muted': '#9ca3af',
      '--border-color': '#e5e7eb',
      '--border-subtle': '#f3f4f6',
      '--btn-primary-bg': '#1f6feb',
      '--btn-primary-text': '#ffffff',
      '--btn-primary-hover': '#0d47a1',
      '--btn-secondary-bg': '#f3f4f6',
      '--btn-secondary-text': '#374151',
      '--btn-secondary-hover': '#e5e7eb'
    },
    aurora: {
      '--brand-color': '#0f766e',
      '--brand-contrast': '#ffffff',
      '--accent-color': '#0ea5a4',
      '--accent-hover': '#0c8c8a',
      '--bg-primary': '#f6fffb',
      '--bg-secondary': '#ecf9f6',
      '--bg-tertiary': '#e0f2f1',
      '--bg-hover': '#d4ede9',
      '--card-bg': '#f6fffb',
      '--card-border': '#99e0d8',
      '--card-shadow': '0 2px 8px rgba(15, 118, 110, 0.08)',
      '--card-shadow-hover': '0 4px 16px rgba(15, 118, 110, 0.12)',
      '--sidebar-bg': '#f6fffb',
      '--sidebar-border': '#ccf2ec',
      '--sidebar-text': '#0d5b54',
      '--sidebar-hover-bg': '#e0f2f1',
      '--sidebar-active-bg': '#ccf2ec',
      '--sidebar-active-text': '#0f766e',
      '--text-primary': '#0d5b54',
      '--text-secondary': '#198754',
      '--text-muted': '#5a9790',
      '--border-color': '#99e0d8',
      '--border-subtle': '#e0f2f1',
      '--btn-primary-bg': '#0f766e',
      '--btn-primary-text': '#ffffff',
      '--btn-primary-hover': '#086b61',
      '--btn-secondary-bg': '#e0f2f1',
      '--btn-secondary-text': '#0d5b54',
      '--btn-secondary-hover': '#ccf2ec'
    },
    nimbus: {
      '--brand-color': '#7c3aed',
      '--brand-contrast': '#ffffff',
      '--accent-color': '#a78bfa',
      '--accent-hover': '#6d28d9',
      '--bg-primary': '#fbf7ff',
      '--bg-secondary': '#f5f1ff',
      '--bg-tertiary': '#ede9fe',
      '--bg-hover': '#e5e0ff',
      '--card-bg': '#fbf7ff',
      '--card-border': '#d8cef2',
      '--card-shadow': '0 2px 8px rgba(124, 58, 237, 0.08)',
      '--card-shadow-hover': '0 4px 16px rgba(124, 58, 237, 0.12)',
      '--sidebar-bg': '#fbf7ff',
      '--sidebar-border': '#e5d9f7',
      '--sidebar-text': '#4c1d95',
      '--sidebar-hover-bg': '#ede9fe',
      '--sidebar-active-bg': '#e5d9f7',
      '--sidebar-active-text': '#7c3aed',
      '--text-primary': '#4c1d95',
      '--text-secondary': '#6b21a8',
      '--text-muted': '#9270c2',
      '--border-color': '#d8cef2',
      '--border-subtle': '#ede9fe',
      '--btn-primary-bg': '#7c3aed',
      '--btn-primary-text': '#ffffff',
      '--btn-primary-hover': '#6d28d9',
      '--btn-secondary-bg': '#ede9fe',
      '--btn-secondary-text': '#4c1d95',
      '--btn-secondary-hover': '#e5d9f7'
    },
    onyx: {
      '--brand-color': '#60a5fa',
      '--brand-contrast': '#ffffff',
      '--accent-color': '#93c5fd',
      '--accent-hover': '#3b82f6',
      '--bg-primary': '#1a1f3a',
      '--bg-secondary': '#0f1420',
      '--bg-tertiary': '#1f2849',
      '--bg-hover': '#2d3548',
      '--card-bg': '#16192b',
      '--card-border': '#2d3f5b',
      '--card-shadow': '0 2px 8px rgba(0, 0, 0, 0.3)',
      '--card-shadow-hover': '0 4px 16px rgba(0, 0, 0, 0.4)',
      '--sidebar-bg': '#0f1420',
      '--sidebar-border': '#1f2849',
      '--sidebar-text': '#d1d5db',
      '--sidebar-hover-bg': '#1f2849',
      '--sidebar-active-bg': '#1e3a5f',
      '--sidebar-active-text': '#60a5fa',
      '--text-primary': '#f3f4f6',
      '--text-secondary': '#b4b6be',
      '--text-muted': '#6b7280',
      '--border-color': '#2d3f5b',
      '--border-subtle': '#1f2849',
      '--btn-primary-bg': '#2563eb',
      '--btn-primary-text': '#ffffff',
      '--btn-primary-hover': '#1e40af',
      '--btn-secondary-bg': '#2d3f5b',
      '--btn-secondary-text': '#d1d5db',
      '--btn-secondary-hover': '#3f4d63'
    }
  };

  function applyPreset(name){
    const preset = PRESETS[name] || PRESETS.default;
    const el = document.documentElement;
    Object.keys(preset).forEach(k => el.style.setProperty(k, preset[k]));
    // Toggle body class for dark-ish palette detection
    if (name === 'onyx') document.body.classList.add('theme-dark'); else document.body.classList.remove('theme-dark');
    localStorage.setItem('audela_theme', name);
  }

  function init(){
    const sel = document.getElementById('theme-select');
    if (!sel) return;
    // load saved
    const saved = localStorage.getItem('audela_theme') || 'default';
    if (PRESETS[saved]) sel.value = saved;
    applyPreset(sel.value);

    sel.addEventListener('change', () => {
      applyPreset(sel.value);
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
