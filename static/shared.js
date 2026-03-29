/**
 * Shared Sidebar & Header Component
 * All pages share the same sidebar, footer, and mobile responsive behavior.
 */

(function () {
  const currentPath = window.location.pathname;

  // ── Sidebar HTML ──
  const sidebarHTML = `
    <!-- Sidebar Overlay (mobile) -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

    <!-- Sidebar -->
    <aside class="app-sidebar" id="appSidebar">
      <!-- Logo -->
      <div class="px-5 pt-6 pb-4">
        <div class="flex items-center gap-2">
          <div class="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-outlined text-white text-xl">smart_toy</span>
          </div>
          <div class="leading-tight">
            <div style="font-family:'Manrope',sans-serif; font-weight:800; font-size:0.8rem; color:#002859; letter-spacing:0.02em;">AI BUSINESS TEAM 2</div>
            <div style="font-size:10px; color:#737782; letter-spacing:0.05em;">Intelligence Layer</div>
          </div>
        </div>
      </div>

      <!-- Start New Roleplay Button -->
      <div class="px-4 pb-5">
        <a href="/simulation" class="flex items-center justify-center gap-2 w-full py-2.5 rounded-full text-white text-sm font-semibold shadow-md hover:shadow-lg transition-all"
           style="background:linear-gradient(135deg,#002859,#003d82);">
          <span class="material-symbols-outlined" style="font-size:18px;">add</span>
          Start New Roleplay
        </a>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-0 space-y-0.5">
        <a href="/" class="sidebar-nav-item ${currentPath === '/' ? 'active' : ''}">
          <span class="material-symbols-outlined" style="font-size:20px;">dashboard</span>
          Dashboard
        </a>
        <a href="/simulation" class="sidebar-nav-item ${currentPath === '/simulation' ? 'active' : ''}">
          <span class="material-symbols-outlined" style="font-size:20px;">sports_esports</span>
          Simulation
        </a>
        <a href="/quiz" class="sidebar-nav-item ${currentPath === '/quiz' ? 'active' : ''}">
          <span class="material-symbols-outlined" style="font-size:20px;">quiz</span>
          Quiz
        </a>
        <a href="/dictionary" class="sidebar-nav-item ${currentPath === '/dictionary' ? 'active' : ''}">
          <span class="material-symbols-outlined" style="font-size:20px;">menu_book</span>
          Dictionary
        </a>
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
  };

  const pageTitle = pageTitles[currentPath] || 'AI Roleplay Agent';

  // ── Header HTML ──
  const headerHTML = `
    <header class="app-header" id="appHeader">
      <div class="flex items-center gap-3">
        <button class="hamburger-btn" onclick="toggleSidebar()" aria-label="메뉴 열기">
          <span class="material-symbols-outlined" style="font-size:24px;">menu</span>
        </button>
        <h1 style="font-family:'Manrope',sans-serif; font-weight:800; font-size:1.125rem; color:#002859;">${pageTitle}</h1>
      </div>
      <div class="flex items-center gap-2">
        <button class="w-10 h-10 rounded-full hover:bg-surface-container-high flex items-center justify-center transition" style="border:none;background:transparent;cursor:pointer;">
          <span class="material-symbols-outlined" style="color:#434751;font-size:22px;">notifications</span>
        </button>
        <button class="w-10 h-10 rounded-full hover:bg-surface-container-high flex items-center justify-center transition" style="border:none;background:transparent;cursor:pointer;">
          <span class="material-symbols-outlined" style="color:#434751;font-size:22px;">settings</span>
        </button>
      </div>
    </header>
  `;

  // ── Fix page title ──
  document.title = `${pageTitle} | AI Roleplay Agent`;

  // ── Inject ──
  document.body.insertAdjacentHTML('afterbegin', sidebarHTML + headerHTML);

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
})();
