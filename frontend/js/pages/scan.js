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
                <h2 class="section-title">Scan Packaged Commodity</h2>
            </div>

            <div class="grid-2">
                <!-- Left: Upload & Controls -->
                <div>
                    <div class="card mb-6">
                        <div class="card-header">
                            <div>
                                <div class="card-title">Product Images</div>
                                <div class="card-subtitle">Upload multiple views of the product label</div>
                            </div>
                        </div>
                        ${ImageUploader.render('scan-upload')}
                    </div>

                    <div class="card mb-6">
                        <div class="card-header">
                            <div class="card-title">Analysis Settings</div>
                        </div>
                        <div class="form-group" style="margin-bottom: 14px;">
                            <label class="form-label">Product Name (Optional)</label>
                            <input type="text" class="form-input" id="product-name-input"
                                   placeholder="e.g., Parle-G Gold Biscuits 200g">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 14px;">
                            <label class="form-label">Product Category (Optional)</label>
                            <select id="scan-category-select" class="form-control">
                                <option value="auto">Auto-Detect Type</option>
                                <option value="general">General Goods</option>
                                <option value="food">Food & Edibles</option>
                                <option value="cosmetic">Cosmetics</option>
                                <option value="medicine">Medicines/Drugs</option>
                                <option value="chemical">Chemicals</option>
                                <option value="electronics">Electronics/Hardware</option>
                            </select>
                        </div>
                        
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="skip-ai-toggle" style="width: 14px; height: 14px; accent-color: var(--accent);">
                            <label for="skip-ai-toggle" style="margin: 0; font-size: 0.82rem; font-weight: 500; cursor: pointer; color: var(--text-secondary);">
                                Bypass AI Verifier (Save API Credits / Fast Mode)
                            </label>
                        </div>
                    </div>

                    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                        <button class="btn btn-outline btn-lg" id="clear-btn" style="flex: 1;">
                            Clear Form
                        </button>
                        <button class="btn btn-primary btn-lg" id="analyze-btn" style="flex: 2;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
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
        `;

        // Initialize uploader
        ImageUploader.init('scan-upload');

        // Buttons
        document.getElementById('analyze-btn')?.addEventListener('click', () => this._runAnalysis());
        document.getElementById('clear-btn')?.addEventListener('click', () => {
            this.mount(document.getElementById('main-content'));
        });
    },

    unmount() {
        ImageUploader.reset();
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

        // Clear the results panel on the right side while the new scan runs
        if (resultsPanel) {
            resultsPanel.innerHTML = `
                <div class="card">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                        </svg>
                        <h3>Analyzing Product...</h3>
                        <p>Please wait while the compliance engine processes your images.</p>
                    </div>
                </div>
            `;
        }

        // Disable button
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Analyzing...';
        pipeline.style.display = 'block';

        try {
            // Step 1: Upload
            this._setStep('upload', 'active');
            const productName = document.getElementById('product-name-input')?.value || '';
            const formData = ImageUploader.getFormData(productName);
            const product = await API.createProduct(formData);
            this.productId = product.id;
            this._setStep('upload', 'done');
            
            // Clear the images from the queue so the user can see it's ready for the next batch
            ImageUploader.reset();
            ImageUploader.renderPreviews('scan-upload');
            if (document.getElementById('product-name-input')) {
                document.getElementById('product-name-input').value = '';
            }

            // Step 2-4: Analysis (server-side pipeline)
            this._setStep('barcode', 'active');
            setTimeout(() => {
                this._setStep('barcode', 'done');
                if (!skipAi) {
                    this._setStep('ai', 'active');
                } else {
                    this._setStep('ai', 'done');
                    const aiStep = document.getElementById('step-ai');
                    if (aiStep) aiStep.style.opacity = '0.5';
                }
            }, 500);

            const categorySelect = document.getElementById('scan-category-select');
            const category = categorySelect ? categorySelect.value : 'auto';
            const result = await API.analyzeProduct(product.id, skipAi, category);
            
            this._setStep('ai', 'done');
            this._setStep('compliance', 'done');

            // Show results
            this.analysisResult = result;
            await this._showResults(product.id, result, skipAi);

            showToast(`Analysis complete! Score: ${result.compliance_score.toFixed(0)}%`,
                result.status === 'compliant' ? 'success' : 'error');

        } catch (error) {
            console.error('Analysis failed:', error);
            showToast(`Analysis failed: ${error.message}`, 'error');

            // Mark current step as error
            ['upload', 'barcode', 'ai', 'compliance'].forEach(step => {
                const el = document.getElementById(`step-${step}`);
                if (el && el.classList.contains('active')) {
                    el.classList.remove('active');
                    el.classList.add('error');
                }
            });
        } finally {
            btn.disabled = false;
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
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
            <div style="background: var(--warning-bg); color: var(--warning); padding: 14px; border-radius: var(--radius-md); margin-bottom: 14px; border: 1px solid var(--warning-border); font-size: 0.82rem; line-height: 1.5;">
                <strong>⚠ AI Evaluator Bypassed</strong><br>
                This score was generated purely by the local OCR and Regex Rule Engine. The AI verifier was skipped, meaning any text missed by OCR (due to curved bottles, bad lighting, etc.) was not double-checked or corrected.
            </div>` : ''}
            <div class="card mb-6">
                ${ComplianceCard.renderScoreCircle(result.compliance_score, result.status)}
                <div style="text-align: center; margin-top: 10px;">
                    <span class="text-sm text-muted">
                        ${result.passed} passed · ${result.failed} failed · ${result.warnings} warnings
                        of ${result.total_checks} checks
                    </span>
                </div>
                <div style="text-align: center; margin-top: 14px; display: flex; gap: 8px; justify-content: center;">
                    <button class="btn btn-success btn-sm" id="generate-report-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
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
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
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

        const imageHtml = paths.map(p => {
            const normalized = p.replace(/\\/g, '/');
            const uploadsIdx = normalized.indexOf('uploads/');
            const relativePath = uploadsIdx >= 0 ? normalized.substring(uploadsIdx) : normalized;
            const url = `${API.BASE_URL.replace('/api', '')}/${relativePath}`;
            return `<img src="${url}" alt="OCR Annotated" style="max-width: 100%; border-radius: var(--radius-md); border: 1px solid var(--border); margin-bottom: 8px;">`;
        }).join('');

        return `
            <div class="card mb-6">
                <div class="card-header">
                    <div>
                        <div class="card-title">OCR Analysis — Annotated Output</div>
                        <div class="card-subtitle">Color-coded bounding boxes show detected text</div>
                    </div>
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; font-size: 0.68rem;">
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(185,28,28,0.08); color: #b91c1c; border: 1px solid rgba(185,28,28,0.2);">■ MRP</span>
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(30,96,145,0.08); color: #1e6091; border: 1px solid rgba(30,96,145,0.2);">■ Net Qty</span>
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(180,83,9,0.08); color: #b45309; border: 1px solid rgba(180,83,9,0.2);">■ Dates</span>
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(45,106,79,0.08); color: #2d6a4f; border: 1px solid rgba(45,106,79,0.2);">■ Mfr</span>
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(128,0,128,0.08); color: #800080; border: 1px solid rgba(128,0,128,0.2);">■ FSSAI</span>
                    <span style="padding: 2px 6px; border-radius: 3px; background: rgba(90,90,90,0.08); color: #5a5a5a; border: 1px solid rgba(90,90,90,0.2);">■ Other</span>
                </div>
                <div>
                    ${imageHtml}
                </div>
            </div>
        `;
    },
};
