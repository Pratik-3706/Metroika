/**
 * Products Page — searchable list of all scanned products.
 */
const ProductsPage = {
    async mount(container) {
        container.innerHTML = `
            <div class="section-header">
                <h2 class="section-title">Products</h2>
                <div class="flex items-center gap-3">
                    <div class="search-bar">
                        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                        <input type="text" class="form-input" id="product-search" placeholder="Search products...">
                    </div>
                    <select class="form-input" id="status-filter" style="width: 140px;">
                        <option value="">All Statuses</option>
                        <option value="compliant">Compliant</option>
                        <option value="non_compliant">Non-Compliant</option>
                        <option value="warning">Warnings</option>
                        <option value="pending">Pending</option>
                    </select>
                    <a href="#scan" class="btn btn-primary btn-sm">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                        </svg>
                        New Scan
                    </a>
                </div>
            </div>
            <div class="card">
                <div id="products-list">
                    <p class="text-muted text-sm">Loading...</p>
                </div>
            </div>
        `;

        // Event listeners
        document.getElementById('product-search')?.addEventListener('input',
            this._debounce(() => this._loadProducts(), 300)
        );
        document.getElementById('status-filter')?.addEventListener('change', () => this._loadProducts());

        await this._loadProducts();
    },

    unmount() {},

    async _loadProducts() {
        const search = document.getElementById('product-search')?.value || '';
        const status = document.getElementById('status-filter')?.value || '';

        try {
            const params = {};
            if (search) params.search = search;
            if (status) params.status = status;

            const products = await API.getProducts(params);
            this._renderProducts(products);
        } catch (error) {
            console.error('Failed to load products:', error);
            document.getElementById('products-list').innerHTML = `
                <div class="empty-state">
                    <h3>Could not load products</h3>
                    <p>${error.message}</p>
                </div>
            `;
        }
    },

    _renderProducts(products) {
        const el = document.getElementById('products-list');
        if (!el) return;

        if (products.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                    </svg>
                    <h3>No products found</h3>
                    <p>Try adjusting your search or scan a new product.</p>
                </div>
            `;
            return;
        }

        el.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Product Name</th>
                        <th>Barcode</th>
                        <th>Status</th>
                        <th>Images</th>
                        <th>Scanned</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${products.map(p => `
                        <tr>
                            <td class="text-mono text-muted">#${p.id}</td>
                            <td class="product-name">${p.name || 'Unnamed Product'}</td>
                            <td class="text-mono text-sm text-muted">${p.barcode_data || '—'}</td>
                            <td>${ComplianceCard.renderStatusBadge(p.status)}</td>
                            <td class="text-muted">${p.image_count}</td>
                            <td class="text-muted text-sm">${new Date(p.created_at).toLocaleDateString()}</td>
                            <td>
                                <div class="flex gap-3">
                                    <button class="btn btn-outline btn-sm" onclick="location.hash='report/${p.id}'">View</button>
                                    <button class="btn btn-sm" style="color: var(--danger);" onclick="ProductsPage._deleteProduct(${p.id})">Delete</button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    async _deleteProduct(id) {
        if (!confirm(`Delete product #${id} and all associated data?`)) return;
        try {
            await API.deleteProduct(id);
            showToast('Product deleted.', 'success');
            this._loadProducts();
        } catch (error) {
            showToast(`Delete failed: ${error.message}`, 'error');
        }
    },

    _debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },
};
