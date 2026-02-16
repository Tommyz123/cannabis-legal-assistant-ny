const API_BASE = 'http://localhost:8000';
let sessionId = null;

document.addEventListener('DOMContentLoaded', async () => {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const welcomeScreen = document.getElementById('welcome-screen');
    const quickActionBtns = document.querySelectorAll('.quick-action');

    // Initialize session
    try {
        const res = await fetch(`${API_BASE}/api/session`, { method: 'POST' });
        const data = await res.json();
        sessionId = data.session_id;
    } catch (e) {
        console.error('Failed to create session:', e);
    }

    // Auto-resize textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value.trim().length > 0) {
            sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    });

    // Send Message
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || !sessionId) return;

        if (welcomeScreen && !welcomeScreen.classList.contains('hidden')) {
            welcomeScreen.classList.add('hidden');
        }

        appendMessage('user', text);
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.classList.add('opacity-50', 'cursor-not-allowed');

        showTypingIndicator();

        try {
            const res = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: text }),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const data = await res.json();
            hideTypingIndicator();
            renderAIResponse(data);
        } catch (e) {
            hideTypingIndicator();
            appendMessage('ai', `<span class="text-red-400">Connection failed. Please ensure the backend server is running. (${e.message})</span>`);
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Quick Action Buttons
    const quickActionQueries = {
        'Search Regulations': 'What are the retail license requirements for cannabis dispensaries in New York?',
        'Compliance Check': 'What are the packaging and labeling compliance requirements for cannabis products?',
    };

    quickActionBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const actionTitle = btn.querySelector('h3').innerText;
            const query = quickActionQueries[actionTitle] || `Query about ${actionTitle}`;
            welcomeScreen.classList.add('hidden');
            userInput.value = query;
            userInput.dispatchEvent(new Event('input'));
            sendMessage();
        });
    });

    function renderAIResponse(data) {
        let html = `<div class="space-y-3">`;
        html += `<p class="leading-relaxed">${escapeHtml(data.answer).replace(/\n/g, '<br>')}</p>`;

        // Sources
        if (data.sources && data.sources.length > 0) {
            html += `<div class="mt-3 pt-3 border-t border-gray-700">`;
            html += `<p class="text-xs font-orbitron text-gray-500 uppercase tracking-widest mb-2">Sources</p>`;
            html += `<div class="space-y-1">`;
            const seen = new Set();
            for (const src of data.sources) {
                const key = src.file_name + src.section_title;
                if (seen.has(key)) continue;
                seen.add(key);
                html += `<div class="flex items-start space-x-2 text-xs text-gray-400">`;
                html += `<i class="fas fa-file-alt text-neon-green mt-0.5 flex-shrink-0"></i>`;
                html += `<span><span class="text-neon-green/80">${escapeHtml(src.file_name)}</span>`;
                if (src.section_title) html += ` — ${escapeHtml(src.section_title)}`;
                html += `</span></div>`;
            }
            html += `</div></div>`;
        }

        // Warnings
        if (data.warnings && data.warnings.length > 0) {
            html += `<div class="mt-3 pt-3 border-t border-yellow-800/50">`;
            html += `<p class="text-xs font-orbitron text-yellow-500 uppercase tracking-widest mb-2">Compliance Warnings</p>`;
            for (const w of data.warnings) {
                html += `<p class="text-xs text-yellow-400/80 flex items-start space-x-2"><i class="fas fa-exclamation-triangle mt-0.5 flex-shrink-0"></i><span>${escapeHtml(w)}</span></p>`;
            }
            html += `</div>`;
        }

        html += `</div>`;
        appendMessage('ai', html);
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function appendMessage(sender, html) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `flex ${sender === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`;
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        if (sender === 'user') {
            msgDiv.innerHTML = `
                <div class="max-w-[80%] md:max-w-[60%] flex flex-col items-end">
                    <div class="message-user p-4 text-white shadow-lg text-sm md:text-base">
                        <p>${typeof html === 'string' && !html.includes('<') ? escapeHtml(html).replace(/\n/g, '<br>') : html}</p>
                    </div>
                    <span class="text-[10px] text-gray-500 mt-1 font-orbitron mr-1">${time}</span>
                </div>
                <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-gray-700 to-gray-600 ml-3 flex items-center justify-center flex-shrink-0 border border-gray-600">
                    <i class="fas fa-user text-xs text-gray-300"></i>
                </div>`;
        } else {
            msgDiv.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-black border border-neon-green/50 mr-3 flex items-center justify-center flex-shrink-0 shadow-neon-green">
                    <i class="fas fa-fingerprint text-xs text-neon-green"></i>
                </div>
                <div class="max-w-[80%] md:max-w-[70%] flex flex-col items-start">
                    <div class="message-ai p-4 text-gray-200 shadow-lg text-sm md:text-base">
                        <div class="ai-content">${html}</div>
                    </div>
                    <span class="text-[10px] text-gray-500 mt-1 font-orbitron ml-1">AI CORE • ${time}</span>
                </div>`;
        }

        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    let typingDiv = null;

    function showTypingIndicator() {
        if (typingDiv) return;
        typingDiv = document.createElement('div');
        typingDiv.className = 'flex justify-start animate-fade-in';
        typingDiv.innerHTML = `
            <div class="w-8 h-8 rounded-full bg-black border border-neon-green/50 mr-3 flex items-center justify-center flex-shrink-0 opacity-50">
                <i class="fas fa-fingerprint text-xs text-neon-green"></i>
            </div>
            <div class="message-ai p-4 shadow-lg flex items-center space-x-1">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>`;
        chatContainer.appendChild(typingDiv);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        if (typingDiv) {
            typingDiv.remove();
            typingDiv = null;
        }
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    userInput.focus();
});
