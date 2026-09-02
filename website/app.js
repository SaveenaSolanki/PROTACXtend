/* ════════════════════════════════════════════════════════════════
   PROTACXtend — Interactive layer (v2, scientific-coherence)
   scroll progress · nav · reveal · counters · install tabs · copy ·
   illustrative pipeline walkthrough · docs tabs
   ════════════════════════════════════════════════════════════════ */
'use strict';

document.addEventListener('DOMContentLoaded', () => {
  initScrollProgress();
  initNavBurger();
  initReveal();
  initCounters();
  initInstallTabs();
  initCopy();
  initWalkthrough();
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
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target;
      const target = parseInt(el.dataset.count, 10);
      const dur = 1100; const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min((t - t0) / dur, 1);
        el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      io.unobserve(el);
    });
  }, { threshold: 0.6 });
  nums.forEach(n => io.observe(n));
}

/* ── install tabs (git clone + docker; PyPI is on the roadmap) ───── */
function initInstallTabs() {
  const btns = document.querySelectorAll('.tab-pill');
  const out = document.getElementById('install-command');
  const cmds = {
    git:   'git clone https://github.com/the-ahuja-lab/PROTACXtend.git',
    docker: 'docker build -t protacxtend https://github.com/the-ahuja-lab/PROTACXtend.git'
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

/* ═══════════════════════════════════════════════════════════════════
   ILLUSTRATIVE PIPELINE WALKTHROUGH
   Browser-only. Precomputed illustrative values — NOT live science.
   Shape mirrors a PROTACXtend run: KNOW retrieval → REASON → DESIGN
   (linkers · retrosynthesis · assembly) → mechanistic layers
   (ternary · ubiquitination · cooperativity · hook effect) →
   degradation models (M4 · M5) → Pareto ranking.
   ═══════════════════════════════════════════════════════════════════ */
function initWalkthrough() {
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
    { n: 'KNOW · retrieval',            m: 'Europe PMC + PubMed + OpenAlex → PMID/DOI verified evidence for {{TARGET}} degradation (illustrative set)', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'KNOW · grading',              m: 'Claim-level grading + citation provenance recorded on dossier', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'REASON · target resolve',     m: 'UniProt/ChEMBL resolution → target record; binder evidence ranked (pChembl)', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'REASON · E3 selection',       m: 'E3 recruiters {{E3}} screened; exit vectors mapped on warhead', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'DESIGN · linkers',            m: '73-method engine → curated + rule-based + generative linker candidates', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'DESIGN · retrosynthesis',     m: 'Synthetic feasibility + filter: 24/32 designs routed to feasible routes', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'DESIGN · assembly',           m: 'Component-aware construction → 32 chimeras · RDKit sanitized · stereoisomers', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'DESIGN · ADMET',              m: 'hERG / AMES / BBB / Lipinski–Veber profile computed (deterministic tool)', s: 'CALCULATED', c: 'trace-ok' },
    { n: 'MECH · ternary',              m: 'Ternary complex ensemble + SE(3) geometric feasibility (surrogate pose path)', s: 'ILLUSTRATIVE', c: 'trace-illu' },
    { n: 'MECH · ubiquitination',       m: 'Lysine ubiquitination feasibility — static-geometry scorer (Module 2)', s: 'STRUCTURAL SURROGATE', c: 'trace-illu' },
    { n: 'MECH · cooperativity',        m: 'Cooperativity feasibility (Module 3 — surrogate; experimental α data-gated)', s: 'STRUCTURAL SURROGATE', c: 'trace-illu' },
    { n: 'MECH · hook effect',          m: 'Three-body equilibrium: occupancy peak, hook onset & severity + MC bounds (Module 1)', s: 'CALCULATED', c: 'trace-ok' },
    { n: 'DISCOVER · degradation M4',   m: 'Module 4 model → illustrative pDC50 band for the top designs', s: 'LEARNED PREDICTION', c: 'trace-learn' },
    { n: 'DISCOVER · cell context M5',  m: 'Module 5 transcriptomic conditioning (DepMap 24Q4 signature proxy)', s: 'LEARNED PREDICTION', c: 'trace-learn' },
    { n: 'DISCOVER · Pareto dossier',   m: 'Ranking with ADMET + novelty + synthetic feasibility → dossier written', s: 'ILLUSTRATIVE', c: 'trace-illu' }
  ];

  /* illustrative values only — model-backed runs require the CLI/API */
  const candidates = {
    BRD4: [
      { r: 1, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-PEG4-JQ1',            dc: '12.4', t: '0.88', rr: 'feasible', a: 'PASS' },
      { r: 2, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl6-dBET6',        dc: '24.8', t: '0.82', rr: 'feasible', a: 'PASS' },
      { r: 3, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Triazole-MZ1',        dc: '38.1', t: '0.79', rr: 'review',   a: 'PASS' },
      { r: 4, s: 'O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl8-ARV771',        dc: '45.0', t: '0.75', rr: 'review',   a: 'PASS' }
    ],
    HMGB2: [
      { r: 1, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG3-CRBN',            dc: '18.6', t: '0.85', rr: 'feasible', a: 'PASS' },
      { r: 2, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-Alkyl5-CRBN',          dc: '31.2', t: '0.80', rr: 'feasible', a: 'PASS' },
      { r: 3, s: 'Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG5-CRBN',            dc: '42.0', t: '0.77', rr: 'review',   a: 'PASS' }
    ],
    EGFR: [
      { r: 1, s: 'C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-PEG4-VHL', dc: '15.1', t: '0.90', rr: 'feasible', a: 'PASS' },
      { r: 2, s: 'C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-Alkyl6-VHL', dc: '29.4', t: '0.84', rr: 'feasible', a: 'PASS' }
    ]
  };

  runBtn.addEventListener('click', async () => {
    const target = targetSel ? targetSel.value : 'BRD4';
    const e3 = e3Sel ? e3Sel.value : 'CRBN';
    const wait = (ms) => new Promise(r => setTimeout(r, ms));

    runBtn.disabled = true;
    label.textContent = 'Walking the pipeline…';
    live.textContent = 'EXECUTING (ILLUSTRATIVE)'; live.classList.add('running');
    trace.innerHTML = ''; meta.textContent = 'illustrative run…';
    table.innerHTML = '<tr><td colspan="7" class="empty-row">ILLUSTRATIVE DEMO — precomputing example values…</td></tr>';

    for (const st of steps) {
      await wait(230 + Math.random() * 170);
      const row = document.createElement('div');
      row.className = 'trace-row new';
      const stClass = st.c === 'trace-ok' ? 'trace-st' : (st.c === 'trace-learn' ? 'trace-st illu' : 'trace-st illu');
      row.innerHTML = `<span class="trace-node">${st.n}</span>
        <span class="trace-msg">${st.m.replace('{{TARGET}}', target).replace('{{E3}}', e3)}</span>
        <span class="${stClass}">[${st.s}]</span>`;
      trace.appendChild(row);
      trace.scrollTop = trace.scrollHeight;
    }

    await wait(280);
    runBtn.disabled = false;
    label.textContent = 'Run walkthrough';
    live.textContent = 'COMPLETE'; live.classList.remove('running');

    const rows = (candidates[target] || candidates.BRD4);
    meta.textContent = `${rows.length} illustrative candidates · ${target} × ${e3}`;
    table.innerHTML = rows.map(c => `
      <tr>
        <td><span class="rank-chip">${c.r}</span></td>
        <td class="smiles-cell" title="${c.s}">${c.s}</td>
        <td><strong>${c.dc}</strong> nM <span class="badge eb-illu">ILLUSTRATIVE</span></td>
        <td>${c.t} <span class="badge eb-illu">SURROGATE</span></td>
        <td>${c.rr}</td>
        <td><span class="pass-badge illu">${c.a} · EXAMPLE</span></td>
        <td><span class="badge eb-illu">ILLUSTRATIVE DEMO</span></td>
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
