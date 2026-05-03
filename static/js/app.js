// ============================================================
// AI API Hub — 前端主逻辑
// 纯 vanilla JavaScript 实现，无框架依赖
// ============================================================

// 全局状态变量
let currentPage = 'dashboard';    // 当前显示的页面名称
let currentProviderId = null;     // 当前查看的提供商 ID（用于详情页）
let allProviders = [];            // 缓存所有提供商数据（用于筛选）

// ====================== 初始化 ======================

document.addEventListener('DOMContentLoaded', () => {
    initApp();                    // 初始化应用（加载统计数据和提供商列表）
    setupEventListeners();        // 绑定全局事件监听器
});

function initApp() {
    loadStats();                  // 加载仪表盘统计数据
    loadProviders();              // 加载提供商卡片网格
}

function setupEventListeners() {
    // 绑定侧边栏导航项点击事件
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();                    // 阻止默认链接行为
            const page = item.dataset.page;        // 获取目标页面名称
            showPage(page);                        // 切换到目标页面
        });
    });

    // 绑定类别筛选按钮点击事件
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // 移除所有按钮的 active 状态
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');           // 激活当前按钮
            filterProviders(btn.dataset.category); // 按类别筛选提供商
        });
    });

    // 绑定搜索框回车事件（Enter 键触发搜索）
    const searchInput = document.getElementById('provider-search');
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') searchProviders();  // 回车触发搜索
        });
    }

    // 绑定模态框遮罩层点击关闭
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();  // 点击遮罩层关闭
    });
}

// ====================== 页面切换 ======================

function showPage(page) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // 移除所有导航项的 active 状态
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    // 显示目标页面
    document.getElementById(`${page}-page`).classList.add('active');
    // 激活对应的导航项
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
    currentPage = page;    // 更新当前页面状态

    // 根据页面类型加载对应数据
    if (page === 'dashboard') {
        loadStats();       // 刷新统计数据
        loadProviders();   // 刷新提供商网格
    } else if (page === 'providers') {
        loadProvidersList();  // 加载提供商管理列表
    } else if (page === 'models') {
        loadAllModels();   // 加载全局模型列表
    } else if (page === 'keys') {
        loadAllKeys();     // 加载全局密钥列表
    } else if (page === 'settings') {
        loadAISettings();  // 加载 AI 设置
    }
}

// ====================== 工具函数 ======================

/**
 * HTML 转义函数，防止 XSS 攻击
 * 将特殊字符替换为 HTML 实体
 */
function escapeHtml(text) {
    if (!text) return '';                           // 空值直接返回空字符串
    const div = document.createElement('div');      // 创建临时 DOM 元素
    div.textContent = text;                         // 设置文本内容（自动转义）
    return div.innerHTML;                           // 返回转义后的 HTML
}

/**
 * 显示 Toast 通知消息
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型：'success' 或 'error'
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');  // 获取容器
    const toast = document.createElement('div');                  // 创建 toast 元素
    toast.className = `toast toast-${type}`;                      // 设置样式类
    toast.textContent = message;                                  // 设置消息文本
    container.appendChild(toast);                                 // 添加到容器
    setTimeout(() => toast.classList.add('show'), 10);            // 触发显示动画
    setTimeout(() => {                                            // 3 秒后自动消失
        toast.classList.remove('show');                           // 移除显示动画
        setTimeout(() => toast.remove(), 300);                    // 动画结束后移除元素
    }, 3000);
}

/**
 * 将 API 密钥脱敏显示
 * 只显示前 4 位和后 4 位，中间用 **** 替代
 */
function maskKey(key) {
    if (!key || key.length <= 8) return '****';                   // 太短则全部遮挡
    return key.substring(0, 4) + '****' + key.substring(key.length - 4);  // 前4+****+后4
}

/**
 * 一键复制文本到剪贴板
 * @param {string} text - 要复制的文本
 * @param {HTMLElement} btn - 触发按钮（用于显示复制成功反馈）
 */
function copyToClipboard(text, btn) {
    if (!text) {                                                 // 如果文本为空
        showToast('没有可复制的内容', 'error');
        return;
    }
    navigator.clipboard.writeText(text).then(() => {             // 使用 Clipboard API 复制
        const originalText = btn.textContent;                    // 保存按钮原始文本
        btn.textContent = '已复制';                               // 显示"已复制"反馈
        btn.classList.add('copied');                             // 添加 copied 样式
        setTimeout(() => {                                       // 1.5 秒后恢复
            btn.textContent = originalText;
            btn.classList.remove('copied');
        }, 1500);
    }).catch(() => {                                             // 如果 Clipboard API 不可用
        // 降级方案：使用 textarea + execCommand
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';                       // 防止页面滚动
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('已复制到剪贴板');
    });
}

/**
 * 获取分类的中文显示名称
 */
function getCategoryName(category) {
    const names = {
        'international': '国外主流',     // 国际主流厂商
        'domestic': '国内主流',          // 国内主流厂商
        'other': '其他'                  // 其他厂商
    };
    return names[category] || category;  // 未知分类直接返回原值
}

/**
 * 统一的 fetch 请求封装
 * 自动处理错误并显示 toast 通知
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },  // 默认 JSON 请求头
            ...options                                          // 合并自定义选项
        });
        if (!response.ok) {                                     // 如果响应状态码非 2xx
            const err = await response.json().catch(() => ({}));// 尝试解析错误信息
            throw new Error(err.error || `请求失败 (${response.status})`);
        }
        return response;                                        // 返回响应对象
    } catch (error) {
        showToast(error.message, 'error');                      // 显示错误 toast
        throw error;                                            // 继续抛出，让调用方处理
    }
}

// ====================== 统计数据 ======================

async function loadStats() {
    try {
        const response = await apiRequest('/api/stats');        // 请求统计数据
        const stats = await response.json();                    // 解析 JSON
        document.getElementById('providers-count').textContent = stats.providers_count;  // 显示提供商数
        document.getElementById('models-count').textContent = stats.models_count;        // 显示模型数
        document.getElementById('keys-count').textContent = stats.keys_count;            // 显示密钥数
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 提供商卡片网格（仪表盘） ======================

async function loadProviders() {
    try {
        const response = await apiRequest('/api/providers');    // 请求提供商列表
        allProviders = await response.json();                   // 缓存到全局变量
        renderProvidersGrid(allProviders);                      // 渲染卡片网格
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

function renderProvidersGrid(providers) {
    const grid = document.getElementById('providers-grid');     // 获取网格容器
    if (providers.length === 0) {                               // 如果没有提供商
        grid.innerHTML = '<p style="color: var(--text-secondary); grid-column: 1/-1;">暂无提供商，请点击左侧"添加提供商"按钮创建</p>';
        return;
    }
    // 使用模板字符串生成卡片 HTML，所有用户输入均通过 escapeHtml 转义
    grid.innerHTML = providers.map(p => `
        <div class="provider-card" onclick="showProviderDetail(${p.id})">
            <div class="provider-card-header">
                <div class="provider-name">${escapeHtml(p.display_name)}</div>
                <div class="provider-category">${escapeHtml(getCategoryName(p.category))}</div>
            </div>
            <div class="provider-url">${escapeHtml(p.base_url) || '未设置URL'}</div>
            <div class="provider-desc">${escapeHtml(p.description) || '暂无描述'}</div>
        </div>
    `).join('');
}

function filterProviders(category) {
    if (category === 'all') {
        renderProvidersGrid(allProviders);                      // 显示全部
    } else {
        const filtered = allProviders.filter(p => p.category === category);  // 按类别过滤
        renderProvidersGrid(filtered);                          // 渲染过滤结果
    }
}

// ====================== 提供商管理列表 ======================

async function loadProvidersList() {
    try {
        const response = await apiRequest('/api/providers');    // 请求提供商列表
        const providers = await response.json();                // 解析 JSON
        renderProvidersList(providers);                         // 渲染列表
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 渲染提供商列表（管理页面和搜索结果共用）
 */
function renderProvidersList(providers) {
    const list = document.getElementById('providers-list');     // 获取列表容器
    if (providers.length === 0) {                               // 如果没有数据
        list.innerHTML = '<p style="color: var(--text-secondary);">暂无提供商</p>';
        return;
    }
    // 生成列表项 HTML，所有用户输入均通过 escapeHtml 转义
    list.innerHTML = providers.map(p => `
        <div class="provider-list-item">
            <div class="provider-list-info">
                <h3>${escapeHtml(p.display_name)}</h3>
                <p>${escapeHtml(p.base_url) || '未设置URL'} &middot; ${escapeHtml(getCategoryName(p.category))}</p>
            </div>
            <div class="provider-list-actions">
                <button class="btn-small" onclick="showProviderDetail(${p.id})">查看</button>
                <button class="btn-small" onclick="showEditProviderModal(${p.id})">编辑</button>
                <button class="btn-small danger" onclick="deleteProvider(${p.id})">删除</button>
            </div>
        </div>
    `).join('');
}

async function searchProviders() {
    const search = document.getElementById('provider-search').value;  // 获取搜索关键词
    try {
        const response = await apiRequest(`/api/providers?search=${encodeURIComponent(search)}`);
        const providers = await response.json();                // 解析搜索结果
        renderProvidersList(providers);                         // 复用列表渲染函数
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 提供商详情页 ======================

async function showProviderDetail(providerId) {
    currentProviderId = providerId;                             // 更新当前提供商 ID
    try {
        const response = await apiRequest(`/api/providers/${providerId}`);
        const provider = await response.json();                 // 获取提供商详情

        // 设置页面标题
        document.getElementById('detail-provider-name').textContent = provider.display_name;

        // 渲染基本信息
        document.getElementById('detail-info').innerHTML = `
            <div class="info-item">
                <div class="info-label">名称</div>
                <div class="info-value">${escapeHtml(provider.name)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">显示名称</div>
                <div class="info-value">${escapeHtml(provider.display_name)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">类别</div>
                <div class="info-value">${escapeHtml(getCategoryName(provider.category))}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Base URL</div>
                <div class="info-value copy-row">
                    <span>${escapeHtml(provider.base_url) || '未设置'}</span>
                    ${provider.base_url ? `<button class="btn-copy" onclick="copyToClipboard('${escapeHtml(provider.base_url)}', this)">复制</button>` : ''}
                </div>
            </div>
            <div class="info-item">
                <div class="info-label">描述</div>
                <div class="info-value">${escapeHtml(provider.description) || '暂无描述'}</div>
            </div>
        `;

        renderModels(provider.models);       // 渲染模型列表
        renderKeys(provider.keys);           // 渲染密钥列表
        showPage('provider-detail');         // 切换到详情页
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 模型渲染 ======================

function renderModels(models) {
    const container = document.getElementById('detail-models'); // 获取模型容器
    if (models.length === 0) {                                  // 如果没有模型
        container.innerHTML = '<p style="color: var(--text-secondary);">暂无模型</p>';
        return;
    }
    // 生成模型表格 HTML
    container.innerHTML = `
        <table class="models-table">
            <thead>
                <tr>
                    <th>模型ID</th>
                    <th>显示名称</th>
                    <th>最大Token</th>
                    <th>多模态</th>
                    <th>函数调用</th>
                    <th>输入价格</th>
                    <th>输出价格</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${models.map(m => `
                    <tr>
                        <td><code>${escapeHtml(m.model_id)}</code></td>
                        <td>${escapeHtml(m.display_name)}</td>
                        <td>${m.max_tokens ? m.max_tokens.toLocaleString() : '-'}</td>
                        <td>${m.supports_vision ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                        <td>${m.supports_function_calling ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                        <td>${m.price_input ? `$${m.price_input}/1K` : '-'}</td>
                        <td>${m.price_output ? `$${m.price_output}/1K` : '-'}</td>
                        <td>
                            <button class="btn-small" onclick="showEditModelModal(${m.id})">编辑</button>
                            <button class="btn-small danger" onclick="deleteModel(${m.id})">删除</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// ====================== 密钥渲染 ======================

function renderKeys(keys) {
    const container = document.getElementById('detail-keys');   // 获取密钥容器
    if (keys.length === 0) {                                    // 如果没有密钥
        container.innerHTML = '<p style="color: var(--text-secondary);">暂无API密钥</p>';
        return;
    }
    // 生成密钥卡片列表 HTML
    container.innerHTML = keys.map(k => `
        <div class="key-card">
            <div class="key-info">
                <h4>${escapeHtml(k.key_name)}</h4>
                <div class="key-value copy-row">
                    <span>${k.api_key ? maskKey(k.api_key) : '未设置'}</span>
                    ${k.api_key ? `<button class="btn-copy" onclick="copyToClipboard('${escapeHtml(k.api_key)}', this)">复制</button>` : ''}
                </div>
                ${k.notes ? `<div class="key-notes">${escapeHtml(k.notes)}</div>` : ''}
            </div>
            <div class="key-actions">
                <button class="btn-small" onclick="showEditKeyModal(${k.id})">编辑</button>
                <button class="btn-small danger" onclick="deleteKey(${k.id})">删除</button>
            </div>
        </div>
    `).join('');
}

// ====================== 全局模型列表（使用批量 API，避免 N+1 查询） ======================

async function loadAllModels() {
    try {
        const response = await apiRequest('/api/models');       // 使用批量 API 一次获取所有模型
        const models = await response.json();                   // 解析 JSON
        const tbody = document.getElementById('models-table-body');  // 获取表格 body

        if (models.length === 0) {                              // 如果没有模型
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--text-secondary);">暂无模型</td></tr>';
            return;
        }

        // 生成模型表格行 HTML
        tbody.innerHTML = models.map(m => `
            <tr>
                <td>${escapeHtml(m.provider_name)}</td>
                <td><code>${escapeHtml(m.model_id)}</code></td>
                <td>${escapeHtml(m.display_name)}</td>
                <td>${m.max_tokens ? m.max_tokens.toLocaleString() : '-'}</td>
                <td>${m.supports_vision ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                <td>${m.supports_function_calling ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                <td>${m.price_input ? `$${m.price_input}/1K` : '-'}</td>
                <td>${m.price_output ? `$${m.price_output}/1K` : '-'}</td>
                <td>
                    <button class="btn-small" onclick="goToModelEdit(${m.provider_id}, ${m.id})">编辑</button>
                    <button class="btn-small danger" onclick="deleteModelFromList(${m.id})">删除</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 从全局模型列表跳转到提供商详情页进行编辑
 */
async function goToModelEdit(providerId, modelId) {
    currentProviderId = providerId;                             // 设置当前提供商 ID
    await showProviderDetail(providerId);                       // 加载提供商详情
    showEditModelModal(modelId);                                // 打开编辑模型模态框
}

/**
 * 从全局模型列表删除模型（删除后刷新列表）
 */
async function deleteModelFromList(modelId) {
    if (!confirm('确定要删除这个模型吗？')) return;              // 确认删除
    try {
        await apiRequest(`/api/models/${modelId}`, { method: 'DELETE' });  // 发送删除请求
        showToast('模型已删除');                                 // 显示成功提示
        loadAllModels();                                        // 刷新模型列表
        loadStats();                                            // 刷新统计数据
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 全局密钥列表（使用批量 API，避免 N+1 查询） ======================

async function loadAllKeys() {
    try {
        const response = await apiRequest('/api/keys');         // 使用批量 API 一次获取所有密钥
        const keys = await response.json();                     // 解析 JSON
        const list = document.getElementById('keys-list');      // 获取列表容器

        if (keys.length === 0) {                                // 如果没有密钥
            list.innerHTML = '<p style="color: var(--text-secondary);">暂无API密钥，请先添加提供商和密钥</p>';
            return;
        }

        // 生成密钥卡片列表 HTML
        list.innerHTML = keys.map(k => `
            <div class="key-card">
                <div class="key-info">
                    <h4>${escapeHtml(k.provider_name)} - ${escapeHtml(k.key_name)}</h4>
                    <div class="key-value copy-row">
                        <span>${k.api_key ? maskKey(k.api_key) : '未设置'}</span>
                        ${k.api_key ? `<button class="btn-copy" onclick="copyToClipboard('${escapeHtml(k.api_key)}', this)">复制</button>` : ''}
                    </div>
                    ${k.notes ? `<div class="key-notes">${escapeHtml(k.notes)}</div>` : ''}
                </div>
                <div class="key-actions">
                    <button class="btn-small" onclick="showEditKeyModalGlobal(${k.id})">编辑</button>
                    <button class="btn-small danger" onclick="deleteKeyFromList(${k.id})">删除</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 从全局密钥列表删除密钥（删除后刷新列表）
 */
async function deleteKeyFromList(keyId) {
    if (!confirm('确定要删除这个API密钥吗？')) return;           // 确认删除
    try {
        await apiRequest(`/api/keys/${keyId}`, { method: 'DELETE' });  // 发送删除请求
        showToast('密钥已删除');                                 // 显示成功提示
        loadAllKeys();                                          // 刷新密钥列表
        loadStats();                                            // 刷新统计数据
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 提供商 CRUD 模态框 ======================

function showAddProviderModal() {
    document.getElementById('modal-title').textContent = '添加API提供商';
    document.getElementById('modal-body').innerHTML = `
        <form id="provider-form">
            <div class="form-group">
                <label>名称 (英文标识)</label>
                <input type="text" name="name" required placeholder="例: openai">
            </div>
            <div class="form-group">
                <label>显示名称</label>
                <input type="text" name="display_name" required placeholder="例: OpenAI">
            </div>
            <div class="form-group">
                <label>Base URL</label>
                <input type="text" name="base_url" placeholder="例: https://api.openai.com/v1">
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" placeholder="描述这个API提供商..."></textarea>
            </div>
            <div class="form-group">
                <label>类别</label>
                <select name="category">
                    <option value="international">国外主流</option>
                    <option value="domestic">国内主流</option>
                    <option value="other">其他</option>
                </select>
            </div>
            <div class="form-actions">
                <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                <button type="submit" class="btn-primary">保存</button>
            </div>
        </form>
    `;
    // 绑定表单提交事件
    document.getElementById('provider-form').addEventListener('submit', async (e) => {
        e.preventDefault();                                     // 阻止默认提交
        const formData = new FormData(e.target);                // 获取表单数据
        const data = Object.fromEntries(formData);              // 转换为对象
        try {
            await apiRequest('/api/providers', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            closeModal();                                       // 关闭模态框
            showToast('提供商已创建');                            // 显示成功提示
            loadProviders();                                    // 刷新提供商列表
            loadStats();                                        // 刷新统计数据
        } catch (error) {
            // 错误已由 apiRequest 统一处理
        }
    });
    openModal();                                                // 打开模态框
}

async function showEditProviderModal(providerId) {
    try {
        const response = await apiRequest(`/api/providers/${providerId}`);
        const provider = await response.json();                 // 获取提供商当前数据
        document.getElementById('modal-title').textContent = '编辑API提供商';
        document.getElementById('modal-body').innerHTML = `
            <form id="provider-form">
                <div class="form-group">
                    <label>名称 (英文标识)</label>
                    <input type="text" name="name" required value="${escapeHtml(provider.name)}">
                </div>
                <div class="form-group">
                    <label>显示名称</label>
                    <input type="text" name="display_name" required value="${escapeHtml(provider.display_name)}">
                </div>
                <div class="form-group">
                    <label>Base URL</label>
                    <input type="text" name="base_url" value="${escapeHtml(provider.base_url) || ''}">
                </div>
                <div class="form-group">
                    <label>描述</label>
                    <textarea name="description">${escapeHtml(provider.description) || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>类别</label>
                    <select name="category">
                        <option value="international" ${provider.category === 'international' ? 'selected' : ''}>国外主流</option>
                        <option value="domestic" ${provider.category === 'domestic' ? 'selected' : ''}>国内主流</option>
                        <option value="other" ${provider.category === 'other' ? 'selected' : ''}>其他</option>
                    </select>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                    <button type="submit" class="btn-primary">保存</button>
                </div>
            </form>
        `;
        // 绑定表单提交事件
        document.getElementById('provider-form').addEventListener('submit', async (e) => {
            e.preventDefault();                                 // 阻止默认提交
            const formData = new FormData(e.target);            // 获取表单数据
            const data = Object.fromEntries(formData);          // 转换为对象
            try {
                await apiRequest(`/api/providers/${providerId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                closeModal();                                   // 关闭模态框
                showToast('提供商已更新');                        // 显示成功提示
                loadProviders();                                // 刷新提供商列表
                if (currentPage === 'provider-detail') {
                    showProviderDetail(providerId);             // 刷新详情页
                }
            } catch (error) {
                // 错误已由 apiRequest 统一处理
            }
        });
        openModal();                                            // 打开模态框
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

async function deleteProvider(providerId) {
    if (!confirm('确定要删除这个提供商及其所有模型和密钥吗？')) return;  // 确认删除
    try {
        await apiRequest(`/api/providers/${providerId}`, { method: 'DELETE' });
        showToast('提供商已删除');                                // 显示成功提示
        loadProviders();                                        // 刷新提供商列表
        loadStats();                                            // 刷新统计数据
        if (currentPage === 'providers') {
            loadProvidersList();                                // 刷新管理列表
        }
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 模型 CRUD 模态框 ======================

function showAddModelModal() {
    if (!currentProviderId) return;                             // 未选中提供商则不操作
    document.getElementById('modal-title').textContent = '添加模型';
    document.getElementById('modal-body').innerHTML = `
        <form id="model-form">
            <div class="form-group">
                <label>模型ID</label>
                <input type="text" name="model_id" required placeholder="例: gpt-4o">
            </div>
            <div class="form-group">
                <label>显示名称</label>
                <input type="text" name="display_name" required placeholder="例: GPT-4o">
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" placeholder="描述这个模型..."></textarea>
            </div>
            <div class="form-group">
                <label>最大Token数</label>
                <input type="number" name="max_tokens" placeholder="例: 128000">
            </div>
            <div class="form-group">
                <label>支持流式输出</label>
                <select name="supports_streaming">
                    <option value="1">是</option>
                    <option value="0">否</option>
                </select>
            </div>
            <div class="form-group">
                <label>支持多模态 (Vision)</label>
                <select name="supports_vision">
                    <option value="0">否</option>
                    <option value="1">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>支持函数调用</label>
                <select name="supports_function_calling">
                    <option value="0">否</option>
                    <option value="1">是</option>
                </select>
            </div>
            <div class="form-group">
                <label>输入价格 ($/1K tokens)</label>
                <input type="number" name="price_input" step="0.0001" placeholder="例: 0.005">
            </div>
            <div class="form-group">
                <label>输出价格 ($/1K tokens)</label>
                <input type="number" name="price_output" step="0.0001" placeholder="例: 0.015">
            </div>
            <div class="form-actions">
                <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                <button type="submit" class="btn-primary">保存</button>
            </div>
        </form>
    `;
    // 绑定表单提交事件
    document.getElementById('model-form').addEventListener('submit', async (e) => {
        e.preventDefault();                                     // 阻止默认提交
        const formData = new FormData(e.target);                // 获取表单数据
        const data = Object.fromEntries(formData);              // 转换为对象
        // 类型转换：字符串转数字
        data.max_tokens = data.max_tokens ? parseInt(data.max_tokens) : null;
        data.price_input = data.price_input ? parseFloat(data.price_input) : null;
        data.price_output = data.price_output ? parseFloat(data.price_output) : null;
        try {
            await apiRequest(`/api/providers/${currentProviderId}/models`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
            closeModal();                                       // 关闭模态框
            showToast('模型已创建');                              // 显示成功提示
            showProviderDetail(currentProviderId);               // 刷新详情页
        } catch (error) {
            // 错误已由 apiRequest 统一处理
        }
    });
    openModal();                                                // 打开模态框
}

async function showEditModelModal(modelId) {
    try {
        const response = await apiRequest(`/api/providers/${currentProviderId}`);
        const provider = await response.json();                 // 获取提供商详情（含模型列表）
        const model = provider.models.find(m => m.id === modelId);  // 查找目标模型
        if (!model) return;                                     // 模型不存在则不操作

        document.getElementById('modal-title').textContent = '编辑模型';
        document.getElementById('modal-body').innerHTML = `
            <form id="model-form">
                <div class="form-group">
                    <label>模型ID</label>
                    <input type="text" name="model_id" required value="${escapeHtml(model.model_id)}">
                </div>
                <div class="form-group">
                    <label>显示名称</label>
                    <input type="text" name="display_name" required value="${escapeHtml(model.display_name)}">
                </div>
                <div class="form-group">
                    <label>描述</label>
                    <textarea name="description">${escapeHtml(model.description) || ''}</textarea>
                </div>
                <div class="form-group">
                    <label>最大Token数</label>
                    <input type="number" name="max_tokens" value="${model.max_tokens || ''}">
                </div>
                <div class="form-group">
                    <label>支持流式输出</label>
                    <select name="supports_streaming">
                        <option value="1" ${model.supports_streaming ? 'selected' : ''}>是</option>
                        <option value="0" ${!model.supports_streaming ? 'selected' : ''}>否</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>支持多模态 (Vision)</label>
                    <select name="supports_vision">
                        <option value="0" ${!model.supports_vision ? 'selected' : ''}>否</option>
                        <option value="1" ${model.supports_vision ? 'selected' : ''}>是</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>支持函数调用</label>
                    <select name="supports_function_calling">
                        <option value="0" ${!model.supports_function_calling ? 'selected' : ''}>否</option>
                        <option value="1" ${model.supports_function_calling ? 'selected' : ''}>是</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>输入价格 ($/1K tokens)</label>
                    <input type="number" name="price_input" step="0.0001" value="${model.price_input || ''}">
                </div>
                <div class="form-group">
                    <label>输出价格 ($/1K tokens)</label>
                    <input type="number" name="price_output" step="0.0001" value="${model.price_output || ''}">
                </div>
                <div class="form-actions">
                    <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                    <button type="submit" class="btn-primary">保存</button>
                </div>
            </form>
        `;
        // 绑定表单提交事件
        document.getElementById('model-form').addEventListener('submit', async (e) => {
            e.preventDefault();                                 // 阻止默认提交
            const formData = new FormData(e.target);            // 获取表单数据
            const data = Object.fromEntries(formData);          // 转换为对象
            // 类型转换
            data.max_tokens = data.max_tokens ? parseInt(data.max_tokens) : null;
            data.price_input = data.price_input ? parseFloat(data.price_input) : null;
            data.price_output = data.price_output ? parseFloat(data.price_output) : null;
            try {
                await apiRequest(`/api/models/${modelId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                closeModal();                                   // 关闭模态框
                showToast('模型已更新');                          // 显示成功提示
                showProviderDetail(currentProviderId);           // 刷新详情页
            } catch (error) {
                // 错误已由 apiRequest 统一处理
            }
        });
        openModal();                                            // 打开模态框
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

async function deleteModel(modelId) {
    if (!confirm('确定要删除这个模型吗？')) return;              // 确认删除
    try {
        await apiRequest(`/api/models/${modelId}`, { method: 'DELETE' });
        showToast('模型已删除');                                 // 显示成功提示
        showProviderDetail(currentProviderId);                   // 刷新详情页
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 密钥 CRUD 模态框 ======================

function showAddKeyModal() {
    if (!currentProviderId) return;                             // 未选中提供商则不操作
    document.getElementById('modal-title').textContent = '添加API密钥';
    document.getElementById('modal-body').innerHTML = `
        <form id="key-form">
            <div class="form-group">
                <label>密钥名称</label>
                <input type="text" name="key_name" required placeholder="例: 主密钥、测试密钥">
            </div>
            <div class="form-group">
                <label>API Key</label>
                <input type="password" name="api_key" placeholder="输入API密钥...">
            </div>
            <div class="form-group">
                <label>备注</label>
                <textarea name="notes" placeholder="添加备注信息..."></textarea>
            </div>
            <div class="form-actions">
                <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                <button type="submit" class="btn-primary">保存</button>
            </div>
        </form>
    `;
    // 绑定表单提交事件
    document.getElementById('key-form').addEventListener('submit', async (e) => {
        e.preventDefault();                                     // 阻止默认提交
        const formData = new FormData(e.target);                // 获取表单数据
        const data = Object.fromEntries(formData);              // 转换为对象
        try {
            await apiRequest(`/api/providers/${currentProviderId}/keys`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
            closeModal();                                       // 关闭模态框
            showToast('密钥已创建');                              // 显示成功提示
            showProviderDetail(currentProviderId);               // 刷新详情页
        } catch (error) {
            // 错误已由 apiRequest 统一处理
        }
    });
    openModal();                                                // 打开模态框
}

/**
 * 编辑密钥模态框（从提供商详情页触发）
 */
async function showEditKeyModal(keyId) {
    try {
        const response = await apiRequest(`/api/providers/${currentProviderId}`);
        const provider = await response.json();                 // 获取提供商详情
        const key = provider.keys.find(k => k.id === keyId);   // 查找目标密钥
        if (!key) return;                                       // 密钥不存在则不操作
        renderEditKeyForm(key, () => showProviderDetail(currentProviderId));  // 渲染编辑表单
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 编辑密钥模态框（从全局密钥列表触发）
 */
async function showEditKeyModalGlobal(keyId) {
    try {
        const response = await apiRequest('/api/keys');         // 获取所有密钥
        const keys = await response.json();                     // 解析 JSON
        const key = keys.find(k => k.id === keyId);            // 查找目标密钥
        if (!key) return;                                       // 密钥不存在则不操作
        renderEditKeyForm(key, () => loadAllKeys());            // 渲染编辑表单，成功后刷新全局列表
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 渲染密钥编辑表单（共用逻辑）
 * @param {Object} key - 密钥对象
 * @param {Function} onSuccess - 更新成功后的回调函数
 */
function renderEditKeyForm(key, onSuccess) {
    document.getElementById('modal-title').textContent = '编辑API密钥';
    document.getElementById('modal-body').innerHTML = `
        <form id="key-form">
            <div class="form-group">
                <label>密钥名称</label>
                <input type="text" name="key_name" required value="${escapeHtml(key.key_name)}">
            </div>
            <div class="form-group">
                <label>API Key</label>
                <input type="password" name="api_key" value="${escapeHtml(key.api_key) || ''}" placeholder="输入API密钥...">
            </div>
            <div class="form-group">
                <label>备注</label>
                <textarea name="notes">${escapeHtml(key.notes) || ''}</textarea>
            </div>
            <div class="form-actions">
                <button type="button" class="btn-secondary" onclick="closeModal()">取消</button>
                <button type="submit" class="btn-primary">保存</button>
            </div>
        </form>
    `;
    // 绑定表单提交事件
    document.getElementById('key-form').addEventListener('submit', async (e) => {
        e.preventDefault();                                     // 阻止默认提交
        const formData = new FormData(e.target);                // 获取表单数据
        const data = Object.fromEntries(formData);              // 转换为对象
        try {
            await apiRequest(`/api/keys/${key.id}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
            closeModal();                                       // 关闭模态框
            showToast('密钥已更新');                              // 显示成功提示
            if (onSuccess) onSuccess();                         // 执行成功回调
        } catch (error) {
            // 错误已由 apiRequest 统一处理
        }
    });
    openModal();                                                // 打开模态框
}

async function deleteKey(keyId) {
    if (!confirm('确定要删除这个API密钥吗？')) return;           // 确认删除
    try {
        await apiRequest(`/api/keys/${keyId}`, { method: 'DELETE' });
        showToast('密钥已删除');                                 // 显示成功提示
        if (currentPage === 'provider-detail') {
            showProviderDetail(currentProviderId);               // 刷新详情页
        } else {
            loadAllKeys();                                      // 刷新全局密钥列表
        }
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== 模态框控制 ======================

function openModal() {
    document.getElementById('modal-overlay').classList.add('active');  // 显示模态框
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');  // 隐藏模态框
}

// ====================== AI 设置 ======================

/**
 * 加载 AI 设置到表单
 */
async function loadAISettings() {
    try {
        const response = await apiRequest('/api/settings');     // 获取所有设置
        const settings = await response.json();                 // 解析 JSON
        document.getElementById('setting-ai-base-url').value = settings.ai_base_url || '';
        document.getElementById('setting-ai-api-key').value = settings.ai_api_key || '';
        document.getElementById('setting-ai-model').value = settings.ai_model || '';
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 保存 AI 设置
 */
async function saveAISettings() {
    const data = {
        ai_base_url: document.getElementById('setting-ai-base-url').value.trim(),
        ai_api_key: document.getElementById('setting-ai-api-key').value.trim(),
        ai_model: document.getElementById('setting-ai-model').value.trim()
    };
    if (!data.ai_base_url || !data.ai_api_key || !data.ai_model) {
        showToast('请填写所有 AI 设置项', 'error');
        return;
    }
    try {
        await apiRequest('/api/settings', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        showToast('AI 设置已保存');
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== AI 解析 ======================

// 缓存解析结果（用于后续导入）
let parsedData = null;

/**
 * 调用 AI 解析文档内容
 */
async function parseDocument() {
    const content = document.getElementById('ai-input').value.trim();  // 获取输入内容
    if (!content) {
        showToast('请输入要解析的文档内容', 'error');
        return;
    }

    const btn = document.getElementById('btn-ai-parse');       // 获取按钮
    const resultDiv = document.getElementById('ai-result');     // 获取结果容器
    const importActions = document.getElementById('ai-import-actions');  // 获取导入按钮容器

    btn.disabled = true;                                        // 禁用按钮防止重复点击
    btn.textContent = '正在解析...';                              // 显示加载状态
    resultDiv.innerHTML = '<p class="ai-loading">AI 正在分析文档内容，请稍候...</p>';
    importActions.style.display = 'none';                       // 隐藏导入按钮

    try {
        const response = await apiRequest('/api/ai/parse', {
            method: 'POST',
            body: JSON.stringify({ content: content })
        });
        parsedData = await response.json();                     // 缓存解析结果

        // 渲染解析结果
        if (!parsedData.providers || parsedData.providers.length === 0) {
            resultDiv.innerHTML = '<p class="ai-placeholder">未识别到提供商信息，请检查文档内容</p>';
            return;
        }

        let html = '';
        let totalModels = 0;
        parsedData.providers.forEach(p => {
            const modelCount = p.models ? p.models.length : 0;
            totalModels += modelCount;
            html += `
                <div class="ai-result-provider">
                    <div class="ai-result-header">
                        <strong>${escapeHtml(p.display_name || p.name)}</strong>
                        <span class="badge ${p.category === 'domestic' ? 'warning' : 'success'}">${escapeHtml(p.category || 'other')}</span>
                    </div>
                    <div class="ai-result-url">${escapeHtml(p.base_url || '未识别')}</div>
                    <div class="ai-result-desc">${escapeHtml(p.description || '')}</div>
                    ${modelCount > 0 ? `
                        <div class="ai-result-models">
                            <span>识别到 ${modelCount} 个模型：</span>
                            ${p.models.map(m => `<code>${escapeHtml(m.model_id)}</code>`).join(', ')}
                        </div>
                    ` : '<div class="ai-result-models">未识别到模型信息</div>'}
                </div>
            `;
        });

        resultDiv.innerHTML = html;
        document.getElementById('ai-import-summary').textContent =
            `将导入 ${parsedData.providers.length} 个提供商，${totalModels} 个模型`;
        importActions.style.display = 'flex';                   // 显示导入按钮

    } catch (error) {
        resultDiv.innerHTML = `<p class="ai-placeholder">解析失败：${escapeHtml(error.message)}</p>`;
    } finally {
        btn.disabled = false;                                   // 恢复按钮
        btn.textContent = 'AI 解析';                             // 恢复按钮文本
    }
}

/**
 * 导入 AI 解析结果
 */
async function importParsedData() {
    if (!parsedData || !parsedData.providers || parsedData.providers.length === 0) {
        showToast('没有可导入的数据', 'error');
        return;
    }

    const btn = event.target;                                   // 获取按钮
    btn.disabled = true;                                        // 禁用按钮
    btn.textContent = '正在导入...';                              // 显示加载状态

    try {
        const response = await apiRequest('/api/ai/import', {
            method: 'POST',
            body: JSON.stringify(parsedData)
        });
        const result = await response.json();
        showToast(result.message);
        parsedData = null;                                      // 清空缓存
        document.getElementById('ai-import-actions').style.display = 'none';  // 隐藏导入按钮
        loadStats();                                            // 刷新统计数据
        loadProviders();                                        // 刷新提供商列表
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    } finally {
        btn.disabled = false;                                   // 恢复按钮
        btn.textContent = '确认导入';                             // 恢复按钮文本
    }
}

/**
 * 清空 AI 输入框
 */
function clearAiInput() {
    document.getElementById('ai-input').value = '';
    document.getElementById('ai-result').innerHTML = '<p class="ai-placeholder">解析结果将显示在这里...</p>';
    document.getElementById('ai-import-actions').style.display = 'none';
    parsedData = null;
}

/**
 * 关闭服务器
 */
async function shutdownServer() {
    if (!confirm('确定要关闭服务器吗？关闭后需要重新启动程序。')) return;
    try {
        await fetch('/api/shutdown', { method: 'POST' });
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-size:20px;color:#888;">服务器已关闭，可以关闭此页面</div>';
    } catch {
        fetch('/api/shutdown', { method: 'POST' }).catch(() => {});
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-size:20px;color:#888;">服务器已关闭，可以关闭此页面</div>';
    }
}
