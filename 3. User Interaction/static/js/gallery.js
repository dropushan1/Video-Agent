document.addEventListener('DOMContentLoaded', () => {
    const videoGrid = document.getElementById('video-grid');
    const emptyState = document.getElementById('empty-state');
    const filterToggle = document.getElementById('filter-toggle');
    const filterPanel = document.getElementById('filter-panel');
    const applyFilterBtn = document.getElementById('apply-filter-btn');
    const activeFilterCount = document.getElementById('active-filter-count');

    // TikTok Modal Elements
    const tiktokModal = document.getElementById('tiktok-modal');
    const tiktokContainer = document.getElementById('tiktok-container');
    const closeTiktok = document.getElementById('close-tiktok');

    let allVideos = [];
    let activeFilters = {
        platform: [],
        category: [],
        tags: [],
        types: []
    };

    // --- Init ---
    const init = async () => {
        // Load session filters
        const savedFilters = sessionStorage.getItem('galleryFilters');
        if (savedFilters) {
            activeFilters = JSON.parse(savedFilters);
            updateFilterCount();
        }
        await loadFilters();
        await fetchVideos();
    };

    // --- Filter Management ---
    const loadFilters = async () => {
        const res = await fetch('/api/gallery/filters');
        const options = await res.json();

        renderFilterGroup('platform', options.platform);
        renderFilterGroup('category', options.category);
        renderFilterGroup('types', options.types);
        renderFilterGroup('tags', options.tags);
    };

    const renderFilterGroup = (type, items) => {
        const container = document.getElementById(`${type}-options`);
        if (!container) return;

        container.innerHTML = '';
        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'option';
            if (activeFilters[type].includes(item)) {
                div.classList.add('selected');
            }
            div.innerText = item;
            div.onclick = () => toggleFilter(type, item, div);
            container.appendChild(div);
        });
    };

    const toggleFilter = (type, value, el) => {
        const index = activeFilters[type].indexOf(value);
        if (index > -1) {
            activeFilters[type].splice(index, 1);
            el.classList.remove('selected');
        } else {
            activeFilters[type].push(value);
            el.classList.add('selected');
        }
        sessionStorage.setItem('galleryFilters', JSON.stringify(activeFilters));
        updateFilterCount();
    };

    const updateFilterCount = () => {
        const count = Object.values(activeFilters).flat().length;
        if (count > 0) {
            activeFilterCount.innerText = count;
            activeFilterCount.classList.remove('hidden');
        } else {
            activeFilterCount.classList.add('hidden');
        }
    };

    filterToggle.onclick = () => {
        filterPanel.classList.toggle('hidden');
    };

    applyFilterBtn.onclick = () => {
        fetchVideos();
        filterPanel.classList.add('hidden');
    };

    // Support Enter & Arrow Keys
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !filterPanel.classList.contains('hidden')) {
            applyFilterBtn.click();
        }

        if (!tiktokModal.classList.contains('hidden')) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                navNext.click();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                navPrev.click();
            } else if (e.key === 'Escape') {
                closeTiktok.click();
            }
        }
    });

    // --- Video Fetching & Rendering ---
    const fetchVideos = async () => {
        const res = await fetch('/api/gallery/videos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(activeFilters)
        });
        allVideos = await res.json();
        renderGallery();
    };

    const renderGallery = () => {
        videoGrid.innerHTML = '';
        if (allVideos.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }
        emptyState.classList.add('hidden');

        const template = document.getElementById('gallery-card-template');
        allVideos.forEach((vid, index) => {
            const clone = template.content.cloneNode(true);
            const card = clone.querySelector('.gallery-card');

            card.querySelector('.card-platform').innerText = vid.platform || 'Unknown';
            card.querySelector('.card-title').innerText = vid.title || 'Untitled';

            const mediaContainer = card.querySelector('.card-media');
            if (vid.file_path && typeof vid.file_path === 'string') {
                const parts = vid.file_path.split('All Files/');
                if (parts.length > 1) {
                    const mediaUrl = `/media/${parts[1]}`;
                    const ext = vid.file_path.split('.').pop().toLowerCase();
                    if (['mp4', 'mov'].includes(ext)) {
                        const v = document.createElement('video');
                        v.src = mediaUrl;
                        v.muted = true;
                        v.loop = true;
                        v.onmouseover = () => v.play();
                        v.onmouseout = () => v.pause();
                        mediaContainer.prepend(v);
                    } else {
                        const img = document.createElement('img');
                        img.src = mediaUrl;
                        mediaContainer.prepend(img);
                    }
                }
            }

            card.onclick = () => openTiktokViewer(index);
            videoGrid.appendChild(clone);
        });
    };

    // --- TikTok Style Viewer ---
    const openTiktokViewer = (startIndex) => {
        tiktokContainer.innerHTML = '';
        const template = document.getElementById('tiktok-item-template');

        allVideos.forEach((vid, index) => {
            const clone = template.content.cloneNode(true);
            const item = clone.querySelector('.tiktok-item');

            item.querySelector('.tiktok-platform').innerText = vid.platform || 'Knowledge';
            item.querySelector('.tiktok-title').innerText = vid.title || 'Untitled';
            item.querySelector('.tiktok-summary').innerText = vid.summary || '';

            const tagContainer = item.querySelector('.tiktok-tags');
            if (vid.tags && typeof vid.tags === 'string') {
                vid.tags.split(',').forEach(tag => {
                    const trimmed = tag.trim();
                    if (trimmed) {
                        const span = document.createElement('span');
                        span.className = 'tiktok-tag';
                        span.innerText = `#${trimmed}`;
                        tagContainer.appendChild(span);
                    }
                });
            }

            const mediaWrapper = item.querySelector('.tiktok-media-wrapper');
            if (vid.file_path) {
                const parts = vid.file_path.split('All Files/');
                if (parts.length > 1) {
                    const mediaUrl = `/media/${parts[1]}`;
                    const ext = vid.file_path.split('.').pop().toLowerCase();
                    if (['mp4', 'mov'].includes(ext)) {
                        const v = document.createElement('video');
                        v.src = mediaUrl;
                        v.controls = true;
                        v.loop = true;
                        v.dataset.type = 'video';
                        mediaWrapper.appendChild(v);
                    } else {
                        const img = document.createElement('img');
                        img.src = mediaUrl;
                        mediaWrapper.appendChild(img);
                    }
                }
            }

            tiktokContainer.appendChild(clone);
        });

        tiktokModal.classList.remove('hidden');

        // Scroll to the clicked item
        setTimeout(() => {
            const items = tiktokContainer.querySelectorAll('.tiktok-item');
            if (items[startIndex]) {
                items[startIndex].scrollIntoView({ behavior: 'auto', block: 'start' });
                // Force a check after scroll
                setTimeout(playCurrentVideo, 100);
            }
        }, 100);
    };

    const playCurrentVideo = () => {
        const items = tiktokContainer.querySelectorAll('.tiktok-item');
        const containerRect = tiktokContainer.getBoundingClientRect();

        items.forEach(item => {
            const rect = item.getBoundingClientRect();
            const video = item.querySelector('video');
            if (!video) return;

            // If item is visible in container
            if (Math.abs(rect.top - containerRect.top) < 10) {
                video.play().catch(e => console.log("Auto-play blocked"));
            } else {
                video.pause();
                video.currentTime = 0;
            }
        });
    };

    tiktokContainer.onscroll = () => {
        // Debounce or use IntersectionObserver for better performance?
        // Simple scroll check for now
        clearTimeout(window.scrollTimeout);
        window.scrollTimeout = setTimeout(playCurrentVideo, 100);
    };

    closeTiktok.onclick = () => {
        tiktokModal.classList.add('hidden');
        tiktokContainer.querySelectorAll('video').forEach(v => v.pause());
    };

    const navPrev = document.querySelector('.nav-prev');
    const navNext = document.querySelector('.nav-next');

    navPrev.onclick = () => {
        tiktokContainer.scrollBy({ top: -window.innerHeight, behavior: 'smooth' });
    };

    navNext.onclick = () => {
        tiktokContainer.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
    };

    // --- Hijack Scroll for One-at-a-time (TikTok style) ---
    let isScrolling = false;
    tiktokContainer.addEventListener('wheel', (e) => {
        if (tiktokModal.classList.contains('hidden')) return;
        e.preventDefault(); // Stop native scrolling

        if (isScrolling) return;

        if (Math.abs(e.deltaY) > 20) { // Threshold
            isScrolling = true;
            if (e.deltaY > 0) {
                navNext.click();
            } else {
                navPrev.click();
            }

            setTimeout(() => {
                isScrolling = false;
            }, 800); // Lock for 800ms
        }
    }, { passive: false });

    init();
});
