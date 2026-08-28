/**
 * Multi-image uploader component with drag-and-drop.
 */
const ImageUploader = {
    files: [],
    labels: [],

    reset() {
        this.files = [];
        this.labels = [];
    },

    render(containerId) {
        return `
            <div class="upload-zone" id="${containerId}-zone">
                <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <div class="upload-text">Drop product images here or click to browse</div>
                <div class="upload-hint">
                    Upload multiple images (front, back, side labels) · JPG, PNG, WebP · Max 10MB each
                </div>
                <input type="file" id="${containerId}-input" multiple accept="image/*" 
                       style="display:none">
            </div>
            <div class="image-preview-grid" id="${containerId}-preview"></div>
        `;
    },

    init(containerId) {
        const zone = document.getElementById(`${containerId}-zone`);
        const input = document.getElementById(`${containerId}-input`);
        const preview = document.getElementById(`${containerId}-preview`);

        if (!zone || !input) return;

        // Click to upload
        zone.addEventListener('click', () => input.click());

        // File selection
        input.addEventListener('change', (e) => {
            this.addFiles(Array.from(e.target.files), containerId);
            input.value = ''; // Reset so same file can be re-selected
        });

        // Drag and drop
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            const droppedFiles = Array.from(e.dataTransfer.files).filter(
                f => f.type.startsWith('image/')
            );
            this.addFiles(droppedFiles, containerId);
        });
    },

    addFiles(newFiles, containerId) {
        const labelNames = ['Front', 'Back', 'Side', 'Top', 'Bottom'];

        newFiles.forEach(file => {
            const idx = this.files.length;
            const label = idx < labelNames.length ? labelNames[idx] : `Image ${idx + 1}`;
            this.files.push(file);
            this.labels.push(label);
        });

        this.renderPreviews(containerId);
    },

    renderPreviews(containerId) {
        const preview = document.getElementById(`${containerId}-preview`);
        if (!preview) return;

        preview.innerHTML = this.files.map((file, idx) => {
            const url = URL.createObjectURL(file);
            return `
                <div class="image-preview-item" data-idx="${idx}">
                    <img src="${url}" alt="${this.labels[idx]}">
                    <div class="label-tag">${this.labels[idx]}</div>
                    <button class="remove-btn" data-idx="${idx}" title="Remove">&times;</button>
                </div>
            `;
        }).join('');

        // Attach remove handlers
        preview.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.idx);
                this.files.splice(idx, 1);
                this.labels.splice(idx, 1);
                this.renderPreviews(containerId);
            });
        });
    },

    getFormData(productName) {
        const formData = new FormData();
        if (productName) {
            formData.append('name', productName);
        }
        this.files.forEach(file => {
            formData.append('images', file);
        });
        formData.append('labels', this.labels.join(','));
        return formData;
    },
};
