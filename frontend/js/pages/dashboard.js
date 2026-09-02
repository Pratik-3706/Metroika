/**
 * Dashboard Page — compliance overview, charts, recent scans.
 */
const DashboardPage = {
    async mount(container) {
        container.innerHTML = `
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6" id="stats-grid">
                ${this._renderSkeletonStats()}
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <div class="text-lg font-semibold text-gray-900 dark:text-white">Compliance Distribution</div>
                            <div class="text-sm text-gray-500 dark:text-gray-400">Product compliance status breakdown</div>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="compliance-donut"></canvas>
                    </div>
                </div>
                <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <div class="text-lg font-semibold text-gray-900 dark:text-white">Common Violations</div>
                            <div class="text-sm text-gray-500 dark:text-gray-400">Most frequently failed compliance checks</div>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="violations-bar"></canvas>
                    </div>
                </div>
            </div>
            <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">Recent Scans</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">Latest product compliance checks</div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="inline-flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium rounded-lg transition-colors px-3 py-1.5 text-xs" id="dash-clear-cache-btn">
                            Clear Temp Files
                        </button>
                        <a href="#scan" class="btn btn-primary px-3 py-1.5 text-xs">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                            New Scan
                        </a>
                    </div>
                </div>
                <div id="recent-scans-table">
                    <p class="text-sm text-gray-500 dark:text-gray-400">Loading...</p>
                </div>
            </div>
        `;

        await this._loadData();

        document.getElementById('dash-clear-cache-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('dash-clear-cache-btn');
            btn.disabled = true;
            btn.innerHTML = 'Clearing...';
            try {
                const res = await API.clearCache();
                showToast(res.message, 'success');
            } catch (error) {
                showToast(`Failed: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'Clear Temp Files';
            }
        });
    },

    unmount() {
        Charts.destroyAll();
    },

    async _loadData() {
        try {
            const [stats, recent] = await Promise.all([
                API.getDashboardStats(),
                API.getRecentScans(),
            ]);

            this._renderStats(stats);
            Charts.createComplianceDonut('compliance-donut', stats);

            if (stats.common_violations && stats.common_violations.length > 0) {
                Charts.createViolationsBar('violations-bar', stats.common_violations);
            }

            this._renderRecentScans(recent);
        } catch (error) {
            console.warn('Dashboard data load failed:', error);
            this._renderEmptyState();
        }
    },

    _renderStats(stats) {
        const grid = document.getElementById('stats-grid');
        if (!grid) return;

        grid.innerHTML = `
            <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-xl border border-blue-100 dark:border-blue-800/50">
                <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Total Products</div>
                <div class="text-3xl font-bold text-gray-900 dark:text-white">${stats.total_products}</div>
            </div>
            <div class="bg-emerald-50 dark:bg-emerald-900/20 p-4 rounded-xl border border-emerald-100 dark:border-emerald-800/50">
                <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Compliant</div>
                <div class="text-3xl font-bold text-gray-900 dark:text-white">${stats.compliant}</div>
                <div class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-2" style="background: var(--success-bg); color: var(--success);">
                    ${stats.compliance_rate}% rate
                </div>
            </div>
            <div class="bg-red-50 dark:bg-red-900/20 p-4 rounded-xl border border-red-100 dark:border-red-800/50">
                <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Non-Compliant</div>
                <div class="text-3xl font-bold text-gray-900 dark:text-white">${stats.non_compliant}</div>
            </div>
            <div class="bg-amber-50 dark:bg-amber-900/20 p-4 rounded-xl border border-amber-100 dark:border-amber-800/50">
                <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Warnings</div>
                <div class="text-3xl font-bold text-gray-900 dark:text-white">${stats.warnings}</div>
            </div>
        `;
    },

    _renderRecentScans(scans) {
        const el = document.getElementById('recent-scans-table');
        if (!el) return;

        if (!scans || scans.length === 0) {
            el.innerHTML = `
                <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                    </svg>
                    <h3>No products scanned yet</h3>
                    <p>Start by scanning a product to see compliance results here.</p>
                    <a href="#scan" class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors mt-4">Scan First Product</a>
                </div>
            `;
            return;
        }

        el.innerHTML = `
            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700 w-full text-left border-collapse">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Images</th>
                        <th>Scanned</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${scans.map(s => `
                        <tr>
                            <td class="font-medium text-gray-900 dark:text-white">${s.product_name || `Product #${s.product_id}`}</td>
                            <td>${ComplianceCard.renderStatusBadge(s.status)}</td>
                            <td class="text-mono ${s.compliance_score >= 80 ? 'text-success' : s.compliance_score >= 50 ? 'text-warning' : 'text-danger'}">
                                ${s.compliance_score.toFixed(0)}%
                            </td>
                            <td class="text-gray-500 dark:text-gray-400">${s.image_count} img</td>
                            <td class="text-sm text-gray-500 dark:text-gray-400">${new Date(s.scanned_at).toLocaleDateString()}</td>
                            <td>
                                <button class="inline-flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium rounded-lg transition-colors px-3 py-1.5 text-xs" onclick="location.hash='report/${s.product_id}'">
                                    View
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    _renderSkeletonStats() {
        return Array(4).fill('').map(() => `
            <div class="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1" style="background: var(--border); height: 14px; width: 80px; border-radius: 4px;"></div>
                <div class="text-3xl font-bold text-gray-900 dark:text-white" style="background: var(--border); height: 32px; width: 60px; border-radius: 6px; margin-top: 8px;"></div>
            </div>
        `).join('');
    },

    _renderEmptyState() {
        const grid = document.getElementById('stats-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-xl border border-blue-100 dark:border-blue-800/50"><div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Total Products</div><div class="text-3xl font-bold text-gray-900 dark:text-white">0</div></div>
                <div class="bg-emerald-50 dark:bg-emerald-900/20 p-4 rounded-xl border border-emerald-100 dark:border-emerald-800/50"><div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Compliant</div><div class="text-3xl font-bold text-gray-900 dark:text-white">0</div></div>
                <div class="bg-red-50 dark:bg-red-900/20 p-4 rounded-xl border border-red-100 dark:border-red-800/50"><div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Non-Compliant</div><div class="text-3xl font-bold text-gray-900 dark:text-white">0</div></div>
                <div class="bg-amber-50 dark:bg-amber-900/20 p-4 rounded-xl border border-amber-100 dark:border-amber-800/50"><div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Warnings</div><div class="text-3xl font-bold text-gray-900 dark:text-white">0</div></div>
            `;
        }
        const table = document.getElementById('recent-scans-table');
        if (table) {
            table.innerHTML = `
                <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                    </svg>
                    <h3>No products scanned yet</h3>
                    <p>Start by scanning a product to see compliance results here.</p>
                    <a href="#scan" class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors mt-4">Scan First Product</a>
                </div>
            `;
        }
    },
};
