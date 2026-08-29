/**
 * Dashboard Page — compliance overview, charts, recent scans.
 */
const DashboardPage = {
    async mount(container) {
        container.innerHTML = `
            <div class="stats-grid" id="stats-grid">
                ${this._renderSkeletonStats()}
            </div>
            <div class="grid-2 mb-6">
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">Compliance Distribution</div>
                            <div class="card-subtitle">Product compliance status breakdown</div>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="compliance-donut"></canvas>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">Common Violations</div>
                            <div class="card-subtitle">Most frequently failed compliance checks</div>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="violations-bar"></canvas>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Recent Scans</div>
                        <div class="card-subtitle">Latest product compliance checks</div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-outline btn-sm" id="dash-clear-cache-btn">
                            Clear Temp Files
                        </button>
                        <a href="#scan" class="btn btn-primary btn-sm">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                            New Scan
                        </a>
                    </div>
                </div>
                <div id="recent-scans-table">
                    <p class="text-muted text-sm">Loading...</p>
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
            <div class="stat-card accent">
                <div class="stat-label">Total Products</div>
                <div class="stat-value">${stats.total_products}</div>
            </div>
            <div class="stat-card success">
                <div class="stat-label">Compliant</div>
                <div class="stat-value">${stats.compliant}</div>
                <div class="stat-change" style="background: var(--success-bg); color: var(--success);">
                    ${stats.compliance_rate}% rate
                </div>
            </div>
            <div class="stat-card danger">
                <div class="stat-label">Non-Compliant</div>
                <div class="stat-value">${stats.non_compliant}</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">Warnings</div>
                <div class="stat-value">${stats.warnings}</div>
            </div>
        `;
    },

    _renderRecentScans(scans) {
        const el = document.getElementById('recent-scans-table');
        if (!el) return;

        if (!scans || scans.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                    </svg>
                    <h3>No products scanned yet</h3>
                    <p>Start by scanning a product to see compliance results here.</p>
                    <a href="#scan" class="btn btn-primary mt-4">Scan First Product</a>
                </div>
            `;
            return;
        }

        el.innerHTML = `
            <table class="data-table">
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
                            <td class="product-name">${s.product_name || `Product #${s.product_id}`}</td>
                            <td>${ComplianceCard.renderStatusBadge(s.status)}</td>
                            <td class="text-mono ${s.compliance_score >= 80 ? 'text-success' : s.compliance_score >= 50 ? 'text-warning' : 'text-danger'}">
                                ${s.compliance_score.toFixed(0)}%
                            </td>
                            <td class="text-muted">${s.image_count} img</td>
                            <td class="text-muted text-sm">${new Date(s.scanned_at).toLocaleDateString()}</td>
                            <td>
                                <button class="btn btn-outline btn-sm" onclick="location.hash='report/${s.product_id}'">
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
            <div class="stat-card">
                <div class="stat-label" style="background: var(--border); height: 14px; width: 80px; border-radius: 4px;"></div>
                <div class="stat-value" style="background: var(--border); height: 32px; width: 60px; border-radius: 6px; margin-top: 8px;"></div>
            </div>
        `).join('');
    },

    _renderEmptyState() {
        const grid = document.getElementById('stats-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="stat-card accent"><div class="stat-label">Total Products</div><div class="stat-value">0</div></div>
                <div class="stat-card success"><div class="stat-label">Compliant</div><div class="stat-value">0</div></div>
                <div class="stat-card danger"><div class="stat-label">Non-Compliant</div><div class="stat-value">0</div></div>
                <div class="stat-card warning"><div class="stat-label">Warnings</div><div class="stat-value">0</div></div>
            `;
        }
        const table = document.getElementById('recent-scans-table');
        if (table) {
            table.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                    </svg>
                    <h3>No products scanned yet</h3>
                    <p>Start by scanning a product to see compliance results here.</p>
                    <a href="#scan" class="btn btn-primary mt-4">Scan First Product</a>
                </div>
            `;
        }
    },
};
