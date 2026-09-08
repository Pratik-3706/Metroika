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

    createComplianceDonut(canvasId, stats = {}) {
        this.initThemeListener();
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Clean up previous instance on this canvas to prevent memory leaks / collision errors
        if (this.instances[canvasId]) {
            this.instances[canvasId].destroy();
            delete this.instances[canvasId];
        }

        const ctx = canvas.getContext('2d');
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        const compliant = stats.compliant || 0;
        const nonCompliant = stats.non_compliant || 0;
        const warnings = stats.warnings || 0;
        const pending = stats.pending || 0;
        const total = compliant + nonCompliant + warnings + pending;

        // If no data, render a sleek placeholder donut with 0-state
        const dataValues = total > 0 
            ? [compliant, nonCompliant, warnings, pending] 
            : [1];
        const bgColors = total > 0
            ? [
                'rgba(16, 185, 129, 0.85)',
                'rgba(239, 68, 68, 0.85)',
                'rgba(245, 158, 11, 0.85)',
                'rgba(100, 116, 139, 0.5)',
              ]
            : [isDark ? 'rgba(51, 65, 85, 0.4)' : 'rgba(226, 232, 240, 0.8)'];

        const borderColors = total > 0
            ? [
                'rgba(16, 185, 129, 1)',
                'rgba(239, 68, 68, 1)',
                'rgba(245, 158, 11, 1)',
                'rgba(100, 116, 139, 1)',
              ]
            : [isDark ? 'rgba(71, 85, 105, 0.6)' : 'rgba(203, 213, 225, 1)'];

        const labels = total > 0
            ? ['Compliant', 'Non-Compliant', 'Warnings', 'Pending']
            : ['No Scans Yet'];

        this.instances[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: dataValues,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1.5,
                    hoverOffset: total > 0 ? 8 : 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '72%',
                animation: {
                    animateScale: true,
                    animateRotate: true,
                    duration: 900,
                    easing: 'easeOutQuart',
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: isDark ? '#94a3b8' : '#475569',
                            padding: 16,
                            font: { family: "'Inter', sans-serif", size: 12, weight: 500 },
                            usePointStyle: true,
                            pointStyleWidth: 8,
                        },
                    },
                    tooltip: {
                        enabled: total > 0,
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

    createViolationsBar(canvasId, violations = []) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Clean up previous instance on this canvas
        if (this.instances[canvasId]) {
            this.instances[canvasId].destroy();
            delete this.instances[canvasId];
        }

        const ctx = canvas.getContext('2d');
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        const labels = (violations.length > 0)
            ? violations.map(v => v.rule_name.length > 25 ? v.rule_name.slice(0, 25) + '…' : v.rule_name)
            : ['No Violations Found'];
        const data = (violations.length > 0)
            ? violations.map(v => v.count)
            : [0];

        this.instances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Violations',
                    data,
                    backgroundColor: 'rgba(239, 68, 68, 0.65)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 1.5,
                    borderRadius: 6,
                    barPercentage: 0.7,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                animation: {
                    duration: 850,
                    easing: 'easeOutQuart',
                },
                scales: {
                    x: {
                        grid: { color: isDark ? '#334155' : '#f1f5f9' },
                        ticks: {
                            color: isDark ? '#94a3b8' : '#64748b',
                            font: { family: "'Inter', sans-serif", size: 11 },
                            stepSize: 1,
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
