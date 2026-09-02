/**
 * Settings Page — manage files, clear cache, and factory reset.
 */
const SettingsPage = {
    mount(container) {
        container.innerHTML = `
            <div class="section-header">
                <h2 class="section-title">Manage Files & System</h2>
            </div>
            
            <div class="card mb-6">
                <div class="card-header">
                    <div>
                        <div class="card-title">Clear Temporary Files</div>
                        <div class="card-subtitle">Deletes generated JSON logs, OCR text files, PDFs, and annotated images. Does NOT delete your products or original images.</div>
                    </div>
                    <button class="btn btn-outline" id="settings-clear-temp-btn">
                        Clear Temp Files
                    </button>
                </div>
            </div>
            
            <div class="card" style="border-color: var(--danger-border); background: var(--danger-bg);">
                <div class="card-header">
                    <div>
                        <div class="card-title" style="color: var(--danger);">Reset Application Data</div>
                        <div class="card-subtitle" style="color: var(--text-secondary);">
                            Wipes the Metroika database (all scanned products and history) and deletes all uploaded images from the app's upload folder. 
                            <strong>This only resets the app data. It will NOT affect anything else on your PC.</strong> 
                            This action cannot be undone.
                        </div>
                    </div>
                    <button class="btn btn-danger" id="settings-factory-reset-btn" style="white-space: nowrap;">
                        Reset App Data
                    </button>
                </div>
            </div>
        `;

        document.getElementById('settings-clear-temp-btn')?.addEventListener('click', async () => {
            const btn = document.getElementById('settings-clear-temp-btn');
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

        document.getElementById('settings-factory-reset-btn')?.addEventListener('click', async () => {
            if (!confirm("⚠️ WARNING: This will delete ALL products, ALL history, and ALL uploaded images! Are you absolutely sure you want to proceed?")) {
                return;
            }
            
            const btn = document.getElementById('settings-factory-reset-btn');
            btn.disabled = true;
            btn.innerHTML = 'Wiping System...';
            try {
                const res = await API.factoryReset();
                showToast(res.message, 'success');
                // Wait a moment, then redirect to Dashboard
                setTimeout(() => {
                    window.location.hash = '#dashboard';
                    window.location.reload();
                }, 1500);
            } catch (error) {
                showToast(`Reset Failed: ${error.message}`, 'error');
                btn.disabled = false;
                btn.innerHTML = 'Reset App Data';
            }
        });
    },

    unmount() {
    }
};
