/* ════════════════════════════════════════════════════════════════
   PROTACXtend — Interactive layer
   scroll progress · nav · reveal · counters · install tabs · copy ·
   agent-pipeline simulator · docs tabs
   ════════════════════════════════════════════════════════════════ */
'use strict';

document.addEventListener('DOMContentLoaded', () => {
  initScrollProgress();
  initNavBurger();
  initReveal();
  initCounters();
  initInstallTabs();
  initCopy();
  initSimulator();
  initDocsTabs();
  document.getElementById('year').textContent = new Date().getFullYear();
});

/* ── top scroll-progress bar ─────────────────────────────────────── */
function initScrollProgress() {
  const bar = document.getElementById('scroll-progress');
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/* ── mobile nav ──────────────────────────────────────────────────── */
function initNavBurger() {
  const burger = document.getElementById('nav-burger');
  const links = document.getElementById('nav-links');
  if (!burger || !links) return;
  burger.addEventListener('click', () => links.classList.toggle('open'));
  links.querySelectorAll('a').forEach(a =>
    a.addEventListener('click', () => links.classList.remove('open')));
}

/* ── scroll reveal ───────────────────────────────────────────────── */
function initReveal() {
  const els = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    els.forEach(el => el.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  els.forEach(el => io.observe(el));
}

/* ── animated stat counters ──────────────────────────────────────── */
function initCounters() {
  const nums = document.querySelectorAll('.stat-num[data-count]');
  if (!nums.length || !('IntersectionObserver' in window)) return;
  const fmt = (v) => v >= 1000 ? (v / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(v);
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target;
      const target = parseInt(el.dataset.count, 10);
      const dur = 1100; const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min((t - t0) / dur, 1);
        el.textContent = fmt(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      io.unobserve(el);
    });
  }, { threshold: 0.6 });
  nums.forEach(n => io.observe(n));
}

/* ── install command tabs ────────────────────────────────────────── */
function initInstallTabs() {
  const btns = document.querySelectorAll('.tab-pill');
  const out = document.getElementById('install-command');
  const cmds = {
    pip:  'pip install protacxtend',
    git:  'git clone https://github.com/the-ahuja-lab/PROTACXtend.git',
    curl: 'curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/install.sh | bash'
  };
  btns.forEach(btn => btn.addEventListener('click', () => {
    btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (out && cmds[btn.dataset.tool]) out.textContent = cmds[btn.dataset.tool];
  }));
}

/* ── copy-to-clipboard ───────────────────────────────────────────── */
function initCopy() {
  const btn = document.getElementById('install-copy-btn');
  const cmd = document.getElementById('install-command');
  if (!btn || !cmd) return;
  btn.addEventListener('click', () => {
    navigator.clipboard.writeText(cmd.textContent.trim()).then(() => {
      const old = btn.innerHTML;
      btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6L9 17l-5-5"/></svg>';
      setTimeout(() => { btn.innerHTML = old; }, 1600);
    });
  });
}

/* ── interactive agent pipeline simulator ────────────────────────── */
function initSimulator() {
  const runBtn = document.getElementById('run-sim-btn');
  if (!runBtn) return;
  const trace = document.getElementById('trace-output');
  const table = document.getElementById('results-table-body');
  const meta  = document.getElementById('res-meta');
  const live  = document.getElementById('trace-live');
  const label = document.getElementById('run-btn-label');
  const targetSel = document.getElementById('target-select');
  const e3Sel = document.getElementById('e3-select');

  const steps = [
    { n: 'SupervisorAgent',            m: 'Parsing design objective → Target {{TARGET}} · E3 recruiter {{E3}} · constraints applied', s: 'OK' },
    { n: 'DesignPlanner',              m: 'Plan committed: 23-node core + closed-loop refinement (31 nodes total)', s: 'OK' },
    { n: 'NpHardSearchControl',        m: 'Search-space control bounds set — NP-hard enumeration bounded', s: 'OK' },
    { n: 'SafetyPrecheck',             m: 'Objective screened against chemistry-safety policy — cleared', s: 'OK' },
    { n: 'TargetResolver',             m: 'UniProt + ChEMBL resolution → target record, pChembl ranked', s: 'OK' },
    { n: 'BinderRetrieval',            m: 'ChEMBL/PubChem/BindingDB → 87 binders · 12 E3 recruiters retrieved', s: 'OK' },
    { n: 'ExitVectorDetection',        m: 'RDKit attachment-point scan → exit vectors mapped on warhead', s: 'OK' },
    { n: 'LinkerGenerator',            m: '73-method engine → PEG / alkyl / triazole / GRU-generative linkers', s: 'OK' },
    { n: 'ConstructProtacs',           m: 'Warhead ⊕ linker ⊕ E3-recruiter → 32 chimeras assembled & sanitized', s: 'OK' },
    { n: 'Validate + CellContext',     m: 'Validity gates passed · cell-line degradation context scored', s: 'OK' },
    { n: 'ADMET + Novelty',            m: 'hERG/AMES/BBB profile PASS · novelty & applicability domain OK', s: 'OK' },
    { n: 'DegradationML',              m: 'Chemprop ensemble → DC50 = 12.4 nM · Dmax = 89.2% · class Active', s: 'OK' },
    { n: 'TernaryFeasibility',         m: 'P4ward ensemble → SE(3) geometric feasibility 0.88 · α > 1', s: 'OK' },
    { n: 'FinalRanking + Report',      m: 'Pareto frontier compiled → top candidates with full provenance', s: 'OK' }
  ];

  const candidates = {
    BRD4: [
      { r: 1, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-PEG4-JQ1',            dc: '12.4 nM', dm: '89.2%', t: '0.88', a: 'PASS' },
      { r: 2, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl6-dBET6',        dc: '24.8 nM', dm: '84.5%', t: '0.82', a: 'PASS' },
      { r: 3, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Triazole-MZ1',        dc: '38.1 nM', dm: '81.0%', t: '0.79', a: 'PASS' },
      { r: 4, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl8-ARV771',        dc: '45.0 nM', dm: '78.4%', t: '0.75', a: 'PASS' }
    ],
    HMGB2: [
      { r: 1, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG3-CRBN',            dc: '18.6 nM', dm: '86.4%', t: '0.85', a: 'PASS' },
      { r: 2, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-Alkyl5-CRBN',          dc: '31.2 nM', dm: '82.1%', t: '0.80', a: 'PASS' },
      { r: 3, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG5-CRBN',            dc: '42.0 nM', dm: '79.8%', t: '0.77', a: 'PASS' }
    ],
    EGFR: [
      { r: 1, s: 'C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-PEG4-VHL', dc: '15.1 nM', dm: '91.0%', t: '0.90', a: 'PASS' },
      { r: 2, s: 'C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-Alkyl6-VHL', dc: '29.4 nM', dm: '85.7%', t: '0.84', a: 'PASS' }
    ]
  };

  runBtn.addEventListener('click', async () => {
    const target = targetSel ? targetSel.value : 'BRD4';
    const e3 = e3Sel ? e3Sel.value : 'CRBN';
    const wait = (ms) => new Promise(r => setTimeout(r, ms));

    runBtn.disabled = true;
    label.textContent = 'Running 31-node pipeline…';
    live.textContent = 'EXECUTING'; live.classList.add('running');
    trace.innerHTML = ''; meta.textContent = 'designing…';
    table.innerHTML = '<tr><td colspan="6" class="empty-row">Executing assembly, ML scoring & ternary simulation…</td></tr>';

    for (const st of steps) {
      await wait(300 + Math.random() * 200);
      const row = document.createElement('div');
      row.className = 'trace-row new';
      row.innerHTML = `<span class="trace-node">${st.n}</span>
        <span class="trace-msg">${st.m.replace('{{TARGET}}', target).replace('{{E3}}', e3)}</span>
        <span class="trace-st">[${st.s}]</span>`;
      trace.appendChild(row);
      trace.scrollTop = trace.scrollHeight;
    }

    await wait(300);
    runBtn.disabled = false;
    label.textContent = 'Run 31-node pipeline';
    live.textContent = 'COMPLETE'; live.classList.remove('running');

    const rows = (candidates[target] || candidates.BRD4);
    meta.textContent = `${rows.length} candidates · ${target} × ${e3}`;
    table.innerHTML = rows.map(c => `
      <tr>
        <td><span class="rank-chip">${c.r}</span></td>
        <td class="smiles-cell" title="${c.s}">${c.s}</td>
        <td><strong>${c.dc}</strong></td><td>${c.dm}</td><td>${c.t}</td>
        <td><span class="pass-badge">${c.a} · LOW RISK</span></td>
      </tr>`).join('');
  });
}

/* ── documentation tabs ──────────────────────────────────────────── */
function initDocsTabs() {
  const tabs = document.querySelectorAll('.docs-tab');
  tabs.forEach(tab => tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.docs-pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    const pane = document.getElementById(tab.dataset.target);
    if (pane) pane.classList.add('active');
  }));
}
