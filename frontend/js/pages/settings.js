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
            
            <div class="card" style="border: 1px solid var(--danger);">
                <div class="card-header">
                    <div>
                        <div class="card-title" style="color: var(--danger);">Factory Reset (Danger Zone)</div>
                        <div class="card-subtitle">Wipes the entire database (all products and history) and deletes ALL files (including original images) from the server. This action cannot be undone. Products will start from #1 again.</div>
                    </div>
                    <button class="btn btn-primary" style="background-color: var(--danger); border-color: var(--danger);" id="settings-factory-reset-btn">
                        Factory Reset System
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
                btn.innerHTML = 'Factory Reset System';
            }
        });
    },

    unmount() {
    }
};
