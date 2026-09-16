const state = { cards: [], track: 'all', query: '' };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value = '') => String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
const fmtDate = value => {
  if (!value) return '日期未知';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }).format(date);
};

const labelMap = {
  paradigm_novelty: '范式新颖性', musculoskeletal_gap: '肌骨空白度', clinical_significance: '临床意义',
  data_feasibility: '数据可行性', mechanistic_depth: '机制深度', competition_urgency: '竞争紧迫度'
};
const noveltyLabels = {
  'Directly studied': '已有直接研究',
  'Adjacent studies exist': '存在相邻研究',
  'No direct match found in current search': '当前检索未见直接匹配',
  'Unresolved': '尚未判定'
};
const conceptTerms = [
  ['bone-muscle crosstalk', '骨—肌互作'], ['spatial transcriptomics', '空间转录组学'],
  ['cell-cell communication', '细胞间通讯'], ['organ-specific aging', '器官特异性衰老'],
  ['longitudinal trajectory', '纵向轨迹'], ['multi-organ network', '多器官网络'],
  ['cardiac magnetic resonance imaging', '心脏磁共振成像'], ['foundation model', '基础模型'],
  ['multimodal imaging', '多模态影像'], ['single-cell aging', '单细胞衰老'],
  ['skeletal aging', '骨骼衰老'], ['muscle aging', '肌肉衰老'], ['bone aging', '骨衰老'],
  ['aging clock', '衰老时钟'], ['digital twin', '数字孪生'], ['risk prediction', '风险预测'],
  ['uk biobank', '英国生物样本库'], ['proteomics', '蛋白质组学'], ['metabolomics', '代谢组学'],
  ['single-cell', '单细胞'], ['multimodal', '多模态'], ['longitudinal', '纵向'],
  ['rejuvenation', '年轻化干预'], ['perturbation', '扰动研究'], ['senescence', '细胞衰老'],
  ['osteosarcopenia', '骨质疏松性肌少症'], ['osteoporosis', '骨质疏松'], ['sarcopenia', '肌少症'],
  ['osteocyte', '骨细胞'], ['osteokine', '骨源性因子'], ['myokine', '肌源性因子'],
  ['frailty', '衰弱'], ['fracture', '骨折'], ['atlas', '图谱'], ['ecg', '心电图'],
  ['cardiac mri', '心脏磁共振'], ['computed tomography', '计算机断层扫描'], ['resource', '数据资源']
];
const titlePhrases = [
  ['a generalizable', '可泛化的'], ['an integrated', '整合的'], ['integrating', '整合'],
  ['reveals', '揭示'], ['identifies', '识别'], ['predicts', '预测'], ['prediction of', '预测'],
  ['associated with', '与……相关'], ['using', '使用'], ['across', '跨'], ['in human', '在人类'],
  ['for', '用于'], ['and', '与'], ['of', '的']
];
const trendLabels = {
  spatial: '空间组学', 'single-cell': '单细胞', 'foundation model': '基础模型', longitudinal: '纵向研究',
  proteomics: '蛋白质组学', metabolomics: '代谢组学', multimodal: '多模态', perturbation: '扰动研究', atlas: '图谱资源'
};
const dataLabels = {
  'UK Biobank': '英国生物样本库', NHANES: 'NHANES', 'hospital DXA': '医院 DXA', CT: 'CT',
  'human tissue': '人体组织', 'animal experiment': '动物实验', omics: '组学', 'clinical cohort': '临床队列'
};

function conceptsFor(card) {
  const haystack = `${card.title || ''} ${card.abstract || ''} ${card.new_paradigm || ''}`.toLowerCase();
  const labels = [];
  conceptTerms.forEach(([term, label]) => {
    if (haystack.includes(term) && !labels.includes(label)) labels.push(label);
  });
  return labels;
}

function chineseTitle(card) {
  const original = card.title || '未命名研究';
  let translated = original;
  [...conceptTerms, ...titlePhrases].sort((a, b) => b[0].length - a[0].length).forEach(([source, target]) => {
    const escapedSource = source.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    translated = translated.replace(new RegExp(`\\b${escapedSource}\\b`, 'gi'), target);
  });
  translated = translated.replace(/\s*:\s*/g, '：').replace(/\s+/g, ' ').replace(/\s*([，。；：])\s*/g, '$1').replace(/([\u3400-\u9fff])\s+(?=[\u3400-\u9fff])/g, '$1').trim();
  const englishWords = translated.match(/[A-Za-z]{3,}/g) || [];
  const concepts = conceptsFor(card);
  if (englishWords.length <= 5 && /[\u3400-\u9fff]/.test(translated)) return translated;
  if (concepts.length) return `${concepts.slice(0, 5).join('、')}相关研究：${card.track === 'A' ? '肌骨直接证据' : '前沿迁移机会'}`;
  return `${card.track === 'A' ? '肌骨直接研究' : '跨学科前沿研究'}（中文概念标题）`;
}

function abstractSentences(text) {
  return (text || '').split(/(?<=[.!?])\s+/).map(item => item.trim()).filter(item => item.length > 20);
}

function structuredDigest(card) {
  const abstract = card.abstract || '';
  const low = abstract.toLowerCase();
  const concepts = conceptsFor(card);
  const topic = concepts.slice(0, 4).join('、') || (card.track === 'A' ? '肌骨疾病与衰老' : '跨学科新方法');
  const background = card.track === 'A'
    ? `研究直接关注${topic}，尝试解释相关生物学变化、疾病风险或临床结局。`
    : `研究来自肌骨领域之外，重点关注${topic}；本雷达评估它是否能迁移到骨质疏松、肌少症或骨折研究。`;
  const summaryMethod = (card.summary_zh || [])[1]?.split('摘要证据：')[0]?.trim();
  const sampleMatches = abstract.match(/\b[\d,]+\s+(?:paired\s+)?(?:participants?|patients?|subjects?|samples?|individuals?|cohorts?)/ig) || [];
  const sampleText = sampleMatches.length ? ` 摘要提到的规模/验证线索：${sampleMatches.slice(0, 3).join('、')}。` : '';
  const localizedData = (card.data_needs || []).map(item => dataLabels[item] || item);
  const methods = `${summaryMethod || `作者采用与${topic}相关的队列、实验或计算分析。`} 所需数据包括：${localizedData.join('、') || '需阅读全文核对'}。${sampleText}`;
  const findings = [];
  if (/improv(?:ed|es|ing)|outperform(?:ed|s)?|superior/.test(low)) findings.push('摘要称新方法相较现有方案提高了预测或分析表现');
  if (/identif(?:y|ied|ies)|reveal(?:ed|s)?|discover(?:ed|s)?/.test(low)) findings.push('研究识别或揭示了新的信号、细胞状态或生物学模式');
  if (/associat(?:ed|ion)|correlat(?:ed|ion)/.test(low)) findings.push('研究报告了目标因素与疾病或临床结局之间的关联');
  if (/external cohort|independent cohort|externally validat|replicat(?:ed|ion)/.test(low)) findings.push('关键结果在外部或独立队列中进行了验证');
  if (/predict(?:ed|ion|s)|prognos/.test(low) && !findings.some(item => item.includes('预测'))) findings.push('结果包含预测或预后评估');
  const result = findings.length
    ? `${findings.join('；')}。具体效应方向、数值与统计显著性需打开原文核对。`
    : '摘要提供了初步结果，但自动规则无法可靠翻译具体效应方向和数值；请结合下方英文摘要证据核对。';
  const discussion = `${card.musculoskeletal_link || '其与骨/肌研究的具体联系仍需人工判断'} ${card.new_paradigm || ''} 目前为摘要级解读，不能替代全文中的讨论、偏倚评估和作者局限。`;
  return { background, methods, result, discussion, evidence: abstractSentences(abstract).slice(0, 3) };
}

function statusInfo(card) {
  return card.publication_status === 'preprint'
    ? { label: '预印本 · 尚未同行评议', short: '预印本', className: 'status-preprint' }
    : { label: '已见刊 · Peer-reviewed', short: '已见刊', className: 'status-published' };
}

function cardNode(card) {
  const node = $('#cardTemplate').content.firstElementChild.cloneNode(true);
  node.classList.add(`track-${card.track}`);
  const status = statusInfo(card);
  const zhTitle = chineseTitle(card);
  const novelty = noveltyLabels[card.novelty_status] || card.novelty_status;
  const digest = structuredDigest(card);
  $('.tags', node).innerHTML = `<span class="tag ${status.className}">${esc(status.label)}</span><span class="tag track">Track ${esc(card.track)}</span><span class="tag novelty">${esc(novelty)}</span>`;
  $('.score strong', node).textContent = card.score_total;
  const titleButton = $('.title-toggle', node);
  $('.title-zh', node).textContent = zhTitle;
  $('.title-en', node).textContent = card.title;
  $('.citation', node).innerHTML = `<strong class="citation-status ${status.className}">${esc(status.short)}</strong>${[card.journal, fmtDate(card.published_date), card.doi ? `DOI ${card.doi}` : '', card.pmid ? `PMID ${card.pmid}` : ''].filter(Boolean).map(esc).join(' · ')}`;
  $('.summary', node).innerHTML = `<p><strong>一句话概览：</strong>${esc(digest.background)}</p>`;
  $('.signal-line p', node).textContent = card.new_paradigm;

  const evidence = digest.evidence.length
    ? digest.evidence.map(item => `<p>${esc(item)}</p>`).join('')
    : '<p>当前记录未提供摘要。请打开原始记录核对。</p>';
  const competition = (card.competition || []).map(item => `<li><a class="source-link" href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a> · ${esc(item.journal || '')} ${esc(item.date || '')}</li>`).join('') || '<li>当前自动检索未返回直接结果；不等于证明不存在相关研究。</li>';
  const bars = Object.entries(card.score_components || {}).map(([key, value]) => `<div class="score-row" title="${esc((card.score_reasons || {})[key] || '')}"><span>${esc(labelMap[key] || key)}</span><div class="bar"><i style="width:${Number(value)}%"></i></div><b>${Number(value)}</b></div>`).join('');
  const details = $('.details', node);
  const detailId = `card-details-${String(card.id || card.article_id || Math.random()).replace(/[^a-z0-9_-]/gi, '')}`;
  details.id = detailId;
  titleButton.setAttribute('aria-controls', detailId);
  $('.expand', node).setAttribute('aria-controls', detailId);
  details.innerHTML = `<div class="paper-brief wide">
    <div class="brief-heading"><div><span>摘要级结构化解读</span><h3>这篇文章大概讲什么</h3></div><small>自动生成 · 重要细节请核对原文</small></div>
    <div class="brief-grid">
      <section><b>01</b><h4>背景</h4><p>${esc(digest.background)}</p></section>
      <section><b>02</b><h4>方法</h4><p>${esc(digest.methods)}</p></section>
      <section><b>03</b><h4>结果</h4><p>${esc(digest.result)}</p></section>
      <section><b>04</b><h4>讨论与肌骨启示</h4><p>${esc(digest.discussion)}</p></section>
    </div>
    <details class="abstract-evidence"><summary>查看英文摘要证据</summary>${evidence}</details>
  </div>
  <div class="detail-grid"><div><h3>为什么现在才做得出来</h3><p>${esc(card.why_now)}</p></div><div><h3>与骨 / 肌的联系</h3><p>${esc(card.musculoskeletal_link)}</p></div><div><h3>尚未解决的问题</h3><ul>${(card.unresolved_questions || []).map(item => `<li>${esc(item)}</li>`).join('')}</ul></div><div><h3>可迁移到骨科的问题</h3><ul>${(card.transfer_questions || []).map(item => `<li>${esc(item)}</li>`).join('')}</ul></div><div><h3>所需数据</h3><p>${(card.data_needs || []).map(esc).join(' · ')}</p></div><div><h3>原始记录</h3><a class="source-link" href="${esc(card.url)}" target="_blank" rel="noopener">打开原文 / Source ↗</a></div><div class="wide"><h3>Opportunity Score 分项</h3><div class="score-bars">${bars}</div></div><div class="wide"><h3>自动构造的二次检索词</h3>${(card.secondary_queries || []).map(query => `<div class="query">${esc(query)}</div>`).join('')}</div><div class="wide"><h3>直接竞争研究（当前检索）</h3><ul>${competition}</ul></div></div>`;

  const expandButton = $('.expand', node);
  expandButton.innerHTML = '展开文章解读、证据与迁移路径 <span>＋</span>';
  const toggle = () => {
    const open = details.hidden;
    details.hidden = !open;
    [titleButton, expandButton].forEach(button => button.setAttribute('aria-expanded', String(open)));
    expandButton.innerHTML = `${open ? '收起文章解读' : '展开文章解读、证据与迁移路径'} <span>${open ? '−' : '＋'}</span>`;
    if (open && matchMedia('(max-width: 640px)').matches) details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };
  titleButton.addEventListener('click', toggle);
  expandButton.addEventListener('click', toggle);
  return node;
}

function fillCards(target, cards) {
  const root = $(target);
  root.replaceChildren();
  if (!cards.length) {
    root.innerHTML = '<div class="empty-state">当前筛选下没有高优先级机会。继续保留检索历史，等待下一次扫描。</div>';
    return;
  }
  cards.forEach(card => root.append(cardNode(card)));
}

function filtered() {
  return state.cards.filter(card => {
    const matchesTrack = state.track === 'all' || card.track === state.track;
    const haystack = `${card.title} ${chineseTitle(card)} ${card.journal} ${card.new_paradigm} ${(card.summary_zh || []).join(' ')}`.toLowerCase();
    return matchesTrack && (!state.query || haystack.includes(state.query));
  });
}

function renderMain() {
  fillCards('#todayCards', filtered().filter(card => card.score_total >= 68).slice(0, 8));
  fillCards('#allCards', state.cards);
  fillCards('#preprintCards', state.cards.filter(card => card.publication_status === 'preprint'));
  fillCards('#methodCards', state.cards.filter(card => card.track === 'B'));
}

function renderMetrics(stats) {
  const items = [['高价值机会', stats.high_value, 'accent'], ['Track A', stats.track_a, ''], ['Track B', stats.track_b, ''], ['预印本信号', stats.preprints, '']];
  $('#metrics').innerHTML = items.map(([label, value, className]) => `<div class="metric ${className}"><strong>${Number(value || 0).toString().padStart(2, '0')}</strong><span>${label}</span></div>`).join('');
}

function renderTrends() {
  const terms = ['spatial', 'single-cell', 'foundation model', 'longitudinal', 'proteomics', 'metabolomics', 'multimodal', 'perturbation', 'atlas'];
  const counts = terms.map(term => ({ term, count: state.cards.filter(card => `${card.title} ${card.new_paradigm}`.toLowerCase().includes(term)).length })).sort((a, b) => b.count - a.count);
  const max = Math.max(1, ...counts.map(item => item.count));
  $('#trendGrid').innerHTML = counts.map((item, index) => `<article class="trend-item"><p class="eyebrow">${String(index + 1).padStart(2, '0')} · SIGNAL</p><strong>${esc(trendLabels[item.term] || item.term)}</strong><small class="trend-en">${esc(item.term)}</small><div class="spark"><i style="width:${item.count / max * 100}%"></i></div><small>${item.count} 篇机会卡命中</small></article>`).join('');
}

function renderCompetition() {
  const cards = state.cards.filter(card => (card.competition || []).length);
  $('#competitionList').innerHTML = cards.length ? cards.map(card => `<article class="alert-item"><div class="alert-score">${card.score_total}</div><div><h3>${esc(chineseTitle(card))}</h3><small>${esc(card.title)}</small><p>${card.competition.length} 条潜在竞争记录 · ${esc(noveltyLabels[card.novelty_status] || card.novelty_status)}</p></div><a href="${esc(card.url)}" target="_blank" rel="noopener">查看原文 ↗</a></article>`).join('') : '<div class="empty-state">当前没有需要升级处理的竞争预警。</div>';
}

function showView(name) {
  $$('.view').forEach(item => item.classList.toggle('active', item.dataset.view === name));
  $$('.side-nav a').forEach(item => item.classList.toggle('active', item.dataset.view === name));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function ideas() { try { return JSON.parse(localStorage.getItem('msk-radar-ideas') || '[]'); } catch { return []; } }
function renderIdeas() {
  const root = $('#ideaList');
  const items = ideas();
  root.innerHTML = items.length ? items.map((item, index) => `<article class="idea"><div><h3>${esc(item.title)}</h3><p>${esc(item.note || '暂无备注')}</p></div><button data-index="${index}" aria-label="删除 ${esc(item.title)}">删除</button></article>`).join('') : '<div class="empty-state">还没有保存研究想法。看到机会卡后，把最想验证的问题记在这里。</div>';
  $$('button[data-index]', root).forEach(button => button.onclick = () => { const next = ideas(); next.splice(Number(button.dataset.index), 1); localStorage.setItem('msk-radar-ideas', JSON.stringify(next)); renderIdeas(); });
}
function toast(text) { const element = document.createElement('div'); element.className = 'toast'; element.textContent = text; document.body.append(element); setTimeout(() => element.remove(), 2200); }

async function init() {
  try {
    const response = await fetch('data.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.cards = data.cards || [];
    renderMetrics(data.stats || {}); renderMain(); renderTrends(); renderCompetition();
    $('#updatedAt').textContent = `最近扫描 ${fmtDate(data.generated_at)}`;
    $('#todayDate').textContent = fmtDate(data.generated_at);
  } catch (error) {
    $('#todayCards').innerHTML = `<div class="empty-state">数据暂时不可用：${esc(error.message)}。请先运行一次雷达任务。</div>`;
    $('#updatedAt').textContent = '数据读取失败';
  }
  renderIdeas();
}

$$('.side-nav a').forEach(anchor => anchor.addEventListener('click', event => { event.preventDefault(); history.replaceState(null, '', anchor.hash); showView(anchor.dataset.view); }));
$$('[data-track]').forEach(button => button.addEventListener('click', () => { $$('[data-track]').forEach(item => item.classList.remove('active')); button.classList.add('active'); state.track = button.dataset.track; renderMain(); }));
$('#searchInput').addEventListener('input', event => { state.query = event.target.value.trim().toLowerCase(); renderMain(); });
$('#ideaForm').addEventListener('submit', event => { event.preventDefault(); const form = new FormData(event.currentTarget); const items = ideas(); items.unshift({ title: form.get('title'), note: form.get('note'), createdAt: new Date().toISOString() }); localStorage.setItem('msk-radar-ideas', JSON.stringify(items)); event.currentTarget.reset(); renderIdeas(); toast('研究想法已保存到本机'); });
showView(location.hash.slice(1) || 'today');
init();
