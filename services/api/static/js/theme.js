/**
 * BankOffer AI — Theme Switcher (Light / Dark)
 * Include this script before the main page script.
 * Works with Tailwind CSS by toggling a 'light-theme' class on <html>.
 */
(function() {
  const STORAGE_KEY = 'boai_theme';

  const LIGHT_CSS = `
    html.light-theme body { background: #f1f5f9 !important; color: #1e293b !important; }
    html.light-theme .glass-card {
      background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248,250,252,0.98)) !important;
      border-color: rgba(148,163,184,0.25) !important;
      color: #1e293b !important;
    }
    html.light-theme .glass-card:hover { border-color: rgba(99,102,241,0.4) !important; }

    /* Sidebar */
    html.light-theme aside, html.light-theme .sidebar-bg {
      background: linear-gradient(180deg, #ffffff, #f8fafc) !important;
      border-color: #e2e8f0 !important;
    }
    html.light-theme .sidebar-link { color: #475569 !important; }
    html.light-theme .sidebar-link:hover, html.light-theme .sidebar-link.active {
      background: rgba(99,102,241,0.08) !important; color: #4f46e5 !important;
    }

    /* Top bar */
    html.light-theme header, html.light-theme .topbar-bg, html.light-theme nav {
      background: rgba(255,255,255,0.9) !important;
      border-color: #e2e8f0 !important;
    }

    /* Text colors */
    html.light-theme h1, html.light-theme h2, html.light-theme h3, html.light-theme h4 { color: #0f172a !important; }
    html.light-theme p, html.light-theme span, html.light-theme td, html.light-theme th, html.light-theme label, html.light-theme li { color: #334155 !important; }
    html.light-theme .text-white { color: #0f172a !important; }
    html.light-theme .text-gray-400, html.light-theme .text-dark-200, html.light-theme .text-dark-300 { color: #64748b !important; }
    html.light-theme .text-gray-500, html.light-theme .text-dark-400 { color: #94a3b8 !important; }
    html.light-theme .text-gray-300 { color: #475569 !important; }

    /* Inputs */
    html.light-theme input, html.light-theme select, html.light-theme textarea {
      background: #ffffff !important; border-color: #cbd5e1 !important; color: #1e293b !important;
    }
    html.light-theme input:focus, html.light-theme select:focus, html.light-theme textarea:focus {
      border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
    }
    html.light-theme input::placeholder { color: #94a3b8 !important; }

    /* Tables */
    html.light-theme table { border-color: #e2e8f0 !important; }
    html.light-theme thead { background: #f8fafc !important; }
    html.light-theme tbody tr { border-color: #f1f5f9 !important; }
    html.light-theme tbody tr:hover { background: rgba(99,102,241,0.04) !important; }

    /* Buttons */
    html.light-theme .customer-btn, html.light-theme .product-item {
      border-color: #cbd5e1 !important; background: #ffffff !important; color: #334155 !important;
    }
    html.light-theme .customer-btn:hover, html.light-theme .product-item:hover {
      border-color: #6366f1 !important; background: rgba(99,102,241,0.05) !important;
    }
    html.light-theme .customer-btn.active, html.light-theme .customer-btn.selected {
      border-color: #6366f1 !important; background: rgba(99,102,241,0.08) !important;
    }

    /* Modals / overlays */
    html.light-theme .modal-bg, html.light-theme [class*="bg-dark-800"], html.light-theme [class*="bg-dark-900"] {
      background: #ffffff !important;
    }
    html.light-theme [class*="bg-dark-700"] { background: #f8fafc !important; }
    html.light-theme [class*="bg-dark-950"] { background: #f1f5f9 !important; }

    /* Score bars keep color */
    html.light-theme .score-bar-bg { background: rgba(99,102,241,0.12) !important; }

    /* Stat cards */
    html.light-theme .stat-glow-green { box-shadow: inset 0 -2px 0 #10b981, 0 1px 3px rgba(0,0,0,0.06) !important; }
    html.light-theme .stat-glow-purple { box-shadow: inset 0 -2px 0 #6366f1, 0 1px 3px rgba(0,0,0,0.06) !important; }
    html.light-theme .stat-glow-cyan { box-shadow: inset 0 -2px 0 #06b6d4, 0 1px 3px rgba(0,0,0,0.06) !important; }
    html.light-theme .stat-glow-amber { box-shadow: inset 0 -2px 0 #f59e0b, 0 1px 3px rgba(0,0,0,0.06) !important; }

    /* Scrollbar */
    html.light-theme * { scrollbar-color: #cbd5e1 transparent !important; }

    /* Badges / pills keep accent colors */
    html.light-theme .bg-green-500\\/10 { background: rgba(16,185,129,0.1) !important; }
    html.light-theme .bg-red-500\\/10 { background: rgba(239,68,68,0.1) !important; }

    /* Toggle track in light */
    html.light-theme .toggle-track.off { background: #cbd5e1 !important; }

    /* Nav links for portal */
    html.light-theme .nav-link { color: #475569 !important; }
    html.light-theme .nav-link:hover { color: #4f46e5 !important; background: rgba(99,102,241,0.06) !important; }
    html.light-theme .nav-link.active { color: #4f46e5 !important; background: rgba(99,102,241,0.1) !important; border-color: #6366f1 !important; }
  `;

  // Inject stylesheet
  const styleEl = document.createElement('style');
  styleEl.id = 'boai-light-theme';
  styleEl.textContent = LIGHT_CSS;
  document.head.appendChild(styleEl);

  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || 'dark';
  }

  function applyTheme(theme) {
    if (theme === 'light') {
      document.documentElement.classList.add('light-theme');
    } else {
      document.documentElement.classList.remove('light-theme');
    }
    localStorage.setItem(STORAGE_KEY, theme);
    // Update any toggle buttons
    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
      const icon = btn.querySelector('.theme-icon');
      const label = btn.querySelector('.theme-label');
      if (icon) icon.textContent = theme === 'light' ? '\u2600\uFE0F' : '\uD83C\uDF19';
      if (label) label.textContent = theme === 'light' ? 'Light' : 'Dark';
    });
  }

  function toggleTheme() {
    const current = getTheme();
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  // Apply immediately
  applyTheme(getTheme());

  // Render a theme toggle button HTML string
  function renderThemeToggle() {
    const theme = getTheme();
    return `<button data-theme-toggle onclick="window.BOAI_THEME.toggle()"
      class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
             border border-dark-500/50 hover:border-accent/30 transition-all"
      title="Toggle theme">
      <span class="theme-icon">${theme === 'light' ? '\u2600\uFE0F' : '\uD83C\uDF19'}</span>
      <span class="theme-label">${theme === 'light' ? 'Light' : 'Dark'}</span>
    </button>`;
  }

  // Expose API
  window.BOAI_THEME = {
    get: getTheme,
    set: applyTheme,
    toggle: toggleTheme,
    renderToggle: renderThemeToggle
  };
})();
