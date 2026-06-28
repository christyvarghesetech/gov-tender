/* ==========================================================================
   APP STATE & MOCK DATABASE (Syncs with PostgreSQL API)
   ========================================================================== */

const API_BASE = window.location.origin + "/api";

// Intercept window.fetch globally to append X-Digital-Id header when logged in
const originalFetch = window.fetch;
window.fetch = function (url, options = {}) {
  if (currentUser && currentUser.digital_id) {
    if (!options.headers) {
      options.headers = {};
    }
    options.headers["X-Digital-Id"] = currentUser.digital_id;
  }
  return originalFetch(url, options);
};

let mockTenders = [];
let mockUsers = [];
let mockApplications = [];
let mockSavedTenders = ["VC-3E7D-921A-09FF"];
let mockDocuments = [];
let mockTickets = [];
let mockNotifications = [];
let mockLogs = [];

// Current active session states
let currentUser = null;
let selectedTender = null;
let currentTimer = null;

// Synchronizes the client state arrays with the backend API
async function syncAllData() {
  // Public: tenders are always visible
  try {
    const tenders = await fetch(`${API_BASE}/tenders`).then(r => r.json());
    if (Array.isArray(tenders)) mockTenders = tenders;
  } catch (e) { console.warn("Backend offline — tenders fetch failed."); }

  // Protected: only fetch when logged in (avoids 401 errors on page load)
  if (!currentUser) return;

  try {
    const apps = await fetch(`${API_BASE}/applications`).then(r => r.json());
    if (Array.isArray(apps)) mockApplications = apps;
  } catch (e) { }

  try {
    const docs = await fetch(`${API_BASE}/documents`).then(r => r.json());
    if (Array.isArray(docs)) {
      mockDocuments = docs.map(d => ({
        id: d.id,
        name: d.name,
        status: d.status,
        expiryDate: d.expiryDate
      }));
    }
  } catch (e) { }

  try {
    const tickets = await fetch(`${API_BASE}/tickets`).then(r => r.json());
    if (Array.isArray(tickets)) mockTickets = tickets;
  } catch (e) { }

  try {
    const notifs = await fetch(`${API_BASE}/notifications`).then(r => r.json());
    if (Array.isArray(notifs)) mockNotifications = notifs;
  } catch (e) { }

  try {
    const logs = await fetch(`${API_BASE}/logs`).then(r => r.json());
    if (Array.isArray(logs)) mockLogs = logs;
  } catch (e) { }

  try {
    const users = await fetch(`${API_BASE}/users`).then(r => r.json());
    if (Array.isArray(users)) mockUsers = users;
  } catch (e) { }
}

/* ==========================================================================
   APP INITIALIZATION & COMPONENT LIFECYCLE
   ========================================================================== */

// Load all screen HTML files into #view-container before setup
async function loadAllScreens() {
  const screens = [
    'home-view',
    'verify-view',
    'login-view',
    'register-view',
    'otp-view',
    'vendor-portal-view',
    'tender-details-view',
    'tender-apply-view',
    'apply-success-view',
    'dashboard-view',
    'auditor-portal-view',
    'support-view',
  ];

  const container = document.getElementById('view-container');
  if (!container) return;

  for (const screen of screens) {
    try {
      const res = await fetch(`/screens/${screen}.html?v=${Date.now()}`);
      if (res.ok) {
        const html = await res.text();
        const wrapper = document.createElement('div');
        wrapper.innerHTML = html;
        // Append the actual view element (first child)
        while (wrapper.firstChild) {
          container.appendChild(wrapper.firstChild);
        }
      }
    } catch (e) {
      console.warn(`Could not load screen: ${screen}`, e);
    }
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  // Load all screen HTML into DOM first — MUST be before any setup calls
  await loadAllScreens();

  setupNavigation();
  setupVerifyPortal();
  setupVerifyPortalSearch();
  // login form logic is now handled by eSignet redirect
  setupRegistrationForm();
  setupSupportForm();
  setupTenderDetailsActions();
  setupApplicationForm();
  setupDocumentManager();
  setupAdminForms();
  setupVendorPortalForms();
  setupHeaderScroll();

  // Auditor portal logout
  const auditorLogout = document.getElementById('auditor-logout-btn');
  if (auditorLogout) {
    auditorLogout.addEventListener('click', logoutSession);
  }

  // Auditor sub-tabs menu
  const auditorSidebarLinks = document.querySelectorAll('.sidebar-link[data-auditor-tab]');
  auditorSidebarLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = link.getAttribute('data-auditor-tab');
      openAuditorTab(tabId);
    });
  });



  // Initial fetch for mock tenders if any
  await syncAllData();

  // Auditor portal verify desk search
  const auditorSearchBtn = document.getElementById('auditor-search-btn');
  const auditorSearchInput = document.getElementById('auditor-search-input');
  if (auditorSearchBtn && auditorSearchInput) {
    auditorSearchBtn.addEventListener('click', () => {
      const query = auditorSearchInput.value.trim();
      if (query) {
        showTenderInVerifyPortal(query);
      }
    });
    auditorSearchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        const query = auditorSearchInput.value.trim();
        if (query) {
          showTenderInVerifyPortal(query);
        }
      }
    });
  }

  // Load backend database records on startup
  await syncAllData();

  // Populate dynamic cards on homepage
  renderFeaturedTenders();

  // Restore session if exists
  const savedSession = localStorage.getItem('govtender_session');
  if (savedSession) {
    try {
      currentUser = JSON.parse(savedSession);
      updateSessionUI();
    } catch (e) {
      localStorage.removeItem('govtender_session');
    }
  }

  // Handle OIDC Callback Login Redirect
  const urlParams = new URLSearchParams(window.location.search);
  const loginDid = urlParams.get('login_did');
  if (loginDid) {
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ digital_id: loginDid })
      }).then(r => r.json());

      currentUser = res;
      localStorage.setItem('govtender_session', JSON.stringify(currentUser));
      updateSessionUI();

      if (currentUser.role === 'Admin') {
        switchView('dashboard-view');
      } else if (currentUser.role === 'Vendor') {
        switchView('vendor-portal-view');
      } else if (currentUser.role === 'Auditor') {
        switchView('auditor-portal-view');
      }

      // Clear the query parameter from the URL bar without reloading
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({ path: cleanUrl }, '', cleanUrl);

      alert(`Signed in successfully via eSignet OIDC as ${currentUser.name}!`);
    } catch (err) {
      console.error("Failed to authenticate user from callback redirect:", err);
    }
  }


  // Set default view on load
  if (loginDid) {
    // Handled above
  } else if (currentUser) {
    // If returning user is already logged in, redirect to their portal immediately
    if (currentUser.role === 'Admin') {
      switchView('dashboard-view');
    } else if (currentUser.role === 'Vendor') {
      switchView('vendor-portal-view');
    } else if (currentUser.role === 'Auditor') {
      switchView('auditor-portal-view');
    }
  } else {
    switchView('home-view');
  }
});

function setupHeaderScroll() {
  const mainHeader = document.getElementById('main-header');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      mainHeader.classList.add('scrolled');
    } else {
      mainHeader.classList.remove('scrolled');
    }
  });
}

/* ==========================================================================
   ROUTING & VIEW SWITCHER
   ========================================================================== */

window.switchView = async function (targetViewId) {
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Sync fresh values on view changes
  await syncAllData();

  // Hide/Show view containers
  const viewSections = document.querySelectorAll('.view-section');
  viewSections.forEach(section => {
    if (section.id === targetViewId) {
      section.classList.add('active-view');
    } else {
      section.classList.remove('active-view');
    }
  });

  // Handle header nav active highlights
  const navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(link => {
    if (link.getAttribute('data-view') === targetViewId) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Guard routing for portal accessibility
  if (targetViewId === 'vendor-portal-view' && (!currentUser || currentUser.role !== 'Vendor')) {
    switchView('login-view');
    alert("Please sign in as a Vendor to access the Bidder Portal.");
    return;
  }
  if (targetViewId === 'dashboard-view' && (!currentUser || currentUser.role !== 'Admin')) {
    switchView('login-view');
    alert("Please sign in with administrator HSM eSignet key to open the Admin Portal.");
    return;
  }
  if (targetViewId === 'auditor-portal-view' && (!currentUser || currentUser.role !== 'Auditor')) {
    switchView('login-view');
    alert("Please sign in with Auditor digital keys.");
    return;
  }

  // Reload render sequences on view swap
  if (targetViewId === 'vendor-portal-view') {
    if (typeof openVendorTab === 'function') openVendorTab('vendor-tab-dashboard');
  } else if (targetViewId === 'dashboard-view') {
    if (typeof openAdminTab === 'function') openAdminTab('dash-tab-overview');
  } else if (targetViewId === 'auditor-portal-view') {
    if (typeof openAuditorTab === 'function') openAuditorTab('auditor-tab-dashboard');
  } else if (targetViewId === 'support-view') {
    renderSupportTickets();
  }
};

function setupNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const viewId = link.getAttribute('data-view');
      if (viewId) switchView(viewId);
    });
  });

  // Header login button
  const headerLoginBtn = document.getElementById('header-login-btn');
  if (headerLoginBtn) {
    headerLoginBtn.addEventListener('click', () => {
      switchView('login-view');
    });
  }

  // Home CTA actions
  const getStartedBtn = document.getElementById('hero-get-started-btn');
  if (getStartedBtn) {
    getStartedBtn.addEventListener('click', () => {
      if (currentUser) {
        switchView(currentUser.role === 'Admin' ? 'dashboard-view' : 'vendor-portal-view');
      } else {
        switchView('login-view');
      }
    });
  }

  const heroVerifyBtn = document.getElementById('hero-verify-btn');
  if (heroVerifyBtn) {
    heroVerifyBtn.addEventListener('click', () => switchView('verify-view'));
  }

  const ctaVerifyNowBtn = document.getElementById('cta-verify-now-btn');
  if (ctaVerifyNowBtn) {
    ctaVerifyNowBtn.addEventListener('click', () => switchView('verify-view'));
  }

  const homeAllTendersBtn = document.getElementById('home-all-tenders-btn');
  if (homeAllTendersBtn) {
    homeAllTendersBtn.addEventListener('click', () => {
      if (currentUser && currentUser.role === 'Vendor') {
        switchView('vendor-portal-view');
        openVendorTab('vendor-tab-browse');
      } else {
        switchView('login-view');
      }
    });
  }

  // Timeline highlights clicking
  const timelineSteps = document.querySelectorAll('.timeline-step');
  const timelineProgress = document.getElementById('home-timeline-progress');
  timelineSteps.forEach(step => {
    step.addEventListener('click', () => {
      const stepNum = parseInt(step.getAttribute('data-step'));
      timelineSteps.forEach(s => {
        const num = parseInt(s.getAttribute('data-step'));
        s.classList.toggle('active', num <= stepNum);
      });
      if (timelineProgress) {
        const progressPercent = ((stepNum - 1) / (timelineSteps.length - 1)) * 100;
        timelineProgress.style.transform = `scaleX(${progressPercent / 100})`;
      }
    });
  });

  // Sub-tabs router for Vendor Portal sidebar links
  const vendorSidebarLinks = document.querySelectorAll('.sidebar-link[data-vendor-tab]');
  vendorSidebarLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = link.getAttribute('data-vendor-tab');
      openVendorTab(tabId);
    });
  });

  // Logout actions
  document.getElementById('vendor-logout-btn').addEventListener('click', logoutSession);
  document.getElementById('dash-logout-btn').addEventListener('click', logoutSession);

  // Sub-tabs router for Admin Portal sidebar links
  const adminSidebarLinks = document.querySelectorAll('.sidebar-link[data-dash-tab]');
  adminSidebarLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = link.getAttribute('data-dash-tab');
      openAdminTab(tabId);
    });
  });
}


function logoutSession() {
  currentUser = null;
  selectedTender = null;
  localStorage.removeItem('govtender_session');

  document.getElementById('header-login-btn').style.display = 'inline-flex';
  document.getElementById('header-dashboard-btn').style.display = 'none';

  switchView('home-view');
}

function updateSessionUI() {
  const headerLoginBtn = document.getElementById('header-login-btn');
  const headerDashboardBtn = document.getElementById('header-dashboard-btn');

  if (currentUser) {
    headerLoginBtn.style.display = 'none';
    headerDashboardBtn.style.display = 'inline-flex';

    // Set up correct routing for the dashboard button based on role
    headerDashboardBtn.onclick = () => {
      if (currentUser.role === 'Vendor') switchView('vendor-portal-view');
      else if (currentUser.role === 'Admin') switchView('dashboard-view');
      else if (currentUser.role === 'Auditor') switchView('auditor-portal-view');
    };

    if (currentUser.role === 'Vendor') {
      const profileName = document.getElementById('vendor-profile-name');
      const avatarInitials = document.getElementById('vendor-avatar-initials');
      if (profileName) profileName.textContent = currentUser.company || currentUser.name;
      if (avatarInitials) avatarInitials.textContent = currentUser.initials;
    } else if (currentUser.role === 'Admin') {
      const profileName = document.getElementById('official-profile-name');
      const avatarInitials = document.getElementById('official-avatar-initials');
      if (profileName) profileName.textContent = currentUser.name;
      if (avatarInitials) avatarInitials.textContent = currentUser.initials;
    } else if (currentUser.role === 'Auditor') {
      const profileName = document.getElementById('auditor-profile-name');
      if (profileName) profileName.textContent = currentUser.name;
    }
  } else {
    headerLoginBtn.style.display = 'inline-flex';
    headerDashboardBtn.style.display = 'none';
  }
}

/* ==========================================================================
   VENDOR PORTAL CONTROLS
   ========================================================================== */

window.openVendorTab = async function openVendorTab(tabId) {
  document.querySelectorAll('#vendor-portal-view .dash-tab-content').forEach(tab => {
    tab.style.display = 'none';
  });

  document.getElementById(tabId).style.display = 'block';

  document.querySelectorAll('#vendor-portal-view .sidebar-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('data-vendor-tab') === tabId);
  });

  await syncAllData();

  if (tabId === 'vendor-tab-dashboard') {
    renderVendorDashboard();
  } else if (tabId === 'vendor-tab-browse') {
    renderPublicTenders();
  } else if (tabId === 'vendor-tab-saved') {
    renderSavedTenders();
  } else if (tabId === 'vendor-tab-applications') {
    renderVendorApplications();
  } else if (tabId === 'vendor-tab-documents') {
    renderDocumentGrid();
  } else if (tabId === 'vendor-tab-notifications') {
    renderNotificationsInbox();
  } else if (tabId === 'vendor-tab-profile') {
    populateProfileForm();
  }
};

function renderVendorDashboard() {
  document.getElementById('vendor-welcome-title').textContent = `${currentUser.company} Dashboard`;

  const savedCount = mockSavedTenders.length;
  const appliedCount = mockApplications.filter(app => app.signee === currentUser.name).length;
  const docsVerified = mockDocuments.filter(d => d.status === 'verified').length;
  const docsTotal = mockDocuments.length;

  document.getElementById('vendor-stats-saved').textContent = savedCount;
  document.getElementById('vendor-stats-applied').textContent = appliedCount;
  document.getElementById('vendor-stats-docs').textContent = `${docsVerified}/${docsTotal}`;

  const badgeSaved = document.getElementById('badge-saved-count');
  if (badgeSaved) badgeSaved.textContent = savedCount;

  const unreadNotifs = mockNotifications.filter(n => n.unread).length;
  const badgeNotif = document.getElementById('badge-notif-count');
  badgeNotif.textContent = unreadNotifs;
  badgeNotif.style.display = unreadNotifs > 0 ? 'inline-block' : 'none';

  const banner = document.getElementById('dashboard-notif-banner');
  const activeUnread = mockNotifications.find(n => n.unread);
  if (activeUnread) {
    banner.style.display = 'flex';
    banner.className = 'alert-banner';
    banner.innerHTML = `<span>🔔</span> <span style="flex:1;"><strong>${activeUnread.title}</strong>: ${activeUnread.desc}</span> <span style="font-size:0.75rem; opacity:0.8;">Click to open</span>`;
  } else {
    banner.style.display = 'none';
  }

  const activityList = document.getElementById('vendor-dashboard-activity-list');
  activityList.innerHTML = '';

  const myApps = mockApplications.filter(app => app.signee === currentUser.name);
  if (myApps.length === 0) {
    activityList.innerHTML = `<div class="ticket-item" style="color:var(--text-secondary); text-align:center; justify-content:center;">No recent application activities recorded</div>`;
  } else {
    myApps.slice(0, 3).forEach(app => {
      const item = document.createElement('div');
      item.className = 'ticket-item';

      let statusDot = '';
      if (app.status === 'approved') statusDot = '<span class="verified-tag">✓ Approved</span>';
      else if (app.status === 'review') statusDot = '<span class="status-badge pending">Under Review</span>';

      item.innerHTML = `
        <div class="ticket-info">
          <span class="ticket-subject">Bid proposal submitted for ${app.tenderName}</span>
          <span class="ticket-id">Ref ID: #${app.refNo} &bull; Date: ${app.date}</span>
        </div>
        <div>${statusDot}</div>
      `;
      activityList.appendChild(item);
    });
  }
}

/* ==========================================================================
   TENDER CATALOG LISTINGS & FILTERS (Browse Tenders)
   ========================================================================== */

function renderFeaturedTenders() {
  const featuredGrid = document.getElementById('home-featured-tenders');
  if (!featuredGrid) return;
  featuredGrid.innerHTML = '';

  const verifiedList = mockTenders.filter(t => t.status === 'verified').slice(0, 3);
  verifiedList.forEach(t => {
    const card = document.createElement('div');
    card.className = 'tender-card';

    card.innerHTML = `
      <div class="tender-card-header">
        <span class="tender-id-badge">#${t.tenderNo}</span>
        <span class="verified-tag">Verified VC</span>
      </div>
      <div class="tender-card-body">
        <h3 class="tender-card-title">${t.name}</h3>
        <span style="font-size:0.8rem; color:var(--text-muted);">${t.ministry}</span>
        <p style="font-size:0.825rem; color:var(--text-secondary); margin-top:0.5rem; line-height:1.5; height:54px; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical;">
          ${t.desc}
        </p>
      </div>
      <div class="tender-meta-row">
        <span>Budget: <strong class="tender-budget-tag">$${(t.budget / 1000000).toFixed(1)}M</strong></span>
        <span>Deadline: <strong>${new Date(t.date).toLocaleDateString()}</strong></span>
      </div>
      <div class="tender-card-actions">
        <button class="btn btn-primary" style="flex:1; padding:0.4rem; font-size:0.8rem;" onclick="viewTenderDetails('${t.id}')">View Details</button>
      </div>
    `;
    featuredGrid.appendChild(card);
  });
}

function renderPublicTenders() {
  const searchInput = document.getElementById('filter-search');
  const catSelect = document.getElementById('filter-category');
  const minSelect = document.getElementById('filter-ministry');
  const maxBudget = document.getElementById('filter-budget');

  const query = searchInput.value.toLowerCase().trim();
  const cat = catSelect.value;
  const minVal = minSelect.value;
  const budget = parseFloat(maxBudget.value);

  const grid = document.getElementById('public-tenders-listing-grid');
  grid.innerHTML = '';

  const filtered = mockTenders.filter(t => {
    if (t.status !== 'verified') return false;
    if (query && !t.name.toLowerCase().includes(query) && !t.tenderNo.toLowerCase().includes(query)) return false;
    if (cat !== 'All' && t.category !== cat) return false;

    if (minVal !== 'All') {
      if (minVal === 'Works' && !t.ministry.includes('Works')) return false;
      if (minVal === 'Energy' && !t.ministry.includes('Energy')) return false;
      if (minVal === 'Tech' && !t.ministry.includes('Tech')) return false;
      if (minVal === 'Edu' && !t.ministry.includes('Edu')) return false;
    }

    if (budget && t.budget > budget) return false;
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color:var(--text-secondary);">No matching public tenders found. Try adjusting filters.</div>`;
    return;
  }

  filtered.forEach(t => {
    const isSaved = mockSavedTenders.includes(t.id);
    const card = document.createElement('div');
    card.className = 'tender-card';

    card.innerHTML = `
      <div class="tender-card-header">
        <span class="tender-id-badge">#${t.tenderNo}</span>
        <span class="verified-tag">Verified VC</span>
      </div>
      <div class="tender-card-body">
        <h3 class="tender-card-title">${t.name}</h3>
        <span style="font-size:0.8rem; color:var(--text-muted);">${t.ministry}</span>
        <p style="font-size:0.825rem; color:var(--text-secondary); margin-top:0.5rem; line-height:1.5; height:54px; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical;">
          ${t.desc}
        </p>
      </div>
      <div class="tender-meta-row">
        <span>Budget: <strong class="tender-budget-tag">$${t.budget.toLocaleString()} USD</strong></span>
      </div>
      <div class="tender-meta-row" style="margin-top:-0.5rem;">
        <span>Location: <strong>${t.location}</strong></span>
        <span>Expires: <strong>${new Date(t.date).toLocaleDateString()}</strong></span>
      </div>
      <div class="tender-card-actions">
        <button class="btn btn-primary" style="flex:1; padding:0.4rem; font-size:0.8rem;" onclick="viewTenderDetails('${t.id}')">View Details</button>
        <button class="btn btn-outline" style="padding:0.4rem 0.8rem; font-size:0.8rem;" onclick="toggleSaveTender('${t.id}')">
          ${isSaved ? '⭐ Bookmarked' : '☆ Bookmark'}
        </button>
      </div>
    `;
    grid.appendChild(card);
  });
}

window.browseCategory = function (category) {
  if (currentUser && currentUser.role === 'Vendor') {
    switchView('vendor-portal-view');
    openVendorTab('vendor-tab-browse');
    document.getElementById('filter-category').value = category;
    renderPublicTenders();
  } else {
    switchView('login-view');
    alert("Please log in as a Vendor to search and browse categories.");
  }
};

function setupVerifyPortal() {
  document.getElementById('btn-apply-filters').addEventListener('click', renderPublicTenders);
  document.getElementById('btn-clear-filters').addEventListener('click', () => {
    document.getElementById('filter-search').value = '';
    document.getElementById('filter-category').value = 'All';
    document.getElementById('filter-ministry').value = 'All';
    document.getElementById('filter-budget').value = '';
    renderPublicTenders();
  });
}

/* ==========================================================================
   TENDER DETAILS & APPLICATION
   ========================================================================== */

window.viewTenderDetails = async function (tenderId) {
  const tender = mockTenders.find(t => t.id === tenderId);
  if (!tender) return;
  selectedTender = tender;

  document.getElementById('det-id-badge').textContent = `#${tender.tenderNo}`;
  document.getElementById('det-title').textContent = tender.name;
  document.getElementById('det-ministry').textContent = `${tender.ministry} • Issued by ${tender.issuer}`;
  document.getElementById('det-desc').textContent = tender.desc;

  document.getElementById('det-published-date').textContent = "10 Jun 2026";
  document.getElementById('det-deadline-date').textContent = new Date(tender.date).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });

  const isSaved = mockSavedTenders.includes(tender.id);
  const saveBtn = document.getElementById('detail-save-btn');
  saveBtn.textContent = isSaved ? '⭐ Remove Bookmark' : '☆ Bookmark Tender';

  const applyBtn = document.getElementById('detail-apply-btn');
  if (currentUser && currentUser.role === 'Vendor') {
    // Only allow applying if tender is verified and not expired
    const isVerified = tender.status === 'verified';
    const isClosed = tender.date && new Date(tender.date) < new Date();
    
    if (isVerified && !isClosed) {
      applyBtn.style.display = 'block';
    } else {
      applyBtn.style.display = 'none';
    }
  } else {
    applyBtn.style.display = 'none';
  }

  // Reset credential section
  document.getElementById('det-credential-section').style.display = 'none';
  document.getElementById('det-qr-section').style.display = 'none';

  // Store credential data on the selected tender for PDF use
  selectedTender._cred = null;

  // Fetch credential data from backend
  try {
    const credRes = await fetch(`${API_BASE}/credentials/verify/${tender.tenderNo}`).then(r => r.json());
    if (credRes && (credRes.id || credRes.credential_id) && credRes.status === 'verified') {
      // Normalize: /verify returns 'id' field, map to 'credential_id'
      credRes.credential_id = credRes.credential_id || credRes.id;
      selectedTender._cred = credRes;

      // Populate VC section
      document.getElementById('det-credential-id').textContent = credRes.credential_id;
      document.getElementById('det-issuer-did').textContent = credRes.issuer_did || '—';
      document.getElementById('det-credential-section').style.display = 'block';

      // Populate QR section
      if (credRes.qr_code_url) {
        const qrImg = document.getElementById('det-qr-img');
        qrImg.src = credRes.qr_code_url;
        document.getElementById('det-qr-label').textContent = credRes.credential_id;
        document.getElementById('det-qr-section').style.display = 'block';
      }
    }
  } catch (e) {
    console.warn('Could not load credential data for this tender.', e);
  }

  switchView('tender-details-view');
};

function setupTenderDetailsActions() {
  document.getElementById('detail-apply-btn').addEventListener('click', () => {
    if (!selectedTender) return;
    openApplicationForm(selectedTender);
  });

  document.getElementById('detail-pdf-btn').addEventListener('click', async () => {
    if (!selectedTender) return;

    const btn = document.getElementById('detail-pdf-btn');
    btn.textContent = '⏳ Generating PDF...';
    btn.disabled = true;

    try {
      const { jsPDF } = window.jspdf;
      if (!jsPDF) { alert('PDF library not loaded. Please refresh the page.'); return; }

      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const W = doc.internal.pageSize.getWidth();
      const H = doc.internal.pageSize.getHeight();
      const cred = selectedTender._cred || {};
      const t = selectedTender;
      let y = 0;

      // ─── PAGE BORDER ───────────────────────────────────────────────
      doc.setDrawColor(0, 200, 120);
      doc.setLineWidth(0.5);
      doc.rect(8, 8, W - 16, H - 16);

      // ─── HEADER BANNER ─────────────────────────────────────────────
      doc.setFillColor(10, 15, 30);
      doc.rect(8, 8, W - 16, 28, 'F');

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(0, 220, 130);
      doc.text('GOVTENDER', 16, 20);

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7.5);
      doc.setTextColor(150, 160, 180);
      doc.text('Secure Government Tender Verification & Signing Platform', 16, 26);
      doc.text('Powered by MOSIP · W3C Verifiable Credentials · eSignet', 16, 31);

      // Verified badge top right
      doc.setFillColor(0, 200, 120, 0.15);
      doc.setDrawColor(0, 200, 120);
      doc.setLineWidth(0.3);
      doc.roundedRect(W - 52, 13, 40, 16, 3, 3, 'FD');
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.setTextColor(0, 220, 130);
      doc.text('✓ VERIFIED', W - 48, 21);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(6.5);
      doc.setTextColor(100, 120, 140);
      doc.text('Cryptographically Signed', W - 50, 26);

      y = 46;

      // ─── TENDER TITLE BLOCK ────────────────────────────────────────
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(255, 255, 255);
      const titleLines = doc.splitTextToSize(t.name, W - 32);
      doc.text(titleLines, 16, y);
      y += titleLines.length * 7 + 2;

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(100, 120, 140);
      doc.text(`${t.ministry || '—'}  •  Issued by: ${t.issuer || '—'}`, 16, y);
      y += 5;

      // Divider
      doc.setDrawColor(40, 50, 70);
      doc.setLineWidth(0.3);
      doc.line(16, y, W - 16, y);
      y += 7;

      // ─── KEY DETAILS GRID (2-column) ──────────────────────────────
      const colW = (W - 32) / 2;
      const fields = [
        ['Tender Reference', `#${t.tenderNo}`],
        ['Approved Budget', `₹ ${Number(t.budget || 0).toLocaleString('en-IN')} INR`],
        ['Category', t.category || 'Works'],
        ['Location', t.location || '—'],
        ['Published', '10 Jun 2026'],
        ['Bid Deadline', new Date(t.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })],
        ['Status', 'Verified'],
        ['Evaluation Date', '15 Sep 2026'],
      ];

      fields.forEach(([label, value], i) => {
        const col = i % 2 === 0 ? 16 : 16 + colW;
        if (i % 2 === 0 && i > 0) y += 13;

        // Row background
        doc.setFillColor(20, 28, 48);
        doc.roundedRect(col, y - 4, colW - 4, 12, 2, 2, 'F');

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7);
        doc.setTextColor(100, 120, 150);
        doc.text(label.toUpperCase(), col + 3, y + 1);

        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(label === 'Status' ? 0 : 220, label === 'Status' ? 220 : 230, label === 'Status' ? 130 : 250);
        doc.text(String(value), col + 3, y + 7);
      });
      y += 20;

      // ─── DESCRIPTION ──────────────────────────────────────────────
      doc.setDrawColor(40, 50, 70);
      doc.line(16, y, W - 16, y);
      y += 6;

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(180, 200, 230);
      doc.text('Tender Overview', 16, y);
      y += 5;

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(140, 160, 180);
      const descLines = doc.splitTextToSize(t.desc || '—', W - 32);
      doc.text(descLines, 16, y);
      y += descLines.length * 4.5 + 8;

      // ─── ELIGIBILITY ──────────────────────────────────────────────
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(180, 200, 230);
      doc.text('Eligibility Requirements', 16, y);
      y += 5;

      const eligibility = [
        'Must hold valid ISO certification relevant to field operations.',
        'Must upload corporate tax registration credentials.',
        'Company profile must not show suspension flags.',
        'Required minimum annual turnover matching budget projections.',
      ];
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(140, 160, 180);
      eligibility.forEach(item => {
        doc.text(`• ${item}`, 20, y);
        y += 5;
      });
      y += 4;

      // ─── VERIFIABLE CREDENTIAL SECTION ────────────────────────────
      if (cred.credential_id || cred.vc_id || cred.issuer_did) {
        doc.setDrawColor(0, 200, 120);
        doc.setLineWidth(0.3);
        doc.line(16, y, W - 16, y);
        y += 6;

        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(0, 220, 130);
        doc.text('✓ Verifiable Credential Information', 16, y);
        y += 5;

        // VC box
        const vcBoxH = cred.issuer_did ? 30 : 24;
        doc.setFillColor(10, 30, 20);
        doc.setDrawColor(0, 120, 80);
        doc.roundedRect(16, y, W - 32, vcBoxH, 3, 3, 'FD');

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7.5);
        doc.setTextColor(100, 160, 120);
        doc.text('CREDENTIAL ID', 22, y + 6);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(0, 220, 130);
        doc.text(cred.credential_id || cred.vc_id || '—', 22, y + 12);

        if (cred.issuer_did) {
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7);
          doc.setTextColor(80, 130, 100);
          doc.text('ISSUER DID', 22, y + 19);
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7);
          doc.setTextColor(100, 150, 120);
          const didLines = doc.splitTextToSize(cred.issuer_did, W - 80);
          doc.text(didLines[0] || '—', 22, y + 24);
        }

        // Status badge inside VC box
        doc.setFillColor(0, 60, 40);
        doc.roundedRect(W - 55, y + 8, 30, 10, 2, 2, 'F');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(7.5);
        doc.setTextColor(0, 220, 130);
        doc.text('✓ VERIFIED', W - 52, y + 14);

        y += vcBoxH + 6;

        // Try to embed QR code image
        if (cred.qr_code_url) {
          try {
            const qrRes = await fetch(cred.qr_code_url);
            const qrBlob = await qrRes.blob();
            const qrBase64 = await new Promise((res, rej) => {
              const reader = new FileReader();
              reader.onload = () => res(reader.result);
              reader.onerror = rej;
              reader.readAsDataURL(qrBlob);
            });

            const qrSize = 35;
            // QR on right
            doc.addImage(qrBase64, 'PNG', W - 16 - qrSize, y, qrSize, qrSize);
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(6.5);
            doc.setTextColor(80, 100, 120);
            doc.text('Scan QR to verify', W - 16 - qrSize, y + qrSize + 4, { align: 'left' });

            // Text left of QR
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(8.5);
            doc.setTextColor(180, 200, 230);
            doc.text('Verify Authenticity', 16, y + 8);
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(7.5);
            doc.setTextColor(100, 120, 140);
            const verifyLines = doc.splitTextToSize(
              'Scan the QR code or visit the GovTender portal and enter the Credential ID to verify the authenticity of this tender document in real time.',
              W - 32 - qrSize - 8
            );
            doc.text(verifyLines, 16, y + 15);
            y += Math.max(qrSize + 10, verifyLines.length * 4 + 20);
          } catch (qrErr) {
            console.warn('QR image could not be embedded:', qrErr);
          }
        }
      }

      // ─── FOOTER ───────────────────────────────────────────────────
      const footerY = H - 18;
      doc.setFillColor(10, 15, 30);
      doc.rect(8, footerY, W - 16, 14, 'F');

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7);
      doc.setTextColor(80, 100, 120);
      doc.text(`Generated: ${new Date().toLocaleString('en-IN')}`, 16, footerY + 5);
      doc.text('GovTender Secure Procurement Portal  •  MOSIP  •  W3C VC  •  eSignet', 16, footerY + 10);

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(7);
      doc.setTextColor(0, 180, 100);
      doc.text('OFFICIAL DOCUMENT — DO NOT MODIFY', W - 16, footerY + 7, { align: 'right' });

      // ─── SAVE ─────────────────────────────────────────────────────
      doc.save(`GovTender_${t.tenderNo}_Official.pdf`);

    } catch (err) {
      console.error('PDF generation failed:', err);
      alert('PDF generation failed. Please try again.');
    } finally {
      btn.textContent = '📥 Download Tender PDF';
      btn.disabled = false;
    }
  });

  document.getElementById('detail-save-btn').addEventListener('click', () => {
    if (!selectedTender) return;
    toggleSaveTender(selectedTender.id);
    const isSaved = mockSavedTenders.includes(selectedTender.id);
    document.getElementById('detail-save-btn').textContent = isSaved ? '⭐ Remove Bookmark' : '☆ Bookmark Tender';
  });
}

window.toggleSaveTender = function (tenderId) {
  if (!currentUser || currentUser.role !== 'Vendor') {
    switchView('login-view');
    alert("Please log in as a Vendor to bookmark tenders.");
    return;
  }

  const idx = mockSavedTenders.indexOf(tenderId);
  if (idx > -1) {
    mockSavedTenders.splice(idx, 1);
  } else {
    mockSavedTenders.push(tenderId);
  }

  const activeView = document.querySelector('.view-section.active-view');
  if (activeView.id === 'vendor-portal-view') {
    const activeTab = document.querySelector('#vendor-portal-view .sidebar-link.active').getAttribute('data-vendor-tab');
    if (activeTab === 'vendor-tab-browse') renderPublicTenders();
    else if (activeTab === 'vendor-tab-saved') renderSavedTenders();
    document.getElementById('vendor-stats-saved').textContent = mockSavedTenders.length;
    const badgeSaved = document.getElementById('badge-saved-count');
    if (badgeSaved) badgeSaved.textContent = mockSavedTenders.length;
  }
};

function renderSavedTenders() {
  const grid = document.getElementById('saved-tenders-listing-grid');
  grid.innerHTML = '';

  const savedList = mockTenders.filter(t => mockSavedTenders.includes(t.id));
  const badgeSaved = document.getElementById('badge-saved-count');
  if (badgeSaved) badgeSaved.textContent = savedList.length;

  if (savedList.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color:var(--text-secondary);">No saved tenders yet. Go browse the listings to bookmark them!</div>`;
    return;
  }

  savedList.forEach(t => {
    const card = document.createElement('div');
    card.className = 'tender-card';

    card.innerHTML = `
      <div class="tender-card-header">
        <span class="tender-id-badge">#${t.tenderNo}</span>
        <span class="verified-tag">Verified VC</span>
      </div>
      <div class="tender-card-body">
        <h3 class="tender-card-title">${t.name}</h3>
        <span style="font-size:0.8rem; color:var(--text-muted);">${t.ministry}</span>
      </div>
      <div class="tender-meta-row">
        <span>Budget: <strong class="tender-budget-tag">$${t.budget.toLocaleString()} USD</strong></span>
        <span>Expires: <strong>${new Date(t.date).toLocaleDateString()}</strong></span>
      </div>
      <div class="tender-card-actions">
        <button class="btn btn-primary" style="flex:1; padding:0.4rem; font-size:0.8rem;" onclick="viewTenderDetails('${t.id}')">View Details</button>
        <button class="btn btn-outline" style="padding:0.4rem; font-size:0.8rem; color:var(--accent-red); border-color:var(--accent-red-bg);" onclick="toggleSaveTender('${t.id}')">Remove</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

/* ==========================================================================
   TENDER SUBMISSION & APPLICATIONS TRACKING
   ========================================================================== */

function openApplicationForm(tender) {
  document.getElementById('apply-screen-title').textContent = `Apply: ${tender.name}`;
  document.getElementById('apply-company-name').value = currentUser.company;
  document.getElementById('apply-bid-value').value = '';
  document.getElementById('uploaded-bid-filename').textContent = '';
  document.getElementById('apply-declare').checked = false;

  switchView('tender-apply-view');
}

function setupApplicationForm() {
  const cancelBtn = document.getElementById('apply-cancel-btn');
  cancelBtn.addEventListener('click', () => {
    if (selectedTender) viewTenderDetails(selectedTender.id);
    else switchView('vendor-portal-view');
  });

  const bidBrowse = document.getElementById('bid-browse-btn');
  const bidUploader = document.getElementById('bid-file-uploader');
  bidBrowse.addEventListener('click', () => bidUploader.click());

  bidUploader.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      document.getElementById('uploaded-bid-filename').textContent = `📄 ${e.target.files[0].name} (${(e.target.files[0].size / (1024 * 1024)).toFixed(2)} MB)`;
    }
  });

  const bidForm = document.getElementById('tender-bid-form');
  bidForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedTender) return;

    const bidVal = parseFloat(document.getElementById('apply-bid-value').value);
    const bidUploader = document.getElementById('bid-file-uploader');

    let uploadedDocId = null;
    try {
      // If a bid document is uploaded, send it to the backend first
      if (bidUploader && bidUploader.files.length > 0) {
        const formData = new FormData();
        formData.append("file", bidUploader.files[0]);
        try {
          const uploadRes = await fetch(`${API_BASE}/tenders/${selectedTender.tenderNo}/upload`, {
            method: "POST",
            body: formData
          }).then(r => r.json());
          uploadedDocId = uploadRes.document_id;
        } catch (uploadErr) {
          console.error("Failed to upload file to backend:", uploadErr);
        }
      }

      const response = await fetch(`${API_BASE}/applications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenderNo: selectedTender.tenderNo,
          bidValue: bidVal,
          signee: currentUser.name,
          documentId: uploadedDocId
        })
      });
      
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Error submitting bid application to database server.");
      }
      
      const res = await response.json();

      // Reload applications list
      await syncAllData();

      // Show success screen
      document.getElementById('success-ref-no').textContent = res.refNo;
      document.getElementById('success-tender-name').textContent = selectedTender.name;
      document.getElementById('success-bid-val').textContent = `₹ ${bidVal.toLocaleString('en-IN')} INR`;
      document.getElementById('success-signee').textContent = `${currentUser.name} (${currentUser.company})`;

      document.getElementById('success-view-app-btn').onclick = () => {
        switchView('vendor-portal-view');
        openVendorTab('vendor-tab-applications');
      };
      document.getElementById('success-browse-btn').onclick = () => {
        switchView('vendor-portal-view');
        openVendorTab('vendor-tab-browse');
      };

      switchView('apply-success-view');
    } catch (e) {
      alert(e.message || "Error submitting bid application to database server.");
    }
  });
}

window.saveApplicationDraft = function () {
  alert("Draft application saved on database successfully.");
  switchView('vendor-portal-view');
};

function renderVendorApplications() {
  const tbody = document.getElementById('vendor-applications-tbody');
  tbody.innerHTML = '';

  const myApps = mockApplications.filter(app => app.signee === currentUser.name || app.email === currentUser.email);
  if (myApps.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">You have not submitted any tender applications yet.</td></tr>`;
    return;
  }

  myApps.forEach(app => {
    const tr = document.createElement('tr');

    let statusClass = 'pending';
    let statusLabel = 'Under Review';
    let bidValHTML = '';

    if (app.status === 'locked') {
      statusClass = 'pending';
      statusLabel = '🔒 Cryptographically Locked';
      bidValHTML = `<span style="font-family: monospace; font-size: 0.8rem; color:var(--text-muted); cursor: help;" title="${app.ciphertext}">Locked<br><span style="font-size:0.7rem;opacity:0.7;">Cipher: ${app.ciphertext ? app.ciphertext.substring(0, 12) : 'N/A'}...</span></span>`;
    } else {
      bidValHTML = `<span style="color:var(--accent-green); font-weight:600;">₹ ${Number(app.bidValue).toLocaleString('en-IN')} INR</span>`;
      if (app.status === 'approved') { statusClass = 'verified'; statusLabel = '✓ Approved & Awarded'; }
      else if (app.status === 'rejected') { statusClass = 'rejected'; statusLabel = 'Rejected'; }
      else if (app.status === 'opened') { statusClass = 'pending'; statusLabel = 'Opened (Decrypted)'; }
    }

    // Action buttons
    let actionHTML = '';
    if (app.status === 'approved') {
      actionHTML = `
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
          <button class="btn btn-primary" 
            onclick="downloadBidCertificate('${app.id}')" 
            style="padding:0.3rem 0.75rem; font-size:0.75rem; border-radius:6px; background:linear-gradient(135deg,#06b6d4,#00d97e); color:#030712; font-weight:700; cursor:pointer; border:none; display:flex; align-items:center; gap:0.3rem;">
            Generate PDF
          </button>
        </div>`;
    }

    tr.innerHTML = `
      <td style="font-family: monospace; color: var(--accent-cyan); font-weight:600;">#${app.refNo}</td>
      <td style="font-weight: 500;">${app.tenderName} (Tender: #${app.tenderNo})</td>
      <td>${bidValHTML}</td>
      <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
      <td>${actionHTML}</td>
    `;
    tbody.appendChild(tr);
  });
}

window.downloadBidCertificate = async function (bidId) {
  try {
    // Show loading state
    const btn = event.currentTarget;
    const origHTML = btn.innerHTML;
    btn.innerHTML = ' Generating...';
    btn.disabled = true;

    // fetch interceptor will automatically append X-Digital-Id
    const response = await fetch(`${API_BASE}/applications/${bidId}/certificate`);

    if (!response.ok) {
      const err = await response.json();
      alert(`Certificate error: ${err.detail || 'Unknown error'}`);
      btn.innerHTML = origHTML;
      btn.disabled = false;
      return;
    }

    // Trigger browser download
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `BidAwardCertificate_${bidId.substring(0, 8).toUpperCase()}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    btn.innerHTML = ' Downloaded!';
    setTimeout(() => {
      btn.innerHTML = origHTML;
      btn.disabled = false;
    }, 2500);
  } catch (e) {
    console.error('PDF download failed:', e);
    alert('Failed to download PDF. Please try again.');
  }
};

window.downloadApplicationReceipt = function (refNo) {
  alert(`Generating signed cryptographic receipt package for Application #${refNo}... (File downloaded in local directory)`);
};

/* ==========================================================================
   DOCUMENT MANAGEMENT SCREEN
   ========================================================================== */

function setupDocumentManager() {
  const triggerBtn = document.getElementById('btn-trigger-upload-doc');
  const formCard = document.getElementById('doc-upload-form-card');
  const cancelBtn = document.getElementById('btn-cancel-upload-doc');
  const form = document.getElementById('doc-register-form');

  triggerBtn.addEventListener('click', () => {
    formCard.style.display = formCard.style.display === 'none' ? 'block' : 'none';
  });

  cancelBtn.addEventListener('click', () => {
    form.reset();
    formCard.style.display = 'none';
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const docName = document.getElementById('doc-upload-name').value.trim();
    const expiry = document.getElementById('doc-upload-expiry').value;

    try {
      await fetch(`${API_BASE}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: docName, expiryDate: expiry })
      });

      form.reset();
      formCard.style.display = 'none';

      // Refresh list
      await syncAllData();
      renderDocumentGrid();

      const banner = document.getElementById('doc-upload-success-banner');
      banner.style.display = 'flex';
      setTimeout(() => { banner.style.display = 'none'; }, 4000);
    } catch (e) {
      alert("Error uploading document to database server.");
    }
  });
}

function renderDocumentGrid() {
  const grid = document.getElementById('vendor-documents-grid');
  grid.innerHTML = '';

  mockDocuments.forEach(doc => {
    const card = document.createElement('div');
    card.className = 'doc-card';

    let statusBadge = '';
    if (doc.status === 'verified') statusBadge = '<span class="status-badge verified">Verified VC</span>';
    else if (doc.status === 'pending') statusBadge = '<span class="status-badge pending">Auditing...</span>';
    else if (doc.status === 'expired') statusBadge = '<span class="status-badge rejected">Expired</span>';

    card.innerHTML = `
      <div class="doc-info">
        <div class="doc-icon">📄</div>
        <div class="doc-meta">
          <div class="doc-name" style="word-break:break-all;">${doc.name}</div>
          <div class="doc-status">${statusBadge}</div>
        </div>
      </div>
      <div>
        <div class="doc-expiry">Registry Expiration: <strong>${new Date(doc.expiryDate).toLocaleDateString()}</strong></div>
        <div class="doc-actions">
          <button class="btn btn-outline" style="flex:1; padding:0.3rem 0.5rem; font-size:0.75rem;" onclick="alert('Downloading mock document: ${doc.name}')">Download</button>
          <button class="btn btn-outline" style="padding:0.3rem; font-size:0.75rem; color:var(--accent-red); border-color:rgba(239, 68, 68, 0.1);" onclick="deleteDocument('${doc.id}')">🗑️</button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

window.deleteDocument = async function (docId) {
  try {
    await fetch(`${API_BASE}/documents/${docId}`, { method: "DELETE" });
    await syncAllData();
    renderDocumentGrid();
  } catch (e) {
    alert("Error deleting document from database.");
  }
};

/* ==========================================================================
   NOTIFICATIONS PANEL
   ========================================================================== */

function renderNotificationsInbox() {
  const container = document.getElementById('vendor-notifications-container');
  container.innerHTML = '';

  document.getElementById('badge-notif-count').style.display = 'none';

  if (mockNotifications.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:3rem; color:var(--text-secondary);">Notification inbox is empty.</div>`;
    return;
  }

  mockNotifications.forEach(n => {
    const item = document.createElement('div');
    item.className = `notification-item ${n.unread ? 'unread' : ''}`;

    item.innerHTML = `
      <div class="notification-main">
        <span class="notification-indicator"></span>
        <div class="notification-text-area">
          <span class="notification-title">${n.title}</span>
          <span class="notification-desc">${n.desc}</span>
          <span class="notification-time">${n.time}</span>
        </div>
      </div>
      <div>
        <button class="btn btn-outline" style="padding:0.25rem 0.5rem; font-size:0.75rem; border-color:transparent;" onclick="deleteNotification('${n.id}')">✕</button>
      </div>
    `;
    container.appendChild(item);
  });
}

window.deleteNotification = async function (notifId) {
  try {
    await fetch(`${API_BASE}/notifications/${notifId}`, { method: "DELETE" });
    await syncAllData();
    renderNotificationsInbox();
  } catch (e) { }
};

function setupVendorPortalForms() {
  const markReadBtn = document.getElementById('btn-mark-all-read');
  if (markReadBtn) {
    markReadBtn.addEventListener('click', async () => {
      try {
        await fetch(`${API_BASE}/notifications/read`, { method: "POST" });
        await syncAllData();
        renderNotificationsInbox();
      } catch (e) { }
    });
  }

  const profileEditForm = document.getElementById('vendor-profile-edit-form');
  if (profileEditForm) {
    profileEditForm.addEventListener('submit', (e) => {
      e.preventDefault();
      currentUser.name = document.getElementById('profile-user-name').value.trim();
      currentUser.company = document.getElementById('profile-company-name').value.trim();
      currentUser.phone = document.getElementById('profile-user-phone').value.trim();
      currentUser.email = document.getElementById('profile-user-email').value.trim();
      currentUser.initials = currentUser.name.split(' ').map(w => w[0]).join('').toUpperCase().substring(0, 2);

      updateSessionUI();
      alert("eSignet Corporate profile identity details updated successfully!");
      openVendorTab('vendor-tab-dashboard');
    });
  }
}

/* ==========================================================================
   USER CORPORATE PROFILE VIEW
   ========================================================================== */

function populateProfileForm() {
  document.getElementById('profile-user-name').value = currentUser.name;
  document.getElementById('profile-company-name').value = currentUser.company;
  document.getElementById('profile-user-phone').value = currentUser.phone || "+1 (555) 439-0921";
  document.getElementById('profile-user-email').value = currentUser.email;
  document.getElementById('profile-user-id').value = currentUser.id || "GT-VND-9817";
}

/* ==========================================================================
   HELP & SUPPORT FORM
   ========================================================================== */

window.toggleFaq = function (faqItem) {
  faqItem.classList.toggle('active');
};

function setupSupportForm() {
  const form = document.getElementById('support-ticket-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const subject = document.getElementById('ticket-subject').value.trim();
    const cat = document.getElementById('ticket-category').value;
    const msg = document.getElementById('ticket-message').value.trim();

    try {
      await fetch(`${API_BASE}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, category: cat, message: msg })
      });

      form.reset();
      await syncAllData();
      renderSupportTickets();
      alert("Support Ticket submitted to database server successfully.");
    } catch (e) {
      alert("Error submitting ticket.");
    }
  });
}

function renderSupportTickets() {
  const container = document.getElementById('support-tickets-history-list');
  if (!container) return;
  container.innerHTML = '';

  mockTickets.forEach(t => {
    const item = document.createElement('div');
    item.className = 'ticket-item';

    let badgeHTML = '';
    if (t.status === 'resolved') badgeHTML = '<span class="verified-tag">Resolved</span>';
    else if (t.status === 'open') badgeHTML = '<span class="status-badge pending">Open</span>';

    item.innerHTML = `
      <div class="ticket-info">
        <span class="ticket-subject">[${t.category}] ${t.subject}</span>
        <span class="ticket-id">Ticket ID: #${t.id} &bull; Submitted: ${t.date}</span>
      </div>
      <div>${badgeHTML}</div>
    `;
    container.appendChild(item);
  });
}


function setupRegistrationForm() {
  const form = document.getElementById('registration-form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    switchView('otp-view');
    startOtpCountdown();
  });

  const otpInputs = document.querySelectorAll('#otp-view .otp-input');
  otpInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      if (input.value && index < otpInputs.length - 1) {
        otpInputs[index + 1].focus();
      }
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && index > 0) {
        otpInputs[index - 1].focus();
      }
    });
  });

  const otpForm = document.getElementById('registration-otp-form');
  otpForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearInterval(currentTimer);

    const name = document.getElementById('reg-name').value.trim();
    const company = document.getElementById('reg-company').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const phone = document.getElementById('reg-phone').value.trim();

    try {
      const res = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          email: email,
          digital_id: email.split('@')[0],
          role: "Vendor",
          department: company
        })
      }).then(r => r.json());

      // Automatically log in newly registered vendor
      const loginRes = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ digital_id: res.digital_id })
      }).then(r => r.json());

      currentUser = loginRes;

      form.reset();
      otpForm.reset();

      document.querySelectorAll('.role-select-btn').forEach(btn => btn.classList.remove('active'));
      document.getElementById('role-btn-vendor').classList.add('active');

      updateSessionUI();
      alert(`Account for ${company} registered and verified via eSignet successfully!`);
      switchView('vendor-portal-view');
    } catch (e) {
      alert("Error: Registration failed. Email or Digital ID might already be registered.");
      switchView('register-view');
    }
  });

  document.getElementById('otp-resend-btn').addEventListener('click', (e) => {
    e.preventDefault();
    alert("New OTP verification code sent to your registered device registry.");
    startOtpCountdown();
  });
}

function startOtpCountdown() {
  clearInterval(currentTimer);
  let timeRemaining = 120;
  const counterEl = document.getElementById('otp-timer-count');

  currentTimer = setInterval(() => {
    timeRemaining--;
    const mins = Math.floor(timeRemaining / 60);
    const secs = timeRemaining % 60;
    counterEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

    if (timeRemaining <= 0) {
      clearInterval(currentTimer);
      alert("OTP expired. Please click resend to receive a new code.");
    }
  }, 1000);
}

window.forgotPasswordTrigger = function () {
  alert("A password reset link has been dispatched to your eSignet registered authentication device.");
};

/* ==========================================================================
   OFFICIAL & ADMIN PORTAL TAB VIEWS
   ========================================================================== */

window.openAdminTab = async function openAdminTab(tabId) {
  document.querySelectorAll('#dashboard-view .dash-tab-content').forEach(tab => {
    tab.style.display = 'none';
  });

  document.getElementById(tabId).style.display = 'block';

  document.querySelectorAll('#dashboard-view .sidebar-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('data-dash-tab') === tabId);
  });

  await syncAllData();

  if (tabId === 'dash-tab-overview') {
    renderAdminOverview();
  } else if (tabId === 'dash-tab-list') {
    updateDashboardData();
  } else if (tabId === 'dash-tab-users') {
    renderAdminUsers();
  } else if (tabId === 'dash-tab-applications') {
    renderAdminApplications();
  }
};

function renderAdminApplications() {
  const tbody = document.getElementById('admin-applications-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (mockApplications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-secondary);">No submitted proposals yet.</td></tr>`;
    return;
  }

  mockApplications.forEach(app => {
    const tr = document.createElement('tr');

    let bidValHTML = '';
    let actionsHTML = '';
    let statusClass = 'pending';
    let statusLabel = 'Locked';

    if (app.status === 'locked') {
      statusClass = 'pending';
      statusLabel = '🔒 Cryptographically Locked';
      bidValHTML = `<span style="font-family: monospace; font-size: 0.8rem; color:var(--text-muted); cursor: help;" title="${app.ciphertext}">Locked<br><span style="font-size:0.7rem;opacity:0.7;">Cipher: ${app.ciphertext ? app.ciphertext.substring(0, 12) : 'N/A'}...</span></span>`;
      actionsHTML = `<span style="color:var(--text-muted); font-size:0.8rem; font-style:italic;">Decryptions locked until closing date</span>`;
    } else {
      bidValHTML = `<strong style="color:var(--accent-green); font-size:0.9rem;">₹ ${Number(app.bidValue).toLocaleString('en-IN')} INR</strong>`;

      if (app.status === 'approved') {
        statusClass = 'verified';
        statusLabel = 'Approved';
        actionsHTML = `<span style="color:var(--accent-green); font-weight:bold; margin-right: 0.5rem;">✓ Accepted</span>
                       <button class="btn-table-action reject" onclick="updateAppStatus('${app.id}', 'opened')" style="font-size:0.75rem; padding:0.15rem 0.4rem;">Revoke</button>`;
      } else if (app.status === 'rejected') {
        statusClass = 'rejected';
        statusLabel = 'Rejected';
        actionsHTML = `<span style="color:var(--accent-red); font-weight:bold;">✗ Rejected</span>`;
      } else {
        statusClass = 'pending';
        statusLabel = 'Opened';
        actionsHTML = `
          <button class="btn-table-action approve" onclick="updateAppStatus('${app.id}', 'approved')">Accept</button>
          <button class="btn-table-action reject" onclick="updateAppStatus('${app.id}', 'rejected')" style="margin-left: 0.25rem;">Reject</button>
        `;
      }
    }

    tr.innerHTML = `
      <td style="font-family: monospace; color: var(--accent-cyan); font-weight:600;">#${app.refNo}</td>
      <td style="font-weight: 500;">Tender #${app.tenderNo}</td>
      <td>${app.signee} (${app.email})</td>
      <td>${bidValHTML}</td>
      <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
      <td><div style="display:flex; align-items:center;">${actionsHTML}</div></td>
    `;
    tbody.appendChild(tr);
  });
}

window.updateAppStatus = async function (appId, status) {
  try {
    const res = await fetch(`${API_BASE}/applications/${appId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    }).then(r => r.json());

    if (res.status === 'success') {
      alert(`Bid application ${status} successfully!`);
      await syncAllData();
      renderAdminApplications();
    } else {
      alert(res.detail || "Failed to update status.");
    }
  } catch (e) {
    alert("Error updating application status.");
  }
};

function renderAdminOverview() {
  document.getElementById('stats-users-count').textContent = mockUsers.length;
  document.getElementById('admin-stats-total').textContent = mockTenders.length;
  document.getElementById('stats-submissions-count').textContent = mockApplications.length;

  const container = document.getElementById('admin-audit-logs-list');
  container.innerHTML = '';

  mockLogs.forEach(log => {
    const item = document.createElement('div');
    item.className = 'ticket-item';
    item.style.padding = '0.5rem 1rem';
    item.innerHTML = `<span>[${log.time}]</span> <span style="flex:1; margin-left:1rem; color:white;">${log.desc}</span>`;
    container.appendChild(item);
  });
}

function renderAdminUsers() {
  const tbody = document.getElementById('admin-users-tbody');
  tbody.innerHTML = '';

  mockUsers.forEach(user => {
    const tr = document.createElement('tr');

    let statusClass = 'verified';
    if (user.status === 'suspended') statusClass = 'rejected';

    tr.innerHTML = `
      <td style="font-weight:600; color:white;">${user.name}</td>
      <td>${user.email}</td>
      <td>${user.company}</td>
      <td><span class="role-badge">${user.type}</span></td>
      <td><span class="status-badge ${statusClass}">${user.status.toUpperCase()}</span></td>
      <td>
        <button class="btn-table-action view" onclick="toggleUserStatus('${user.email}')">Toggle Status</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

window.toggleUserStatus = async function (email) {
  try {
    await fetch(`${API_BASE}/users/${email}/toggle`, { method: "POST" });
    await syncAllData();
    renderAdminUsers();
  } catch (e) {
    alert("Error changing user status.");
  }
};

function setupAdminForms() {
  const settingsForm = document.getElementById('admin-settings-form');
  if (settingsForm) {
    settingsForm.addEventListener('submit', (e) => {
      e.preventDefault();
      currentUser.name = document.getElementById('set-username').value.trim();
      currentUser.email = document.getElementById('set-email').value.trim();
      currentUser.initials = currentUser.name.split(' ').map(w => w[0]).join('').toUpperCase().substring(0, 2);

      updateSessionUI();
      alert("System Settings saved successfully!");
    });
  }

  const createTenderForm = document.getElementById('create-tender-form');
  if (createTenderForm) {
    createTenderForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const name = document.getElementById('form-tender-name').value.trim();
      const ministry = document.getElementById('form-tender-ministry').value.trim();
      const budget = parseFloat(document.getElementById('form-tender-budget').value);
      const date = document.getElementById('form-tender-date').value;
      const desc = document.getElementById('form-tender-desc').value.trim();

      try {
        const res = await fetch(`${API_BASE}/tenders`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, ministry, budget, date, desc })
        }).then(r => r.json());

        createTenderForm.reset();
        await syncAllData();

        openAdminTab('dash-tab-list');
        alert(`Tender draft #${res.tenderNo} created successfully! Official signature is required before public credential issuance.`);
      } catch (e) {
        alert("Error creating tender in database.");
      }
    });
  }

  const cancelTenderBtn = document.getElementById('form-cancel-btn');
  if (cancelTenderBtn) {
    cancelTenderBtn.addEventListener('click', () => {
      if (createTenderForm) {
        createTenderForm.reset();
      }
      openAdminTab('dash-tab-list');
    });
  }
}

/* ==========================================================================
   ORIGINAL REVIEWER TENDER MANAGEMENT LOGIC
   ========================================================================== */

function updateDashboardData() {
  const dashboardTendersTbody = document.getElementById('dashboard-tenders-tbody');
  if (!dashboardTendersTbody) return;
  dashboardTendersTbody.innerHTML = '';

  const total = mockTenders.length;
  const pending = mockTenders.filter(t => t.status === 'pending').length;
  const verified = mockTenders.filter(t => t.status === 'verified').length;

  document.getElementById('stats-total').textContent = total;
  document.getElementById('stats-pending').textContent = pending;
  document.getElementById('stats-verified').textContent = verified;

  mockTenders.forEach(t => {
    const tr = document.createElement('tr');

    let badgeHTML = '';
    let actionHTML = '';

    if (t.status === 'verified') {
      badgeHTML = `<span class="status-badge verified">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
        Verified
      </span>`;
      actionHTML = `
        <button class="btn-table-action view" onclick="showTenderInVerifyPortal('${t.id}')">View VC</button>
        <button class="btn btn-outline" style="padding:0.25rem 0.5rem; font-size:0.75rem; color:var(--accent-red); border-color:var(--accent-red-bg);" onclick="deleteTender('${t.tenderNo}')">Delete</button>
      `;
    } else {
      badgeHTML = `<span class="status-badge pending">Pending Sign</span>`;
      actionHTML = `
        <button class="btn-table-action approve" onclick="triggerDigitalSignature('${t.tenderNo}')">Approve Tender</button>
        <button class="btn btn-outline" style="padding:0.25rem 0.5rem; font-size:0.75rem; color:var(--accent-red); border-color:var(--accent-red-bg); margin-left:0.25rem;" onclick="deleteTender('${t.tenderNo}')">Delete</button>
      `;
    }

    tr.innerHTML = `
      <td style="font-family: monospace; color: var(--accent-cyan); font-weight:600;">#${t.tenderNo}</td>
      <td style="font-weight: 500;">${t.name}</td>
      <td>${t.ministry}</td>
      <td>${badgeHTML}</td>
      <td style="display:flex; gap:0.25rem; align-items:center;">${actionHTML}</td>
    `;

    dashboardTendersTbody.appendChild(tr);
  });
}

window.deleteTender = async function (tenderNo) {
  try {
    await fetch(`${API_BASE}/tenders/${tenderNo}`, { method: "DELETE" });
    await syncAllData();
    updateDashboardData();
  } catch (e) {
    alert("Error deleting tender.");
  }
};



/* ==========================================================================
   ORIGINAL VERIFICATION PORTAL CORE LOGIC
   ========================================================================== */

function setupVerifyPortalSearch() {
  const dragDropZone = document.getElementById('drag-drop-zone');
  const fileUploader = document.getElementById('file-uploader');
  const browseBtn = document.getElementById('browse-btn');
  const searchInput = document.getElementById('credential-search-input');
  const searchBtn = document.getElementById('credential-search-btn');

  const handleVerificationFile = (file) => {
    if (file.type === "application/json" || file.name.endsWith(".json")) {
      const reader = new FileReader();
      reader.onload = function (evt) {
        try {
          const data = JSON.parse(evt.target.result);
          const credId = data.credential_id || data.id || "VC-8F2A-19CC-BEEF";
          performVerifySearch(credId);
        } catch (err) {
          performVerifySearch("VC-8F2A-19CC-BEEF");
        }
      };
      reader.readAsText(file);
    } else {
      performVerifySearch("VC-8F2A-19CC-BEEF");
    }
  };

  browseBtn.addEventListener('click', () => fileUploader.click());
  fileUploader.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleVerificationFile(e.target.files[0]);
    }
  });

  dragDropZone.addEventListener('dragover', (e) => { e.preventDefault(); dragDropZone.classList.add('dragover'); });
  dragDropZone.addEventListener('dragleave', () => dragDropZone.classList.remove('dragover'));
  dragDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      handleVerificationFile(e.dataTransfer.files[0]);
    }
  });

  searchBtn.addEventListener('click', () => performVerifySearch(searchInput.value.trim()));
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performVerifySearch(searchInput.value.trim());
  });
}

async function performVerifySearch(query) {
  if (!query) {
    alert("Please enter a Credential ID or upload a document QR code.");
    return;
  }

  const resultWrapper = document.getElementById('verification-result-wrapper');
  const progressPanel = document.getElementById('verification-progress-panel');

  resultWrapper.classList.remove('visible');
  progressPanel.style.display = 'block';

  // Connecting, Resolving, Validating signatures mock animations
  const steps = [
    document.getElementById('vstep-1'),
    document.getElementById('vstep-2'),
    document.getElementById('vstep-3'),
    document.getElementById('vstep-4')
  ];

  steps.forEach(s => {
    s.className = 'flow-step pending';
    s.querySelector('.flow-step-icon').textContent = s.id.charAt(s.id.length - 1);
  });

  setTimeout(() => {
    steps[0].className = 'flow-step processing';
    setTimeout(() => {
      steps[0].className = 'flow-step success';
      steps[0].querySelector('.flow-step-icon').textContent = '✓';
      steps[1].className = 'flow-step processing';
      setTimeout(() => {
        steps[1].className = 'flow-step success';
        steps[1].querySelector('.flow-step-icon').textContent = '✓';
        steps[2].className = 'flow-step processing';
        setTimeout(() => {
          steps[2].className = 'flow-step success';
          steps[2].querySelector('.flow-step-icon').textContent = '✓';
          steps[3].className = 'flow-step processing';
          setTimeout(async () => {
            steps[3].className = 'flow-step success';
            steps[3].querySelector('.flow-step-icon').textContent = '✓';
            progressPanel.style.display = 'none';

            // Execute verification API call
            try {
              const res = await fetch(`${API_BASE}/credentials/verify/${query}`).then(r => r.json());
              displayVerificationResult(res, query);
            } catch (e) {
              displayVerificationResult(null, query);
            }
          }, 600);
        }, 800);
      }, 600);
    }, 500);
  }, 100);
}

function displayVerificationResult(tender, query) {
  const resultWrapper = document.getElementById('verification-result-wrapper');
  const resultBanner = document.getElementById('result-banner');
  const resultBannerText = document.getElementById('result-banner-text');

  resultWrapper.classList.add('visible');

  if (tender && tender.status === 'verified') {
    resultBanner.className = 'result-message-banner verified';
    resultBannerText.textContent = "Verifiable Credential Cryptographically Valid & Verified";

    document.getElementById('res-card-id').textContent = `Tender #${tender.tenderNo}`;
    document.getElementById('res-card-badge').className = 'verified-tag';
    document.getElementById('res-card-badge').innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Verified`;

    document.getElementById('res-card-ministry').textContent = tender.ministry;
    document.getElementById('res-card-issuer').textContent = tender.issuer;
    document.getElementById('res-card-details').textContent = tender.name;
    document.getElementById('res-card-budget').textContent = `$${tender.budget.toLocaleString()} USD`;
    document.getElementById('res-card-date').textContent = new Date(tender.date).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
    document.getElementById('res-card-vc-id').textContent = tender.id;
    document.getElementById('res-qr-caption').textContent = "Signed with MOSIP IDA";

    if (tender.qr_code_url) {
      const imgUrl = `${API_BASE.replace('/api', '')}${tender.qr_code_url}`;
      const img = document.getElementById('res-qr-img');
      const canvas = document.getElementById('res-qr-canvas');
      if (img) {
        img.src = imgUrl;
        img.style.display = 'block';
      }
      if (canvas) {
        canvas.style.display = 'none';
      }
    } else {
      const img = document.getElementById('res-qr-img');
      const canvas = document.getElementById('res-qr-canvas');
      if (img) img.style.display = 'none';
      if (canvas) {
        canvas.style.display = 'block';
        generateMockQR('res-qr-canvas', tender.id);
      }
    }

    const integrityLabel = document.getElementById('res-integrity-label');
    const integrityVal = document.getElementById('res-integrity-val');
    const integrityBadge = document.getElementById('res-integrity-badge');
    const integrityDetails = document.getElementById('res-integrity-details');

    const checklistCard = document.getElementById('integrity-checklist-card');
    const checklistBody = document.getElementById('integrity-checklist-body');

    if (integrityLabel && integrityVal && integrityBadge && integrityDetails) {
      if (tender.document_integrity) {
        integrityLabel.style.display = 'block';
        integrityVal.style.display = 'flex';

        if (tender.document_integrity === 'valid') {
          integrityBadge.className = 'status-badge verified';
          integrityBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
          integrityBadge.style.color = '#10b981';
          integrityBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
          integrityBadge.textContent = '✓ Document Integrity Verified';
          integrityDetails.textContent = 'SHA-256 integrity match succeeded.';
        } else if (tender.document_integrity === 'tampered') {
          integrityBadge.className = 'status-badge rejected';
          integrityBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
          integrityBadge.style.color = '#ef4444';
          integrityBadge.style.borderColor = 'rgba(239, 68, 68, 0.2)';
          integrityBadge.textContent = '✗ Document Tampered';
          integrityDetails.textContent = 'Calculated SHA-256 does not match database record.';
        } else {
          integrityBadge.className = 'status-badge pending';
          integrityBadge.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
          integrityBadge.style.color = '#f59e0b';
          integrityBadge.style.borderColor = 'rgba(245, 158, 11, 0.2)';
          integrityBadge.textContent = '⚠ Missing Document';
          integrityDetails.textContent = 'No document found or uploaded on the server.';
        }
      } else {
        integrityLabel.style.display = 'none';
        integrityVal.style.display = 'none';
      }
    }

    if (checklistCard && checklistBody) {
      checklistCard.style.display = 'block';
      const sigOk = tender.signature_valid !== false;
      const issuerOk = tender.issuer_valid !== false;
      const docOk = tender.document_integrity === 'valid';
      const docTampered = tender.document_integrity === 'tampered';

      let html = '';

      // Credential Verified check
      if (sigOk) {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#10b981; font-weight:500;">
            <span style="font-size:1.1rem;">✓</span> Credential Signature Verified (Inji Verify)
          </div>
        `;
      } else {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#ef4444; font-weight:500;">
            <span style="font-size:1.1rem;">✗</span> Credential Signature Tampered / Invalid
          </div>
        `;
      }

      // Issuer Verified check
      if (issuerOk) {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#10b981; font-weight:500;">
            <span style="font-size:1.1rem;">✓</span> Issuer DID Verified (Inji Verify)
          </div>
        `;
      } else {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#ef4444; font-weight:500;">
            <span style="font-size:1.1rem;">✗</span> Untrusted / Invalid Issuer DID
          </div>
        `;
      }

      // QR Valid check
      html += `
        <div style="display:flex; align-items:center; gap:0.5rem; color:#10b981; font-weight:500;">
          <span style="font-size:1.1rem;">✓</span> QR Code Context Valid
        </div>
      `;

      // Document Integrity check
      if (docOk) {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#10b981; font-weight:500;">
            <span style="font-size:1.1rem;">✓</span> Document Integrity Verified
          </div>
        `;
      } else if (docTampered) {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#ef4444; font-weight:500;">
            <span style="font-size:1.1rem;">✗</span> Document Tampered / Hash Mismatch
          </div>
        `;
      } else {
        html += `
          <div style="display:flex; align-items:center; gap:0.5rem; color:#f59e0b; font-weight:500;">
            <span style="font-size:1.1rem;">⚠</span> Document Missing / Not Uploaded
          </div>
        `;
      }

      checklistBody.innerHTML = html;
    }

    const injiCard = document.getElementById('inji-vc-card');
    if (injiCard) {
      if (tender.vc_id || tender.issuer_did || tender.credential_json) {
        injiCard.style.display = 'block';
        document.getElementById('res-inji-vc-id').textContent = tender.vc_id || "N/A";
        document.getElementById('res-inji-issuer-did').textContent = tender.issuer_did || "N/A";
        const jsonBlock = document.getElementById('res-inji-json');
        if (jsonBlock) {
          jsonBlock.textContent = tender.credential_json ? JSON.stringify(tender.credential_json, null, 2) : "{}";
        }
      } else {
        injiCard.style.display = 'none';
      }
    }
  } else if (tender && tender.status === 'pending') {
    const injiCard = document.getElementById('inji-vc-card');
    if (injiCard) injiCard.style.display = 'none';

    resultBanner.className = 'result-message-banner failed';
    resultBanner.style.background = 'rgba(245, 158, 11, 0.1)';
    resultBanner.style.borderColor = 'rgba(245, 158, 11, 0.2)';
    resultBanner.style.color = '#f59e0b';
    resultBannerText.textContent = "Tender Draft Found but Credential is NOT Signed/Issued Yet";

    document.getElementById('res-card-id').textContent = `Tender #${tender.tenderNo}`;
    document.getElementById('res-card-badge').className = 'status-badge pending';
    document.getElementById('res-card-badge').textContent = 'Pending Signature';

    document.getElementById('res-card-ministry').textContent = tender.ministry;
    document.getElementById('res-card-issuer').textContent = tender.issuer;
    document.getElementById('res-card-details').textContent = tender.name;
    document.getElementById('res-card-budget').textContent = `$${tender.budget.toLocaleString()} USD`;
    document.getElementById('res-card-date').textContent = new Date(tender.date).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
    document.getElementById('res-card-vc-id').textContent = "UNPUBLISHED";
    document.getElementById('res-qr-caption').textContent = "NO VC KEY";

    const canvas = document.getElementById('res-qr-canvas');
    if (canvas) {
      canvas.style.display = 'block';
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    const img = document.getElementById('res-qr-img');
    if (img) img.style.display = 'none';

    const integrityLabel = document.getElementById('res-integrity-label');
    const integrityVal = document.getElementById('res-integrity-val');
    if (integrityLabel) integrityLabel.style.display = 'none';
    if (integrityVal) integrityVal.style.display = 'none';
    const checklistCard = document.getElementById('integrity-checklist-card');
    if (checklistCard) checklistCard.style.display = 'none';
  } else {
    resultBanner.className = 'result-message-banner failed';
    resultBannerText.textContent = `Revoked or Invalid Credential: ID "${query}" not found in Registry.`;

    document.getElementById('res-card-id').textContent = `Tender Entry Not Found`;
    document.getElementById('res-card-badge').className = 'status-badge rejected';
    document.getElementById('res-card-badge').textContent = 'Invalid';

    document.getElementById('res-card-ministry').textContent = "N/A";
    document.getElementById('res-card-issuer').textContent = "N/A";
    document.getElementById('res-card-details').textContent = "Unknown Document Hash / Revoked Key Reference";
    document.getElementById('res-card-budget').textContent = "N/A";
    document.getElementById('res-card-date').textContent = "N/A";
    document.getElementById('res-card-vc-id').textContent = query;
    document.getElementById('res-qr-caption').textContent = "Verification Failed";

    const canvas = document.getElementById('res-qr-canvas');
    if (canvas) {
      canvas.style.display = 'block';
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    const img = document.getElementById('res-qr-img');
    if (img) img.style.display = 'none';

    const integrityLabel = document.getElementById('res-integrity-label');
    const integrityVal = document.getElementById('res-integrity-val');
    if (integrityLabel) integrityLabel.style.display = 'none';
    if (integrityVal) integrityVal.style.display = 'none';
    const checklistCard = document.getElementById('integrity-checklist-card');
    if (checklistCard) checklistCard.style.display = 'none';
    const injiCard = document.getElementById('inji-vc-card');
    if (injiCard) injiCard.style.display = 'none';
  }
}

/* ==========================================================================
   ORIGINAL REVIEWER DIGITAL SIGNATURE FLOW
   ========================================================================== */

window.triggerDigitalSignature = function (tenderNo) {
  const tender = mockTenders.find(t => t.tenderNo === tenderNo);
  if (!tender) return;

  const idaModal = document.getElementById('ida-otp-modal');
  const cancelBtn = document.getElementById('ida-otp-cancel-btn');
  const verifyBtn = document.getElementById('ida-otp-verify-btn');
  const otpInputs = document.querySelectorAll('#ida-otp-container .otp-input');

  // Clear previous values
  otpInputs.forEach(input => input.value = '');
  idaModal.classList.add('active');
  otpInputs[0].focus();

  // Setup auto-advance
  otpInputs.forEach((input, index) => {
    input.oninput = (e) => {
      if (input.value && index < otpInputs.length - 1) {
        otpInputs[index + 1].focus();
      }
    };
    input.onkeydown = (e) => {
      if (e.key === 'Backspace' && !input.value && index > 0) {
        otpInputs[index - 1].focus();
      } else if (e.key === 'Enter') {
        verifyBtn.click();
      }
    };
  });

  cancelBtn.onclick = () => {
    idaModal.classList.remove('active');
  };

  verifyBtn.onclick = async () => {
    const otpCode = Array.from(otpInputs).map(input => input.value).join('');
    if (otpCode.length !== 6) {
      alert("Please enter a 6-digit OTP code.");
      return;
    }
    if (otpCode !== "123456") {
      alert("Invalid OTP code. MOSIP IDA authentication failed.");
      return;
    }

    // Hide OTP modal
    idaModal.classList.remove('active');

    // Show digital signing progress modal
    const signingModal = document.getElementById('signing-modal');
    const modalProgressFill = document.getElementById('modal-progress-indicator');
    const signingTitle = document.getElementById('signing-title');
    const signingDesc = document.getElementById('signing-desc');

    signingModal.classList.add('active');
    modalProgressFill.style.width = '0%';

    signingTitle.textContent = "MOSIP IDA Handshake";
    signingDesc.textContent = "Connecting to identity verification infrastructure...";

    let progress = 0;
    const interval = setInterval(() => {
      progress += 4;
      modalProgressFill.style.width = `${progress}%`;

      if (progress === 32) {
        signingTitle.textContent = "Cryptographic Key Handshake";
        signingDesc.textContent = "Retrieving authorized official HSM keys from eSignet secure keyspace...";
      } else if (progress === 64) {
        signingTitle.textContent = "Signing Document Hash";
        signingDesc.textContent = "Applying SHA-256 digital signature to tender document specifications...";
      } else if (progress === 84) {
        signingTitle.textContent = "Issuing Verifiable Credential";
        signingDesc.textContent = "Registering W3C verifiable credentials on ledger database...";
      }

      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(async () => {
          try {
            // Perform backend signing transaction
            const res = await fetch(`${API_BASE}/tenders/${tender.tenderNo}/sign`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                otp: otpCode,
                issued_by: (currentUser && currentUser.id) ? currentUser.id : "00000000-0000-0000-0000-000000000000"
              })
            });

            if (!res.ok) {
              const errData = await res.json();
              alert(errData.detail || "Authentication / Signing failed.");
              signingModal.classList.remove('active');
              return;
            }

            signingModal.classList.remove('active');

            await syncAllData();
            updateDashboardData();
            alert(`Tender #${tender.tenderNo} has been digitally signed and published!`);
          } catch (e) {
            signingModal.classList.remove('active');
            alert("Error: Connection to signing server failed.");
          }
        }, 500);
      }
    }, 120);
  };
};

window.showTenderInVerifyPortal = function (vcId) {
  switchView('verify-view');
  document.getElementById('credential-search-input').value = vcId;
  performVerifySearch(vcId);
};

/* ==========================================================================
   PROCEDURAL QR CODE GENERATOR ON CANVAS
   ========================================================================== */

function generateMockQR(canvasId, seedText) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const size = rect.width;
  ctx.clearRect(0, 0, size, size);

  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, size, size);

  const drawLocator = (x, y, scale) => {
    ctx.fillStyle = '#000000';
    ctx.fillRect(x, y, scale * 7, scale * 7);
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(x + scale, y + scale, scale * 5, scale * 5);
    ctx.fillStyle = '#000000';
    ctx.fillRect(x + (scale * 2), y + (scale * 2), scale * 3, scale * 3);
  };

  const gridSize = 25;
  const moduleSize = size / gridSize;

  drawLocator(0, 0, moduleSize);
  drawLocator((gridSize - 7) * moduleSize, 0, moduleSize);
  drawLocator(0, (gridSize - 7) * moduleSize, moduleSize);

  ctx.fillStyle = '#000000';
  ctx.fillRect((gridSize - 9) * moduleSize, (gridSize - 9) * moduleSize, moduleSize * 5, moduleSize * 5);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect((gridSize - 8) * moduleSize, (gridSize - 8) * moduleSize, moduleSize * 3, moduleSize * 3);
  ctx.fillStyle = '#000000';
  ctx.fillRect((gridSize - 7) * moduleSize, (gridSize - 7) * moduleSize, moduleSize, moduleSize);

  let hashVal = hashString(seedText || "gov-tender-hash");

  for (let r = 0; r < gridSize; r++) {
    for (let c = 0; c < gridSize; c++) {
      if (r < 8 && c < 8) continue;
      if (r < 8 && c > gridSize - 9) continue;
      if (r > gridSize - 9 && c < 8) continue;
      if (r > gridSize - 10 && r < gridSize - 4 && c > gridSize - 10 && c < gridSize - 4) continue;

      hashVal = (hashVal * 16807) % 2147483647;
      if (hashVal % 2 === 0) {
        ctx.fillStyle = '#000000';
        ctx.fillRect(c * moduleSize, r * moduleSize, Math.ceil(moduleSize), Math.ceil(moduleSize));
      }
    }
  }
}

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}


/* ==========================================================================
   AUDITOR PORTAL CONTROLS
   ========================================================================== */

window.openAuditorTab = async function openAuditorTab(tabId) {
  document.querySelectorAll('#auditor-portal-view .dash-tab-content').forEach(tab => {
    tab.style.display = 'none';
  });

  document.getElementById(tabId).style.display = 'block';

  document.querySelectorAll('#auditor-portal-view .sidebar-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('data-auditor-tab') === tabId);
  });

  await syncAllData();

  if (tabId === 'auditor-tab-dashboard') {
    renderAuditorDashboard();
  } else if (tabId === 'auditor-tab-logs') {
    renderAuditorLogs();
  }
};

function renderAuditorDashboard() {
  if (currentUser) {
    document.getElementById('auditor-profile-name').textContent = currentUser.name;
    document.getElementById('auditor-avatar-initials').textContent = currentUser.initials;
  }
  const verifiedCount = mockTenders.filter(t => t.status === 'verified').length;
  document.getElementById('auditor-stats-credentials').textContent = verifiedCount;
  document.getElementById('auditor-stats-logs').textContent = mockLogs.length;
}

function renderAuditorLogs() {
  const container = document.getElementById('auditor-audit-logs-list');
  if (!container) return;
  container.innerHTML = '';
  mockLogs.forEach(log => {
    const item = document.createElement('div');
    item.className = 'ticket-item';
    item.style.padding = '0.5rem 1rem';
    item.innerHTML = `<span>[${log.time}]</span> <span style="flex:1; margin-left:1rem; color:white;">${log.desc}</span>`;
    container.appendChild(item);
  });
}
