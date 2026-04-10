/* ══════════════════════════════════════════════════════════════════════════
   WebIntel v2.0 — Frontend Application (Full Backend Integration)
   ══════════════════════════════════════════════════════════════════════════ */

const API_BASE = https://backend-multiagent.onrender.com/;

// ─── State ──────────────────────────────────────────────────────────────────
let authToken = localStorage.getItem('webintel_token');
let currentUser = null;
let currentSessionId = null;
let currentReportData = null;
let citationChart = null;
let traceStep = 0;


// ══════════════════════════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════════════════════════

function showLogin() {
  document.getElementById('loginForm').style.display = '';
  document.getElementById('registerForm').style.display = 'none';
  document.getElementById('loginError').textContent = '';
}

function showRegister() {
  document.getElementById('loginForm').style.display = 'none';
  document.getElementById('registerForm').style.display = '';
  document.getElementById('registerError').textContent = '';
}

async function handleLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errorEl = document.getElementById('loginError');
  const btn = document.getElementById('loginBtn');

  if (!email || !password) {
    errorEl.textContent = 'Please fill in all fields';
    return;
  }

  btn.classList.add('loading');
  btn.querySelector('.auth-btn-text').textContent = 'Signing in...';
  btn.querySelector('.auth-btn-loader').style.display = 'inline-block';

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      errorEl.textContent = data.detail || 'Login failed';
      return;
    }

    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem('webintel_token', authToken);
    localStorage.setItem('webintel_user', JSON.stringify(currentUser));
    showApp();
  } catch (e) {
    errorEl.textContent = 'Network error. Is the server running?';
  } finally {
    btn.classList.remove('loading');
    btn.querySelector('.auth-btn-text').textContent = 'Sign In';
    btn.querySelector('.auth-btn-loader').style.display = 'none';
  }
}

async function handleRegister() {
  const username = document.getElementById('regUsername').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const errorEl = document.getElementById('registerError');
  const btn = document.getElementById('registerBtn');

  if (!username || !email || !password) {
    errorEl.textContent = 'Please fill in all fields';
    return;
  }

  if (password.length < 6) {
    errorEl.textContent = 'Password must be at least 6 characters';
    return;
  }

  btn.classList.add('loading');
  btn.querySelector('.auth-btn-text').textContent = 'Creating account...';
  btn.querySelector('.auth-btn-loader').style.display = 'inline-block';

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      errorEl.textContent = data.detail || 'Registration failed';
      return;
    }

    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem('webintel_token', authToken);
    localStorage.setItem('webintel_user', JSON.stringify(currentUser));
    showApp();
    showToast('Account created successfully!', 'success');
  } catch (e) {
    errorEl.textContent = 'Network error. Is the server running?';
  } finally {
    btn.classList.remove('loading');
    btn.querySelector('.auth-btn-text').textContent = 'Create Account';
    btn.querySelector('.auth-btn-loader').style.display = 'none';
  }
}

function handleLogout() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem('webintel_token');
  localStorage.removeItem('webintel_user');
  document.getElementById('authScreen').style.display = '';
  document.getElementById('appScreen').style.display = 'none';
  showLogin();
}

function showApp() {
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('appScreen').style.display = '';

  // Set user info in header
  if (currentUser) {
    document.getElementById('userAvatar').textContent = currentUser.username[0].toUpperCase();
    document.getElementById('userName').textContent = currentUser.username;
  }

  // Load history
  loadHistory();
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authToken}`,
  };
}


// ══════════════════════════════════════════════════════════════════════════════
// PIPELINE — Real Backend Integration with SSE
// ══════════════════════════════════════════════════════════════════════════════

async function runPipeline() {
  const query = document.getElementById('queryInput').value.trim();
  if (!query) return;

  const mode = document.getElementById('modeSelect').value;
  const queryType = document.getElementById('typeSelect').value;
  const btn = document.getElementById('runBtn');

  // Reset UI
  hideEmpty();
  document.getElementById('mainContent').style.display = '';
  resetPanels();
  btn.classList.add('loading');
  btn.textContent = '⟳ Analyzing…';
  document.getElementById('traceStatus').textContent = 'RUNNING';
  traceStep = 0;

  try {
    // Step 1: Submit query to backend
    const res = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ query, mode, query_type: queryType }),
    });

    if (res.status === 401) {
      handleLogout();
      showToast('Session expired. Please login again.', 'error');
      return;
    }

    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || 'Query failed', 'error');
      resetButton(btn);
      return;
    }

    currentSessionId = data.session_id;

    // Step 2: Connect to SSE stream
    connectSSE(currentSessionId, btn);

  } catch (e) {
    showToast('Network error. Is the server running?', 'error');
    resetButton(btn);
  }
}

function connectSSE(sessionId, btn) {
  const evtSource = new EventSource(`${API_BASE}/stream/${sessionId}`);

  evtSource.addEventListener('trace', (e) => {
    const data = JSON.parse(e.data);
    addTraceItem(data.step, data.message);
  });

  evtSource.addEventListener('claim', (e) => {
    const claim = JSON.parse(e.data);
    addClaimCard(claim);
  });

  evtSource.addEventListener('report', (e) => {
    const report = JSON.parse(e.data);
    currentReportData = report;
    renderReport(report);
  });

  evtSource.addEventListener('error', (e) => {
    try {
      const data = JSON.parse(e.data);
      showToast(data.message || 'Pipeline error', 'error');
    } catch {
      // SSE connection error
    }
  });

  evtSource.addEventListener('done', (e) => {
    evtSource.close();
    document.getElementById('traceStatus').textContent = 'DONE';
    resetButton(btn);
    loadHistory(); // Refresh sidebar
  });

  // Handle SSE connection errors
  evtSource.onerror = () => {
    evtSource.close();
    resetButton(btn);
  };
}


// ── Trace Panel ─────────────────────────────────────────────────────────────

const AGENT_ICONS = ['🧠', '🌐', '📊', '🔍', '📈'];
const AGENT_NAMES = ['Planner Agent', 'Search Agent', 'Extraction Agent', 'Verification Agent', 'Report Agent'];

function addTraceItem(step, message) {
  const list = document.getElementById('traceList');

  // Update previous running items to done
  list.querySelectorAll('.trace-item.running').forEach(item => {
    item.className = 'trace-item done';
    const st = item.querySelector('.trace-status');
    st.className = 'trace-status done';
    st.textContent = '✓ COMPLETE';
  });

  // Determine agent info
  const agentIdx = Math.min(Math.floor((step - 1) / 2), 4);
  const icon = AGENT_ICONS[agentIdx] || '⚙️';
  const name = AGENT_NAMES[agentIdx] || `Step ${step}`;

  // Check if this agent already has an item
  const existingId = `trace-agent-${agentIdx}`;
  let existing = document.getElementById(existingId);

  if (existing) {
    // Update the log
    const log = existing.querySelector('.trace-log');
    log.innerHTML += `<br/>${message}`;
    return;
  }

  const item = document.createElement('div');
  item.className = 'trace-item running';
  item.id = existingId;
  item.style.animationDelay = `${step * 0.05}s`;
  item.innerHTML = `
    <div class="trace-icon">${icon}</div>
    <div class="trace-info">
      <div class="trace-name">${name}</div>
      <div class="trace-status running"><span class="pulse-dot"></span>RUNNING</div>
      <div class="trace-log">${message}</div>
    </div>
  `;
  list.appendChild(item);

  // Glow effect
  document.getElementById('tracePanel').classList.add('active-glow');
}


// ── Claims Panel ────────────────────────────────────────────────────────────

let claimCounter = 0;

function addClaimCard(claim) {
  const list = document.getElementById('claimsList');
  if (claimCounter === 0) list.innerHTML = '';

  claimCounter++;
  document.getElementById('claimCount').textContent = claimCounter;

  const conf = claim.confidence || 0;
  const confClass = conf >= 70 ? 'high' : conf >= 40 ? 'mid' : 'low';
  const status = claim.status || 'verified';
  const flagClass = status === 'verified' ? 'verified' : status === 'conflict' ? 'conflict' : 'unverified';

  const sources = (claim.supporting_sources || []).slice(0, 3).map(s => extractDomain(s)).join(', ');
  const sourceCount = (claim.supporting_sources || []).length;

  const card = document.createElement('div');
  card.className = `claim-card ${flagClass}`;
  card.style.animationDelay = `${claimCounter * 0.08}s`;
  card.innerHTML = `
    <div class="claim-text">${escapeHtml(claim.claim)}</div>
    <div class="claim-meta">
      <div class="conf-wrap">
        <div class="conf-track"><div class="conf-fill ${confClass}" style="width:${conf}%"></div></div>
        <span class="conf-pct ${confClass}">${Math.round(conf)}%</span>
      </div>
      <span class="claim-flag ${flagClass}">${status}</span>
    </div>
    ${sources ? `<div class="claim-sources">${sourceCount} source${sourceCount > 1 ? 's' : ''} · ${sources}</div>` : ''}
  `;
  list.appendChild(card);
}


// ── Report Rendering ────────────────────────────────────────────────────────

function renderReport(report) {
  // Show report section
  const section = document.getElementById('reportSection');
  section.style.display = '';

  // Query
  document.getElementById('reportQuery').textContent = `Query: ${report.query || ''}`;

  // Scores
  const conf = Math.round(report.overall_confidence || 0);
  const scoreRow = document.getElementById('scoreRow');
  scoreRow.innerHTML = `
    <div class="score-chip">
      <span class="score-num g">${conf}%</span>
      <span class="score-lbl">Confidence</span>
    </div>
    <div class="score-chip">
      <span class="score-num b">${report.total_sources_visited || 0}</span>
      <span class="score-lbl">Sources</span>
    </div>
    <div class="score-chip">
      <span class="score-num y">${report.conflicts_detected || 0}</span>
      <span class="score-lbl">Conflicts</span>
    </div>
    <div class="score-chip">
      <span class="score-num g">${report.conflicts_resolved || 0}</span>
      <span class="score-lbl">Resolved</span>
    </div>
  `;

  // Generate executive summary from claims
  const summary = generateSummary(report);
  document.getElementById('reportSummary').innerHTML = summary;

  // Render sources
  renderSources(report.sources || []);

  // Render conflicts
  renderConflicts(report.verified_claims || []);

  // Render compare table
  if (report.compare_table) {
    renderCompareTable(report.compare_table);
  }

  // Render diff
  if (report.diff) {
    renderDiff(report.diff);
  }

  // Render chart
  renderCitationChart(report.sources || []);

  // Show bottom row
  document.getElementById('bottomRow').style.display = '';

  // Footer
  document.getElementById('footerGen').textContent =
    `Generated: ${new Date().toISOString().split('T')[0]} · Session #${currentSessionId?.slice(0, 8) || ''}`;
}

function generateSummary(report) {
  const claims = report.verified_claims || [];
  if (claims.length === 0) return 'No claims were extracted for this query.';

  const verified = claims.filter(c => c.status === 'verified');
  const conflicts = claims.filter(c => c.status === 'conflict' || c.conflicting_sources?.length > 0);

  let summary = '';
  if (verified.length > 0) {
    summary += verified.slice(0, 3).map(c =>
      `<strong style="color:#fff">${escapeHtml(c.claim)}</strong> (${Math.round(c.confidence)}% confidence)`
    ).join('. ') + '. ';
  }
  if (conflicts.length > 0) {
    summary += `<br/><br/>⚠️ ${conflicts.length} claim${conflicts.length > 1 ? 's' : ''} had conflicting information across sources.`;
  }

  summary += `<br/><br/>Overall confidence: <strong style="color:var(--green)">${Math.round(report.overall_confidence || 0)}%</strong> across ${report.total_sources_visited || 0} sources.`;

  return summary;
}


// ── Sources Panel ───────────────────────────────────────────────────────────

function renderSources(sources) {
  const list = document.getElementById('sourceList');
  list.innerHTML = '';

  if (!sources.length) {
    list.innerHTML = '<div class="panel-empty">No sources found</div>';
    return;
  }

  document.getElementById('sourceCount').textContent = `${sources.length} visited`;

  sources.forEach((src, i) => {
    const tier = src.trust_tier || 'unknown';
    const score = src.trust_score || 0;
    const tierClass = tier === 'high' ? 'high' : tier === 'medium' ? 'medium' : tier === 'low' ? 'low' : 'unknown';
    const discarded = src.discarded ? ' discarded' : '';

    const item = document.createElement('div');
    item.className = `source-item${discarded}`;
    item.style.animationDelay = `${i * 0.05}s`;
    item.innerHTML = `
      <div class="src-top">
        <span class="src-domain">${escapeHtml(src.domain || extractDomain(src.url || ''))}</span>
        <span class="trust-badge ${tierClass}">${tier.toUpperCase()}</span>
      </div>
      <div class="src-trust-row">
        <div class="src-trust-track"><div class="src-trust-fill ${tierClass}" style="width:${score}%"></div></div>
        <span class="src-trust-val ${tierClass}">${score}</span>
      </div>
      <div class="src-stats">
        <span class="src-stat"><span class="dot agree"></span>${src.agreement_count || 0} agree</span>
        <span class="src-stat"><span class="dot conflict"></span>${src.conflict_count || 0} conflict</span>
      </div>
    `;
    list.appendChild(item);
  });
}


// ── Conflicts Panel ─────────────────────────────────────────────────────────

function renderConflicts(claims) {
  const conflictClaims = claims.filter(c =>
    c.status === 'conflict' || (c.conflicting_sources && c.conflicting_sources.length > 0)
  );

  const list = document.getElementById('conflictList');
  list.innerHTML = '';

  document.getElementById('conflictCount').textContent = `${conflictClaims.length} conflicts`;

  if (conflictClaims.length === 0) {
    list.innerHTML = '<div class="panel-empty">No conflicts detected ✓</div>';
    return;
  }

  conflictClaims.forEach(claim => {
    const item = document.createElement('div');
    item.className = 'conflict-item';

    const supportSrc = (claim.supporting_sources || []).slice(0, 1).map(extractDomain).join(', ');
    const conflictSrc = (claim.conflicting_sources || []).slice(0, 1).map(extractDomain).join(', ');

    item.innerHTML = `
      <div class="conflict-claims">
        <div class="conf-claim-a">
          ${escapeHtml(claim.claim)}
          <div class="conf-src">${supportSrc || 'unknown'}</div>
        </div>
        <div class="conf-claim-b">
          ${escapeHtml(claim.conflict_detail || 'Conflicting data from other sources')}
          <div class="conf-src">${conflictSrc || 'unknown'}</div>
        </div>
      </div>
      <div class="conflict-resolution">${claim.resolution_method ? `✓ Resolution: ${claim.resolution_method}` : '⚠ Unresolved conflict'}</div>
    `;
    list.appendChild(item);
  });
}


// ── Compare Table ───────────────────────────────────────────────────────────

function renderCompareTable(compareData) {
  if (!compareData || !compareData.criteria || !compareData.criteria.length) return;

  const container = document.getElementById('compareContent');
  const entities = compareData.entities || [];
  const criteria = compareData.criteria || [];
  const data = compareData.data || {};

  let html = '<div style="overflow-x:auto;"><table class="compare-table"><thead><tr><th>Criterion</th>';
  entities.forEach(e => { html += `<th>${escapeHtml(e)}</th>`; });
  html += '</tr></thead><tbody>';

  criteria.forEach(criterion => {
    html += `<tr><td>${escapeHtml(criterion)}</td>`;
    entities.forEach(entity => {
      const cell = data[criterion]?.[entity];
      const val = cell?.value || 'N/A';
      const conf = cell?.confidence || 0;
      const color = conf >= 70 ? 'var(--green)' : conf >= 40 ? '#fff' : 'var(--amber)';
      html += `<td style="color:${color}">${escapeHtml(val)}</td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  container.innerHTML = html;
}


// ── Diff View ───────────────────────────────────────────────────────────────

function renderDiff(diff) {
  if (!diff) return;

  const container = document.getElementById('diffContent');
  let html = '';

  (diff.added || []).forEach(d => {
    html += `<div class="diff-item added"><div class="diff-tag added">+ NEW CLAIM</div>${escapeHtml(d.claim)}</div>`;
  });
  (diff.removed || []).forEach(d => {
    html += `<div class="diff-item removed"><div class="diff-tag removed">− REMOVED</div>${escapeHtml(d.claim)}</div>`;
  });
  (diff.changed || []).forEach(d => {
    html += `<div class="diff-item changed"><div class="diff-tag changed">~ CHANGED</div>${escapeHtml(d.claim)} · Confidence: ${d.old_confidence}% → ${d.new_confidence}%</div>`;
  });

  if (!html) html = '<div class="panel-empty">No changes detected</div>';
  container.innerHTML = html;
}


// ── Citation Chart ──────────────────────────────────────────────────────────

function renderCitationChart(sources) {
  if (citationChart) citationChart.destroy();

  const canvas = document.getElementById('citationChart');
  if (!canvas) return;

  const labels = sources.slice(0, 8).map(s => s.domain || 'unknown');
  const agrees = sources.slice(0, 8).map(s => s.agreement_count || 0);
  const conflicts = sources.slice(0, 8).map(s => s.conflict_count || 0);

  citationChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Agreements',
          data: agrees,
          backgroundColor: 'rgba(0,229,160,0.7)',
          borderColor: 'rgba(0,229,160,1)',
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'Conflicts',
          data: conflicts,
          backgroundColor: 'rgba(255,74,107,0.7)',
          borderColor: 'rgba(255,74,107,1)',
          borderWidth: 1,
          borderRadius: 4,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: '#5a7a96',
            font: { family: "'Syne Mono', monospace", size: 10 },
            boxWidth: 12,
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#5a7a96', font: { family: "'Syne Mono', monospace", size: 9 } },
          grid: { color: '#1c2a3a' },
        },
        y: {
          ticks: { color: '#5a7a96', font: { family: "'Syne Mono', monospace", size: 10 } },
          grid: { color: '#1c2a3a' },
          beginAtZero: true,
        }
      }
    }
  });
}


// ══════════════════════════════════════════════════════════════════════════════
// HISTORY & EXPORT
// ══════════════════════════════════════════════════════════════════════════════

async function loadHistory() {
  if (!authToken) return;

  try {
    const res = await fetch(`${API_BASE}/reports?limit=20`, {
      headers: authHeaders(),
    });

    if (res.status === 401) return;
    const data = await res.json();
    const reports = data.reports || [];

    const list = document.getElementById('historyList');
    if (reports.length === 0) {
      list.innerHTML = '<div class="panel-empty">No previous queries yet</div>';
      return;
    }

    list.innerHTML = reports.map(r => {
      const conf = Math.round(r.overall_confidence || 0);
      const confClass = conf >= 70 ? 'high' : conf >= 40 ? 'mid' : 'low';
      const date = new Date(r.created_at).toLocaleDateString();
      return `
        <div class="history-item" onclick="loadHistoryReport('${r.session_id}')">
          <div class="hi-query">${escapeHtml(r.query || '')}</div>
          <div class="hi-meta">
            <span>${r.mode || ''} · ${r.query_type || ''}</span>
            <span>${date}</span>
            <span class="hi-conf ${confClass}">${conf}%</span>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

async function loadHistoryReport(sessionId) {
  toggleSidebar();

  try {
    const res = await fetch(`${API_BASE}/reports/${sessionId}`, {
      headers: authHeaders(),
    });

    if (!res.ok) return;
    const reportData = await res.json();

    // Show UI
    hideEmpty();
    document.getElementById('mainContent').style.display = '';
    resetPanels();

    // Set query
    document.getElementById('queryInput').value = reportData.query || '';

    // Render the report
    const report = reportData.report || reportData;
    currentSessionId = sessionId;
    currentReportData = report;

    // Add claims
    (report.verified_claims || []).forEach(claim => addClaimCard(claim));

    // Render full report
    renderReport(report);

  } catch (e) {
    showToast('Failed to load report', 'error');
  }
}

async function exportReport(format) {
  if (!currentSessionId) {
    showToast('No report to export. Run a query first.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/export/${currentSessionId}/${format}`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
    });

    if (!res.ok) {
      showToast(`Export failed: ${res.statusText}`, 'error');
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `webintel-${currentSessionId.slice(0, 8)}.${format === 'json' ? 'json' : 'pdf'}`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`${format.toUpperCase()} exported successfully`, 'success');
  } catch (e) {
    showToast('Export failed', 'error');
  }
}

async function scheduleMonitor() {
  const query = document.getElementById('queryInput').value.trim();
  if (!query) {
    showToast('Enter a query first', 'error');
    return;
  }

  const mode = document.getElementById('modeSelect').value;
  const queryType = document.getElementById('typeSelect').value;

  try {
    const res = await fetch(`${API_BASE}/monitors`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        query,
        mode,
        query_type: queryType,
        interval_hours: 24,
      }),
    });

    if (res.ok) {
      showToast('Monitor scheduled! Will re-run every 24h', 'success');
    } else {
      showToast('Failed to create monitor', 'error');
    }
  } catch (e) {
    showToast('Network error', 'error');
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════════════════════════

function resetPanels() {
  document.getElementById('traceList').innerHTML = '';
  document.getElementById('claimsList').innerHTML = '<div class="panel-empty">Waiting for data...</div>';
  document.getElementById('sourceList').innerHTML = '<div class="panel-empty">Sources will appear here</div>';
  document.getElementById('conflictList').innerHTML = '<div class="panel-empty">No conflicts detected</div>';
  document.getElementById('reportSection').style.display = 'none';
  document.getElementById('bottomRow').style.display = 'none';
  document.getElementById('claimCount').textContent = '0';
  document.getElementById('sourceCount').textContent = '0';
  document.getElementById('conflictCount').textContent = '0 conflicts';
  claimCounter = 0;
  currentReportData = null;
}

function resetButton(btn) {
  btn.classList.remove('loading');
  btn.textContent = '▶ Analyze';
}

function hideEmpty() {
  document.getElementById('emptyState').classList.remove('visible');
}

function switchTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('open');
}

function setQ(el) {
  document.getElementById('queryInput').value = el.textContent;
}

function setChip(el) {
  document.querySelectorAll('.mode-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('typeSelect').value = el.dataset.type;
}

function switchQueryType() {
  const v = document.getElementById('typeSelect').value;
  document.querySelectorAll('.mode-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.type === v);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url;
  }
}

function showToast(msg, type = '') {
  // Remove existing
  document.querySelectorAll('.toast').forEach(t => t.remove());

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add('visible');
  });

  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}


// ══════════════════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════════════════

window.addEventListener('load', () => {
  // Check for existing session
  const savedUser = localStorage.getItem('webintel_user');
  if (authToken && savedUser) {
    try {
      currentUser = JSON.parse(savedUser);
      // Verify token is still valid
      fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${authToken}` },
      }).then(res => {
        if (res.ok) {
          showApp();
        } else {
          handleLogout();
        }
      }).catch(() => {
        // Offline — show app anyway with cached data
        showApp();
      });
    } catch {
      handleLogout();
    }
  }

  // Enter key on auth inputs
  document.getElementById('loginPassword')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLogin();
  });
  document.getElementById('regPassword')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleRegister();
  });
});
