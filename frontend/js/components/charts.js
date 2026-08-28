/**
 * Chart components using Chart.js for the dashboard.
 */
const Charts = {
    instances: {},

    destroyAll() {
        Object.values(this.instances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.instances = {};
    },

    initThemeListener() {
        if (this._listenerAdded) return;
        window.addEventListener('themeChanged', (e) => {
            // Re-render charts with new theme colors if we are on dashboard
            if (App.currentPage === DashboardPage) {
                DashboardPage._loadData();
            }
        });
        this._listenerAdded = true;
    },

    createComplianceDonut(canvasId, stats) {
        this.initThemeListener();
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        this.instances[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Compliant', 'Non-Compliant', 'Warnings', 'Pending'],
                datasets: [{
                    data: [
                        stats.compliant || 0,
                        stats.non_compliant || 0,
                        stats.warnings || 0,
                        stats.pending || 0,
                    ],
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(239, 68, 68, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(100, 116, 139, 0.5)',
                    ],
                    borderColor: [
                        'rgba(16, 185, 129, 1)',
                        'rgba(239, 68, 68, 1)',
                        'rgba(245, 158, 11, 1)',
                        'rgba(100, 116, 139, 1)',
                    ],
                    borderWidth: 1,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: isDark ? '#94a3b8' : '#475569',
                            padding: 16,
                            font: { family: "'Inter', sans-serif", size: 12 },
                            usePointStyle: true,
                            pointStyleWidth: 8,
                        },
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: isDark ? '#f8fafc' : '#0f172a',
                        bodyColor: isDark ? '#cbd5e1' : '#475569',
                        borderColor: isDark ? '#334155' : '#e2e8f0',
                        borderWidth: 1,
                        cornerRadius: 8,
                        padding: 12,
                        boxPadding: 6,
                        usePointStyle: true,
                    },
                },
            },
        });
    },

    createViolationsBar(canvasId, violations) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const labels = violations.map(v => v.rule_name.length > 25 ? v.rule_name.slice(0, 25) + '…' : v.rule_name);
        const data = violations.map(v => v.count);

        this.instances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Violations',
                    data,
                    backgroundColor: 'rgba(239, 68, 68, 0.6)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 1,
                    borderRadius: 6,
                    barPercentage: 0.7,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                scales: {
                    x: {
                        grid: { color: isDark ? '#334155' : '#f1f5f9' },
                        ticks: {
                            color: isDark ? '#94a3b8' : '#64748b',
                            font: { family: "'Inter', sans-serif", size: 11 },
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: isDark ? '#cbd5e1' : '#475569',
                            font: { family: "'Inter', sans-serif", size: 11 },
                        },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: isDark ? '#f8fafc' : '#0f172a',
                        bodyColor: isDark ? '#cbd5e1' : '#475569',
                        borderColor: isDark ? '#334155' : '#e2e8f0',
                        borderWidth: 1,
                        cornerRadius: 8,
                        padding: 12,
                    },
                },
            },
        });
    },
};
