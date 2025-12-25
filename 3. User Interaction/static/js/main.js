document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');
    const sessionList = document.getElementById('session-list');
    const newChatBtn = document.getElementById('new-chat-btn');
    const welcomeHero = document.getElementById('welcome-hero');

    let currentSessionId = null;

    // --- Session Management ---

    const loadSessions = async () => {
        const res = await fetch('/api/sessions');
        const sessions = await res.json();
        sessionList.innerHTML = '';
        sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
            item.innerHTML = `
                <span class="session-name">${s.name}</span>
                <div class="session-actions">
                    <i class="fa-solid fa-pen" onclick="event.stopPropagation(); renameSession('${s.id}')"></i>
                    <i class="fa-solid fa-trash" onclick="event.stopPropagation(); deleteSession('${s.id}')"></i>
                </div>
            `;
            item.onclick = () => switchSession(s.id);
            sessionList.appendChild(item);
        });
    };

    const switchSession = async (sessionId) => {
        currentSessionId = sessionId;
        welcomeHero.classList.remove('hidden'); // Show by default, then hide if messages exist
        chatHistory.querySelectorAll('.message, .results-container').forEach(e => e.remove());

        await loadHistory(sessionId);
        loadSessions();
    };

    const loadHistory = async (sessionId) => {
        const res = await fetch(`/api/sessions/${sessionId}/history`);
        const history = await res.json();
        if (history.length > 0) welcomeHero.classList.add('hidden');

        history.forEach(h => {
            if (h.type === 'result') {
                renderRecommendations(h.metadata, false); // false = don't scroll yet
            } else {
                addMessage(h.content, h.role, false);
            }
        });
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    const createNewChat = async () => {
        const res = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: "New Chat" })
        });
        const data = await res.json();
        switchSession(data.id);
    };

    window.renameSession = async (id) => {
        const newName = prompt("Enter new chat name:");
        if (!newName) return;
        await fetch(`/api/sessions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        loadSessions();
    };

    window.deleteSession = async (id) => {
        if (!confirm("Are you sure you want to delete this chat?")) return;
        await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
        if (currentSessionId === id) createNewChat();
        else loadSessions();
    };

    newChatBtn.onclick = createNewChat;

    // --- UI Logic ---

    const addMessage = (text, type, shouldScroll = true) => {
        const template = document.getElementById('message-template');
        const clone = template.content.cloneNode(true);
        const div = clone.querySelector('.message');
        div.classList.add(type);
        const content = div.querySelector('.content');

        if (type === 'ai') {
            content.innerHTML = marked.parse(text);
        } else {
            content.innerText = text;
        }

        chatHistory.appendChild(clone);
        if (shouldScroll) chatHistory.scrollTop = chatHistory.scrollHeight;

        // Hide welcome hero on first message
        welcomeHero.classList.add('hidden');
    };

    const renderRecommendations = (data, shouldScroll = true) => {
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'results-container';

        // 1. AI Answer (if nested)
        if (data.answer_text) {
            const answerDiv = document.createElement('div');
            answerDiv.className = 'ai-answer-section';
            answerDiv.innerHTML = `
                <div class="section-title"><i class="fa-solid fa-sparkles"></i> AI Analysis & Advice</div>
                <div class="ai-answer">${marked.parse(data.answer_text)}</div>
             `;
            resultsDiv.appendChild(answerDiv);
        }

        // 2. Video Recommendations Gallery
        const recs = [...(data.recommendations_with_notes || []), ...(data.other_recommendations || [])];
        if (recs.length > 0) {
            const videoSection = document.createElement('div');
            videoSection.className = 'video-recommendations';

            // Toggle Button
            const toggleId = `gallery-${Math.random().toString(36).substr(2, 9)}`;
            videoSection.innerHTML = `
                <button class="gallery-toggle-btn" onclick="toggleGallery('${toggleId}')">
                    <i class="fa-solid fa-photo-film"></i> View Knowledge Gallery (${recs.length})
                </button>
                <div id="${toggleId}" class="gallery-collapsible">
                    <div class="video-grid"></div>
                </div>
            `;

            const grid = videoSection.querySelector('.video-grid');
            const cardTemplate = document.getElementById('video-card-template');

            recs.forEach((rec, index) => {
                const card = cardTemplate.content.cloneNode(true);
                const videoCard = card.querySelector('.video-card');
                videoCard.style.animationDelay = `${index * 0.1}s`;

                card.querySelector('.platform-badge').innerText = rec.platform || 'Knowledge';
                card.querySelector('.video-title').innerText = rec.title || 'Untitled';
                card.querySelector('.video-note').innerText = rec.note || '';

                const mediaContainer = card.querySelector('.media-container');
                let mediaElement = null;

                if (rec.file_path) {
                    const parts = rec.file_path.split('All Files/');
                    if (parts.length > 1) {
                        const mediaUrl = `/media/${parts[1]}`;
                        const ext = rec.file_path.split('.').pop().toLowerCase();
                        const fsBtn = card.querySelector('.fullscreen-btn');

                        if (['mp4', 'mov'].includes(ext)) {
                            mediaElement = document.createElement('video');
                            mediaElement.src = mediaUrl;
                            mediaElement.controls = false;

                            // Click video -> Zoom (Open Modal)
                            mediaElement.onclick = (e) => {
                                e.stopPropagation();
                                openTiktokStyleViewer(index, recs);
                            };

                            mediaContainer.appendChild(mediaElement);

                            // Configure Button -> Play/Pause
                            fsBtn.title = "Play/Pause";
                            fsBtn.innerHTML = '<i class="fa-solid fa-play"></i>';

                            fsBtn.onclick = (e) => {
                                e.stopPropagation();
                                if (mediaElement.paused) mediaElement.play();
                                else mediaElement.pause();
                            };

                            // Sync Icon with State
                            const updateIcon = () => {
                                fsBtn.innerHTML = mediaElement.paused
                                    ? '<i class="fa-solid fa-play"></i>'
                                    : '<i class="fa-solid fa-pause"></i>';
                            };
                            mediaElement.addEventListener('play', updateIcon);
                            mediaElement.addEventListener('pause', updateIcon);
                            mediaElement.addEventListener('ended', () => {
                                mediaElement.currentTime = 0; // Reset
                                updateIcon(); // Should show play
                            });

                        } else {
                            mediaElement = document.createElement('img');
                            mediaElement.src = mediaUrl;

                            // Click image -> Zoom (Open Modal)
                            mediaElement.onclick = (e) => {
                                e.stopPropagation();
                                openTiktokStyleViewer(index, recs);
                            };

                            mediaContainer.appendChild(mediaElement);

                            // Remove button for images (click image does the job)
                            if (fsBtn) fsBtn.remove();
                        }
                    }
                }

                // Remove the old fsBtn logic outside the if block if it exists
                // The template has the button, but we handled it above.
                // We need to make sure we don't attach the old listener.
                // The old listener was attached at lines 182-185.
                // I will remove that block in this replacement or ensure it doesn't run.
                // Since I am replacing the whole block including where lines 181-185 were, 
                // I need to make sure I don't leave them out if they are needed for something else,
                // but here I handled fsBtn logic inside the if(rec.file_path). 
                // Wait, what if rec.file_path is missing? 
                // If missing, mediaElement is null, logic skips. 
                // The fsBtn would remain with default icon but do nothing?
                // The original code lines 181-185:
                /*
                 const fsBtn = card.querySelector('.fullscreen-btn');
                 fsBtn.onclick = (e) => {
                     e.stopPropagation();
                     openTiktokStyleViewer(index, recs);
                 };
                */
                // In my replacement, I am handling fsBtn inside the file_path block.
                // If no file_path, the card has no media, so button is useless. Maybe remove it?
                // But the original code only created mediaElement if file_path existed.

                grid.appendChild(card);
            });

            resultsDiv.appendChild(videoSection);
        }

        chatHistory.appendChild(resultsDiv);
        if (shouldScroll) chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    // --- TikTok Style Viewer ---
    const tiktokModal = document.getElementById('tiktok-modal');
    const tiktokContainer = document.getElementById('tiktok-container');
    const closeTiktok = document.getElementById('close-tiktok');
    const navPrev = document.querySelector('.nav-prev');
    const navNext = document.querySelector('.nav-next');

    // Reuse play/pause overlay logic
    const togglePlayPause = (video, wrapper) => {
        if (video.paused) {
            video.play();
            showPlayPauseIcon(wrapper, 'play');
        } else {
            video.pause();
            showPlayPauseIcon(wrapper, 'pause');
        }
    };

    const showPlayPauseIcon = (wrapper, type) => {
        // Remove existing overlay
        const existing = wrapper.querySelector('.play-pause-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'play-pause-overlay';
        overlay.innerHTML = type === 'play' ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-pause"></i>';
        wrapper.appendChild(overlay);

        // Auto remove handled by CSS animation, but cleanup is good
        setTimeout(() => {
            if (overlay.parentNode === wrapper) overlay.remove();
        }, 800);
    };

    const openTiktokStyleViewer = (startIndex, videos) => {
        tiktokContainer.innerHTML = '';
        const template = document.getElementById('tiktok-item-template');

        videos.forEach((vid, index) => {
            const clone = template.content.cloneNode(true);
            const item = clone.querySelector('.tiktok-item');

            item.querySelector('.tiktok-platform').innerText = vid.platform || 'Knowledge';
            item.querySelector('.tiktok-title').innerText = vid.title || 'Untitled';

            // Use note as summary if summary is missing (Chat returns note)
            item.querySelector('.tiktok-summary').innerText = vid.summary || vid.note || '';

            const mediaWrapper = item.querySelector('.tiktok-media-wrapper');
            if (vid.file_path) {
                const parts = vid.file_path.split('All Files/');
                if (parts.length > 1) {
                    const mediaUrl = `/media/${parts[1]}`;
                    const ext = vid.file_path.split('.').pop().toLowerCase();
                    if (['mp4', 'mov'].includes(ext)) {
                        const v = document.createElement('video');
                        v.src = mediaUrl;
                        v.loop = true;
                        // Click to toggle play/pause
                        v.onclick = () => togglePlayPause(v, mediaWrapper);

                        // Hide initially for polish
                        v.style.opacity = '0';
                        v.style.transition = 'opacity 0.3s';

                        // Show when ready
                        v.onloadeddata = () => {
                            v.style.opacity = '1';
                        };

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

            // If item is visible in container (with tolerance)
            if (Math.abs(rect.top - containerRect.top) < 50) {
                video.play().catch(e => console.log("Auto-play blocked"));
            } else {
                video.pause();
                video.currentTime = 0;
            }
        });
    };

    tiktokContainer.onscroll = () => {
        clearTimeout(window.scrollTimeout);
        window.scrollTimeout = setTimeout(playCurrentVideo, 100);
    };

    closeTiktok.onclick = () => {
        tiktokModal.classList.add('hidden');
        tiktokContainer.querySelectorAll('video').forEach(v => v.pause());
    };

    navPrev.onclick = () => {
        tiktokContainer.scrollBy({ top: -window.innerHeight, behavior: 'smooth' });
    };

    navNext.onclick = () => {
        tiktokContainer.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
    };

    // Hijack Scroll for One-at-a-time
    let isScrolling = false;
    tiktokContainer.addEventListener('wheel', (e) => {
        if (tiktokModal.classList.contains('hidden')) return;
        e.preventDefault();

        if (isScrolling) return;

        if (Math.abs(e.deltaY) > 20) {
            isScrolling = true;
            if (e.deltaY > 0) {
                navNext.click();
            } else {
                navPrev.click();
            }
            setTimeout(() => { isScrolling = false; }, 800);
        }
    }, { passive: false });

    // Keyboard support
    document.addEventListener('keydown', (e) => {
        if (!tiktokModal.classList.contains('hidden')) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                navNext.click();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                navPrev.click();
            } else if (e.key === 'Escape') {
                closeTiktok.click();
            } else if (e.key === ' ' || e.key === 'Spacebar') {
                // Toggle play/pause for current video
                e.preventDefault();
                const items = tiktokContainer.querySelectorAll('.tiktok-item');
                const containerRect = tiktokContainer.getBoundingClientRect();
                items.forEach(item => {
                    const rect = item.getBoundingClientRect();
                    if (Math.abs(rect.top - containerRect.top) < 50) {
                        const video = item.querySelector('video');
                        const wrapper = item.querySelector('.tiktok-media-wrapper');
                        if (video) togglePlayPause(video, wrapper);
                    }
                });
            }
        }
    });


    window.toggleGallery = (id) => {
        const el = document.getElementById(id);
        const btn = el.previousElementSibling;
        if (el.style.display === 'block') {
            el.style.display = 'none';
            btn.innerHTML = `<i class="fa-solid fa-photo-film"></i> View Knowledge Gallery`;
        } else {
            el.style.display = 'block';
            btn.innerHTML = `<i class="fa-solid fa-chevron-up"></i> Hide Gallery`;
        }
    };

    const openVideo = (path) => {
        fetch('/api/open-video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
    };

    const handleSend = async () => {
        const query = userInput.value.trim();
        if (!query || !currentSessionId) return;

        addMessage(query, 'user');
        userInput.value = '';
        setLoader(true, "Searching knowledge...");

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, session_id: currentSessionId })
            });
            const data = await res.json();
            setLoader(false);
            if (data.error) addMessage(data.error, 'ai');
            else renderRecommendations(data);
        } catch (e) {
            setLoader(false);
            addMessage("Error connecting to server.", 'ai');
        }
    };

    const setLoader = (show, text = "") => {
        loader.className = show ? 'loading-overlay' : 'loading-overlay hidden';
        loaderText.innerText = text;
    };

    sendBtn.onclick = handleSend;
    userInput.onkeypress = (e) => { if (e.key === 'Enter') handleSend(); };

    // Init
    loadSessions().then(() => {
        // Create new chat if none exist
        fetch('/api/sessions').then(r => r.json()).then(sessions => {
            if (sessions.length === 0) createNewChat();
            else switchSession(sessions[0].id);
        });
    });

    // Quick Tips
    document.querySelectorAll('.tip').forEach(tip => {
        tip.onclick = () => { userInput.value = tip.innerText.replace(/"/g, ''); userInput.focus(); };
    });
});
