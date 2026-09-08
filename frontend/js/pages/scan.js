/**
 * Scan Page — multi-image upload, analysis pipeline, results display.
 */
const ScanPage = {
    analysisResult: null,
    productId: null,

    mount(container) {
        ImageUploader.reset();
        this.analysisResult = null;
        this.productId = null;

        container.innerHTML = `
            <div class="section-header">
                <h2 class="section-title">Compliance Scanner</h2>
            </div>

            <!-- Mode Selector Tabs -->
            <div class="flex gap-3 mb-6" style="border-bottom: 1px solid var(--border-color); padding-bottom: 12px;">
                <button class="btn btn-primary btn-sm" id="tab-pkg-btn">📸 Packaging Images Scan</button>
                <button class="btn btn-outline btn-sm" id="tab-ecom-btn">🌐 E-Commerce Listing Audit</button>
            </div>

            <!-- 1. Packaging Images Mode -->
            <div id="packaging-mode-container" class="grid-2">
                <!-- Left: Upload & Controls -->
                <div>
                    <div class="card mb-6">
                        <div class="card-header">
                            <div class="card-title">Product Images</div>
                            <div class="card-subtitle">Upload multiple views of the product label</div>
                        </div>
                        ${ImageUploader.render('scan-upload')}
                    </div>

                    <div class="card mb-6">
                        <div class="card-header">
                            <div class="card-title">Analysis Settings</div>
                        </div>
                        <div class="form-group" style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Name (Optional)</label>
                            <input type="text" class="form-input" id="product-name-input"
                                   placeholder="e.g., Parle-G Gold Biscuits 200g">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Category (Optional)</label>
                            <select id="scan-category-select" class="form-control" style="width: 100%;">
                                <option value="auto">Auto-Detect Type</option>
                                <option value="general">General Goods</option>
                                <option value="food">Food & Edibles</option>
                                <option value="cosmetic">Cosmetics</option>
                                <option value="medicine">Medicines/Drugs</option>
                                <option value="chemical">Chemicals</option>
                                <option value="electronics">Electronics/Hardware</option>
                            </select>
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 0; display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="skip-ai-toggle" style="width: 16px; height: 16px;">
                            <label for="skip-ai-toggle" style="margin: 0; font-weight: 500; cursor: pointer;">
                                Bypass AI Verifier (Save API Credits / Fast Mode)
                            </label>
                        </div>
                    </div>

                    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                        <button class="btn btn-outline btn-lg" id="clear-btn" style="flex: 1;">
                            Clear Form
                        </button>
                        <button class="btn btn-primary btn-lg" id="analyze-btn" style="flex: 2;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                                <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/>
                                <circle cx="12" cy="13" r="4"/>
                            </svg>
                            Analyze for Compliance
                        </button>
                    </div>

                    <!-- Pipeline Progress -->
                    <div id="pipeline-progress" style="display: none;">
                        <div class="pipeline-steps">
                            <div class="pipeline-step" id="step-upload">
                                <span>📤</span> Upload
                            </div>
                            <div class="pipeline-connector" id="conn-1"></div>
                            <div class="pipeline-step" id="step-barcode">
                                <span>📊</span> Barcode + OCR
                            </div>
                            <div class="pipeline-connector" id="conn-2"></div>
                            <div class="pipeline-step" id="step-ai">
                                <span>⚖️</span> Rule Engine
                            </div>
                            <div class="pipeline-connector" id="conn-3"></div>
                            <div class="pipeline-step" id="step-compliance">
                                <span>🤖</span> AI Verify
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right: Results -->
                <div id="results-panel">
                    <div class="card">
                        <div class="empty-state">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                                <polyline points="14 2 14 8 20 8"/>
                                <line x1="16" y1="13" x2="8" y2="13"/>
                                <line x1="16" y1="17" x2="8" y2="17"/>
                            </svg>
                            <h3>Upload images to begin</h3>
                            <p>Upload product label images and click "Analyze" to check compliance with Legal Metrology Rules.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 2. E-Commerce Listing Audit Mode -->
            <div id="ecommerce-mode-container" class="grid-2" style="display: none;">
                <div>
                    <div class="card mb-6">
                        <div class="card-header">
                            <div class="card-title">E-Commerce Product Listing Metadata</div>
                            <div class="card-subtitle">Mandatory declarations under Legal Metrology Rule 6(10)</div>
                        </div>
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Title *</label>
                            <input type="text" class="form-input" id="ecom-title" placeholder="e.g. Fortune Sunlite Refined Sunflower Oil, 1L Pouch" required>
                        </div>
                        <div class="grid-2" style="gap: 12px; margin-bottom: 12px;">
                            <div class="form-group">
                                <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">MRP (₹) *</label>
                                <input type="text" class="form-input" id="ecom-mrp" placeholder="e.g. ₹ 165.00 (incl. of all taxes)">
                            </div>
                            <div class="form-group">
                                <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Net Quantity *</label>
                                <input type="text" class="form-input" id="ecom-qty" placeholder="e.g. 1 L or 910 g">
                            </div>
                        </div>
                        <div class="grid-2" style="gap: 12px; margin-bottom: 12px;">
                            <div class="form-group">
                                <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Country of Origin *</label>
                                <input type="text" class="form-input" id="ecom-coo" placeholder="e.g. India">
                            </div>
                            <div class="form-group">
                                <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Category</label>
                                <select id="ecom-category" class="form-control" style="width: 100%;">
                                    <option value="food" selected>Food & Edibles</option>
                                    <option value="general">General Goods</option>
                                    <option value="cosmetic">Cosmetics</option>
                                    <option value="electronics">Electronics</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Manufacturer / Packer Name & Full Address *</label>
                            <input type="text" class="form-input" id="ecom-mfr" placeholder="e.g. Adani Wilmar Limited, Fortune House, Ahmedabad 380009, Gujarat">
                        </div>
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Consumer Care Details (Toll-Free / Email) *</label>
                            <input type="text" class="form-input" id="ecom-care" placeholder="e.g. Care: 1800 233 9999, care@adaniwilmar.in">
                        </div>
                        <div class="form-group" style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Description / Ingredients List</label>
                            <textarea class="form-input" id="ecom-desc" rows="3" placeholder="Paste full product details, ingredients, or specifications..."></textarea>
                        </div>
                        <button class="btn btn-primary btn-lg" id="ecom-audit-btn" style="width: 100%;">
                            ⚖️ Audit E-Commerce Listing (Rule 6(10))
                        </button>
                    </div>
                </div>
                <div id="ecom-results-panel">
                    <div class="card">
                        <div class="empty-state">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="2" y1="12" x2="22" y2="12"></line>
                                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                            </svg>
                            <h3>Fill listing details to audit</h3>
                            <p>Rule 6(10) requires digital marketplace listings to declare manufacturer, country of origin, net quantity, MRP, and consumer care.</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Initialize uploader
        ImageUploader.init('scan-upload');

        // Tab Switching
        const tabPkgBtn = document.getElementById('tab-pkg-btn');
        const tabEcomBtn = document.getElementById('tab-ecom-btn');
        const pkgContainer = document.getElementById('packaging-mode-container');
        const ecomContainer = document.getElementById('ecommerce-mode-container');

        tabPkgBtn?.addEventListener('click', () => {
            tabPkgBtn.className = 'btn btn-primary btn-sm';
            tabEcomBtn.className = 'btn btn-outline btn-sm';
            pkgContainer.style.display = 'grid';
            ecomContainer.style.display = 'none';
        });

        tabEcomBtn?.addEventListener('click', () => {
            tabEcomBtn.className = 'btn btn-primary btn-sm';
            tabPkgBtn.className = 'btn btn-outline btn-sm';
            pkgContainer.style.display = 'none';
            ecomContainer.style.display = 'grid';
        });

        // E-Commerce Audit Button
        document.getElementById('ecom-audit-btn')?.addEventListener('click', async () => {
            const title = document.getElementById('ecom-title')?.value.trim();
            if (!title) {
                showToast('Please enter a product title.', 'error');
                return;
            }

            const btn = document.getElementById('ecom-audit-btn');
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Auditing Listing...';

            try {
                const payload = {
                    title,
                    mrp: document.getElementById('ecom-mrp')?.value.trim(),
                    net_quantity: document.getElementById('ecom-qty')?.value.trim(),
                    country_of_origin: document.getElementById('ecom-coo')?.value.trim(),
                    manufacturer: document.getElementById('ecom-mfr')?.value.trim(),
                    consumer_care: document.getElementById('ecom-care')?.value.trim(),
                    category: document.getElementById('ecom-category')?.value,
                    description: document.getElementById('ecom-desc')?.value.trim(),
                };

                const res = await API.auditEcommerceListing(payload);
                const panel = document.getElementById('ecom-results-panel');
                if (panel) {
                    panel.innerHTML = `
                        <div class="card mb-6">
                            ${ComplianceCard.renderScoreCircle(res.compliance_score, res.status)}
                            <div style="text-align: center; margin-top: 8px;">
                                <span class="text-sm text-muted">
                                    ${res.passed} passed · ${res.failed} failed · ${res.warnings} warnings
                                </span>
                            </div>
                        </div>
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">E-Commerce Listing Rule Checks</div>
                                <div class="card-subtitle">${res.checks.length} checks under Rule 6(10)</div>
                            </div>
                            ${ComplianceCard.renderCheckList(res.checks)}
                        </div>
                    `;
                }
                showToast('E-Commerce listing audit complete!', 'success');
            } catch (err) {
                showToast(`Audit failed: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '⚖️ Audit E-Commerce Listing (Rule 6(10))';
            }
        });

        // Buttons
        document.getElementById('analyze-btn')?.addEventListener('click', () => this._runAnalysis());
        document.getElementById('clear-btn')?.addEventListener('click', () => {
            this.mount(document.getElementById('main-content'));
        });
    },

    unmount() {
        ImageUploader.reset();
    },

    _renderScanningLoader(skipAi = false) {
        const resultsPanel = document.getElementById('results-panel');
        if (!resultsPanel) return;

        resultsPanel.innerHTML = `
            <div class="card scanning-hud-card" id="scanning-hud-card">
                <div class="scanner-header">
                    <div class="scanner-live-badge">
                        <span class="live-dot"></span>
                        <span>ANALYSIS IN PROGRESS</span>
                    </div>
                    <div class="scanner-engine-tag">
                        ${skipAi ? '⚡ Fast Mode (Local Rule Engine)' : '🤖 Multilingual OCR + Vision AI'}
                    </div>
                </div>
                
                <div class="scanner-viewport">
                    <div class="scanner-laser-beam"></div>
                    <div class="scanner-grid-overlay"></div>
                    <div class="scanner-corner corner-tl"></div>
                    <div class="scanner-corner corner-tr"></div>
                    <div class="scanner-corner corner-bl"></div>
                    <div class="scanner-corner corner-br"></div>
                    
                    <div class="scanner-center-content">
                        <div class="logo-wrapper compact" style="margin: 0 auto 10px auto;">
                            <div class="glow-bg" style="width: 140px; height: 140px;"></div>
                            <img class="layer layer-glow" src="assets/loading_animation/last_layer.png" alt="">
                            <img class="layer layer-middle" src="assets/loading_animation/middle_layer.png" alt="">
                            <img class="layer layer-top" src="assets/loading_animation/top_layer.png" alt="">
                        </div>
                        <div class="scanner-main-status" id="scanner-dynamic-title">Uploading Packaging Images...</div>
                        <div class="scanner-sub-status" id="scanner-dynamic-sub">Validating packaging facets and orientation...</div>
                    </div>
                </div>

                <div class="scanner-footer">
                    <div class="scanner-progress-bar-wrap">
                        <div class="scanner-progress-bar-fill"></div>
                    </div>
                    <div class="scanner-milestones" id="scanner-milestones">
                        <span class="milestone-item active" id="m-upload">📤 Upload</span>
                        <span class="milestone-arrow">→</span>
                        <span class="milestone-item" id="m-ocr">⚡ PaddleOCR</span>
                        <span class="milestone-arrow">→</span>
                        <span class="milestone-item" id="m-rules">⚖️ Rules</span>
                        <span class="milestone-arrow">→</span>
                        <span class="milestone-item" id="m-ai">${skipAi ? '⚡ Fast' : '🤖 AI Verify'}</span>
                    </div>
                </div>
            </div>
        `;
    },

    async _runAnalysis() {
        if (ImageUploader.files.length === 0) {
            showToast('Please upload at least one product image.', 'error');
            return;
        }

        const btn = document.getElementById('analyze-btn');
        const pipeline = document.getElementById('pipeline-progress');
        const resultsPanel = document.getElementById('results-panel');
        const skipAi = document.getElementById('skip-ai-toggle')?.checked || false;

        // Render animated holographic scanner loader
        this._renderScanningLoader(skipAi);

        // Disable button
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Analyzing...';
        pipeline.style.display = 'block';

        // Stages ticker to dynamically animate progress while waiting for backend
        const pipelineStages = [
            { title: "Scanning Barcode & QR Code Matrix...", sub: "Extracting GTIN-13/EAN and origin identifiers", step: "barcode", m: "m-ocr" },
            { title: "Running Multilingual PaddleOCR (GPU)...", sub: "Detecting Hindi (Devanagari), Tamil, Telugu, and English text", step: "barcode", m: "m-ocr" },
            { title: "Extracting Bilingual Label Declarations...", sub: "Recognizing mandatory markings, MRP, net quantity, and addresses", step: "ai", m: "m-rules" },
            { title: "Validating Legal Metrology Rules, 2011...", sub: "Evaluating Rules 6, 7, 8, 9, 10 for packaged commodities", step: "ai", m: "m-rules" },
            { title: skipAi ? "Finalizing Rule Compliance..." : "AI Vision Verifier Cross-Referencing...", sub: skipAi ? "Synthesizing statutory check findings" : "Comparing physical packaging images against table data and fixing attributes", step: "compliance", m: "m-ai" },
            { title: "Compiling Compliance Score & Report...", sub: "Finalizing statutory scoring and audit results", step: "compliance", m: "m-ai" },
        ];

        let stageIdx = 0;
        const stageInterval = setInterval(() => {
            if (stageIdx < pipelineStages.length) {
                const stage = pipelineStages[stageIdx];
                const titleEl = document.getElementById('scanner-dynamic-title');
                const subEl = document.getElementById('scanner-dynamic-sub');
                if (titleEl) titleEl.textContent = stage.title;
                if (subEl) subEl.textContent = stage.sub;

                this._setStep(stage.step, 'active');

                document.querySelectorAll('.milestone-item').forEach(el => el.classList.remove('active'));
                const activeMilestone = document.getElementById(stage.m);
                if (activeMilestone) activeMilestone.classList.add('active');

                stageIdx++;
            }
        }, 1600);

        try {
            // Step 1: Upload
            this._setStep('upload', 'active');
            const productName = document.getElementById('product-name-input')?.value || '';
            const formData = ImageUploader.getFormData(productName);
            const product = await API.createProduct(formData);
            this.productId = product.id;
            this._setStep('upload', 'done');

            // Clear images from the queue
            ImageUploader.reset();
            ImageUploader.renderPreviews('scan-upload');
            if (document.getElementById('product-name-input')) {
                document.getElementById('product-name-input').value = '';
            }

            const categorySelect = document.getElementById('scan-category-select');
            const category = categorySelect ? categorySelect.value : 'auto';

            // Run backend compliance analysis (OCR + Rules + AI Verifier)
            const result = await API.analyzeProduct(product.id, skipAi, category);

            clearInterval(stageInterval);
            this._setStep('barcode', 'done');
            this._setStep('ai', 'done');
            this._setStep('compliance', 'done');

            // Show results
            this.analysisResult = result;
            await this._showResults(product.id, result, skipAi);

            showToast(`Analysis complete! Score: ${result.compliance_score.toFixed(0)}%`,
                result.status === 'compliant' ? 'success' : 'error');

        } catch (error) {
            clearInterval(stageInterval);
            console.error('Analysis failed:', error);
            showToast(`Analysis failed: ${error.message}`, 'error');

            if (resultsPanel) {
                resultsPanel.innerHTML = `
                    <div class="card">
                        <div class="empty-state">
                            <h3 style="color: var(--danger);">Analysis Failed</h3>
                            <p>${error.message || 'An error occurred while analyzing the product.'}</p>
                            <button class="btn btn-primary mt-4" onclick="ScanPage.mount(document.getElementById('main-content'))">Try Again</button>
                        </div>
                    </div>
                `;
            }

            // Mark current step as error
            ['upload', 'barcode', 'ai', 'compliance'].forEach(step => {
                const el = document.getElementById(`step-${step}`);
                if (el && el.classList.contains('active')) {
                    el.classList.remove('active');
                    el.classList.add('error');
                }
            });
        } finally {
            clearInterval(stageInterval);
            btn.disabled = false;
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                    <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/>
                    <circle cx="12" cy="13" r="4"/>
                </svg>
                Analyze for Compliance
            `;
        }
    },

    _setStep(step, state) {
        const el = document.getElementById(`step-${step}`);
        if (el) {
            el.classList.remove('active', 'done', 'error');
            el.classList.add(state);
        }
        // Update connector
        const stepOrder = ['upload', 'barcode', 'ai', 'compliance'];
        const idx = stepOrder.indexOf(step);
        if (idx > 0 && state === 'done') {
            const conn = document.getElementById(`conn-${idx}`);
            if (conn) conn.classList.add('done');
        }
    },

    async _showResults(productId, result, skipAi = false) {
        const panel = document.getElementById('results-panel');
        if (!panel) return;

        // Load full analysis
        let analysis;
        try {
            analysis = await API.getAnalysis(productId);
        } catch (e) {
            analysis = null;
        }

        const checks = analysis?.checks || [];

        panel.innerHTML = `
            ${skipAi ? `
            <div style="background-color: rgba(255, 193, 7, 0.1); color: #ffb800; padding: 16px; border-radius: 12px; margin-bottom: 16px; border: 1px solid rgba(255, 193, 7, 0.3);">
                <strong>⚠️ AI Evaluator Bypassed</strong><br>
                This score was generated purely by the local OCR and Regex Rule Engine. The AI verifier was skipped, meaning any text missed by OCR (due to curved bottles, bad lighting, etc.) was not double-checked or corrected.
            </div>` : ''}
            <div class="card mb-6">
                ${ComplianceCard.renderScoreCircle(result.compliance_score, result.status, result.passed, result.total_checks)}
                <div style="text-align: center; margin-top: 16px; display: flex; gap: 8px; justify-content: center;">
                    <button class="btn btn-success btn-sm" id="generate-report-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Generate PDF Report
                    </button>
                    <a href="#report/${productId}" class="btn btn-outline btn-sm">View Details</a>
                </div>
            </div>
            ${this._renderAnnotatedImages(analysis)}
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Compliance Checks</div>
                    <div class="card-subtitle">${checks.length} checks performed</div>
                </div>
                ${ComplianceCard.renderCheckList(checks)}
            </div>
        `;

        // Report generation
        document.getElementById('generate-report-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('generate-report-btn');
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Generating...';
            try {
                const report = await API.generateReport(productId);
                await API.downloadReport(report.filename);
                showToast('Report downloaded!', 'success');
            } catch (error) {
                showToast(`Report generation failed: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    Generate PDF Report
                `;
            }
        });
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
                    <div class="card-subtitle">Color-coded bounding boxes show detected text</div>
                </div>
                <div style="padding: 0 16px 8px;">
                    <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; font-size: 10px;">
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(255,0,0,0.1); color: #ff4444; border: 1px solid rgba(255,0,0,0.3);">■ MRP</span>
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(0,0,255,0.1); color: #4444ff; border: 1px solid rgba(0,0,255,0.3);">■ Net Qty</span>
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(255,165,0,0.1); color: #ff8c00; border: 1px solid rgba(255,165,0,0.3);">■ Dates</span>
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(0,128,0,0.1); color: #008000; border: 1px solid rgba(0,128,0,0.3);">■ Mfr</span>
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(128,0,128,0.1); color: #800080; border: 1px solid rgba(128,0,128,0.3);">■ FSSAI</span>
                        <span style="padding: 2px 6px; border-radius: 3px; background: rgba(0,200,0,0.1); color: #00c800; border: 1px solid rgba(0,200,0,0.3);">■ Other</span>
                    </div>
                </div>
                <div style="padding: 0 16px 16px;">
                    ${imageHtml}
                </div>
            </div>
        `;
    },
};
