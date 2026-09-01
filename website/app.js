// PROTACXtend Interactive Web Application Logic

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initInstallTabs();
  initCopyButtons();
  initInteractiveSimulator();
  initDocsTabs();
});

/* Theme Toggle (Dark/Light) */
function initThemeToggle() {
  const themeToggle = document.getElementById('theme-toggle');
  const sunIcon = document.getElementById('sun-icon');
  const moonIcon = document.getElementById('moon-icon');

  const savedTheme = localStorage.getItem('theme') || 'dark';
  applyTheme(savedTheme);

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = document.documentElement.classList.contains('light') ? 'light' : 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
      localStorage.setItem('theme', newTheme);
    });
  }

  function applyTheme(theme) {
    if (theme === 'light') {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
      if (sunIcon) sunIcon.style.display = 'none';
      if (moonIcon) moonIcon.style.display = 'block';
    } else {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
      if (sunIcon) sunIcon.style.display = 'block';
      if (moonIcon) moonIcon.style.display = 'none';
    }
  }
}

/* Install Tab Switcher */
function initInstallTabs() {
  const tabBtns = document.querySelectorAll('.install-toggle');
  const installCmdSpan = document.getElementById('install-command');

  const commands = {
    pip: 'pip install protacxtend',
    git: 'git clone https://github.com/the-ahuja-lab/PROTACXtend.git',
    curl: 'curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/install.sh | bash'
  };

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tool = btn.getAttribute('data-tool');
      if (installCmdSpan && commands[tool]) {
        installCmdSpan.textContent = commands[tool];
      }
    });
  });
}

/* Copy to Clipboard */
function initCopyButtons() {
  const copyBtn = document.getElementById('install-copy-btn');
  const installCmdSpan = document.getElementById('install-command');

  if (copyBtn && installCmdSpan) {
    copyBtn.addEventListener('click', () => {
      const textToCopy = installCmdSpan.textContent.trim();
      navigator.clipboard.writeText(textToCopy).then(() => {
        const originalHTML = copyBtn.innerHTML;
        copyBtn.innerHTML = `<svg size="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;color:var(--primary);"><path d="M20 6L9 17l-5-5"></path></svg>`;
        setTimeout(() => {
          copyBtn.innerHTML = originalHTML;
        }, 2000);
      });
    });
  }
}

/* Interactive PROTAC Simulator */
function initInteractiveSimulator() {
  const runBtn = document.getElementById('run-sim-btn');
  const traceOutput = document.getElementById('trace-output');
  const resultsTableBody = document.getElementById('results-table-body');
  const targetSelect = document.getElementById('target-select');
  const e3Select = document.getElementById('e3-select');

  if (!runBtn) return;

  const mockTraces = [
    { node: "SupervisorAgent", msg: "Parsing design objective → Target: {{TARGET}}, E3: {{E3}}", status: "OK" },
    { node: "TargetResolver", msg: "UniProt / ChEMBL resolution → CHEMBL6066530 (pChembl=8.4)", status: "OK" },
    { node: "BinderRetrieval", msg: "Retrieved 87 target binders + 12 E3 recruits from ChEMBL DB", status: "OK" },
    { node: "ExitVectorDetect", msg: "RDKit attachment points identified on warhead C-7 vector", status: "OK" },
    { node: "LinkerGenerator", msg: "73-method engine generated 16 PEG/alkyl/triazole linkers", status: "OK" },
    { node: "ConstructPROTACs", msg: "32 candidate PROTAC molecules assembled and sanitized", status: "OK" },
    { node: "TernaryComplex", msg: "P4ward simulation run → SE(3) geometric feasibility score: 0.88", status: "OK" },
    { node: "DegradationML", msg: "Chemprop DC50 prediction: 12.4 nM | Dmax: 89.2% | Class: Active", status: "OK" },
    { node: "ADMETSafety", msg: "hERG: 0.02, AMES: 0.08, Lipinski & Veber rules passed", status: "OK" },
    { node: "FinalReport", msg: "Pareto front ranking compiled → Top 4 PROTACs ready", status: "OK" }
  ];

  const mockCandidates = {
    BRD4: [
      { rank: 1, smiles: "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-PEG4-JQ1", dc50: "12.4 nM", dmax: "89.2%", ternary: "0.88", admet: "PASS (Low Risk)" },
      { rank: 2, smiles: "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl6-dBET6", dc50: "24.8 nM", dmax: "84.5%", ternary: "0.82", admet: "PASS (Low Risk)" },
      { rank: 3, smiles: "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Triazole-MZ1", dc50: "38.1 nM", dmax: "81.0%", ternary: "0.79", admet: "PASS (Low Risk)" },
      { rank: 4, smiles: "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1-Alkyl8-ARV771", dc50: "45.0 nM", dmax: "78.4%", ternary: "0.75", admet: "PASS (Low Risk)" }
    ],
    HMGB2: [
      { rank: 1, smiles: "Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG3-CRBN", dc50: "18.6 nM", dmax: "86.4%", ternary: "0.85", admet: "PASS (Low Risk)" },
      { rank: 2, smiles: "Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-Alkyl5-CRBN", dc50: "31.2 nM", dmax: "82.1%", ternary: "0.80", admet: "PASS (Low Risk)" },
      { rank: 3, smiles: "Cc1nc(C)c2c(n1)N(C)c3ccc(Cl)cc3C2=O-PEG5-CRBN", dc50: "42.0 nM", dmax: "79.8%", ternary: "0.77", admet: "PASS (Low Risk)" }
    ],
    EGFR: [
      { rank: 1, smiles: "C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-PEG4-VHL", dc50: "15.1 nM", dmax: "91.0%", ternary: "0.90", admet: "PASS (Low Risk)" },
      { rank: 2, smiles: "C=CC(=O)Nc1cc(Nc2nccc(n2)c3cn(C)c4ccccc34)c(OC)cc1-Alkyl6-VHL", dc50: "29.4 nM", dmax: "85.7%", ternary: "0.84", admet: "PASS (Low Risk)" }
    ]
  };

  runBtn.addEventListener('click', async () => {
    const target = targetSelect ? targetSelect.value : 'BRD4';
    const e3 = e3Select ? e3Select.value : 'CRBN';

    runBtn.disabled = true;
    runBtn.textContent = "Running 23-Node Pipeline...";
    traceOutput.innerHTML = "";
    resultsTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);">Executing molecular assembly and ternary simulation...</td></tr>`;

    for (let i = 0; i < mockTraces.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 350));
      const step = mockTraces[i];
      const msg = step.msg.replace('{{TARGET}}', target).replace('{{E3}}', e3);
      
      const row = document.createElement('div');
      row.className = 'trace-step';
      row.innerHTML = `
        <span class="trace-node">${step.node}</span>
        <span class="trace-msg">${msg}</span>
        <span class="trace-status-ok">[${step.status}]</span>
      `;
      traceOutput.appendChild(row);
      traceOutput.scrollTop = traceOutput.scrollHeight;
    }

    runBtn.disabled = false;
    runBtn.textContent = "Run PROTACXtend Pipeline";

    const cands = mockCandidates[target] || mockCandidates['BRD4'];
    resultsTableBody.innerHTML = cands.map(c => `
      <tr>
        <td><strong>#${c.rank}</strong></td>
        <td class="smiles-cell" title="${c.smiles}">${c.smiles}</td>
        <td><span style="color:var(--primary);font-weight:600;">${c.dc50}</span></td>
        <td>${c.dmax}</td>
        <td>${c.ternary}</td>
        <td><span class="badge" style="font-size:0.7rem;">${c.admet}</span></td>
      </tr>
    `).join('');
  });
}

/* Documentation Tab Navigation */
function initDocsTabs() {
  const tabs = document.querySelectorAll('.docs-tab');
  const contents = document.querySelectorAll('.docs-pane');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      contents.forEach(c => c.style.display = 'none');

      tab.classList.add('active');
      const paneId = tab.getAttribute('data-target');
      const targetPane = document.getElementById(paneId);
      if (targetPane) {
        targetPane.style.display = 'block';
      }
    });
  });
}
