// ============================================================
// AI API Hub — 前端主逻辑
// 纯 vanilla JavaScript 实现，无框架依赖
// ============================================================

// 全局状态变量
let currentPage = 'dashboard';    // 当前显示的页面名称
let currentProviderId = null;     // 当前查看的提供商 ID（用于详情页）
let allProviders = [];            // 缓存所有提供商数据（用于筛选）
let allModelsCache = [];          // 缓存所有模型数据（用于筛选和折叠）
let modelsSort = { col: '', dir: 'asc' };  // 模型列表排序状态

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

    // 初始化文件拖拽区
    setupFileDropZone();
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
    grid.innerHTML = providers.map(p => {
        const apiUrls = p.api_urls || [];                      // 获取 URL 列表
        const urlText = apiUrls.length > 0                     // 如果有 URL
            ? apiUrls.map(u => u.label || 'API').join('、') + ' · ' + apiUrls[0].url  // 显示标签和第一个 URL
            : '未设置URL';                                     // 无 URL 时的默认文本
        return `
        <div class="provider-card" onclick="showProviderDetail(${p.id})">
            <div class="provider-card-header">
                <div class="provider-name">${escapeHtml(p.display_name)}</div>
                <div class="provider-category">${escapeHtml(getCategoryName(p.category))}</div>
            </div>
            <div class="provider-url" title="${escapeHtml(urlText)}">${escapeHtml(urlText)}</div>
            <div class="provider-desc">${escapeHtml(p.description) || '暂无描述'}</div>
        </div>
    `;}).join('');
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
    list.innerHTML = providers.map(p => {
        const apiUrls = p.api_urls || [];                      // 获取 URL 列表
        const urlSummary = apiUrls.length > 0                  // 如果有 URL
            ? apiUrls.map(u => u.label || 'API').join('、')    // 显示所有标签
            : '未设置URL';                                     // 无 URL 时的默认文本
        return `
        <div class="provider-list-item">
            <div class="provider-list-info">
                <h3>${escapeHtml(p.display_name)}</h3>
                <p>${escapeHtml(urlSummary)} &middot; ${escapeHtml(getCategoryName(p.category))}</p>
            </div>
            <div class="provider-list-actions">
                <button class="btn-small" onclick="showProviderDetail(${p.id})">查看</button>
                <button class="btn-small" onclick="showEditProviderModal(${p.id})">编辑</button>
                <button class="btn-small danger" onclick="deleteProvider(${p.id})">删除</button>
            </div>
        </div>
    `;}).join('');
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
        const apiUrls = provider.api_urls || [];               // 获取 URL 列表
        const urlsHtml = apiUrls.length > 0                    // 如果有 URL
            ? apiUrls.map(u => `
                <div class="url-display-item">
                    <span class="url-display-label">${escapeHtml(u.label || 'API')}</span>
                    <span class="badge ${u.format === 'anthropic' ? 'warning' : 'success'}">${escapeHtml(u.format || 'openai')}</span>
                    <span class="url-display-link">${escapeHtml(u.url)}</span>
                    <button class="btn-copy" onclick="copyToClipboard('${escapeHtml(u.url)}', this)">复制</button>
                </div>
            `).join('')
            : '<span style="color: var(--text-secondary);">未设置</span>';  // 无 URL 时显示提示

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
            <div class="info-item info-item-wide">
                <div class="info-label">API URLs</div>
                <div class="info-value url-display-list">${urlsHtml}</div>
            </div>
            <div class="info-item info-item-wide">
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
                    <th>缓存价格</th>
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
                        <td>${m.price_input ? `¥${m.price_input}/1M` : '-'}</td>
                        <td>${m.price_input_cached ? `¥${m.price_input_cached}/1M` : '-'}</td>
                        <td>${m.price_output ? `¥${m.price_output}/1M` : '-'}</td>
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
        const response = await apiRequest('/api/models');      // 请求所有模型列表
        allModelsCache = await response.json();                // 缓存到全局变量
        filterModels();                                        // 执行筛选和渲染
    } catch (error) {}                                         // 错误已由 apiRequest 处理
}

function sortModelsBy(col) {
    if (modelsSort.col === col) {                           // 如果点击的是当前排序列
        modelsSort.dir = modelsSort.dir === 'asc' ? 'desc' : 'asc';  // 切换排序方向
    } else {
        modelsSort.col = col;                               // 设置新的排序列
        modelsSort.dir = 'asc';                             // 默认升序
    }
    filterModels();                                         // 重新筛选并渲染
}

function filterModels() {
    const tbody = document.getElementById('models-table-body');  // 获取表格主体
    if (!tbody) return;                                          // 元素不存在则退出

    const searchVal = (document.getElementById('models-search')?.value || '').toLowerCase();  // 获取全局搜索关键词
    const collapse = document.getElementById('models-collapse-toggle')?.checked || false;     // 获取折叠开关状态

    // 收集列筛选条件（文本输入框）
    const filters = {};
    document.querySelectorAll('.filter-row input[data-col]').forEach(input => {
        const val = input.value.trim().toLowerCase();          // 获取筛选值并转小写
        if (val) filters[input.dataset.col] = val;            // 非空则加入筛选条件
    });
    // 收集列筛选条件下拉框
    document.querySelectorAll('.filter-row select[data-col]').forEach(sel => {
        if (sel.value !== '') filters[sel.dataset.col] = sel.value;  // 非空则加入筛选条件
    });

    // 筛选模型：先全局搜索，再逐列筛选
    let filtered = allModelsCache.filter(m => {
        if (searchVal) {                                       // 如果有全局搜索关键词
            const haystack = `${m.provider_name} ${m.model_id} ${m.display_name}`.toLowerCase();  // 拼接搜索范围
            if (!haystack.includes(searchVal)) return false;   // 不匹配则排除
        }
        for (const [col, val] of Object.entries(filters)) {   // 遍历列筛选条件
            if (col === 'supports_vision' || col === 'supports_function_calling') {
                if (String(m[col] ? 1 : 0) !== val) return false;  // 布尔列精确匹配
            } else {
                if (!String(m[col] || '').toLowerCase().includes(val)) return false;  // 文本列模糊匹配
            }
        }
        return true;                                           // 通过所有筛选条件
    });

    // 排序
    if (modelsSort.col) {                                      // 如果有排序列
        const dir = modelsSort.dir === 'asc' ? 1 : -1;        // 排序方向：升序=1，降序=-1
        filtered.sort((a, b) => {
            const va = a[modelsSort.col] ?? 0;                 // 获取值，null 默认 0
            const vb = b[modelsSort.col] ?? 0;
            return (va - vb) * dir;                            // 数值比较并乘以方向
        });
    }

    if (filtered.length === 0) {                               // 如果没有匹配结果
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color: var(--text-secondary);">暂无匹配模型</td></tr>';
        return;
    }

    // 按提供商分组
    const groups = {};
    filtered.forEach(m => {
        const key = m.provider_name || '未知提供商';           // 分组键
        if (!groups[key]) groups[key] = [];                    // 初始化分组数组
        groups[key].push(m);                                   // 添加到对应分组
    });

    let html = '';                                             // 构建表格 HTML
    for (const [provider, models] of Object.entries(groups)) { // 遍历每个分组
        if (collapse) {                                        // 如果折叠模式开启
            html += `
                <tr class="provider-group-header" onclick="toggleProviderGroup(this)">
                    <td colspan="10">
                        <span class="group-toggle">&#x25B6;</span>
                        <strong>${escapeHtml(provider)}</strong>
                        <span class="group-count">(${models.length} 个模型)</span>
                    </td>
                </tr>
            `;
        }
        models.forEach(m => {                                  // 遍历分组内的模型
            html += `
                <tr class="${collapse ? 'provider-group-row collapsed' : ''}">
                    <td>${escapeHtml(m.provider_name)}</td>
                    <td><code>${escapeHtml(m.model_id)}</code></td>
                    <td>${escapeHtml(m.display_name)}</td>
                    <td>${m.max_tokens ? m.max_tokens.toLocaleString() : '-'}</td>
                    <td>${m.supports_vision ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                    <td>${m.supports_function_calling ? '<span class="badge success">是</span>' : '<span class="badge warning">否</span>'}</td>
                    <td>${m.price_input ? `¥${m.price_input}/1M` : '-'}</td>
                    <td>${m.price_input_cached ? `¥${m.price_input_cached}/1M` : '-'}</td>
                    <td>${m.price_output ? `¥${m.price_output}/1M` : '-'}</td>
                    <td>
                        <button class="btn-small" onclick="goToModelEdit(${m.provider_id}, ${m.id})">编辑</button>
                        <button class="btn-small danger" onclick="deleteModelFromList(${m.id})">删除</button>
                    </td>
                </tr>
            `;
        });
    }
    tbody.innerHTML = html;                                    // 写入表格 DOM

    // 更新排序指示器（▲/▼ 箭头）
    const sortCols = { max_tokens: 3, price_input: 6, price_input_cached: 7, price_output: 8 };  // 可排序列索引映射
    document.querySelectorAll('#models-table thead tr:first-child th').forEach((th, i) => {
        th.classList.remove('sort-asc', 'sort-desc');          // 清除所有排序样式
        for (const [col, idx] of Object.entries(sortCols)) {   // 遍历可排序列
            if (i === idx && modelsSort.col === col) {         // 匹配当前排序列
                th.classList.add(modelsSort.dir === 'asc' ? 'sort-asc' : 'sort-desc');  // 添加排序方向样式
            }
        }
    });
}

function toggleProviderGroup(headerRow) {
    const icon = headerRow.querySelector('.group-toggle');      // 获取折叠图标元素
    const expanding = icon.textContent === '▶';                // 当前是折叠状态则展开
    icon.textContent = expanding ? '▼' : '▶';                 // 切换图标方向
    let row = headerRow.nextElementSibling;                     // 获取下一行
    while (row && row.classList.contains('provider-group-row')) {  // 遍历同组行
        row.style.display = expanding ? '' : 'none';           // 展开显示，折叠隐藏
        row = row.nextElementSibling;                           // 移动到下一行
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

// ====================== URL 动态列表 ======================

let urlEntryIndex = 0;                                         // URL 条目计数器（用于生成唯一索引）

function createUrlEntryHtml(entry = {}) {
    const idx = urlEntryIndex++;                               // 递增索引
    return `
        <div class="url-entry" data-index="${idx}">
            <input type="text" class="url-entry-label" value="${escapeHtml(entry.label || '')}" placeholder="名称，如：按量计费">
            <input type="text" class="url-entry-url" value="${escapeHtml(entry.url || '')}" placeholder="完整 API 地址">
            <select class="url-entry-format">
                <option value="openai" ${entry.format === 'openai' ? 'selected' : ''}>OpenAI</option>
                <option value="anthropic" ${entry.format === 'anthropic' ? 'selected' : ''}>Anthropic</option>
            </select>
            <button type="button" class="btn-small danger" onclick="removeUrlEntry(this)">删除</button>
        </div>
    `;
}

function addUrlEntry(containerId, entry = {}) {
    const container = document.getElementById(containerId);     // 获取容器元素
    container.insertAdjacentHTML('beforeend', createUrlEntryHtml(entry));  // 追加新条目 HTML
}

function removeUrlEntry(btn) {
    btn.closest('.url-entry').remove();                         // 找到最近的 url-entry 父元素并移除
}

function collectApiUrls(formEl) {
    const entries = formEl.querySelectorAll('.url-entry');      // 获取所有 URL 条目
    const urls = [];                                            // 结果数组
    entries.forEach(entry => {
        const url = entry.querySelector('.url-entry-url').value.trim();  // 获取 URL 值
        if (url) {                                              // URL 非空才收集
            urls.push({
                label: entry.querySelector('.url-entry-label').value.trim() || 'API',  // 标签，默认 'API'
                url: url,                                       // URL 地址
                format: entry.querySelector('.url-entry-format').value  // 接口格式
            });
        }
    });
    return urls;                                                // 返回 URL 数组
}

function renderApiUrlsForm(containerId, apiUrls) {
    urlEntryIndex = 0;                                          // 重置索引计数器
    const container = document.getElementById(containerId);     // 获取容器元素
    container.innerHTML = '';                                   // 清空容器
    const urls = Array.isArray(apiUrls) ? apiUrls : [];        // 确保是数组
    if (urls.length === 0) {
        addUrlEntry(containerId);                               // 至少显示一行空条目
    } else {
        urls.forEach(u => addUrlEntry(containerId, u));        // 为每个已有 URL 创建条目
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
                <label>API URLs</label>
                <div id="url-entries" class="url-entries"></div>
                <button type="button" class="btn-small" onclick="addUrlEntry('url-entries')">+ 添加URL</button>
                <small>可添加多个地址（如不同计费方式），选择接口格式</small>
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
    renderApiUrlsForm('url-entries', []);                      // 初始化空的 URL 列表
    document.getElementById('provider-form').addEventListener('submit', async (e) => {
        e.preventDefault();                                     // 阻止表单默认提交
        const formData = new FormData(e.target);                // 获取表单数据
        const data = Object.fromEntries(formData);              // 转换为对象
        data.api_urls = collectApiUrls(e.target);              // 收集 URL 列表数据
        delete data.url_label;                                  // 清理临时字段
        delete data.url_value;
        delete data.url_format;
        try {
            await apiRequest('/api/providers', {
                method: 'POST',                                // POST 创建新提供商
                body: JSON.stringify(data)                     // 序列化为 JSON
            });
            closeModal();                                       // 关闭模态框
            showToast('提供商已创建');                          // 显示成功提示
            loadProviders();                                    // 刷新提供商列表
            loadStats();                                        // 刷新统计数据
        } catch (error) {}                                     // 错误已由 apiRequest 处理
    });
    openModal();                                                // 打开模态框
}

async function showEditProviderModal(providerId) {
    try {
        const response = await apiRequest(`/api/providers/${providerId}`);
        const provider = await response.json();
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
                    <label>API URLs</label>
                    <div id="url-entries" class="url-entries"></div>
                    <button type="button" class="btn-small" onclick="addUrlEntry('url-entries')">+ 添加URL</button>
                    <small>可添加多个地址（如不同计费方式），选择接口格式</small>
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
        renderApiUrlsForm('url-entries', provider.api_urls);   // 填充已有的 URL 数据
        document.getElementById('provider-form').addEventListener('submit', async (e) => {
            e.preventDefault();                                 // 阻止表单默认提交
            const formData = new FormData(e.target);            // 获取表单数据
            const data = Object.fromEntries(formData);          // 转换为对象
            data.api_urls = collectApiUrls(e.target);          // 收集 URL 列表数据
            try {
                await apiRequest(`/api/providers/${providerId}`, {
                    method: 'PUT',                             // PUT 更新提供商
                    body: JSON.stringify(data)                 // 序列化为 JSON
                });
                closeModal();                                   // 关闭模态框
                showToast('提供商已更新');                      // 显示成功提示
                loadProviders();                                // 刷新提供商列表
                if (currentPage === 'provider-detail') {       // 如果在详情页
                    showProviderDetail(providerId);             // 刷新详情页
                }
            } catch (error) {}                                 // 错误已由 apiRequest 处理
        });
        openModal();                                            // 打开模态框
    } catch (error) {}                                         // 错误已由 apiRequest 处理
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
                <label>输入价格 (¥/1M tokens)</label>
                <input type="number" name="price_input" step="0.01" placeholder="例: 5">
            </div>
            <div class="form-group">
                <label>缓存命中价格 (¥/1M tokens)</label>
                <input type="number" name="price_input_cached" step="0.01" placeholder="例: 1">
            </div>
            <div class="form-group">
                <label>输出价格 (¥/1M tokens)</label>
                <input type="number" name="price_output" step="0.01" placeholder="例: 15">
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
        data.price_input_cached = data.price_input_cached ? parseFloat(data.price_input_cached) : null;
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
                    <label>输入价格 (¥/1M tokens)</label>
                    <input type="number" name="price_input" step="0.01" value="${model.price_input || ''}">
                </div>
                <div class="form-group">
                    <label>缓存命中价格 (¥/1M tokens)</label>
                    <input type="number" name="price_input_cached" step="0.01" value="${model.price_input_cached || ''}">
                </div>
                <div class="form-group">
                    <label>输出价格 (¥/1M tokens)</label>
                    <input type="number" name="price_output" step="0.01" value="${model.price_output || ''}">
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
            data.price_input_cached = data.price_input_cached ? parseFloat(data.price_input_cached) : null;
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
        document.getElementById('setting-ai-format').value = settings.ai_format || 'openai';  // 设置接口格式
        document.getElementById('setting-ai-url').value = settings.ai_url || settings.ai_base_url || '';  // 设置 API URL
        document.getElementById('setting-ai-api-key').value = settings.ai_api_key || '';  // 设置 API Key
        document.getElementById('setting-ai-model').value = settings.ai_model || '';  // 设置模型名称
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

/**
 * 保存 AI 设置
 */
async function saveAISettings() {
    const data = {
        ai_format: document.getElementById('setting-ai-format').value,  // 获取接口格式
        ai_url: document.getElementById('setting-ai-url').value.trim(),  // 获取 API URL
        ai_api_key: document.getElementById('setting-ai-api-key').value.trim(),  // 获取 API Key
        ai_model: document.getElementById('setting-ai-model').value.trim()  // 获取模型名称
    };
    if (!data.ai_url || !data.ai_api_key || !data.ai_model) {  // 检查必填项
        showToast('请填写所有 AI 设置项', 'error');
        return;
    }
    try {
        await apiRequest('/api/settings', {
            method: 'PUT',                                     // PUT 更新设置
            body: JSON.stringify(data)                         // 序列化为 JSON
        });
        showToast('AI 设置已保存');                            // 显示成功提示
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    }
}

// ====================== AI 解析 ======================

// 缓存解析结果（用于后续导入）
let parsedData = null;
let currentInputMode = 'text';  // 当前输入模式：text / file / url
let selectedFile = null;        // 选中的文件

/**
 * 切换输入模式
 */
function switchInputMode(mode) {
    currentInputMode = mode;                                   // 更新当前输入模式状态
    // 切换 tab 高亮
    document.querySelectorAll('.ai-tab').forEach(t => t.classList.remove('active'));  // 移除所有 tab 的 active
    document.querySelector(`.ai-tab[data-mode="${mode}"]`).classList.add('active');   // 激活当前 tab
    // 切换输入区域
    document.querySelectorAll('.ai-input-mode').forEach(el => el.style.display = 'none');  // 隐藏所有输入区
    document.getElementById(`input-mode-${mode}`).style.display = 'block';           // 显示当前输入区
}

/**
 * 初始化文件拖拽区
 */
function setupFileDropZone() {
    const dropZone = document.getElementById('ai-file-drop');   // 获取拖拽区域
    const fileInput = document.getElementById('ai-file-input'); // 获取文件输入框
    if (!dropZone || !fileInput) return;                        // 元素不存在则退出

    dropZone.addEventListener('click', () => fileInput.click());  // 点击拖拽区触发文件选择
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });  // 拖入时高亮
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));  // 拖出时取消高亮
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();                                     // 阻止默认打开文件行为
        dropZone.classList.remove('dragover');                  // 取消高亮
        if (e.dataTransfer.files.length > 0) handleFileSelected(e.dataTransfer.files[0]);  // 处理拖放的文件
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileSelected(fileInput.files[0]);  // 处理选择的文件
    });
}

/**
 * 处理文件选中
 */
function handleFileSelected(file) {
    selectedFile = file;                                       // 保存选中的文件到全局变量
    const sizeKB = (file.size / 1024).toFixed(1);             // 计算 KB 大小
    const sizeMB = (file.size / 1024 / 1024).toFixed(2);     // 计算 MB 大小
    const sizeStr = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;  // 超过 1MB 显示 MB
    document.getElementById('ai-file-name').textContent = `${file.name} (${sizeStr})`;  // 显示文件名和大小
    document.getElementById('ai-file-info').style.display = 'flex';  // 显示文件信息区
    document.getElementById('ai-file-drop').style.display = 'none';  // 隐藏拖拽区
}

/**
 * 清除文件选择
 */
function clearFileInput() {
    selectedFile = null;                                       // 清空文件引用
    document.getElementById('ai-file-input').value = '';       // 重置文件输入框
    document.getElementById('ai-file-info').style.display = 'none';  // 隐藏文件信息区
    document.getElementById('ai-file-drop').style.display = 'block'; // 显示拖拽区
}

/**
 * 渲染解析结果（公共逻辑）
 */
function renderParseResult(data) {
    const resultDiv = document.getElementById('ai-result');     // 获取结果容器
    const importActions = document.getElementById('ai-import-actions');  // 获取导入操作区

    parsedData = data;                                         // 缓存解析结果（用于后续导入）

    if (!data.providers || data.providers.length === 0) {      // 如果没有识别到提供商
        resultDiv.innerHTML = '<p class="ai-placeholder">未识别到提供商信息，请检查文档内容</p>';
        return;
    }

    let html = '';                                             // 构建结果 HTML
    let totalModels = 0;                                       // 模型总数计数
    data.providers.forEach(p => {
        const modelCount = p.models ? p.models.length : 0;    // 当前提供商的模型数
        totalModels += modelCount;                             // 累加模型总数
        const apiUrls = p.api_urls || [];                      // 获取 URL 列表
        const urlsDisplay = apiUrls.length > 0                 // 如果有 URL
            ? apiUrls.map(u => `<code>${escapeHtml(u.label || 'API')}: ${escapeHtml(u.url)}</code>`).join('<br>')  // 显示标签+URL
            : escapeHtml(p.base_url || '未识别');              // 否则显示 base_url
        html += `
            <div class="ai-result-provider">
                <div class="ai-result-header">
                    <strong>${escapeHtml(p.display_name || p.name)}</strong>
                    <span class="badge ${p.category === 'domestic' ? 'warning' : 'success'}">${escapeHtml(p.category || 'other')}</span>
                </div>
                <div class="ai-result-url">${urlsDisplay}</div>
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

    resultDiv.innerHTML = html;                                // 写入结果 HTML
    document.getElementById('ai-import-summary').textContent =
        `将导入 ${data.providers.length} 个提供商，${totalModels} 个模型`;  // 显示导入摘要
    importActions.style.display = 'flex';                      // 显示导入操作按钮
}

/**
 * 调用 AI 解析文档内容（支持文本、文件、URL 三种模式）
 */
async function parseDocument() {
    const btn = document.getElementById('btn-ai-parse');        // 获取解析按钮
    const resultDiv = document.getElementById('ai-result');     // 获取结果容器
    const importActions = document.getElementById('ai-import-actions');  // 获取导入操作区

    btn.disabled = true;                                       // 禁用按钮防止重复点击
    btn.textContent = '正在解析...';                           // 更新按钮文本
    resultDiv.innerHTML = '<p class="ai-loading">AI 正在分析文档内容，请稍候...</p>';  // 显示加载提示
    importActions.style.display = 'none';                      // 隐藏导入操作区

    try {
        let response;                                          // 响应对象

        if (currentInputMode === 'file' && selectedFile) {
            // 文件上传模式
            const formData = new FormData();                   // 创建 FormData 对象
            formData.append('mode', 'file');                   // 设置模式为文件
            formData.append('file', selectedFile);             // 添加文件
            response = await fetch('/api/ai/parse', { method: 'POST', body: formData });  // 发送文件上传请求
        } else if (currentInputMode === 'url') {
            // URL 模式
            const url = document.getElementById('ai-url-input').value.trim();  // 获取 URL
            if (!url) {                                        // URL 为空则提示
                showToast('请输入网页 URL', 'error');
                btn.disabled = false;                          // 恢复按钮
                btn.textContent = 'AI 解析';                   // 恢复按钮文本
                resultDiv.innerHTML = '<p class="ai-placeholder">解析结果将显示在这里...</p>';
                return;
            }
            const formData = new FormData();                   // 创建 FormData 对象
            formData.append('mode', 'url');                    // 设置模式为 URL
            formData.append('url', url);                       // 添加 URL
            response = await fetch('/api/ai/parse', { method: 'POST', body: formData });  // 发送 URL 请求
        } else {
            // 文本模式
            const content = document.getElementById('ai-input').value.trim();  // 获取文本内容
            if (!content) {                                    // 内容为空则提示
                showToast('请输入要解析的文档内容', 'error');
                btn.disabled = false;                          // 恢复按钮
                btn.textContent = 'AI 解析';                   // 恢复按钮文本
                resultDiv.innerHTML = '<p class="ai-placeholder">解析结果将显示在这里...</p>';
                return;
            }
            response = await fetch('/api/ai/parse', {
                method: 'POST',                                // POST 请求
                headers: { 'Content-Type': 'application/json' },  // JSON 格式
                body: JSON.stringify({ content })              // 发送文本内容
            });
        }

        if (!response.ok) {                                    // 如果响应状态码非 2xx
            const err = await response.json().catch(() => ({}));  // 尝试解析错误信息
            throw new Error(err.error || `请求失败 (${response.status})`);
        }

        const data = await response.json();                    // 解析响应 JSON
        renderParseResult(data);                               // 渲染解析结果

    } catch (error) {
        resultDiv.innerHTML = `<p class="ai-placeholder">解析失败：${escapeHtml(error.message)}</p>`;  // 显示错误信息
    } finally {
        btn.disabled = false;                                  // 恢复按钮
        btn.textContent = 'AI 解析';                           // 恢复按钮文本
    }
}

/**
 * 导入 AI 解析结果
 */
async function importParsedData() {
    if (!parsedData || !parsedData.providers || parsedData.providers.length === 0) {  // 检查是否有数据
        showToast('没有可导入的数据', 'error');
        return;
    }

    const btn = event.target;                                  // 获取触发按钮
    btn.disabled = true;                                       // 禁用按钮防止重复点击
    btn.textContent = '正在导入...';                           // 更新按钮文本

    try {
        const overwrite = document.getElementById('ai-overwrite-mode').checked;  // 获取是否覆盖已有数据
        const response = await apiRequest('/api/ai/import', {
            method: 'POST',                                    // POST 请求
            body: JSON.stringify({ ...parsedData, overwrite })  // 合并数据和覆盖标志
        });
        const result = await response.json();                  // 解析响应
        showToast(result.message);                             // 显示导入结果
        parsedData = null;                                     // 清空缓存数据
        document.getElementById('ai-import-actions').style.display = 'none';  // 隐藏导入操作区
        loadStats();                                           // 刷新统计数据
        loadProviders();                                       // 刷新提供商列表
    } catch (error) {
        // 错误已由 apiRequest 统一处理
    } finally {
        btn.disabled = false;                                  // 恢复按钮
        btn.textContent = '确认导入';                          // 恢复按钮文本
    }
}

/**
 * 清空 AI 输入
 */
function clearAiInput() {
    document.getElementById('ai-input').value = '';            // 清空文本输入框
    document.getElementById('ai-url-input').value = '';        // 清空 URL 输入框
    clearFileInput();                                          // 清除文件选择
    document.getElementById('ai-result').innerHTML = '<p class="ai-placeholder">解析结果将显示在这里...</p>';  // 重置结果区
    document.getElementById('ai-import-actions').style.display = 'none';  // 隐藏导入操作区
    parsedData = null;                                         // 清空缓存数据
}

/**
 * 关闭服务器
 */
async function shutdownServer() {
    if (!confirm('确定要关闭服务器吗？关闭后需要重新启动程序。')) return;  // 确认关闭
    try {
        await fetch('/api/shutdown', { method: 'POST' });      // 发送关闭请求
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-size:20px;color:#888;">服务器已关闭，可以关闭此页面</div>';
    } catch {
        fetch('/api/shutdown', { method: 'POST' }).catch(() => {});  // 重试一次
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-size:20px;color:#888;">服务器已关闭，可以关闭此页面</div>';
    }
}
