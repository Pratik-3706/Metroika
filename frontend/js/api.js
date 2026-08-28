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
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...(!options.isFormData && { 'Content-Type': 'application/json' }),
                    ...options.headers,
                },
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Handle file downloads
            if (response.headers.get('content-type')?.includes('application/pdf')) {
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
    async analyzeProduct(productId, skipAi = false) {
        return this.request(`/api/products/${productId}/analyze?skip_ai=${skipAi}`, {
            method: 'POST',
        });
    },

    async getAnalysis(productId) {
        return this.request(`/api/products/${productId}/analysis`);
    },

    // ----- Reports -----
    async generateReport(productId) {
        return this.request(`/api/products/${productId}/report`, {
            method: 'POST',
        });
    },

    async downloadReport(filename) {
        const url = `${this.BASE_URL}/api/reports/${filename}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to download report');
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
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
