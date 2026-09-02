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
                    backgroundColor: isDark
                        ? ['#4ead8a', '#e76f51', '#e09f3e', '#4a4a4a']
                        : ['#2d6a4f', '#b91c1c', '#b45309', '#c4c4c0'],
                    borderColor: isDark ? '#1c1c1c' : '#ffffff',
                    borderWidth: 2,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '72%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: isDark ? '#a0a0a0' : '#5c5c5c',
                            padding: 14,
                            font: { family: "'Inter', sans-serif", size: 11, weight: 500 },
                            usePointStyle: true,
                            pointStyleWidth: 6,
                        },
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#242424' : '#ffffff',
                        titleColor: isDark ? '#e8e8e8' : '#1a1a1a',
                        bodyColor: isDark ? '#a0a0a0' : '#5c5c5c',
                        borderColor: isDark ? '#3d3d3d' : '#e8e7e4',
                        borderWidth: 1,
                        cornerRadius: 6,
                        padding: 10,
                        boxPadding: 4,
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
                    backgroundColor: isDark ? 'rgba(231, 111, 81, 0.5)' : 'rgba(185, 28, 28, 0.5)',
                    borderColor: isDark ? '#e76f51' : '#b91c1c',
                    borderWidth: 1,
                    borderRadius: 4,
                    barPercentage: 0.65,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                indexAxis: 'y',
                scales: {
                    x: {
                        grid: { color: isDark ? '#2e2e2e' : '#f0f0ec' },
                        ticks: {
                            color: isDark ? '#6b6b6b' : '#8a8a8a',
                            font: { family: "'Inter', sans-serif", size: 10 },
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: isDark ? '#a0a0a0' : '#5c5c5c',
                            font: { family: "'Inter', sans-serif", size: 10 },
                        },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: isDark ? '#242424' : '#ffffff',
                        titleColor: isDark ? '#e8e8e8' : '#1a1a1a',
                        bodyColor: isDark ? '#a0a0a0' : '#5c5c5c',
                        borderColor: isDark ? '#3d3d3d' : '#e8e7e4',
                        borderWidth: 1,
                        cornerRadius: 6,
                        padding: 10,
                    },
                },
            },
        });
    },
};
