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
            return '<p class="text-muted text-sm">No compliance checks available.</p>';
        }

        return `
            <div class="check-list">
                ${checks.map(c => this.renderCheckItem(c)).join('')}
            </div>
        `;
    },

    renderCheckItem(check) {
        const icon = this.statusIcons[check.status] || '?';
        return `
            <div class="check-item">
                <div class="check-icon ${check.status}">${icon}</div>
                <div class="check-content">
                    <div class="check-title">${check.rule_name}</div>
                    <div class="check-reference">${check.rule_reference}</div>
                    <div class="check-details">${check.details}</div>
                    ${check.evidence ? `<div class="check-evidence">Evidence: ${check.evidence}</div>` : ''}
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
