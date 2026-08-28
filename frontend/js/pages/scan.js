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
                            <div class="card-title">Product Images</div>
                            <div class="card-subtitle">Upload multiple views of the product label</div>
                        </div>
                        ${ImageUploader.render('scan-upload')}
                    </div>

                    <div class="card mb-6">
                        <div class="card-header">
                            <div class="card-title">Product Name (Optional)</div>
                        </div>
                        <div class="form-group" style="margin-bottom: 16px;">
                            <input type="text" class="form-input" id="product-name-input"
                                   placeholder="e.g., Parle-G Gold Biscuits 200g">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 0; display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="skip-ai-toggle" style="width: 16px; height: 16px;">
                            <label for="skip-ai-toggle" style="margin: 0; font-weight: 500; cursor: pointer;">
                                Bypass AI Vision Check (Save API Credits / Fast Mode)
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
                                <span>📊</span> Barcode Scan
                            </div>
                            <div class="pipeline-connector" id="conn-2"></div>
                            <div class="pipeline-step" id="step-ai">
                                <span>🤖</span> AI Analysis
                            </div>
                            <div class="pipeline-connector" id="conn-3"></div>
                            <div class="pipeline-step" id="step-compliance">
                                <span>✅</span> Compliance Check
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

            const result = await API.analyzeProduct(product.id, skipAi);
            this._setStep('ai', 'done');
            this._setStep('compliance', 'done');

            // Show results
            this.analysisResult = result;
            await this._showResults(product.id, result);

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

    async _showResults(productId, result) {
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
            <div class="card mb-6">
                ${ComplianceCard.renderScoreCircle(result.compliance_score, result.status)}
                <div style="text-align: center; margin-top: 12px;">
                    <span class="text-sm text-muted">
                        ${result.passed} passed · ${result.failed} failed · ${result.warnings} warnings
                        of ${result.total_checks} checks
                    </span>
                </div>
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
};
