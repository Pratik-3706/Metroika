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

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Left: Upload & Controls -->
                <div>
                    <div class="card mb-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="text-lg font-semibold text-gray-900 dark:text-white">Product Images</div>
                            <div class="text-sm text-gray-500 dark:text-gray-400">Upload multiple views of the product label</div>
                        </div>
                        ${ImageUploader.render('scan-upload')}
                    </div>

                    <div class="card mb-6">
                        <div class="flex justify-between items-start mb-4">
                            <div class="text-lg font-semibold text-gray-900 dark:text-white">Analysis Settings</div>
                        </div>
                        <div class="mb-4" style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Name (Optional)</label>
                            <input type="text" class="form-input" id="product-name-input"
                                   placeholder="e.g., Parle-G Gold Biscuits 200g">
                        </div>
                        
                        <div class="mb-4" style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 13px; margin-bottom: 4px; font-weight: 500;">Product Category (Optional)</label>
                            <select id="scan-category-select" class="block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white px-3 py-2 border" style="width: 100%;">
                                <option value="auto">Auto-Detect Type</option>
                                <option value="general">General Goods</option>
                                <option value="food">Food & Edibles</option>
                                <option value="cosmetic">Cosmetics</option>
                                <option value="medicine">Medicines/Drugs</option>
                                <option value="chemical">Chemicals</option>
                                <option value="electronics">Electronics/Hardware</option>
                            </select>
                        </div>
                        
                        <div class="mb-4" style="margin-bottom: 0; display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="skip-ai-toggle" style="width: 16px; height: 16px;">
                            <label for="skip-ai-toggle" style="margin: 0; font-weight: 500; cursor: pointer;">
                                Bypass AI Verifier (Save API Credits / Fast Mode)
                            </label>
                        </div>
                    </div>

                    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                        <button class="inline-flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium rounded-lg transition-colors btn-lg" id="clear-btn" style="flex: 1;">
                            Clear Form
                        </button>
                        <button class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors btn-lg" id="analyze-btn" style="flex: 2;">
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
                    <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                        <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
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
                <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                    <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
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
                ${ComplianceCard.renderScoreCircle(result.compliance_score, result.status)}
                <div style="text-align: center; margin-top: 12px;">
                    <span class="text-sm text-muted">
                        ${result.passed} passed · ${result.failed} failed · ${result.warnings} warnings
                        of ${result.total_checks} checks
                    </span>
                </div>
                <div style="text-align: center; margin-top: 16px; display: flex; gap: 8px; justify-content: center;">
                    <button class="btn btn-success px-3 py-1.5 text-xs" id="generate-report-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Generate PDF Report
                    </button>
                    <a href="#report/${productId}" class="btn btn-outline px-3 py-1.5 text-xs">View Details</a>
                </div>
            </div>
            ${this._renderAnnotatedImages(analysis)}
            <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700">
                <div class="flex justify-between items-start mb-4">
                    <div class="text-lg font-semibold text-gray-900 dark:text-white">Compliance Checks</div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">${checks.length} checks performed</div>
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

        const imageHtml = paths.map(p => {
            const normalized = p.replace(/\\/g, '/');
            const uploadsIdx = normalized.indexOf('uploads/');
            const relativePath = uploadsIdx >= 0 ? normalized.substring(uploadsIdx) : normalized;
            const url = `${API.BASE_URL.replace('/api', '')}/${relativePath}`;
            return `<img src="${url}" alt="OCR Annotated" style="max-width: 100%; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 8px;">`;
        }).join('');

        return `
            <div class="card mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="text-lg font-semibold text-gray-900 dark:text-white">🔍 OCR Analysis — Annotated Output</div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">Color-coded bounding boxes show detected text</div>
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
