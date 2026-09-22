/**
 * Report Page — detailed analysis view for a single product.
 */
const ReportPage = {
    async mount(container, productId) {
        if (!productId) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No product selected</h3>
                    <p>Go to Products to select one.</p>
                    <a href="#products" class="btn btn-primary mt-4">View Products</a>
                </div>
            `;
            return;
        }

        container.innerHTML = '<p class="text-muted text-sm">Loading product details...</p>';

        try {
            const [product, analysis] = await Promise.all([
                API.getProduct(productId),
                API.getAnalysis(productId).catch(() => null),
            ]);

            this._render(container, product, analysis);
        } catch (error) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>Could not load product</h3>
                    <p>${error.message}</p>
                    <a href="#products" class="btn btn-outline mt-4">Back to Products</a>
                </div>
            `;
        }
    },

    unmount() {},

    _render(container, product, analysis) {
        const checks = analysis?.checks || [];
        const hasAnalysis = analysis !== null;

        // Parse extracted data
        let extracted = {};
        if (analysis?.extracted_data) {
            try { extracted = JSON.parse(analysis.extracted_data); } catch (e) {}
        }

        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h2 class="section-title">${product.name || `Product #${product.id}`}</h2>
                    <div class="text-sm text-muted mt-1">
                        Scanned: ${new Date(product.created_at).toLocaleString()}
                        ${product.barcode_data ? ` · Barcode: ${product.barcode_data} (${product.barcode_type || 'Unknown'})` : ''}
                        ${extracted['detected_category'] ? ` · <span style="color:var(--primary); font-weight:bold;">Type: ${extracted['detected_category'].toUpperCase()}</span>` : ''}
                    </div>
                </div>
                <div class="flex gap-3" style="align-items: center;">
                    <button class="btn btn-outline btn-sm" id="clear-cache-btn">Clear Temp Files</button>
                    <select id="manual-category" class="form-control form-control-sm" style="display: inline-block; width: auto; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border);">
                        <option value="auto">Auto-Detect Type</option>
                        <option value="general">General Goods</option>
                        <option value="food">Food & Edibles</option>
                        <option value="cosmetic">Cosmetics</option>
                        <option value="medicine">Medicines/Drugs</option>
                        <option value="chemical">Chemicals</option>
                        <option value="electronics">Electronics/Hardware</option>
                    </select>
                    <button class="btn btn-primary btn-sm" id="run-analysis-btn">
                        ${hasAnalysis ? 'Re-Analyze' : 'Analyze Now'}
                    </button>
                    ${hasAnalysis ? `
                        <button class="btn btn-outline btn-sm" id="dl-csv-btn" title="Export as editable CSV format">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                            </svg>
                            Export CSV
                        </button>
                        <button class="btn btn-success btn-sm" id="dl-report-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Download PDF
                        </button>
                        ${(localStorage.getItem('metroika_role') || 'public') === 'inspector' ? `
                            <button class="btn btn-warning btn-sm" id="draft-notice-btn" style="background: #dc2626; color: #fff; border-color: #b91c1c;">
                                ⚖️ Draft Show Cause Notice
                            </button>
                        ` : ''}
                    ` : ''}
                    <a href="#products" class="btn btn-outline btn-sm">← Back</a>
                </div>
            </div>

            <!-- Product Images -->
            <div class="card mb-6">
                <div class="card-header">
                    <div class="card-title">Product Images</div>
                    <div class="card-subtitle">${product.images.length} images uploaded</div>
                </div>
                <div class="product-images-carousel">
                    ${product.images.map(img => `
                        <img src="${API.getImageUrl(img.image_path)}"
                             alt="${img.label}" title="${img.label}: ${img.filename}">
                    `).join('')}
                </div>
            </div>

            ${hasAnalysis ? `
                ${this._renderAnnotatedImages(analysis)}

                <!-- Compliance Score -->
                <div class="grid-2 mb-6">
                    <div class="card" style="position: relative; overflow: hidden;">
                        ${(() => {
                            const isCompliant = (analysis.compliance_score >= 100 && (analysis.failed_checks === 0 || !analysis.failed_checks)) || product.status === 'compliant';
                            const effectiveStatus = isCompliant ? 'compliant' : product.status;
                            return `
                                <img src="${isCompliant ? 'assets/compliance_seal.png' : 'assets/violation_stamp.png'}" 
                                     alt="Status Stamp" 
                                     style="position: absolute; right: 16px; top: 16px; width: ${isCompliant ? '64px' : '96px'}; opacity: 0.85; pointer-events: none;">
                                ${ComplianceCard.renderScoreCircle(analysis.compliance_score, effectiveStatus, analysis.passed_checks, analysis.total_checks)}
                            `;
                        })()}
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Extracted Label Data</div>
                        </div>
                        <dl class="extracted-data">
                            ${this._renderExtractedField('Product Name', extracted['product_name'])}
                            ${this._renderExtractedField('Manufacturer', extracted['manufacturer_name'])}
                            ${this._renderExtractedField('Net Quantity', extracted['net_quantity'])}
                            ${this._renderExtractedField('Unit Sale Price (USP)', extracted['unit_sale_price'])}
                            ${this._renderExtractedField('Mfg. Date', extracted['manufacture_date'])}
                            ${this._renderExtractedField('MRP', extracted['mrp'])}
                            ${this._renderExtractedField('Best Before', extracted['expiry_date'])}
                            ${this._renderExtractedField('Batch No.', extracted['batch_number'])}
                            ${this._renderExtractedField('Consumer Care', extracted['consumer_care'])}
                            ${this._renderExtractedField('FSSAI License', extracted['fssai_license'])}
                            ${this._renderExtractedField('Language', extracted['language'])}
                            ${this._renderExtractedField('Ingredients', extracted['ingredients'])}
                            ${this._renderExtractedField('Allergens', extracted['allergens'])}
                            ${this._renderExtractedField('Country of Origin', extracted['country_of_origin'])}
                            ${this._renderExtractedField('Nutritional Info', extracted['nutritional_info'])}
                            ${this._renderExtractedField('Storage', extracted['storage_instructions'])}
                            ${this._renderExtractedField('Veg / Non-Veg', extracted['veg_nonveg'])}
                            ${this._renderExtractedField('Barcode/QR', extracted['barcode'])}
                        </dl>
                    </div>
                </div>

                <!-- Compliance Checks -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Detailed Compliance Checks</div>
                        <div class="card-subtitle">${checks.length} checks against Legal Metrology Rules</div>
                    </div>
                    ${ComplianceCard.renderCheckList(checks)}
                </div>
            ` : `
                <div class="card">
                    <div class="empty-state">
                        <h3>No analysis yet</h3>
                        <p>Click "Analyze Now" to run the compliance analysis.</p>
                    </div>
                </div>
            `}
        `;

        // Event handlers
        document.getElementById('dl-report-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('dl-report-btn');
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Generating...';
            try {
                const report = await API.generateReport(product.id);
                await API.downloadReport(report.filename);
                showToast('Report downloaded!', 'success');
            } catch (error) {
                showToast(`Failed: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Download PDF
                `;
            }
        });

        document.getElementById('dl-csv-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('dl-csv-btn');
            btn.disabled = true;
            try {
                await API.downloadReportCsv(product.id);
                showToast('Editable CSV report downloaded!', 'success');
            } catch (error) {
                showToast(`Failed to export CSV: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        });

        document.getElementById('draft-notice-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('draft-notice-btn');
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Drafting...';
            try {
                const notice = await API.getShowCauseNotice(product.id);
                const content = document.getElementById('notice-modal-content');
                if (content) {
                    content.innerHTML = `
                        <div class="legal-notice-doc">
                            <h2>Government of India</h2>
                            <h2>Department of Consumer Affairs · Legal Metrology Division</h2>
                            <div class="doc-subtitle">Office of the Senior Inspector of Legal Metrology</div>
                            
                            <div class="doc-meta">
                                <div><strong>Notice No:</strong> ${notice.notice_number}</div>
                                <div><strong>Date:</strong> ${notice.date_of_issue}</div>
                            </div>

                            <p><strong>To:</strong><br>
                            ${notice.recipient_name}<br>
                            <em>(Manufacturer / Packer / Importer of Subject Commodity)</em></p>

                            <p><strong>SUB: STATUTORY SHOW CAUSE NOTICE UNDER SECTION 36 OF THE LEGAL METROLOGY ACT, 2009.</strong></p>

                            <p>WHEREAS, an inspection was conducted under the Legal Metrology (Packaged Commodities) Rules, 2011 on commodity labeled <strong>"${notice.product_name}"</strong> (Product ID: #${notice.product_id}${notice.barcode ? `, Barcode: ${notice.barcode}` : ''}).</p>

                            <p>AND WHEREAS, physical and digital visual analysis established that the package fails to conform to the mandatory declarations prescribed by law, constituting <strong>${notice.total_violations} statutory offence(s)</strong>:</p>

                            <div style="margin: 16px 0;">
                                ${notice.violations.length > 0 ? notice.violations.map((v, i) => `
                                    <div class="violation-box">
                                        <strong>${i+1}. ${v.rule}</strong><br>
                                        <span><strong>Offence Finding:</strong> ${v.finding}</span><br>
                                        <span><strong>Statutory Section:</strong> <span style="color:#b91c1c; font-weight:600;">${v.statutory_provision}</span></span><br>
                                        <span><strong>Statutory Penalty:</strong> ${v.statutory_penalty}</span>
                                    </div>
                                `).join('') : '<p class="text-success">No critical violations detected. Commodity meets standard requirements.</p>'}
                            </div>

                            <p>NOW THEREFORE, in exercise of the powers conferred under Section 15 & Section 36 of the Legal Metrology Act, 2009, you are hereby directed to <strong>SHOW CAUSE within ${notice.compliance_deadline_days} days</strong> from the receipt of this notice why legal prosecution and compounding proceedings should not be initiated against your company and nominated directors under Section 39 of the Act.</p>

                            <p style="font-size: 0.82rem; color: #555;">Note: Failure to reply within the stipulated period shall be deemed that you have no explanation to offer, and ex-parte enforcement action will follow without further notice.</p>

                            <div class="sig-block">
                                <div>
                                    <strong>${notice.inspector_name}</strong><br>
                                    <span>${notice.inspector_designation}</span><br>
                                    <span>Government Seal / Signature</span>
                                </div>
                            </div>
                        </div>
                    `;
                    document.getElementById('notice-modal').style.display = 'flex';
                }
            } catch (error) {
                showToast(`Notice Generation Failed: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '⚖️ Draft Show Cause Notice';
            }
        });

        document.getElementById('clear-cache-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('clear-cache-btn');
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

        document.getElementById('run-analysis-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('run-analysis-btn');
            const catSelect = document.getElementById('manual-category');
            const category = catSelect ? catSelect.value : 'auto';
            
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Analyzing...';
            try {
                await API.analyzeProduct(product.id, false, category);
                showToast('Analysis complete!', 'success');
                // Reload page
                this.mount(container, product.id);
            } catch (error) {
                showToast(`Analysis failed: ${error.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Analyze Now';
            }
        });
    },

    _renderExtractedField(label, value) {
        return `
            <dt>${label}</dt>
            <dd>${value || '<span class="text-muted">—</span>'}</dd>
        `;
    },

    _renderAnnotatedImages(analysis) {
        if (!analysis?.ocr_annotated_images) return '';

        let paths = [];
        try {
            paths = JSON.parse(analysis.ocr_annotated_images);
        } catch (e) {
            return '';
        }

        if (!paths || paths.length === 0) return '';

        // Convert absolute paths to URLs served by the backend
        const imageHtml = paths.map((p, idx) => {
            const normalized = p.replace(/\\/g, '/');
            const uploadsIdx = normalized.indexOf('uploads/');
            const relativePath = uploadsIdx >= 0 ? normalized.substring(uploadsIdx) : normalized;
            const url = `${API.BASE_URL.replace('/api', '')}/${relativePath}?t=${Date.now()}`;
            return `
                <div style="margin-bottom: 24px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-gold);">
                            📷 View ${idx + 1} — OCR Recognition Overlay (Same Orientation)
                        </span>
                        <a href="${url}" target="_blank" style="color: var(--text-muted); font-size: 11px; text-decoration: underline;">
                            Open Full Resolution ↗
                        </a>
                    </div>
                    <img src="${url}" alt="OCR Annotated" style="max-width: 100%; width: 100%; border-radius: var(--radius-md); border: 1px solid var(--border); display: block; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
                </div>
            `;
        }).join('');

        return `
            <div class="card mb-6">
                <div class="card-header">
                    <div class="card-title">🔍 OCR Analysis — Annotated Output</div>
                    <div class="card-subtitle">Color-coded bounding boxes around detected text fields</div>
                </div>
                <div style="padding: 0 16px 8px;">
                    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; font-size: 11px;">
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(255,0,0,0.1); color: #ff4444; border: 1px solid rgba(255,0,0,0.3);">■ MRP</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(0,0,255,0.1); color: #4444ff; border: 1px solid rgba(0,0,255,0.3);">■ Net Qty</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(255,165,0,0.1); color: #ff8c00; border: 1px solid rgba(255,165,0,0.3);">■ Dates</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(0,128,0,0.1); color: #008000; border: 1px solid rgba(0,128,0,0.3);">■ Manufacturer</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(128,0,128,0.1); color: #800080; border: 1px solid rgba(128,0,128,0.3);">■ FSSAI</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(0,255,255,0.1); color: #008080; border: 1px solid rgba(0,128,128,0.3);">■ Nutritional</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(255,105,180,0.1); color: #ff69b4; border: 1px solid rgba(255,105,180,0.3);">■ Ingredients</span>
                        <span style="padding: 2px 8px; border-radius: 4px; background: rgba(0,200,0,0.1); color: #00c800; border: 1px solid rgba(0,200,0,0.3);">■ Other</span>
                    </div>
                </div>
                <div style="padding: 0 16px 16px;">
                    ${imageHtml}
                </div>
            </div>
        `;
    },
};
