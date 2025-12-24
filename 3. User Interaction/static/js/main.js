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
                        if (['mp4', 'mov'].includes(ext)) {
                            mediaElement = document.createElement('video');
                            mediaElement.src = mediaUrl;
                            mediaElement.controls = false; // Custom play tool
                            mediaElement.onclick = (e) => {
                                e.stopPropagation();
                                if (mediaElement.paused) mediaElement.play();
                                else mediaElement.pause();
                            };
                            mediaContainer.appendChild(mediaElement);
                        } else {
                            mediaElement = document.createElement('img');
                            mediaElement.src = mediaUrl;
                            mediaContainer.appendChild(mediaElement);
                        }
                    }
                }

                // Full Screen Modal Logic
                const fsBtn = card.querySelector('.fullscreen-btn');
                fsBtn.onclick = (e) => {
                    e.stopPropagation();
                    showMediaModal(rec.file_path);
                };

                grid.appendChild(card);
            });

            resultsDiv.appendChild(videoSection);
        }

        chatHistory.appendChild(resultsDiv);
        if (shouldScroll) chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    // --- Modal Logic ---
    const mediaModal = document.getElementById('media-modal');
    const modalBody = document.getElementById('modal-body');
    const closeModal = document.getElementById('close-modal');

    const showMediaModal = (filePath) => {
        modalBody.innerHTML = '';
        const parts = filePath.split('All Files/');
        if (parts.length <= 1) return;

        const mediaUrl = `/media/${parts[1]}`;
        const ext = filePath.split('.').pop().toLowerCase();

        if (['mp4', 'mov'].includes(ext)) {
            const v = document.createElement('video');
            v.src = mediaUrl;
            v.controls = true;
            v.autoplay = true;
            modalBody.appendChild(v);
        } else {
            const img = document.createElement('img');
            img.src = mediaUrl;
            modalBody.appendChild(img);
        }

        mediaModal.classList.remove('hidden');
    };

    const hideMediaModal = () => {
        mediaModal.classList.add('hidden');
        modalBody.innerHTML = '';
    };

    closeModal.onclick = hideMediaModal;
    mediaModal.onclick = (e) => {
        if (e.target === mediaModal) hideMediaModal();
    };

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
