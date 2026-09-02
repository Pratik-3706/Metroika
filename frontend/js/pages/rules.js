/**
 * Rules Reference Page — displays all Legal Metrology rules checked by the system.
 */
const RulesPage = {
    mount(container) {
        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h2 class="section-title">Legal Metrology Rules Reference</h2>
                    <p class="text-sm text-muted mt-1">
                        Legal Metrology (Packaged Commodities) Rules, 2011 — with amendments up to 2026
                    </p>
                </div>
            </div>

            <!-- Font Size Requirements -->
            <div class="card mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">Font Size Requirements — Rule 7 (Table I)</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">
                            Minimum height of numerals and letters based on Principal Display Panel area
                        </div>
                    </div>
                </div>
                <table class="font-table">
                    <thead>
                        <tr>
                            <th>PDP Area (cm²)</th>
                            <th>Minimum Height of Characters</th>
                            <th>Minimum Width</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Up to 50 cm²</td>
                            <td>1 mm</td>
                            <td>≥ ⅓ of height</td>
                        </tr>
                        <tr>
                            <td>50 – 100 cm²</td>
                            <td>2 mm</td>
                            <td>≥ ⅓ of height</td>
                        </tr>
                        <tr>
                            <td>100 – 500 cm²</td>
                            <td>3 mm</td>
                            <td>≥ ⅓ of height</td>
                        </tr>
                        <tr>
                            <td>Above 500 cm²</td>
                            <td>4 mm</td>
                            <td>≥ ⅓ of height</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- MRP Format -->
            <div class="card mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">MRP Declaration Format — Rule 6(1)(e)</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">Maximum Retail Price format requirements</div>
                    </div>
                </div>
                <div style="padding: 16px 0;">
                    <div style="padding: 16px 20px; background: var(--info-bg); border: 1px solid rgba(59,130,246,0.2); border-radius: var(--radius-md); margin-bottom: 12px;">
                        <p class="text-sm" style="color: var(--info);">
                            <strong>Required Format:</strong><br>
                            <code style="font-family: var(--font-mono); font-size: 0.85rem;">
                                MRP ₹ _____ (inclusive of all taxes)
                            </code>
                        </p>
                    </div>
                    <ul style="list-style: disc; padding-left: 20px; color: var(--text-secondary); font-size: 0.85rem; line-height: 1.8;">
                        <li>MRP must be inclusive of ALL taxes</li>
                        <li>Must use the term "MRP" or "M.R.P."</li>
                        <li>Must include "inclusive of all taxes" or equivalent wording</li>
                        <li>Currency must be in Indian Rupees (₹ or Rs.)</li>
                        <li>No product shall be sold above the MRP</li>
                    </ul>
                </div>
            </div>

            <!-- All Compliance Rules -->
            <div class="card mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">Mandatory Declarations — Rule 6</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">All mandatory declarations checked by Metroika</div>
                    </div>
                </div>
            </div>

            <div class="rules-grid">
                ${this._getRules().map(rule => `
                    <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div class="font-mono text-sm text-blue-600 dark:text-blue-400 font-semibold">${rule.id}</div>
                        <div class="font-medium text-gray-900 dark:text-white">${rule.name}</div>
                        <div class="rule-ref">${rule.reference}</div>
                        <div class="text-sm text-gray-600 dark:text-gray-400 mt-2">${rule.description}</div>
                        <div style="margin-top: 10px;">
                            <span class="check-severity ${rule.severity}">${rule.severity}</span>
                        </div>
                    </div>
                `).join('')}
            </div>

            <!-- Additional Info -->
            <div class="card mt-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">Key Amendments (2024–2026)</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">Recent updates to the rules</div>
                    </div>
                </div>
                <ul style="list-style: disc; padding-left: 20px; color: var(--text-secondary); font-size: 0.85rem; line-height: 2;">
                    <li><strong>E-Commerce (July 2026):</strong> E-commerce entities must provide searchable/sortable filters for "Country of Origin" on imported products. — Rule 6(10A)</li>
                    <li><strong>Medical Devices (2025):</strong> Harmonized with Medical Devices Rules, 2017. Font size/dimension standards of Medical Devices Rules take precedence.</li>
                    <li><strong>Registration (2026):</strong> Registration certificates now valid indefinitely. Annual online update of details required.</li>
                    <li><strong>Accountability (2026):</strong> Companies must specify the name of the Director responsible for compliance.</li>
                    <li><strong>Standard Pack Sizes:</strong> Schedule II (standard pack sizes) was omitted in 2021. Manufacturers no longer restricted to specific pack sizes.</li>
                </ul>
            </div>
        `;
    },

    unmount() {},

    _getRules() {
        return [
            {
                id: 'R6_1_A_NAME',
                name: 'Manufacturer / Packer / Importer Name',
                reference: 'Rule 6(1)(a)',
                description: 'The name of the manufacturer, or the packer, or the importer shall be declared on the package.',
                severity: 'critical',
            },
            {
                id: 'R6_1_A_ADDR',
                name: 'Manufacturer / Packer / Importer Address',
                reference: 'Rule 6(1)(a)',
                description: 'The complete address of the manufacturer, packer, or importer must be declared.',
                severity: 'critical',
            },
            {
                id: 'R6_1_B',
                name: 'Common / Generic Name of Commodity',
                reference: 'Rule 6(1)(b)',
                description: 'The common or generic name of the commodity contained in the package shall be mentioned.',
                severity: 'high',
            },
            {
                id: 'R6_1_C',
                name: 'Net Quantity',
                reference: 'Rule 6(1)(c)',
                description: 'The net quantity in terms of standard units of weight, measure or number.',
                severity: 'critical',
            },
            {
                id: 'R6_1_D',
                name: 'Month & Year of Manufacture',
                reference: 'Rule 6(1)(d)',
                description: 'The month and year of manufacture, packing, or import.',
                severity: 'high',
            },
            {
                id: 'R6_1_E',
                name: 'Maximum Retail Price (MRP)',
                reference: 'Rule 6(1)(e)',
                description: 'Retail sale price inclusive of all taxes, declared as "MRP Rs. ____ (inclusive of all taxes)".',
                severity: 'critical',
            },
            {
                id: 'R6_1_F',
                name: 'Consumer Care Details',
                reference: 'Rule 6(1)(f)',
                description: 'Name, address, telephone number and email for consumer complaints.',
                severity: 'high',
            },
            {
                id: 'R6_1_G',
                name: 'Country of Origin',
                reference: 'Rule 6(1)(g)',
                description: 'For imported products, the country of origin must be declared.',
                severity: 'high',
            },
            {
                id: 'MRP_FMT',
                name: 'MRP Format Compliance',
                reference: 'Rule 6(1)(e)',
                description: 'MRP must follow the format: "MRP Rs. ____ (inclusive of all taxes)".',
                severity: 'high',
            },
            {
                id: 'DATE_FMT',
                name: 'Date Format Compliance',
                reference: 'Rule 6(1)(d)',
                description: 'Date should be in MM/YYYY or "Month YYYY" format.',
                severity: 'medium',
            },
            {
                id: 'R7_FONT',
                name: 'Font Size Compliance',
                reference: 'Rule 7 (Table I)',
                description: 'Minimum height of numerals/letters based on Principal Display Panel area.',
                severity: 'medium',
            },
            {
                id: 'R8_PDP',
                name: 'Principal Display Panel',
                reference: 'Rule 8',
                description: 'All declarations must appear on the Principal Display Panel.',
                severity: 'medium',
            },
            {
                id: 'R6_LANG',
                name: 'Language of Declarations',
                reference: 'Rule 6(3)',
                description: 'Declarations shall be in English or Hindi.',
                severity: 'medium',
            },
            {
                id: 'BARCODE',
                name: 'Barcode / QR Code',
                reference: 'Industry Standard',
                description: 'Valid barcode or QR code for traceability.',
                severity: 'low',
            },
            {
                id: 'R6_UNIT',
                name: 'Unit Sale Price',
                reference: 'Rule 6(2)',
                description: 'Unit sale price for consumer comparison.',
                severity: 'low',
            },
        ];
    },
};
