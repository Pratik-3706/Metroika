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
                    ${check.statutory_penalty ? `<div class="penalty-tag">⚖️ ${check.statutory_penalty}</div>` : ''}
                </div>
                <span class="check-severity ${check.severity}">${check.severity}</span>
            </div>
        `;
    },

    renderScoreCircle(score, status, passedCount = null, totalCount = null) {
        const roundedScore = Math.round(score || 0);
        const nonCompliantPct = Math.max(0, 100 - roundedScore);

        // If score is 100% and 0 violations, it is statutorily compliant (avoid displaying red non-compliant)
        let effectiveStatus = status;
        if (roundedScore >= 100 && (passedCount === null || totalCount === null || Number(passedCount) >= Number(totalCount))) {
            effectiveStatus = 'compliant';
        }
        
        // Gauge stroke circumference (2 * PI * 64 ≈ 402)
        const circumference = 402;
        const offset = Math.max(0, circumference - (circumference * roundedScore) / 100);

        return `
            <div class="compliance-score-dashboard-card">
                <div class="gauge-wrap">
                    <svg class="score-gauge-svg" viewBox="0 0 160 160">
                        <circle cx="80" cy="80" r="64" class="gauge-track"/>
                        <circle cx="80" cy="80" r="64" class="gauge-fill ${effectiveStatus}" 
                                stroke-dasharray="${circumference}" 
                                stroke-dashoffset="${offset}"/>
                    </svg>
                    <div class="gauge-center-content">
                        <span class="gauge-number">${roundedScore}%</span>
                        <span class="gauge-sub">RULES PASSED</span>
                    </div>
                </div>
                
                <div class="score-audit-verdict">
                    ${effectiveStatus === 'compliant' ? `
                        <div class="verdict-pill compliant">
                            <span class="verdict-dot"></span>
                            <span>STATUTORILY COMPLIANT · APPROVED</span>
                        </div>
                        <div class="verdict-summary">
                            <div class="verdict-tags-row">
                                <span class="pass-tag">✓ 100% Rules Passed</span>
                                <span class="zero-tag">0 Violations</span>
                            </div>
                            <p class="verdict-note">All mandatory declarations under Legal Metrology Rules, 2011 are present and fully compliant.</p>
                        </div>
                    ` : effectiveStatus === 'non_compliant' ? `
                        <div class="verdict-pill non_compliant">
                            <span class="verdict-dot"></span>
                            <span>NON-COMPLIANT · DEFECTS DETECTED</span>
                        </div>
                        <div class="verdict-summary">
                            <div class="verdict-tags-row">
                                <span class="pass-tag">✓ ${roundedScore}% Rules Passed (${passedCount ? `${passedCount} of ${totalCount}` : 'Passed'})</span>
                                <span class="fail-tag">✕ ${nonCompliantPct}% Failed (${totalCount && passedCount ? `${totalCount - passedCount} Violations` : 'Defects Found'})</span>
                            </div>
                            <p class="verdict-note">Under Rule 6, packaged goods require <strong>100% compliance</strong>. A single violation renders the product legally Non-Compliant.</p>
                        </div>
                    ` : `
                        <div class="verdict-pill warning">
                            <span class="verdict-dot"></span>
                            <span>ADVISORY / WARNING</span>
                        </div>
                        <div class="verdict-summary">
                            <div class="verdict-tags-row">
                                <span class="pass-tag">✓ ${roundedScore}% Rules Passed</span>
                                <span class="warn-tag">⚠ Advisory Warnings</span>
                            </div>
                            <p class="verdict-note">Statutory declarations are detected but contain formatting or clarity warnings.</p>
                        </div>
                    `}
                </div>
            </div>
        `;
    },

    renderStatusBadge(status) {
        const labels = {
            compliant: '100% Compliant',
            non_compliant: 'Non-Compliant',
            warning: 'Warning / Advisory',
            pending: 'Pending Audit',
        };
        const text = labels[status] || status.replace('_', '-');
        return `
            <span class="status-badge ${status}">
                <span class="status-dot"></span>
                <span>${text}</span>
            </span>
        `;
    },
};
