/**
 * Shared Sidebar & Header Component (v2 — with auth)
 * All pages share the same sidebar, footer, auth guard, and mobile responsive behavior.
 */

(function () {
  const currentPath = window.location.pathname;

  // ── Auth Guard ──
  // login 페이지가 아니면 토큰 체크
  if (currentPath !== '/login') {
    const token = localStorage.getItem('token');
    if (!token) {
      window.location.href = '/login';
      return;
    }
  }

  // ── HTML escape helper (XSS 방지) — 전역 노출 ──
  function escapeHTML(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  window.escapeHTML = escapeHTML;

  // ── User info from localStorage (빠른 렌더링용, /api/auth/me로 검증) ──
  let currentUser = null;
  try {
    currentUser = JSON.parse(localStorage.getItem('user'));
  } catch (e) { /* ignore */ }

  const userName = currentUser ? escapeHTML(currentUser.name) : '';
  const userPosition = currentUser ? escapeHTML(currentUser.position) : '';
  const userDept = currentUser ? escapeHTML(currentUser.department) : '';
  const userRole = currentUser ? currentUser.role : 'user';

  // ── 401 중복 리다이렉트 방지 플래그 ──
  var _isRedirecting = false;

  // ── Sidebar HTML ──
  const adminMenuItem = userRole === 'admin'
    ? `<a href="/admin" class="sidebar-nav-item ${currentPath === '/admin' ? 'active' : ''}">Admin</a>`
    : '';

  const sidebarHTML = `
    <!-- Sidebar Overlay (mobile) -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

    <!-- Sidebar -->
    <aside class="app-sidebar" id="appSidebar">
      <!-- Logo -->
      <div class="px-5 pt-6 pb-4">
        <div class="flex items-center gap-2">
          <div class="leading-tight">
            <div style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',sans-serif; font-weight:800; font-size:1.05rem; color:#1d1d1f; letter-spacing:-0.02em;">AICC Role Playing Agent</div>
            <div style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',sans-serif; font-size:10px; color:#86868b; letter-spacing:0.01em;">Personal Learning Platform</div>
          </div>
        </div>
      </div>

      <!-- Start New Roleplay Button -->
      <div class="px-4 pb-5">
        <a href="/simulation" class="flex items-center justify-center gap-2 w-full py-2.5 rounded-full text-[#0071e3] text-sm font-semibold shadow-[0_4px_12px_rgba(0,0,0,0.08)] hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] transition-all bg-white border border-gray-100"
           style="font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',sans-serif;">
          <span class="material-symbols-outlined" style="font-size:18px; color:#0071e3;">add</span>
          Start New Roleplay
        </a>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-0 space-y-0.5">
        <a href="/" class="sidebar-nav-item ${currentPath === '/' ? 'active' : ''}">Dashboard</a>
        <a href="/simulation" class="sidebar-nav-item ${currentPath === '/simulation' ? 'active' : ''}">Simulation</a>
        <a href="/quiz" class="sidebar-nav-item ${currentPath === '/quiz' ? 'active' : ''}">Quiz</a>
        <a href="/dictionary" class="sidebar-nav-item ${currentPath === '/dictionary' ? 'active' : ''}">Dictionary</a>
        <a href="/lectures" class="sidebar-nav-item ${currentPath === '/lectures' ? 'active' : ''}">Lectures</a>
        <a href="/history" class="sidebar-nav-item ${currentPath === '/history' ? 'active' : ''}">History</a>
        ${adminMenuItem}
      </nav>

      <!-- Footer -->
      <div class="px-5 py-4 border-t" style="border-color:rgba(195,198,210,0.3);">
        <p style="font-size:10px; color:#737782;">v2.0 &middot; Powered by Claude</p>
      </div>
    </aside>
  `;

  // ── Page titles ──
  const pageTitles = {
    '/': 'Dashboard',
    '/simulation': 'Simulation',
    '/quiz': 'Quiz',
    '/dictionary': 'Dictionary',
    '/history': 'History',
    '/admin': 'Admin',
    '/lectures': 'Lecture Materials',
  };

  const pageTitle = pageTitles[currentPath] || 'AI Roleplay Agent';

  // ── Header HTML (with user info + logout) ──
  const userDisplay = userName
    ? `<div class="user-info-display" onclick="openChangePassword()" style="cursor:pointer;" title="비밀번호 변경">
         <span class="material-symbols-outlined" style="font-size:20px;color:#434751;">account_circle</span>
         <span class="user-info-text">${userName} ${userPosition}님</span>
         <span class="user-info-dept">(${userDept})</span>
       </div>`
    : '';

  const headerHTML = `
    <header class="app-header" id="appHeader">
      <div class="flex items-center gap-3">
        <button class="hamburger-btn" onclick="toggleSidebar()" aria-label="메뉴 열기">
          <span class="material-symbols-outlined" style="font-size:24px;">menu</span>
        </button>
        <h1 style="font-family:'Manrope',sans-serif; font-weight:800; font-size:1.125rem; color:#0071e3;">${pageTitle}</h1>
      </div>
      <div class="flex items-center gap-3">
        ${userDisplay}
        <button onclick="handleLogout()" class="logout-btn" title="로그아웃">
          <span class="material-symbols-outlined" style="font-size:20px;">logout</span>
        </button>
      </div>
    </header>
  `;

  // ── Fix page title ──
  document.title = `${pageTitle} | AI Roleplay Agent`;

  // ── Password Change Modal HTML ──
  const passwordModalHTML = `
    <div id="pwModal" style="display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,0.4); align-items:center; justify-content:center;">
      <div style="background:#fff; border-radius:16px; padding:28px; width:90%; max-width:380px; box-shadow:0 8px 32px rgba(0,0,0,0.15);">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:20px;">
          <span class="material-symbols-outlined" style="color:#0071e3;">lock</span>
          <h3 style="font-family:'Manrope',sans-serif; font-weight:800; font-size:1.1rem; color:#0071e3; margin:0;">비밀번호 변경</h3>
        </div>
        <div style="margin-bottom:14px;">
          <label style="display:block; font-size:13px; color:#434751; margin-bottom:4px;">현재 비밀번호</label>
          <input type="password" id="pw-current" style="width:100%; padding:10px 12px; border:1px solid #c3c6d2; border-radius:10px; font-size:14px; box-sizing:border-box;" />
        </div>
        <div style="margin-bottom:14px;">
          <label style="display:block; font-size:13px; color:#434751; margin-bottom:4px;">새 비밀번호</label>
          <input type="password" id="pw-new" style="width:100%; padding:10px 12px; border:1px solid #c3c6d2; border-radius:10px; font-size:14px; box-sizing:border-box;" />
        </div>
        <div style="margin-bottom:20px;">
          <label style="display:block; font-size:13px; color:#434751; margin-bottom:4px;">새 비밀번호 확인</label>
          <input type="password" id="pw-confirm" style="width:100%; padding:10px 12px; border:1px solid #c3c6d2; border-radius:10px; font-size:14px; box-sizing:border-box;" />
        </div>
        <p id="pw-error" style="color:#d32f2f; font-size:13px; margin:0 0 12px 0; display:none;"></p>
        <p id="pw-success" style="color:#2e7d32; font-size:13px; margin:0 0 12px 0; display:none;"></p>
        <div style="display:flex; gap:8px; justify-content:flex-end;">
          <button onclick="closeChangePassword()" style="padding:8px 18px; border-radius:10px; border:1px solid #c3c6d2; background:#fff; color:#434751; font-size:14px; cursor:pointer;">취소</button>
          <button onclick="submitChangePassword()" id="pw-submit-btn" style="padding:8px 18px; border-radius:10px; border:none; background:#0071e3; color:#fff; font-size:14px; font-weight:600; cursor:pointer;">변경</button>
        </div>
      </div>
    </div>
  `;

  // ── Inject ──
  if (currentPath !== '/login') {
    document.body.insertAdjacentHTML('afterbegin', sidebarHTML + headerHTML + passwordModalHTML);
  }

  // ── Toggle sidebar (mobile) ──
  window.toggleSidebar = function () {
    const sidebar = document.getElementById('appSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  };

  // Close sidebar on nav click (mobile)
  document.querySelectorAll('.sidebar-nav-item').forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.innerWidth < 1024) {
        window.toggleSidebar();
      }
    });
  });

  // ── Logout ──
  window.handleLogout = function () {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  };

  // ── authFetch: 인증 헤더 자동 추가 래퍼 ──
  window.authFetch = async function (url, options = {}) {
    const token = localStorage.getItem('token');
    if (!token) {
      window.location.href = '/login';
      throw new Error('No token');
    }

    const headers = options.headers || {};
    headers['Authorization'] = 'Bearer ' + token;
    if (options.body && typeof options.body === 'string') {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    options.headers = headers;

    const res = await fetch(url, options);
    if (res.status === 401) {
      if (!_isRedirecting) {
        _isRedirecting = true;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
      throw new Error('Unauthorized');
    }
    return res;
  };

  // ── 접속 로그 기록 ──
  if (currentPath !== '/login') {
    try {
      authFetch('/api/access-log', {
        method: 'POST',
        body: JSON.stringify({ action: 'page_view', page: currentPath }),
      }).catch(function () { /* silently ignore */ });
    } catch (e) { /* ignore */ }
  }

  // ── Verify token on page load (background) ──
  if (currentPath !== '/login') {
    authFetch('/api/auth/me')
      .then(function (res) {
        if (res.ok) {
          return res.json();
        }
        throw new Error('Invalid token');
      })
      .then(function (user) {
        // Update cached user info if changed
        localStorage.setItem('user', JSON.stringify(user));
        window.dispatchEvent(new Event('user-updated'));
      })
      .catch(function (err) {
        // authFetch already handles 401 redirect; only handle other errors here
        if (err.message !== 'Unauthorized' && err.message !== 'No token') {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
      });
  }

  // ── Password Change Modal Functions ──
  window.openChangePassword = function () {
    var modal = document.getElementById('pwModal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.getElementById('pw-current').value = '';
    document.getElementById('pw-new').value = '';
    document.getElementById('pw-confirm').value = '';
    document.getElementById('pw-error').style.display = 'none';
    document.getElementById('pw-success').style.display = 'none';
    document.getElementById('pw-submit-btn').disabled = false;
  };

  window.closeChangePassword = function () {
    var modal = document.getElementById('pwModal');
    if (modal) modal.style.display = 'none';
  };

  window.submitChangePassword = async function () {
    var errEl = document.getElementById('pw-error');
    var successEl = document.getElementById('pw-success');
    var btn = document.getElementById('pw-submit-btn');
    errEl.style.display = 'none';
    successEl.style.display = 'none';

    var current = document.getElementById('pw-current').value;
    var newPw = document.getElementById('pw-new').value;
    var confirm = document.getElementById('pw-confirm').value;

    if (!current || !newPw || !confirm) {
      errEl.textContent = '모든 항목을 입력해주세요.';
      errEl.style.display = 'block';
      return;
    }
    if (newPw !== confirm) {
      errEl.textContent = '새 비밀번호가 일치하지 않습니다.';
      errEl.style.display = 'block';
      return;
    }
    if (newPw.length < 4) {
      errEl.textContent = '새 비밀번호는 4자 이상이어야 합니다.';
      errEl.style.display = 'block';
      return;
    }

    btn.disabled = true;
    try {
      var res = await authFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: newPw }),
      });
      if (res.ok) {
        successEl.textContent = '비밀번호가 변경되었습니다.';
        successEl.style.display = 'block';
        setTimeout(function () { closeChangePassword(); }, 1500);
      } else {
        var data = await res.json();
        errEl.textContent = data.detail || '비밀번호 변경에 실패했습니다.';
        errEl.style.display = 'block';
        btn.disabled = false;
      }
    } catch (e) {
      errEl.textContent = '서버 오류가 발생했습니다.';
      errEl.style.display = 'block';
      btn.disabled = false;
    }
  };

  // ── Expose currentUser for pages ──
  window.getCurrentUser = function () {
    try {
      return JSON.parse(localStorage.getItem('user'));
    } catch (e) {
      return null;
    }
  };
})();
