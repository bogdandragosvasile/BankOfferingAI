/**
 * BankOffer AI — Authentication (Keycloak OIDC)
 * Include this script before the main page script.
 *
 * In DEMO_MODE (no Keycloak available), provides a mock auth flow
 * with role-based demo users.
 */
(function() {
  const STORAGE_KEY = 'boai_auth';
  const KC_CONFIG_URL = '/static/js/keycloak.json';

  // Demo users for when Keycloak is unavailable
  const DEMO_USERS = {
    admin: {
      sub: 'demo-admin-001',
      email: 'admin@bankofferai.com',
      name: 'System Administrator',
      roles: ['admin', 'employee'],
      customer_id: '0'
    },
    employee: {
      sub: 'demo-employee-001',
      email: 'manager@bankofferai.com',
      name: 'Relationship Manager',
      roles: ['employee'],
      customer_id: '0'
    },
    client: {
      sub: 'demo-client-001',
      email: 'client1@bankofferai.com',
      name: 'Demo Client',
      roles: ['client'],
      customer_id: '1'
    }
  };

  let _keycloak = null;
  let _currentUser = null;
  let _demoMode = true; // Default to demo mode; set false if Keycloak inits successfully
  let _onAuthChange = [];

  // ---- Keycloak integration ----
  async function initKeycloak() {
    try {
      // Check if keycloak-js is loaded
      if (typeof Keycloak === 'undefined') {
        console.log('[Auth] Keycloak JS not loaded, using demo mode');
        return false;
      }

      _keycloak = new Keycloak({
        url: 'https://auth.lupulup.com',
        realm: 'bankofferai',
        clientId: 'bankofferai-app'
      });

      const authenticated = await _keycloak.init({
        pkceMethod: 'S256',
        checkLoginIframe: false
      });

      if (authenticated) {
        _demoMode = false;
        _currentUser = {
          sub: _keycloak.tokenParsed.sub,
          email: _keycloak.tokenParsed.email,
          name: _keycloak.tokenParsed.name || _keycloak.tokenParsed.preferred_username,
          roles: _keycloak.tokenParsed.roles || _keycloak.tokenParsed.realm_access?.roles || [],
          customer_id: _keycloak.tokenParsed.customer_id || '0'
        };
        _saveSession();
        _notifyChange();

        // Token refresh
        setInterval(() => {
          _keycloak.updateToken(30).catch(() => {
            console.warn('[Auth] Token refresh failed, session may have expired');
            logout();
          });
        }, 60000);

        return true;
      }
      // Keycloak is available but user is not logged in
      _demoMode = false;
      return false;
    } catch (e) {
      console.log('[Auth] Keycloak init failed, using demo mode:', e.message);
      return false;
    }
  }

  const KC_BASE = 'https://auth.lupulup.com/realms/bankofferai/protocol/openid-connect';

  function keycloakLogin() {
    if (_keycloak) {
      try {
        _keycloak.login({ redirectUri: window.location.href });
        return;
      } catch(e) {
        console.warn('[Auth] Keycloak adapter login failed, using direct redirect');
      }
    }
    // Fallback: direct redirect without PKCE (works for public clients)
    const params = new URLSearchParams({
      client_id: 'bankofferai-app',
      redirect_uri: window.location.href,
      response_type: 'code',
      scope: 'openid email profile',
    });
    window.location.href = KC_BASE + '/auth?' + params.toString();
  }

  function keycloakRegister() {
    if (_keycloak) {
      try {
        _keycloak.register({ redirectUri: window.location.href });
        return;
      } catch(e) {}
    }
    const params = new URLSearchParams({
      client_id: 'bankofferai-app',
      redirect_uri: window.location.href,
      response_type: 'code',
      scope: 'openid email profile',
    });
    window.location.href = KC_BASE + '/registrations?' + params.toString();
  }

  function keycloakLogout() {
    if (_keycloak) {
      try {
        _keycloak.logout({ redirectUri: window.location.origin });
        return;
      } catch(e) {}
    }
    const params = new URLSearchParams({
      client_id: 'bankofferai-app',
      post_logout_redirect_uri: window.location.origin,
    });
    window.location.href = KC_BASE + '/logout?' + params.toString();
  }

  // ---- Demo mode auth ----
  const ROLE_PORTALS = {
    admin: '/admin',
    employee: '/',
    client: '/portal'
  };

  function demoLogin(role) {
    const user = DEMO_USERS[role];
    if (!user) return;
    _currentUser = { ...user };
    _demoMode = true;
    _saveSession();

    // Redirect to the correct portal for this role
    const targetPortal = ROLE_PORTALS[role];
    const currentPath = window.location.pathname;
    if (targetPortal && currentPath !== targetPortal) {
      window.location.href = targetPortal;
      return; // skip _notifyChange — the page will reload
    }
    _notifyChange();
  }

  // ---- Common ----
  function logout() {
    if (!_demoMode && _keycloak) {
      keycloakLogout();
      return;
    }
    _currentUser = null;
    localStorage.removeItem(STORAGE_KEY);
    _notifyChange();
  }

  function getUser() {
    return _currentUser;
  }

  function isAuthenticated() {
    return _currentUser !== null;
  }

  function hasRole(role) {
    return _currentUser?.roles?.includes(role) || false;
  }

  function isAdmin() {
    return hasRole('admin');
  }

  function isEmployee() {
    return hasRole('employee');
  }

  function isClient() {
    return hasRole('client');
  }

  function isDemoMode() {
    return _demoMode;
  }

  function getToken() {
    if (!_demoMode && _keycloak) {
      return _keycloak.token;
    }
    return null;
  }

  function getAuthHeader() {
    const token = getToken();
    return token ? { 'Authorization': 'Bearer ' + token } : {};
  }

  function onAuthChange(callback) {
    _onAuthChange.push(callback);
    // Immediately invoke with current state so late subscribers get the initial state
    try { callback(_currentUser); } catch(e) { console.error('[Auth] Callback error:', e); }
  }

  function _notifyChange() {
    _onAuthChange.forEach(cb => {
      try { cb(_currentUser); } catch(e) { console.error('[Auth] Callback error:', e); }
    });
  }

  function _saveSession() {
    if (_currentUser) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        user: _currentUser,
        demo: _demoMode,
        ts: Date.now()
      }));
    }
  }

  function _restoreSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const data = JSON.parse(raw);
      // Session expires after 8 hours
      if (Date.now() - data.ts > 8 * 60 * 60 * 1000) {
        localStorage.removeItem(STORAGE_KEY);
        return false;
      }
      _currentUser = data.user;
      _demoMode = data.demo;
      return true;
    } catch(e) {
      return false;
    }
  }

  // Render a user badge + logout button
  function renderUserBadge() {
    if (!_currentUser) return '';
    const roleColors = {
      admin: 'bg-red-500/20 text-red-400',
      employee: 'bg-cyan-500/20 text-cyan-400',
      client: 'bg-green-500/20 text-green-400'
    };
    const primaryRole = _currentUser.roles[0] || 'client';
    const roleClass = roleColors[primaryRole] || roleColors.client;
    const roleName = primaryRole.charAt(0).toUpperCase() + primaryRole.slice(1);
    const demoTag = _demoMode ? '<span class="text-amber-400 text-[10px] ml-1">(demo)</span>' : '';

    return `<div class="flex items-center gap-2">
      <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-dark-500/50">
        <div class="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center text-accent text-xs font-bold">
          ${_currentUser.name.charAt(0)}
        </div>
        <div class="text-xs">
          <div class="font-medium text-white">${_currentUser.name}${demoTag}</div>
          <span class="px-1.5 py-0.5 rounded text-[10px] font-medium ${roleClass}">${roleName}</span>
        </div>
      </div>
      <button onclick="window.BOAI_AUTH.logout()" class="p-1.5 rounded-lg hover:bg-red-500/10 text-dark-300 hover:text-red-400 transition-colors" title="Log out">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
        </svg>
      </button>
    </div>`;
  }

  // Render login form (demo mode selector or Keycloak redirect)
  function renderLoginScreen(options = {}) {
    const { title, subtitle, allowedRoles } = options;
    const t = window.BOAI_I18N?.t || (k => k);

    if (!_demoMode && _keycloak) {
      // Keycloak mode — show login/register buttons
      return `<div class="min-h-screen flex items-center justify-center">
        <div class="glass-card rounded-2xl p-8 max-w-md w-full text-center">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-accent/20 flex items-center justify-center">
            <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-white mb-2">${title || t('auth.login_title')}</h2>
          <p class="text-dark-300 mb-6">${subtitle || t('auth.login_subtitle')}</p>
          <button onclick="window.BOAI_AUTH.keycloakLogin()"
            class="w-full py-3 bg-accent hover:bg-accent-dark text-white rounded-xl font-medium transition-colors mb-3">
            ${t('common.login')}
          </button>
          <button onclick="window.BOAI_AUTH.keycloakRegister()"
            class="w-full py-3 border border-accent/30 hover:bg-accent/10 text-accent rounded-xl font-medium transition-colors">
            ${t('common.register')}
          </button>
        </div>
      </div>`;
    }

    // Demo mode — show user selector cards
    const roles = allowedRoles || ['admin', 'employee', 'client'];
    const roleInfo = {
      admin: { icon: '\uD83D\uDEE1\uFE0F', color: 'red', desc: t('auth.role_admin') },
      employee: { icon: '\uD83D\uDCBC', color: 'cyan', desc: t('auth.role_employee') },
      client: { icon: '\uD83D\uDC64', color: 'green', desc: t('auth.role_client') }
    };

    const cards = roles.map(role => {
      const info = roleInfo[role];
      const user = DEMO_USERS[role];
      return `<button onclick="window.BOAI_AUTH.demoLogin('${role}')"
        class="glass-card rounded-xl p-5 text-left hover:border-${info.color}-500/40 transition-all group">
        <div class="text-3xl mb-3">${info.icon}</div>
        <div class="font-semibold text-white group-hover:text-${info.color}-400 transition-colors">${info.desc}</div>
        <div class="text-xs text-dark-300 mt-1">${user.email}</div>
      </button>`;
    }).join('');

    return `<div class="min-h-screen flex items-center justify-center p-4">
      <div class="max-w-lg w-full">
        <div class="text-center mb-8">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-accent/20 flex items-center justify-center">
            <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-white mb-2" data-i18n="app.name">BankOffer AI</h2>
          <p class="text-dark-300" data-i18n="auth.demo_select">${t('auth.demo_select')}</p>
          <div class="mt-2 px-3 py-1 inline-block rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium">
            Demo Mode
          </div>
        </div>
        <div class="grid gap-3">${cards}</div>
      </div>
    </div>`;
  }

  // Initialize: try restoring session, then try Keycloak
  async function init() {
    const restored = _restoreSession();
    if (restored && _demoMode) {
      // Demo session restored
      _notifyChange();
      return;
    }
    // Try Keycloak init
    const kcOk = await initKeycloak();
    if (!kcOk && !restored) {
      // No auth at all
      _notifyChange();
    }
  }

  // Expose API
  window.BOAI_AUTH = {
    init,
    getUser,
    isAuthenticated,
    hasRole,
    isAdmin,
    isEmployee,
    isClient,
    isDemoMode,
    getToken,
    getAuthHeader,
    demoLogin,
    logout,
    onAuthChange,
    keycloakLogin,
    keycloakRegister,
    renderUserBadge,
    renderLoginScreen
  };

  // Auto-init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
