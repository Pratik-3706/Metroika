/**
 * Compliance card component — renders individual check results.
 */
const ComplianceCard = {
    statusIcons: {
        pass: '✓',
        fail: '✗',
        warning: '⚠',
        not_applicable: '—',
    },

    renderCheckList(checks) {
        if (!checks || checks.length === 0) {
            return '<p class="text-sm text-gray-500 dark:text-gray-400">No compliance checks available.</p>';
        }

        return `
            <div class="space-y-4">
                ${checks.map(c => this.renderCheckItem(c)).join('')}
            </div>
        `;
    },

    renderCheckItem(check) {
        const icon = this.statusIcons[check.status] || '?';
        return `
            <div class="flex gap-3 p-3 rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                <div class="check-icon ${check.status}">${icon}</div>
                <div class="check-content">
                    <div class="font-medium text-gray-900 dark:text-white text-sm">${check.rule_name}</div>
                    <div class="text-xs text-gray-500 font-mono mt-0.5">${check.rule_reference}</div>
                    <div class="text-sm text-gray-600 dark:text-gray-300 mt-1">${check.details}</div>
                    ${check.evidence ? `<div class="text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-2 rounded mt-2 text-gray-500 dark:text-gray-400">Evidence: ${check.evidence}</div>` : ''}
                </div>
                <span class="check-severity ${check.severity}">${check.severity}</span>
            </div>
        `;
    },

    renderScoreCircle(score, status) {
        const colors = {
            compliant: 'var(--success)',
            non_compliant: 'var(--danger)',
            warning: 'var(--warning)',
            pending: 'var(--text-muted)',
        };
        const statusLabels = {
            compliant: 'COMPLIANT',
            non_compliant: 'NON-COMPLIANT',
            warning: 'HAS WARNINGS',
            pending: 'PENDING',
        };

        const color = colors[status] || colors.pending;
        const label = statusLabels[status] || status;

        return `
            <div class="compliance-score">
                <div class="score-circle" style="--score-pct: ${score}; --score-color: ${color};">
                    <div class="score-value" style="color: ${color}">${Math.round(score)}%</div>
                    <div class="score-label">Score</div>
                </div>
                <div class="score-status" style="color: ${color}">${label}</div>
            </div>
        `;
    },

    renderStatusBadge(status) {
        return `
            <span class="status-badge ${status}">
                <span class="status-dot"></span>
                ${status.replace('_', '-')}
            </span>
        `;
    },
};
