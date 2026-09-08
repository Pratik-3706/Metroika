/**
 * Metroika API Client
 * Handles all backend API communication.
 */
const API = {
    BASE_URL: 'http://localhost:8000',

    /**
     * Generic fetch wrapper with error handling.
     */
    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        try {
            const token = localStorage.getItem('metroika_token');
            const headers = {
                ...(!options.isFormData && { 'Content-Type': 'application/json' }),
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...options.headers,
            };

            const response = await fetch(url, {
                ...options,
                headers,
            });

            if (!response.ok) {
                if (response.status === 401) {
                    localStorage.removeItem('metroika_token');
                    localStorage.removeItem('metroika_role');
                    localStorage.removeItem('metroika_user');
                }
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Handle file downloads (PDF and CSV)
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/pdf') || contentType.includes('text/csv')) {
                return response.blob();
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                throw new Error('Cannot connect to server. Make sure the backend is running on port 8000.');
            }
            throw error;
        }
    },

    // ----- Products -----
    async createProduct(formData) {
        return this.request('/api/products', {
            method: 'POST',
            body: formData,
            isFormData: true,
        });
    },

    async getProducts(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/products${query ? '?' + query : ''}`);
    },

    async getProduct(id) {
        return this.request(`/api/products/${id}`);
    },

    async deleteProduct(id) {
        return this.request(`/api/products/${id}`, { method: 'DELETE' });
    },

    // ----- Analysis -----
    async analyzeProduct(productId, skipAi = false, category = 'auto') {
        let url = `/api/products/${productId}/analyze?skip_ai=${skipAi}`;
        if (category && category !== 'auto') {
            url += `&category=${category}`;
        }
        return this.request(url, {
            method: 'POST',
        });
    },

    async getAnalysis(productId) {
        return this.request(`/api/products/${productId}/analysis`);
    },

    async clearCache() {
        return this.request(`/api/products/clear_cache`, {
            method: 'POST',
        });
    },

    async factoryReset() {
        return this.request(`/api/products/factory_reset`, {
            method: 'POST',
        });
    },

    // ----- Reports -----
    async generateReport(productId) {
        return this.request(`/api/products/${productId}/report`, {
            method: 'POST',
        });
    },

    async downloadReport(filenameOrId) {
        let filename = filenameOrId;
        // If passed a numeric product ID, trigger report generation first
        if (typeof filenameOrId === 'number' || (/^\d+$/.test(String(filenameOrId).trim()))) {
            const reportData = await this.generateReport(filenameOrId);
            filename = reportData.filename || (reportData.download_url ? reportData.download_url.split('/').pop() : `compliance_report_${filenameOrId}.pdf`);
        } else if (typeof filename === 'string' && filename.includes('/')) {
            filename = filename.split('/').pop();
        }

        const blob = await this.request(`/api/reports/${filename}`);
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            if (document.body.contains(link)) {
                document.body.removeChild(link);
            }
            URL.revokeObjectURL(blobUrl);
        }, 1500);
        return filename;
    },

    async getReport(filename) {
        return this.downloadReport(filename);
    },

    async downloadReportCsv(productId) {
        const blob = await this.request(`/api/products/${productId}/report/csv`);
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = `compliance_report_${productId}.csv`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        setTimeout(() => {
            if (document.body.contains(link)) {
                document.body.removeChild(link);
            }
            URL.revokeObjectURL(blobUrl);
        }, 1500);
    },

    async getShowCauseNotice(productId) {
        return this.request(`/api/products/${productId}/report/notice`);
    },

    async auditEcommerceListing(data) {
        return this.request('/api/products/audit_listing', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    // ----- Authentication & RBAC -----
    async login(username, password) {
        const res = await this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        if (res.access_token) {
            localStorage.setItem('metroika_token', res.access_token);
            localStorage.setItem('metroika_role', res.user.role);
            localStorage.setItem('metroika_user', JSON.stringify(res.user));
        }
        return res;
    },

    async getCurrentUser() {
        return this.request('/api/auth/me');
    },

    async getRoles() {
        return this.request('/api/auth/roles');
    },

    logout() {
        localStorage.removeItem('metroika_token');
        localStorage.removeItem('metroika_role');
        localStorage.removeItem('metroika_user');
    },

    // ----- Dashboard -----
    async getDashboardStats() {
        return this.request('/api/dashboard/stats');
    },

    async getRecentScans(limit = 10) {
        return this.request(`/api/dashboard/recent?limit=${limit}`);
    },

    // ----- Health -----
    async healthCheck() {
        return this.request('/api/health');
    },

    /**
     * Get the URL for a product image.
     */
    getImageUrl(imagePath) {
        // Extract just the relative path from uploads/
        const parts = imagePath.replace(/\\/g, '/');
        const uploadsIdx = parts.indexOf('uploads/');
        if (uploadsIdx >= 0) {
            return `${this.BASE_URL}/${parts.substring(uploadsIdx)}`;
        }
        return `${this.BASE_URL}/uploads/${parts}`;
    },
};

// ----- Toast Helper -----
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
    };

    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        toast.style.transition = 'all 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
