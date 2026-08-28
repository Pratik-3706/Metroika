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
    },

    pageTitles: {
        dashboard: 'Dashboard',
        scan: 'Scan Product',
        products: 'Products',
        report: 'Compliance Report',
        rules: 'Rules Reference',
    },

    init() {
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

        // Initial route
        this.route();
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
