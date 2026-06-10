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
            const verRes = await fetch('/api/version');
            const verData = await verRes.json();
            const versionBadge = document.getElementById('app-version-badge');
            if (versionBadge && verData.version) {
                versionBadge.textContent = 'v' + verData.version;
            }

            // Check for update
            const res = await fetch('/api/update/check');
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
                        } else {
                            createPlatformForm('rocket');
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

        document.getElementById('kpi-tasks-container').innerHTML = '<div class="empty-state">Đang chạy trình duyệt cào dữ liệu KPI và gửi cho AI... Vui lòng đợi (khoảng 30s)</div>';

        try {
            const res = await fetch('/api/kpi/scan_and_fix', { method: 'POST' });
            if(res.ok) {
                const data = await res.json();
                kpiTasks = data.tasks;
                renderKpiTasks();
            } else {
                const err = await res.json();
                alert("Lỗi: " + err.detail);
                document.getElementById('kpi-tasks-container').innerHTML = `<div class="empty-state" style="color:var(--danger)">Lỗi: ${err.detail}</div>`;
            }
        } catch(e) {
            alert("Lỗi kết nối.");
            document.getElementById('kpi-tasks-container').innerHTML = `<div class="empty-state" style="color:var(--danger)">Lỗi kết nối.</div>`;
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

    document.getElementById('btn-tool-nhapviec').addEventListener('click', async () => {
        const overlay = document.getElementById('progress-overlay');
        const fill = document.getElementById('progress-bar-fill');
        const percent = document.getElementById('progress-percent');
        const count = document.getElementById('progress-count');
        const msg = document.getElementById('progress-msg');
        
        // Reset overlay
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
        if (rawTasks.length === 0) {
            container.innerHTML = `<div class="empty-state">Không có việc mới hôm nay.</div>`;
            return;
        }

        container.innerHTML = '';
        rawTasks.forEach((task, index) => {
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
                }
                rawTasks.splice(index, 1);
                renderRawTasks();
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
                document.getElementById('processed-tasks-container').innerHTML = `<pre style="white-space: pre-wrap; font-family: 'Inter', sans-serif;">${data.content}</pre>`;
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
                body: JSON.stringify({ message: text, active_tab: activeTab })
            });
            const data = await res.json();
            
            // Remove loading bubble
            loadingMsg.remove();

            const aiMsg = document.createElement('div');
            aiMsg.className = 'msg ai';
            aiMsg.textContent = data.reply;
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
