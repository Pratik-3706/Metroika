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
                        <button class="btn btn-success btn-sm" id="dl-report-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Download PDF Report
                        </button>
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
                    <div class="card">
                        ${ComplianceCard.renderScoreCircle(analysis.compliance_score, product.status)}
                        <div style="text-align: center; margin-top: 8px;">
                            <span class="text-sm text-muted">
                                ${analysis.passed_checks} passed · ${analysis.failed_checks} failed · ${analysis.warning_checks} warnings
                            </span>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Extracted Label Data</div>
                        </div>
                        <dl class="extracted-data">
                            ${this._renderExtractedField('Product Name', extracted['product_name'])}
                            ${this._renderExtractedField('Manufacturer', extracted['manufacturer_name'])}
                            ${this._renderExtractedField('Net Quantity', extracted['net_quantity'])}
                            ${this._renderExtractedField('Mfg. Date', extracted['manufacture_date'])}
                            ${this._renderExtractedField('MRP', extracted['mrp'])}
                            ${this._renderExtractedField('Best Before', extracted['expiry_date'])}
                            ${this._renderExtractedField('Batch No.', extracted['batch_number'])}
                            ${this._renderExtractedField('Consumer Care', extracted['consumer_care'])}
                            ${this._renderExtractedField('FSSAI License', extracted['fssai_license'])}
                            ${this._renderExtractedField('Ingredients', extracted['ingredients'])}
                            ${this._renderExtractedField('Allergens', extracted['allergens'])}
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
                    Download PDF Report
                `;
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
        const imageHtml = paths.map(p => {
            // Extract the relative path from "uploads/..." onwards
            const normalized = p.replace(/\\/g, '/');
            const uploadsIdx = normalized.indexOf('uploads/');
            const relativePath = uploadsIdx >= 0 ? normalized.substring(uploadsIdx) : normalized;
            const url = `${API.BASE_URL.replace('/api', '')}/${relativePath}`;
            return `<img src="${url}" alt="OCR Annotated" style="max-width: 100%; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 8px;">`;
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
