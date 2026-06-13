document.addEventListener('DOMContentLoaded', () => {
    
    // --- DOM Elements ---
    const sceneLogin = document.getElementById('scene-login');
    const sceneSetup = document.getElementById('scene-setup');
    const sceneMain = document.getElementById('scene-main');

    const btnLogin = document.getElementById('btn-login');
    const loginError = document.getElementById('login-error');

    const btnSaveSetup = document.getElementById('btn-save-setup');
    
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // --- State ---
    let projectsList = [];
    let rawTasks = [];
    let processedTasks = [];
    let excludedRooms = [];
    let currentRawFilter = 'all';
    let currentProcessedFilter = 'all';
    let activePlatforms = ['rocket'];
    let processedTasksContent = '';

    function updateActivePlatforms(platforms) {
        activePlatforms = ['rocket'];
        if (platforms && platforms.length > 0) {
            platforms.forEach(p => {
                if (p.type && !activePlatforms.includes(p.type)) {
                    activePlatforms.push(p.type);
                }
            });
        }
        renderFilterBars();
    }

    function renderFilterBars() {
        const rawBar = document.getElementById('raw-filter-bar');
        const processedBar = document.getElementById('processed-filter-bar');
        
        if (!rawBar || !processedBar) return;
        
        const labels = {
            'all': 'Tất cả',
            'rocket': 'Rocket.Chat',
            'git': 'Git (Local)',
            'email': 'Email (IMAP)',
            'slack': 'Slack',
            'telegram': 'Telegram'
        };
        
        const renderBar = (bar, currentFilter, setFilterFn, onFilterChange) => {
            bar.innerHTML = '';
            
            const allBtn = document.createElement('button');
            allBtn.className = `filter-capsule ${currentFilter === 'all' ? 'active' : ''}`;
            allBtn.textContent = 'Tất cả';
            allBtn.addEventListener('click', () => {
                setFilterFn('all');
                onFilterChange();
            });
            bar.appendChild(allBtn);
            
            activePlatforms.forEach(p => {
                if (p === 'all') return;
                const btn = document.createElement('button');
                btn.className = `filter-capsule ${currentFilter === p ? 'active' : ''}`;
                btn.textContent = labels[p] || p;
                btn.addEventListener('click', () => {
                    setFilterFn(p);
                    onFilterChange();
                });
                bar.appendChild(btn);
            });
        };
        
        renderBar(rawBar, currentRawFilter, (val) => currentRawFilter = val, () => {
            renderFilterBars();
            renderRawTasks();
        });
        
        renderBar(processedBar, currentProcessedFilter, (val) => currentProcessedFilter = val, () => {
            renderFilterBars();
            renderProcessedTasks();
        });
    }

    function parseProcessedTasks(markdown) {
        if (!markdown) return { dateHeader: '', tasks: [] };
        const lines = markdown.split('\n');
        const tasks = [];
        let currentTask = null;
        let dateHeader = '';
        
        for (let line of lines) {
            line = line.trim();
            if (line.startsWith('# Daily Tasks')) {
                dateHeader = line;
            } else if (line.startsWith('## Task')) {
                if (currentTask) {
                    tasks.push(currentTask);
                }
                currentTask = {
                    project: '',
                    platform: 'rocket',
                    title: '',
                    rawLines: [line]
                };
            } else if (currentTask) {
                currentTask.rawLines.push(line);
                if (line.startsWith('- **Project**:')) {
                    currentTask.project = line.split(':', 2)[1].trim();
                } else if (line.startsWith('- **Platform**:')) {
                    currentTask.platform = line.split(':', 2)[1].trim().toLowerCase();
                } else if (line.startsWith('- **Title**:')) {
                    currentTask.title = line.split(':', 2)[1].trim();
                }
            }
        }
        if (currentTask) {
            tasks.push(currentTask);
        }
        return { dateHeader, tasks };
    }

    function renderProcessedTasks() {
        const container = document.getElementById('processed-tasks-container');
        if (!container) return;
        
        if (!processedTasksContent || processedTasksContent.includes('Chưa có dữ liệu')) {
            container.innerHTML = `<div class="empty-state">Chưa có dữ liệu. Hãy bấm "2. Tạo việc".</div>`;
            return;
        }
        
        const { dateHeader, tasks } = parseProcessedTasks(processedTasksContent);
        
        const filteredTasks = tasks.filter(t => {
            if (currentProcessedFilter === 'all') return true;
            return t.platform === currentProcessedFilter;
        });
        
        if (filteredTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Không có công việc nào thuộc nền tảng này hôm nay.</div>`;
            return;
        }
        
        let md = dateHeader + '\n\n';
        filteredTasks.forEach((t, idx) => {
            md += `## Task ${idx + 1}\n`;
            t.rawLines.forEach(line => {
                if (!line.startsWith('## Task')) {
                    md += line + '\n';
                }
            });
            md += '\n';
        });
        
        container.innerHTML = `<pre style="white-space: pre-wrap; font-family: 'Inter', sans-serif;">${md.trim()}</pre>`;
    }

    // --- Init ---
    fetch('/api/projects').then(res => res.json()).then(data => {
        if (data.projects) {
            projectsList = data.projects;
        }
    }).catch(e => console.log("Không thể tải danh sách dự án lưu sẵn:", e));

    // --- Auto-Update Check ---
    (async function checkForUpdates() {
        try {
            // Show current version
            const verRes = await fetch('/api/version?t=' + Date.now());
            const verData = await verRes.json();
            const versionBadge = document.getElementById('app-version-badge');
            if (versionBadge && verData.version) {
                versionBadge.textContent = 'v' + verData.version;
            }

            // Check for update
            const res = await fetch('/api/update/check?t=' + Date.now());
            const data = await res.json();
            if (data.has_update) {
                const banner = document.getElementById('update-banner');
                const versionInfo = document.getElementById('update-version-info');
                const changelog = document.getElementById('update-changelog');
                if (banner) {
                    banner.classList.remove('hidden');
                    if (versionInfo) versionInfo.textContent = `v${data.current_version} → v${data.remote_version}`;
                    if (changelog && data.changelog) changelog.textContent = data.changelog;
                }
            }
        } catch (e) {
            console.log('Không thể kiểm tra cập nhật:', e);
        }
    })();

    btnLogin.addEventListener('click', async () => {
        const user = document.getElementById('login-username').value;
        const pass = document.getElementById('login-password').value;

        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            });

            if (res.ok) {
                sceneLogin.classList.add('hidden');
                
                try {
                    const cfgRes = await fetch('/api/config');
                    const config = await cfgRes.json();
                    excludedRooms = config.excluded_rooms || [];
                    
                    if (Object.keys(config).length > 0 && config.workai_user) {
                        sceneMain.classList.remove('hidden');
                        
                        document.getElementById('setup-name').value = config.name || '';
                        document.getElementById('setup-role').value = config.role || '';
                        document.getElementById('setup-ai-provider').value = config.ai_provider || 'gemini';
                        document.getElementById('setup-ai-key').value = config.ai_key || '';
                        document.getElementById('setup-workai-user').value = config.workai_user || '';
                        document.getElementById('setup-workai-pass').value = config.workai_pass || '';
                        
                        platformsList.innerHTML = '';
                        if (config.platforms && config.platforms.length > 0) {
                            config.platforms.forEach(p => {
                                createPlatformForm(p.type);
                                const lastItem = platformsList.lastElementChild;
                                if (p.url && lastItem.querySelector('.plat-url')) lastItem.querySelector('.plat-url').value = p.url;
                                if (p.uid && lastItem.querySelector('.plat-uid')) lastItem.querySelector('.plat-uid').value = p.uid;
                                if (p.token && lastItem.querySelector('.plat-token')) lastItem.querySelector('.plat-token').value = p.token;
                            });
                            updateActivePlatforms(config.platforms);
                        } else {
                            createPlatformForm('rocket');
                            updateActivePlatforms([]);
                        }
                    } else {
                        sceneSetup.classList.remove('hidden');
                    }
                } catch (e) {
                    sceneSetup.classList.remove('hidden');
                }
            } else {
                const data = await res.json();
                loginError.textContent = data.detail;
                loginError.classList.remove('hidden');
            }
        } catch (e) {
            loginError.textContent = "Không thể kết nối đến server.";
            loginError.classList.remove('hidden');
        }
    });

    document.getElementById('btn-settings').addEventListener('click', () => {
        sceneMain.classList.add('hidden');
        sceneSetup.classList.remove('hidden');
    });

    // --- Setup Test Buttons ---
    document.getElementById('btn-test-ai').addEventListener('click', async () => {
        const provider = document.getElementById('setup-ai-provider').value;
        const key = document.getElementById('setup-ai-key').value;
        const resSpan = document.getElementById('res-test-ai');
        
        if (!key) {
            resSpan.textContent = "Vui lòng nhập API Key";
            resSpan.style.color = "var(--danger)";
            return;
        }
        
        resSpan.textContent = "Đang kiểm tra...";
        resSpan.style.color = "var(--text-secondary)";
        
        try {
            const res = await fetch('/api/test/ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: provider, api_key: key })
            });
            const data = await res.json();
            if (data.status === 'success') {
                resSpan.textContent = data.message;
                resSpan.style.color = "var(--success)";
            } else {
                resSpan.textContent = data.message;
                resSpan.style.color = "var(--danger)";
            }
        } catch (e) {
            resSpan.textContent = "Lỗi kết nối server";
            resSpan.style.color = "var(--danger)";
        }
    });

    document.getElementById('btn-test-workai').addEventListener('click', async () => {
        const user = document.getElementById('setup-workai-user').value;
        const pass = document.getElementById('setup-workai-pass').value;
        const resSpan = document.getElementById('res-test-workai');
        
        if (!user || !pass) {
            resSpan.textContent = "Vui lòng nhập tài khoản và mật khẩu";
            resSpan.style.color = "var(--danger)";
            return;
        }
        
        resSpan.textContent = "Đang đăng nhập giả lập (Có thể mất 10s)...";
        resSpan.style.color = "var(--text-secondary)";
        
        try {
            const res = await fetch('/api/test/workai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            });
            const data = await res.json();
            if (data.status === 'success') {
                resSpan.textContent = data.message;
                resSpan.style.color = "var(--success)";
            } else {
                resSpan.textContent = data.message;
                resSpan.style.color = "var(--danger)";
            }
        } catch (e) {
            resSpan.textContent = "Lỗi kết nối server";
            resSpan.style.color = "var(--danger)";
        }
    });

    // --- Setup Platforms Logic ---
    const btnAddPlatform = document.getElementById('btn-add-platform');
    const platformsList = document.getElementById('platforms-list');

    function createPlatformForm(type) {
        const div = document.createElement('div');
        div.className = 'form-group platform-item';
        div.style.padding = '15px';
        div.style.border = '1px solid var(--panel-border)';
        div.style.borderRadius = '8px';
        div.style.background = 'rgba(0,0,0,0.2)';
        div.dataset.type = type;

        let content = '';
        if (type === 'rocket') {
            content = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <label>Rocket.Chat</label>
                    <button class="btn outline btn-remove-plat" style="width: auto; padding: 4px 8px; font-size: 0.8rem;">Xóa</button>
                </div>
                <input type="text" class="plat-url" placeholder="Server URL (VD: https://chat.horus.io.vn)">
                <input type="text" class="plat-uid" placeholder="User ID">
                <input type="password" class="plat-token" placeholder="Auth Token">
                <button type="button" class="btn outline btn-manage-blacklist" style="width: auto; padding: 6px 12px; font-size: 0.85rem; margin-top: 5px; border-color: var(--danger); color: var(--danger);">Quản lý Nhóm loại trừ</button>
            `;
        } else if (type === 'telegram') {
            content = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <label>Telegram</label>
                    <button class="btn outline btn-remove-plat" style="width: auto; padding: 4px 8px; font-size: 0.8rem;">Xóa</button>
                </div>
                <input type="text" class="plat-url" placeholder="Chat ID (VD: -100123456789)">
                <input type="password" class="plat-token" placeholder="Bot Token (từ @BotFather)">
            `;
        } else if (type === 'email') {
            content = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <label>Email (IMAP)</label>
                    <button class="btn outline btn-remove-plat" style="width: auto; padding: 4px 8px; font-size: 0.8rem;">Xóa</button>
                </div>
                <input type="text" class="plat-url" placeholder="IMAP Server (VD: imap.gmail.com)">
                <input type="text" class="plat-uid" placeholder="Email Address">
                <input type="password" class="plat-token" placeholder="App Password">
            `;
        } else if (type === 'slack') {
            content = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <label>Slack</label>
                    <button class="btn outline btn-remove-plat" style="width: auto; padding: 4px 8px; font-size: 0.8rem;">Xóa</button>
                </div>
                <input type="password" class="plat-token" placeholder="Slack Bot / User Token (xoxb-... hoặc xoxp-...)">
            `;
        } else if (type === 'git') {
            content = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <label>Git (Local)</label>
                    <button class="btn outline btn-remove-plat" style="width: auto; padding: 4px 8px; font-size: 0.8rem;">Xóa</button>
                </div>
                <input type="text" class="plat-url" placeholder="Thư mục chứa code (VD: D:\\Projects\\GameRPG)">
                <input type="text" class="plat-uid" placeholder="Tên tác giả commit (VD: Chu Văn Mai)">
            `;
        }
        
        div.innerHTML = content;
        
        div.querySelector('.btn-remove-plat').addEventListener('click', () => {
            div.remove();
        });

        const btnManageBlacklist = div.querySelector('.btn-manage-blacklist');
        if (btnManageBlacklist) {
            btnManageBlacklist.addEventListener('click', () => {
                showBlacklistModal();
            });
        }

        platformsList.appendChild(div);
    }

    // Default load Rocket Chat if empty
    if (platformsList.children.length === 0) {
        createPlatformForm('rocket');
    }

    btnAddPlatform.addEventListener('click', () => {
        const type = document.getElementById('new-plat-type').value;
        createPlatformForm(type);
    });

    // --- Setup Save Logic ---
    btnSaveSetup.addEventListener('click', async () => {
        const name = document.getElementById('setup-name').value;
        const role = document.getElementById('setup-role').value;
        const aiProvider = document.getElementById('setup-ai-provider').value;
        const aiKey = document.getElementById('setup-ai-key').value;
        const workaiUser = document.getElementById('setup-workai-user').value;
        const workaiPass = document.getElementById('setup-workai-pass').value;

        const platforms = [];
        document.querySelectorAll('.platform-item').forEach(item => {
            const type = item.dataset.type;
            const plat = { type: type };
            if (item.querySelector('.plat-url')) plat.url = item.querySelector('.plat-url').value;
            if (item.querySelector('.plat-uid')) plat.uid = item.querySelector('.plat-uid').value;
            if (item.querySelector('.plat-token')) plat.token = item.querySelector('.plat-token').value;
            platforms.push(plat);
        });

        const configData = {
            name, role,
            ai_provider: aiProvider,
            ai_key: aiKey,
            workai_user: workaiUser,
            workai_pass: workaiPass,
            platforms: platforms,
            excluded_rooms: excludedRooms
        };

        try {
            const res = await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData)
            });
            if(res.ok) {
                sceneSetup.classList.add('hidden');
                sceneMain.classList.remove('hidden');
                updateActivePlatforms(platforms);
            } else {
                alert("Lỗi lưu cấu hình");
            }
        } catch (e) {
            alert("Không thể kết nối đến server.");
        }
    });

    // --- Tabs Logic ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    // --- Tools Logic ---
    document.getElementById('btn-scan-projects').addEventListener('click', async () => {
        const btn = document.getElementById('btn-scan-projects');
        btn.textContent = "Đang quét...";
        // Call API
        try {
            const res = await fetch('/api/projects/scan');
            if(res.ok) {
                const data = await res.json();
                projectsList = data.projects;
                alert("Đã quét được " + projectsList.length + " dự án!");
            } else {
                const data = await res.json();
                alert("Lỗi: " + data.detail);
            }
        } catch (e) {
            alert("Lỗi khi quét dự án: " + e);
        }
        btn.textContent = "Làm mới Dự án WorkAI";
    });

    let kpiTasks = [];

    document.getElementById('btn-tool-suakpi').addEventListener('click', async () => {
        const btn = document.getElementById('btn-tool-suakpi');
        btn.textContent = "Đang quét KPI...";
        
        // Chuyển sang tab Sửa KPI
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        const kpiTab = document.querySelector('.tab-btn[data-tab="tab-suakpi"]');
        if(kpiTab) kpiTab.classList.add('active');
        document.getElementById('tab-suakpi').classList.add('active');

        const container = document.getElementById('kpi-tasks-container');
        container.innerHTML = `
            <div class="empty-state">
                <div style="margin-bottom: 15px; font-weight: bold;">Đang chạy trình duyệt cào dữ liệu KPI và gửi cho AI... Vui lòng đợi (khoảng 30s)</div>
                <div id="kpi-scan-log-display" style="text-align: left; font-family: monospace; background: rgba(15, 23, 42, 0.6); padding: 15px; border-radius: 8px; font-size: 0.85em; max-height: 250px; overflow-y: auto; border: 1px solid var(--panel-border); color: #38bdf8; line-height: 1.5;">
                    Chờ khởi động tiến trình...
                </div>
            </div>
        `;

        // Bắt đầu thăm dò log
        let isPolling = true;
        const pollLogs = async () => {
            if (!isPolling) return;
            try {
                const statusRes = await fetch('/api/kpi/status');
                if (statusRes.ok && isPolling) {
                    const statusData = await statusRes.json();
                    const logDisplay = document.getElementById('kpi-scan-log-display');
                    if (logDisplay && statusData.logs && statusData.logs.length > 0) {
                        logDisplay.innerHTML = statusData.logs
                            .map(line => `<div>${escapeHtml(line)}</div>`)
                            .join('');
                        // Tự động cuộn xuống cuối
                        logDisplay.scrollTop = logDisplay.scrollHeight;
                    }
                }
            } catch (err) {
                console.error("Lỗi thăm dò trạng thái quét KPI:", err);
            }
            if (isPolling) {
                setTimeout(pollLogs, 1000);
            }
        };
        setTimeout(pollLogs, 1000);

        try {
            const res = await fetch('/api/kpi/scan_and_fix', { method: 'POST' });
            isPolling = false; // Dừng poll log
            if(res.ok) {
                const data = await res.json();
                kpiTasks = data.tasks;
                renderKpiTasks();
            } else {
                const err = await res.json();
                alert("Lỗi: " + err.detail);
                container.innerHTML = `<div class="empty-state" style="color:var(--danger)">Lỗi: ${err.detail}</div>`;
            }
        } catch(e) {
            isPolling = false; // Dừng poll log
            alert("Lỗi kết nối.");
            container.innerHTML = `<div class="empty-state" style="color:var(--danger)">Lỗi kết nối.</div>`;
        }
        btn.textContent = "4. Sửa KPI";
    });

    function renderKpiTasks() {
        const container = document.getElementById('kpi-tasks-container');
        if (kpiTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Tuyệt vời! Bạn không có đầu việc nào bị đánh giá "Không đạt".</div>`;
            return;
        }

        container.innerHTML = '';
        kpiTasks.forEach((task, index) => {
            const div = document.createElement('div');
            div.className = 'task-item';
            div.style.borderLeftColor = 'var(--danger)';

            div.innerHTML = `
                <div class="task-item-header">
                    <span class="task-badge" style="background:var(--danger)">KPI #${index + 1}</span>
                    <strong style="color:var(--text-primary)">${task.title}</strong>
                </div>
                <div class="task-content" style="background: rgba(239,68,68,0.1); padding: 10px; border-radius: 6px; margin: 10px 0;">
                    <div style="color: var(--danger); font-weight: 500; margin-bottom: 5px;">❌ Lý do: ${task.reason}</div>
                    <div style="color: #f59e0b; font-size: 0.9em; text-decoration: line-through;">💡 Gợi ý hệ thống: ${task.suggestion}</div>
                </div>
                <div class="task-content" style="margin-top: 10px;">
                    <strong style="color: var(--primary);">🤖 AI Đề xuất sửa:</strong>
                    <textarea class="kpi-fixed-title" rows="2" style="width: 100%; margin-top: 5px; padding: 10px; background: var(--input-bg); border: 1px solid var(--panel-border); color: var(--text-primary); border-radius: 6px;">${task.fixed_title}</textarea>
                </div>
            `;
            container.appendChild(div);
        });
    }

    let previewTasks = [];

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderPreviewTasks() {
        const container = document.getElementById('preview-tasks-container');
        if (!container) return;
        
        if (previewTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Chưa có dữ liệu preview. Nhấn "Quét dữ liệu từ WorkAI" để tải thông tin công việc đã nhập.</div>`;
            return;
        }
        
        container.innerHTML = '';
        previewTasks.forEach((task, index) => {
            const card = document.createElement('div');
            card.className = 'preview-task-card';
            card.style.padding = '20px';
            card.style.marginBottom = '20px';
            card.style.borderRadius = '12px';
            card.style.border = '1px solid var(--panel-border)';
            card.style.background = 'rgba(30, 41, 59, 0.4)';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '12px';
            card.dataset.index = index;
            card.dataset.issueKey = task.issue_key || '';
            card.dataset.project = task.project || '';
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px;">
                    <span style="font-weight: 600; color: #60a5fa; font-size: 1.05rem;">${task.issue_key || 'Chưa có Key'}</span>
                    <span style="font-size: 0.85rem; color: var(--text-secondary);">Dự án: ${task.project || ''}</span>
                </div>
                <div class="form-group" style="margin-bottom: 8px;">
                    <label style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">Tiêu đề (Summary)</label>
                    <input type="text" class="preview-title-input" value="${escapeHtml(task.title || '')}" style="margin-bottom: 0;">
                </div>
                <div class="form-group" style="margin-bottom: 8px;">
                    <label style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">Mô tả (Description)</label>
                    <textarea class="preview-desc-textarea" rows="4" style="width:100%; padding:12px; border-radius:8px; border:1px solid var(--panel-border); background:var(--input-bg); color:var(--text-primary); outline:none; font-family:inherit; font-size:0.95rem; resize:vertical;">${escapeHtml(task.description || '')}</textarea>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                    <label style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">Tiêu chí nghiệm thu (Acceptance Criteria)</label>
                    <textarea class="preview-ac-textarea" rows="3" style="width:100%; padding:12px; border-radius:8px; border:1px solid var(--panel-border); background:var(--input-bg); color:var(--text-primary); outline:none; font-family:inherit; font-size:0.95rem; resize:vertical;">${escapeHtml(task.acceptance_criteria || '')}</textarea>
                </div>
            `;
            container.appendChild(card);
        });
    }

    document.getElementById('btn-scan-preview').addEventListener('click', async () => {
        const overlay = document.getElementById('progress-overlay');
        const fill = document.getElementById('progress-bar-fill');
        const percent = document.getElementById('progress-percent');
        const count = document.getElementById('progress-count');
        const msg = document.getElementById('progress-msg');
        const titleEl = document.getElementById('progress-title');
        const cancelBtn = document.getElementById('btn-cancel-nhapviec');
        
        // Reset overlay for scanning
        if (titleEl) titleEl.textContent = "Đang quét dữ liệu từ WorkAI...";
        fill.style.width = '0%';
        percent.textContent = '0%';
        count.textContent = '0/0';
        msg.textContent = 'Đang chuẩn bị quét...';
        overlay.style.display = 'flex';
        overlay.classList.remove('hidden');
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.textContent = "Hủy tiến trình";
        }

        let intervalId = null;

        try {
            const res = await fetch('/api/preview/scan', { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Không thể khởi chạy tiến trình quét.");
            }

            intervalId = setInterval(async () => {
                try {
                    const statusRes = await fetch('/api/preview/status');
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        
                        const total = statusData.total || 0;
                        const current = statusData.current || 0;
                        const state = statusData.status;
                        const message = statusData.msg || '';

                        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
                        fill.style.width = `${percentage}%`;
                        percent.textContent = `${percentage}%`;
                        count.textContent = `${current}/${total}`;
                        msg.textContent = message;

                        if (state === 'success') {
                            clearInterval(intervalId);
                            setTimeout(async () => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                // Load scanned data
                                const dataRes = await fetch('/api/preview/data');
                                if (dataRes.ok) {
                                    const previewData = await dataRes.json();
                                    previewTasks = previewData.tasks || [];
                                    renderPreviewTasks();
                                }
                                alert("Đã quét thành công các công việc từ WorkAI!");
                            }, 1000);
                        } else if (state === 'error') {
                            clearInterval(intervalId);
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                alert("Lỗi khi quét công việc:\n" + message);
                            }, 1000);
                        }
                    }
                } catch (err) {
                    console.error("Lỗi thăm dò trạng thái quét:", err);
                }
            }, 1000);

        } catch (e) {
            if (intervalId) clearInterval(intervalId);
            overlay.style.display = 'none';
            overlay.classList.add('hidden');
            alert("Lỗi: " + e.message);
        }
    });

    document.getElementById('btn-submit-preview').addEventListener('click', async () => {
        const cards = document.querySelectorAll('.preview-task-card');
        if (cards.length === 0) {
            alert("Không có công việc nào để cập nhật. Hãy chạy Quét dữ liệu trước.");
            return;
        }

        const updatedTasks = [];
        cards.forEach(card => {
            const index = card.dataset.index;
            const issueKey = card.dataset.issueKey;
            const project = card.dataset.project;
            const titleInput = card.querySelector('.preview-title-input');
            const descTextarea = card.querySelector('.preview-desc-textarea');
            const acTextarea = card.querySelector('.preview-ac-textarea');

            updatedTasks.push({
                issue_key: issueKey,
                project: project,
                title: titleInput ? titleInput.value.trim() : '',
                description: descTextarea ? descTextarea.value.trim() : '',
                acceptance_criteria: acTextarea ? acTextarea.value.trim() : ''
            });
        });

        if (!confirm("Bạn có chắc chắn muốn cập nhật các thay đổi này lên WorkAI không?")) {
            return;
        }

        const overlay = document.getElementById('progress-overlay');
        const fill = document.getElementById('progress-bar-fill');
        const percent = document.getElementById('progress-percent');
        const count = document.getElementById('progress-count');
        const msg = document.getElementById('progress-msg');
        const titleEl = document.getElementById('progress-title');
        const cancelBtn = document.getElementById('btn-cancel-nhapviec');
        
        // Reset overlay for updating
        if (titleEl) titleEl.textContent = "Đang cập nhật lên WorkAI...";
        fill.style.width = '0%';
        percent.textContent = '0%';
        count.textContent = '0/0';
        msg.textContent = 'Đang khởi động tiến trình cập nhật...';
        overlay.style.display = 'flex';
        overlay.classList.remove('hidden');
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.textContent = "Hủy tiến trình";
        }

        let intervalId = null;

        try {
            const res = await fetch('/api/preview/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedTasks)
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Không thể khởi chạy tiến trình cập nhật.");
            }

            intervalId = setInterval(async () => {
                try {
                    const statusRes = await fetch('/api/preview/status');
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        
                        const total = statusData.total || 0;
                        const current = statusData.current || 0;
                        const state = statusData.status;
                        const message = statusData.msg || '';

                        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
                        fill.style.width = `${percentage}%`;
                        percent.textContent = `${percentage}%`;
                        count.textContent = `${current}/${total}`;
                        msg.textContent = message;

                        if (state === 'success') {
                            clearInterval(intervalId);
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                alert("Đã cập nhật thành công lên WorkAI!");
                            }, 1000);
                        } else if (state === 'error') {
                            clearInterval(intervalId);
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                alert("Lỗi khi cập nhật công việc:\n" + message);
                            }, 1000);
                        }
                    }
                } catch (err) {
                    console.error("Lỗi thăm dò trạng thái cập nhật:", err);
                }
            }, 1000);

        } catch (e) {
            if (intervalId) clearInterval(intervalId);
            overlay.style.display = 'none';
            overlay.classList.add('hidden');
            alert("Lỗi: " + e.message);
        }
    });

    const btnTonghop = document.getElementById('btn-tool-tonghop');
    btnTonghop.addEventListener('click', () => runTonghopFlow(false));

    async function runTonghopFlow(force = false) {
        btnTonghop.disabled = true;
        btnTonghop.textContent = "Đang quét...";
        document.getElementById('raw-tasks-container').innerHTML = `<div class="empty-state">Đang quét tin nhắn...</div>`;
        try {
            const url = force ? '/api/run/tonghop?force=true' : '/api/run/tonghop';
            const res = await fetch(url, { method: 'POST' });
            if(res.ok) {
                const data = await res.json();
                rawTasks = data.tasks;
                renderRawTasks();
                if (rawTasks.length === 0) {
                    document.getElementById('raw-tasks-container').innerHTML = `
                        <div class="empty-state">
                            Không tìm thấy việc mới từ lần quét trước.
                            <br><br>
                            <a href="#" id="link-force-sync" style="color: var(--primary); text-decoration: underline;">[Quét lại toàn bộ tin nhắn từ đầu ngày hôm nay]</a>
                        </div>
                    `;
                    const forceLink = document.getElementById('link-force-sync');
                    if (forceLink) {
                        forceLink.addEventListener('click', (e) => {
                            e.preventDefault();
                            runTonghopFlow(true);
                        });
                    }
                }
                // Chuyển sang tab raw
                document.querySelector('[data-tab="tab-raw"]').click();
            } else {
                const err = await res.json();
                document.getElementById('raw-tasks-container').innerHTML = `<div class="error-text">Lỗi: ${err.detail}</div>`;
            }
        } catch (e) {
            document.getElementById('raw-tasks-container').innerHTML = `<div class="error-text">Lỗi kết nối.</div>`;
        } finally {
            btnTonghop.disabled = false;
            btnTonghop.textContent = "1. Tổng hợp";
        }
    }

    document.getElementById('btn-restore-tasks').addEventListener('click', async () => {
        try {
            const res = await fetch('/api/raw_tasks/restore', { method: 'POST' });
            if(res.ok) {
                const data = await res.json();
                rawTasks = data.tasks;
                renderRawTasks();
                alert("Đã phục hồi tất cả các việc bị xóa!");
            }
        } catch (e) {
            alert("Lỗi kết nối khi phục hồi.");
        }
    });

    document.getElementById('btn-tool-taoviec').addEventListener('click', async () => {
        document.getElementById('processed-tasks-container').innerHTML = `<div class="empty-state">AI đang xử lý công việc... Vui lòng chờ...</div>`;
        try {
            const res = await fetch('/api/run/taoviec', { method: 'POST' });
            if(res.ok) {
                const data = await res.json();
                // Render markdown content
                document.getElementById('processed-tasks-container').innerHTML = `<pre style="white-space: pre-wrap; font-family: 'Inter', sans-serif;">${data.content}</pre>`;
                // Chuyển tab
                document.querySelector('[data-tab="tab-processed"]').click();
            } else {
                const err = await res.json();
                document.getElementById('processed-tasks-container').innerHTML = `<div class="error-text">Lỗi: ${err.detail}</div>`;
            }
        } catch (e) {
            document.getElementById('processed-tasks-container').innerHTML = `<div class="error-text">Lỗi kết nối.</div>`;
        }
    });

    // Cancel button click event listener
    const btnCancelNhapviec = document.getElementById('btn-cancel-nhapviec');
    if (btnCancelNhapviec) {
        btnCancelNhapviec.addEventListener('click', async () => {
            if (confirm("Bạn có chắc chắn muốn hủy tiến trình đang chạy? Các công việc đã cập nhật/thêm thành công sẽ được giữ nguyên.")) {
                try {
                    btnCancelNhapviec.disabled = true;
                    btnCancelNhapviec.textContent = "Đang hủy...";
                    await fetch('/api/run/nhapviec/cancel', { method: 'POST' });
                    await fetch('/api/preview/cancel', { method: 'POST' });
                } catch (err) {
                    console.error("Lỗi khi gửi yêu cầu hủy:", err);
                } finally {
                    btnCancelNhapviec.disabled = false;
                    btnCancelNhapviec.textContent = "Hủy tiến trình";
                }
            }
        });
    }

    document.getElementById('btn-tool-nhapviec').addEventListener('click', async () => {
        // Confirmation before proceeding
        if (!processedTasksContent || processedTasksContent.includes('Chưa có dữ liệu')) {
            alert("Không có dữ liệu công việc đã tạo. Hãy bấm '2. Tạo việc' trước.");
            return;
        }

        const proceed = confirm("Bạn có chắc chắn muốn nhập toàn bộ các công việc này lên WorkAI không?\n\n(Hệ thống sẽ tự động bỏ qua các công việc đã nhập trước đó để tránh trùng lặp)");
        if (!proceed) return;

        const overlay = document.getElementById('progress-overlay');
        const fill = document.getElementById('progress-bar-fill');
        const percent = document.getElementById('progress-percent');
        const count = document.getElementById('progress-count');
        const msg = document.getElementById('progress-msg');
        
        // Reset overlay and buttons
        if (btnCancelNhapviec) {
            btnCancelNhapviec.disabled = false;
            btnCancelNhapviec.textContent = "Hủy tiến trình";
        }
        fill.style.width = '0%';
        percent.textContent = '0%';
        count.textContent = '0/0';
        msg.textContent = 'Đang khởi động tiến trình...';
        overlay.style.display = 'flex';
        overlay.classList.remove('hidden');

        let intervalId = null;

        try {
            const res = await fetch('/api/run/nhapviec', { method: 'POST' });
            if(!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Không thể khởi chạy kịch bản.");
            }

            // Start polling status
            intervalId = setInterval(async () => {
                try {
                    const statusRes = await fetch('/api/run/nhapviec/status');
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        
                        // Update UI
                        const total = statusData.total || 0;
                        const current = statusData.current || 0;
                        const state = statusData.status; // running, success, error, idle
                        const message = statusData.msg || '';

                        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
                        fill.style.width = `${percentage}%`;
                        percent.textContent = `${percentage}%`;
                        count.textContent = `${current}/${total}`;
                        msg.textContent = message;

                        if (state === 'success') {
                            clearInterval(intervalId);
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                alert("Hoàn thành! " + message);
                            }, 1500);
                        } else if (state === 'error') {
                            clearInterval(intervalId);
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                overlay.classList.add('hidden');
                                alert("Lỗi khi nhập việc:\n" + message);
                            }, 1500);
                        }
                    }
                } catch (err) {
                    console.error("Lỗi thăm dò trạng thái:", err);
                }
            }, 1000);

        } catch (e) {
            if (intervalId) clearInterval(intervalId);
            overlay.style.display = 'none';
            overlay.classList.add('hidden');
            alert("Lỗi: " + e.message);
        }
    });

    function renderRawTasks() {
        const container = document.getElementById('raw-tasks-container');
        if (!container) return;

        if (rawTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Không có việc mới hôm nay.</div>`;
            return;
        }

        // Filter the tasks by platform
        const filteredTasks = rawTasks.filter(task => {
            if (currentRawFilter === 'all') return true;
            
            const roomName = task.room_name || '';
            let platform = 'rocket';
            if (roomName.startsWith('Git -')) {
                platform = 'git';
            } else if (roomName.startsWith('Email:')) {
                platform = 'email';
            }
            return platform === currentRawFilter;
        });

        if (filteredTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Không có công việc nào thuộc nền tảng này hôm nay.</div>`;
            return;
        }

        container.innerHTML = '';
        filteredTasks.forEach((task, index) => {
            const div = document.createElement('div');
            div.className = 'task-item';
            div.dataset.index = index;
            
            let options = `<option value="">-- Chọn dự án --</option>`;
            projectsList.forEach(p => {
                const selected = (task.project_code && task.project_code === p.code) ? 'selected' : '';
                options += `<option value="${p.code}" ${selected}>${p.name}</option>`;
            });

            div.innerHTML = `
                <div class="task-item-header">
                    <div>
                        <span class="task-badge">Task #${index + 1}</span>
                        <select class="task-project-select">${options}</select>
                    </div>
                    <div>
                        <button class="btn outline btn-detail-task" style="width: auto; padding: 2px 8px; font-size: 0.8rem; height: 24px; margin-right: 5px;">Chi tiết</button>
                        <button class="btn outline btn-delete-task" style="width: auto; border-color: var(--danger); color: var(--danger); padding: 2px 8px; font-size: 0.8rem; height: 24px;">Xóa</button>
                    </div>
                </div>
                <div class="task-content">
                    <strong>[${task.room_name}]</strong> ${task.sender}: ${task.text}
                </div>
            `;
            
            // Add detail logic
            div.querySelector('.btn-detail-task').addEventListener('click', () => {
                alert("ĐOẠN CHAT GỐC:\n\n" + (task.original_chat || "Không có dữ liệu gốc"));
            });

            // Add project change logic
            div.querySelector('.task-project-select').addEventListener('change', async (e) => {
                const projectCode = e.target.value;
                task.project_code = projectCode;
                try {
                    await fetch('/api/raw_tasks/update_project', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id: task.id, project_code: projectCode })
                    });
                } catch(e) {
                    console.error("Lỗi khi cập nhật dự án:", e);
                }
            });

            // Add delete logic
            div.querySelector('.btn-delete-task').addEventListener('click', async () => {
                if(task.id) {
                    try {
                        await fetch('/api/raw_tasks/hide', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ id: task.id })
                        });
                    } catch(e) {
                        console.error("Lỗi khi ẩn task:", e);
                    }
                    
                    const idxInRaw = rawTasks.findIndex(t => t.id === task.id);
                    if (idxInRaw !== -1) {
                        rawTasks.splice(idxInRaw, 1);
                    }
                    renderRawTasks();
                }
            });

            container.appendChild(div);
        });
    }
    
    // --- Data Loading Helpers ---
    async function loadRawTasks() {
        try {
            const res = await fetch('/api/raw_tasks');
            if(res.ok) {
                const data = await res.json();
                rawTasks = data.tasks;
                renderRawTasks();
            }
        } catch(e) {
            console.error("Lỗi khi tải danh sách task thô:", e);
        }
    }

    async function loadProcessedTasks() {
        try {
            const res = await fetch('/api/taoviec/content');
            if(res.ok) {
                const data = await res.json();
                processedTasksContent = data.content;
                renderProcessedTasks();
            }
        } catch(e) {
            console.error("Lỗi khi tải nội dung memorytask.md:", e);
        }
    }

    async function loadKpiTasks() {
        try {
            const res = await fetch('/api/kpi/content');
            if(res.ok) {
                const data = await res.json();
                kpiTasks = data.tasks;
                renderKpiTasks();
            }
        } catch(e) {
            console.error("Lỗi khi tải danh sách KPI:", e);
        }
    }

    // --- Refresh Buttons Logic ---
    const btnForceSync = document.getElementById('btn-force-sync');
    if(btnForceSync) {
        btnForceSync.addEventListener('click', () => {
            if(confirm("Bạn có chắc chắn muốn xóa danh sách hiện tại và quét lại toàn bộ tin nhắn/commit từ đầu ngày hôm nay không?")) {
                runTonghopFlow(true);
            }
        });
    }

    const btnRefreshRaw = document.getElementById('btn-refresh-raw');
    const btnRefreshProcessed = document.getElementById('btn-refresh-processed');
    const btnRefreshKpi = document.getElementById('btn-refresh-kpi');

    if(btnRefreshRaw) {
        btnRefreshRaw.addEventListener('click', async () => {
            btnRefreshRaw.textContent = "Đang tải...";
            btnRefreshRaw.disabled = true;
            await loadRawTasks();
            btnRefreshRaw.textContent = "⟲ Làm mới nội dung";
            btnRefreshRaw.disabled = false;
        });
    }

    if(btnRefreshProcessed) {
        btnRefreshProcessed.addEventListener('click', async () => {
            btnRefreshProcessed.textContent = "Đang tải...";
            btnRefreshProcessed.disabled = true;
            await loadProcessedTasks();
            btnRefreshProcessed.textContent = "⟲ Làm mới nội dung";
            btnRefreshProcessed.disabled = false;
        });
    }

    if(btnRefreshKpi) {
        btnRefreshKpi.addEventListener('click', async () => {
            btnRefreshKpi.textContent = "Đang tải...";
            btnRefreshKpi.disabled = true;
            await loadKpiTasks();
            btnRefreshKpi.textContent = "⟲ Làm mới nội dung";
            btnRefreshKpi.disabled = false;
        });
    }

    // --- AI Chat Logic ---
    const chatInput = document.getElementById('chat-input');
    const btnSendChat = document.getElementById('btn-send-chat');
    const chatMessages = document.getElementById('chat-messages');

    btnSendChat.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keypress', (e) => {
        if(e.key === 'Enter') sendChatMessage();
    });

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if(!text) return;

        // Add user msg
        const userMsg = document.createElement('div');
        userMsg.className = 'msg user';
        userMsg.textContent = text;
        chatMessages.appendChild(userMsg);
        chatInput.value = '';
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const activeTab = document.querySelector('.tab-btn.active').dataset.tab;

        // Disable input & button for loading feedback
        chatInput.disabled = true;
        btnSendChat.disabled = true;

        // Append loading bubble
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'msg ai';
        loadingMsg.innerHTML = `<div class="loading-dots"><span></span><span></span><span></span></div>`;
        chatMessages.appendChild(loadingMsg);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Call API
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: text, 
                    active_tab: activeTab,
                    raw_filter: currentRawFilter,
                    processed_filter: currentProcessedFilter
                })
            });
            const data = await res.json();
            
            // Remove loading bubble
            loadingMsg.remove();

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg ai';
            
            // Simple markdown formatter
            const formatReply = (txt) => {
                if (!txt) return "";
                let esc = txt
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
                esc = esc.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
                esc = esc.replace(/\*(.*?)\*/g, "<em>$1</em>");
                esc = esc.replace(/^[-\*]\s+(.*)/gm, "• $1");
                esc = esc.replace(/\n/g, "<br>");
                return esc;
            };
            
            aiMsg.innerHTML = formatReply(data.reply);
            chatMessages.appendChild(aiMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Auto-refresh Tab 2 if it's the active tab
            if (activeTab === 'tab-processed') {
                await loadProcessedTasks();
            }

            // Auto-refresh Tab 1 if it's the active tab
            if (activeTab === 'tab-raw') {
                await loadRawTasks();
            }

        } catch (e) {
            // Remove loading bubble
            loadingMsg.remove();

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg ai error-text';
            aiMsg.textContent = "Lỗi kết nối AI.";
            chatMessages.appendChild(aiMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } finally {
            // Re-enable input & button
            chatInput.disabled = false;
            btnSendChat.disabled = false;
            chatInput.focus();
        }
    }

    // --- Blacklist Modal Logic ---
    const blacklistModal = document.getElementById('blacklist-modal');
    const blacklistItemsList = document.getElementById('blacklist-items-list');
    const inputNewBlacklist = document.getElementById('input-new-blacklist');
    const btnAddBlacklist = document.getElementById('btn-add-blacklist');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const btnCancelBlacklist = document.getElementById('btn-cancel-blacklist');
    const btnSaveBlacklist = document.getElementById('btn-save-blacklist');

    let tempExcludedRooms = [];

    function showBlacklistModal() {
        tempExcludedRooms = [...excludedRooms];
        renderBlacklistItems();
        blacklistModal.classList.remove('hidden');
        blacklistModal.style.display = 'flex';
    }

    function hideBlacklistModal() {
        blacklistModal.classList.add('hidden');
        blacklistModal.style.display = 'none';
        inputNewBlacklist.value = '';
    }

    function renderBlacklistItems() {
        blacklistItemsList.innerHTML = '';
        if (tempExcludedRooms.length === 0) {
            blacklistItemsList.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 10px;">Chưa có nhóm loại trừ nào.</div>';
            return;
        }
        tempExcludedRooms.forEach((room, idx) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'blacklist-item';
            itemDiv.innerHTML = `
                <span>${room}</span>
                <button class="btn-remove-blacklist-item" data-index="${idx}">&times;</button>
            `;
            
            itemDiv.querySelector('.btn-remove-blacklist-item').addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                tempExcludedRooms.splice(index, 1);
                renderBlacklistItems();
            });
            
            blacklistItemsList.appendChild(itemDiv);
        });
    }

    if (btnAddBlacklist) {
        btnAddBlacklist.addEventListener('click', () => {
            const val = inputNewBlacklist.value.trim();
            if (val) {
                if (tempExcludedRooms.some(r => r.toLowerCase() === val.toLowerCase())) {
                    alert("Nhóm này đã có trong danh sách.");
                    return;
                }
                tempExcludedRooms.push(val);
                inputNewBlacklist.value = '';
                renderBlacklistItems();
            }
        });
    }

    if (inputNewBlacklist) {
        inputNewBlacklist.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                btnAddBlacklist.click();
            }
        });
    }

    if (btnCloseModal) btnCloseModal.addEventListener('click', hideBlacklistModal);
    if (btnCancelBlacklist) btnCancelBlacklist.addEventListener('click', hideBlacklistModal);

    if (btnSaveBlacklist) {
        btnSaveBlacklist.addEventListener('click', async () => {
            excludedRooms = [...tempExcludedRooms];
            hideBlacklistModal();
            
            btnSaveBlacklist.disabled = true;
            btnSaveBlacklist.textContent = "Đang lưu...";
            const ok = await saveCurrentConfigLocally();
            btnSaveBlacklist.disabled = false;
            btnSaveBlacklist.textContent = "Lưu lại";
            
            if (ok) {
                alert("Đã lưu danh sách nhóm loại trừ thành công!");
            } else {
                alert("Có lỗi xảy ra khi lưu danh sách nhóm loại trừ.");
            }
        });
    }

    async function saveCurrentConfigLocally() {
        const name = document.getElementById('setup-name').value;
        const role = document.getElementById('setup-role').value;
        const aiProvider = document.getElementById('setup-ai-provider').value;
        const aiKey = document.getElementById('setup-ai-key').value;
        const workaiUser = document.getElementById('setup-workai-user').value;
        const workaiPass = document.getElementById('setup-workai-pass').value;

        const platforms = [];
        document.querySelectorAll('.platform-item').forEach(item => {
            const type = item.dataset.type;
            const plat = { type: type };
            if (item.querySelector('.plat-url')) plat.url = item.querySelector('.plat-url').value;
            if (item.querySelector('.plat-uid')) plat.uid = item.querySelector('.plat-uid').value;
            if (item.querySelector('.plat-token')) plat.token = item.querySelector('.plat-token').value;
            platforms.push(plat);
        });

        const configData = {
            name, role,
            ai_provider: aiProvider,
            ai_key: aiKey,
            workai_user: workaiUser,
            workai_pass: workaiPass,
            platforms: platforms,
            excluded_rooms: excludedRooms
        };

        try {
            const res = await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData)
            });
            return res.ok;
        } catch (e) {
            console.error("Lỗi lưu cấu hình tự động:", e);
            return false;
        }
    }
    // --- Update Button Handler ---
    const btnApplyUpdate = document.getElementById('btn-apply-update');
    if (btnApplyUpdate) {
        btnApplyUpdate.addEventListener('click', async () => {
            const banner = document.getElementById('update-banner');
            const progress = document.getElementById('update-progress');
            if (banner) banner.classList.add('hidden');
            if (progress) progress.classList.remove('hidden');

            try {
                const res = await fetch('/api/update/apply', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    if (progress) progress.querySelector('span').textContent = 'Đang khởi động lại...';
                    // Wait for server to restart, then reload
                    setTimeout(() => {
                        let attempts = 0;
                        const tryReload = setInterval(async () => {
                            attempts++;
                            try {
                                const check = await fetch('/api/version');
                                if (check.ok) {
                                    clearInterval(tryReload);
                                    window.location.reload();
                                }
                            } catch (e) {
                                if (attempts > 20) {
                                    clearInterval(tryReload);
                                    alert('Cập nhật xong! Vui lòng mở lại ứng dụng.');
                                }
                            }
                        }, 1000);
                    }, 3000);
                } else {
                    alert('Lỗi cập nhật: ' + (data.message || 'Không rõ'));
                    if (progress) progress.classList.add('hidden');
                    if (banner) banner.classList.remove('hidden');
                }
            } catch (e) {
                alert('Lỗi kết nối: ' + e.message);
                if (progress) progress.classList.add('hidden');
                if (banner) banner.classList.remove('hidden');
            }
        });
    }
});
