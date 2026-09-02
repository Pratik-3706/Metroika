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
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white">Clear Temporary Files</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">Deletes generated JSON logs, OCR text files, PDFs, and annotated images. Does NOT delete your products or original images.</div>
                    </div>
                    <button class="inline-flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium rounded-lg transition-colors" id="settings-clear-temp-btn">
                        Clear Temp Files
                    </button>
                </div>
            </div>
            
            <div class="bg-white dark:bg-gray-800 shadow rounded-xl p-5 border border-gray-100 dark:border-gray-700" style="border: 1px solid var(--danger); background-color: rgba(239, 68, 68, 0.05);">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="text-lg font-semibold text-gray-900 dark:text-white" style="color: var(--danger);">Reset Application Data (Danger Zone)</div>
                        <div class="text-sm text-gray-500 dark:text-gray-400" style="color: var(--text-primary); opacity: 0.9;">
                            Wipes the Metroika database (all scanned products and history) and deletes all uploaded images from the app's upload folder. 
                            <strong>This only resets the app data. It will NOT affect anything else on your PC.</strong> 
                            This action cannot be undone.
                        </div>
                    </div>
                    <button class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors" style="background-color: var(--danger); border-color: var(--danger); white-space: nowrap;" id="settings-factory-reset-btn">
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
