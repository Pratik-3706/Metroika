/**
 * Metroika SPA Router & App Controller
 */
const App = {
    currentPage: null,

    pages: {
        dashboard: DashboardPage,
        scan: ScanPage,
        products: ProductsPage,
        report: ReportPage,
        rules: RulesPage,
        settings: SettingsPage,
    },

    pageTitles: {
        dashboard: 'Dashboard',
        scan: 'Scan Product',
        products: 'Products',
        report: 'Compliance Report',
        rules: 'Rules Reference',
        settings: 'Settings',
    },

    async init() {
        // Handle hash-based routing
        window.addEventListener('hashchange', () => this.route());

        // Menu toggle for mobile
        document.getElementById('menu-toggle')?.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
        });

        // Close sidebar when clicking outside on mobile
        document.getElementById('main-content')?.addEventListener('click', () => {
            document.getElementById('sidebar')?.classList.remove('open');
        });

        // Theme toggle
        this.initTheme();

        // Notice Modal
        this.initNoticeModal();

        // Custom Login Modal & Role Switcher
        this.initLoginModal();
        this.initRoleSwitcher();

        // Ensure we are authenticated BEFORE mounting initial route to prevent 401 race condition
        await this.ensureAuth();

        // Initial route
        this.route();

        // Dismiss the rotating emblem loader once app is ready
        this.dismissLoadingScreen();
    },

    dismissLoadingScreen() {
        const loader = document.getElementById('app-loading-screen');
        if (loader) {
            setTimeout(() => {
                loader.classList.add('fade-out');
                setTimeout(() => {
                    if (loader.parentNode) loader.parentNode.removeChild(loader);
                }, 600);
            }, 600);
        }
    },

    async ensureAuth() {
        const token = localStorage.getItem('metroika_token');
        if (!token) {
            for (let i = 0; i < 5; i++) {
                try {
                    await API.login('public', 'Public@2026!');
                    break;
                } catch (err) {
                    if (i < 4) {
                        await new Promise(r => setTimeout(r, 600));
                    } else {
                        console.warn('Initial public authentication deferred:', err);
                    }
                }
            }
        }
    },

    initTheme() {
        const toggleBtn = document.getElementById('theme-toggle');
        if (!toggleBtn) return;

        const sunIcon = toggleBtn.querySelector('.sun-icon');
        const moonIcon = toggleBtn.querySelector('.moon-icon');

        // Check local storage or system preference
        const savedTheme = localStorage.getItem('metroika-theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        const isDark = savedTheme === 'dark' || (!savedTheme && prefersDark);
        
        this.applyTheme(isDark, sunIcon, moonIcon);

        toggleBtn.addEventListener('click', () => {
            const currentlyDark = document.documentElement.getAttribute('data-theme') === 'dark';
            this.applyTheme(!currentlyDark, sunIcon, moonIcon);
        });
    },

    applyTheme(isDark, sunIcon, moonIcon) {
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('metroika-theme', 'dark');
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        } else {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('metroika-theme', 'light');
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        }

        // Trigger chart redraw if they exist
        if (typeof Charts !== 'undefined') {
            const event = new CustomEvent('themeChanged', { detail: { isDark } });
            window.dispatchEvent(event);
        }
    },

    initRoleSwitcher() {
        const badgeBtn = document.getElementById('role-badge-btn');
        const dropdown = document.getElementById('role-dropdown-menu');
        const roleLabel = document.getElementById('role-badge-label');
        const roleIcon = document.getElementById('role-badge-icon');

        if (!badgeBtn || !dropdown) return;

        // Current role
        let currentRole = localStorage.getItem('metroika_role') || 'public';
        this.updateRoleBadge(currentRole, roleLabel, roleIcon);

        badgeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        });

        document.addEventListener('click', () => {
            dropdown.style.display = 'none';
        });

        dropdown.querySelectorAll('.role-opt').forEach((opt) => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.style.display = 'none';
                const role = opt.dataset.role;
                this.openLoginModal(role);
            });
        });
    },

    initLoginModal() {
        const modal = document.getElementById('login-modal');
        const closeBtn = document.getElementById('login-modal-close');
        const cancelBtn = document.getElementById('login-modal-cancel');
        const form = document.getElementById('login-modal-form');
        const togglePassBtn = document.getElementById('login-pass-toggle');
        const demoPassBtn = document.getElementById('login-auto-demo-btn');
        const passInput = document.getElementById('login-password-input');
        const userInput = document.getElementById('login-username-input');
        const errorBox = document.getElementById('login-error-box');
        const submitBtn = document.getElementById('login-modal-submit-btn');

        if (!modal) return;

        const closeModal = () => {
            modal.style.display = 'none';
            if (errorBox) {
                errorBox.style.display = 'none';
                errorBox.textContent = '';
            }
        };

        closeBtn?.addEventListener('click', closeModal);
        cancelBtn?.addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // Toggle password visibility
        togglePassBtn?.addEventListener('click', () => {
            if (passInput) {
                const isPass = passInput.type === 'password';
                passInput.type = isPass ? 'text' : 'password';
                togglePassBtn.textContent = isPass ? '🔒' : '👁️';
            }
        });

        // Demo password fill
        const defaultPasswords = {
            inspector: 'Inspector@2026!',
            merchant: 'Merchant@2026!',
            public: 'Public@2026!',
        };

        const fillDemoPassword = () => {
            const activeCard = modal.querySelector('.role-select-card.active');
            const targetRole = activeCard ? activeCard.dataset.role : 'inspector';
            if (passInput) passInput.value = defaultPasswords[targetRole] || 'Public@2026!';
            if (errorBox) errorBox.style.display = 'none';
        };
        demoPassBtn?.addEventListener('click', fillDemoPassword);

        // Role cards selection inside modal
        modal.querySelectorAll('.role-select-card').forEach((card) => {
            card.addEventListener('click', () => {
                modal.querySelectorAll('.role-select-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');

                const user = card.dataset.user;
                const role = card.dataset.role;
                if (userInput) userInput.value = user;
                if (passInput) passInput.value = defaultPasswords[role] || '';

                const icon = card.querySelector('.role-card-icon')?.textContent || '🛡️';
                const modalIcon = document.getElementById('login-modal-icon');
                if (modalIcon) modalIcon.textContent = icon;
                if (errorBox) errorBox.style.display = 'none';
            });
        });

        // Form submit handler
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = userInput?.value.trim();
            const password = passInput?.value;

            if (!username || !password) {
                if (errorBox) {
                    errorBox.textContent = 'Please enter both username and password.';
                    errorBox.style.display = 'block';
                }
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;margin-right:6px;"></div> Signing In...';
            }
            if (errorBox) errorBox.style.display = 'none';

            try {
                const res = await API.login(username, password);
                closeModal();

                const roleLabel = document.getElementById('role-badge-label');
                const roleIcon = document.getElementById('role-badge-icon');
                this.updateRoleBadge(res.user.role, roleLabel, roleIcon);
                showToast(`Successfully authenticated as ${res.user.role.toUpperCase()} (${res.user.username})`, 'success');

                // Broadcast role change event
                window.dispatchEvent(new CustomEvent('roleChanged', { detail: { role: res.user.role } }));

                // Refresh current page if needed
                if (this.currentPage && typeof this.currentPage.mount === 'function') {
                    const hash = window.location.hash.slice(1) || 'dashboard';
                    const parts = hash.split('/');
                    const contentEl = document.getElementById('page-content');
                    this.currentPage.mount(contentEl, parts[1] || null);
                }
            } catch (err) {
                if (errorBox) {
                    errorBox.textContent = err.message || 'Authentication failed. Please check credentials.';
                    errorBox.style.display = 'block';
                }
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<span>Sign In</span>';
                }
            }
        });
    },

    openLoginModal(preselectedRole = null) {
        const modal = document.getElementById('login-modal');
        if (!modal) return;

        const role = preselectedRole || localStorage.getItem('metroika_role') || 'inspector';
        const card = modal.querySelector(`.role-select-card[data-role="${role}"]`) || modal.querySelector('.role-select-card');
        if (card) {
            card.click();
        }

        const errorBox = document.getElementById('login-error-box');
        if (errorBox) {
            errorBox.style.display = 'none';
            errorBox.textContent = '';
        }

        modal.style.display = 'flex';
        const passInput = document.getElementById('login-password-input');
        if (passInput) {
            passInput.focus();
            passInput.select();
        }
    },

    updateRoleBadge(role, labelEl, iconEl) {
        if (!labelEl) return;
        const config = {
            inspector: { icon: '🛡️', label: 'Inspector Mode' },
            merchant: { icon: '🏢', label: 'Merchant Mode' },
            public: { icon: '👤', label: 'Consumer Mode' },
        };
        const cfg = config[role] || config.inspector;
        if (iconEl) iconEl.textContent = cfg.icon;
        labelEl.textContent = cfg.label;

        // Update body data-role for CSS targeting (hiding elements)
        document.body.setAttribute('data-role', role);

        // Update active class in dropdown
        document.querySelectorAll('.role-opt').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.role === role);
        });
    },

    initNoticeModal() {
        const modal = document.getElementById('notice-modal');
        const closeBtn = document.getElementById('notice-modal-close');
        const dismissBtn = document.getElementById('notice-dismiss-btn');
        const printBtn = document.getElementById('notice-print-btn');

        const closeModal = () => {
            if (modal) modal.style.display = 'none';
        };

        closeBtn?.addEventListener('click', closeModal);
        dismissBtn?.addEventListener('click', closeModal);
        modal?.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        printBtn?.addEventListener('click', () => {
            const content = document.getElementById('notice-modal-content');
            if (!content) return;
            const printWin = window.open('', '', 'width=800,height=900');
            printWin.document.write(`
                <html>
                <head>
                    <title>Statutory Show Cause Notice</title>
                    <style>
                        body { font-family: "Times New Roman", Times, serif; padding: 40px; color: #111; line-height: 1.5; }
                        h2 { text-align: center; text-transform: uppercase; margin-bottom: 4px; }
                        .doc-subtitle { text-align: center; font-style: italic; border-bottom: 1px solid #777; padding-bottom: 12px; margin-bottom: 20px; }
                        .doc-meta { display: flex; justify-content: space-between; margin-bottom: 20px; }
                        .violation-box { background: #fdf2f2; border-left: 4px solid #b91c1c; padding: 12px; margin: 12px 0; }
                        .sig-block { margin-top: 50px; text-align: right; }
                    </style>
                </head>
                <body>${content.innerHTML}</body>
                </html>
            `);
            printWin.document.close();
            printWin.focus();
            setTimeout(() => { printWin.print(); printWin.close(); }, 250);
        });
    },

    route() {
        const hash = window.location.hash.slice(1) || 'dashboard';
        const parts = hash.split('/');
        const pageName = parts[0];
        const pageParam = parts[1] || null;

        // Update nav active state
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.page === pageName);
        });

        // Update page title
        const titleEl = document.getElementById('page-title');
        if (titleEl) {
            titleEl.textContent = this.pageTitles[pageName] || pageName;
        }

        // Unmount current page
        if (this.currentPage && typeof this.currentPage.unmount === 'function') {
            this.currentPage.unmount();
        }

        // Mount new page
        const PageHandler = this.pages[pageName];
        if (PageHandler) {
            this.currentPage = PageHandler;
            const contentEl = document.getElementById('page-content');
            contentEl.innerHTML = '';
            contentEl.className = 'page-content page-enter';

            if (typeof PageHandler.mount === 'function') {
                PageHandler.mount(contentEl, pageParam);
            }
        } else {
            // 404 fallback
            document.getElementById('page-content').innerHTML = `
                <div class="empty-state">
                    <h3>Page not found</h3>
                    <p>The page "${pageName}" doesn't exist.</p>
                    <a href="#dashboard" class="btn btn-primary mt-4">Go to Dashboard</a>
                </div>
            `;
        }

        // Close mobile sidebar
        document.getElementById('sidebar')?.classList.remove('open');
    },
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => App.init());
