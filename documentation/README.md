# PROTACXtend Documentation Hub

Welcome to the official documentation for **PROTACXtend** — an open-source AI platform for target-to-lead PROTAC discovery, generative linker assembly, ternary complex modeling, and degradation prediction.

Developed at **Ahuja Lab** (Department of Computational Biology, IIIT Delhi) by **Saveena Solanki** and team.

---

## 📚 Documentation Index

| Section | Description | Link |
| :--- | :--- | :--- |
| **🚀 Getting Started** | Installation, environment setup, dependencies, fast-track quickstart | [GETTING_STARTED.md](GETTING_STARTED.md) |
| **🏗️ Architecture & Scientific Stack** | 23-node agentic workflow graph + 8 controlled-search/feedback extensions (= 31 nodes), supervisor engine, physics + ML stack | [ARCHITECTURE.md](ARCHITECTURE.md) |
| **🧭 Canonical Execution Stack (ADR-001)** | The single control plane: request parser → task graph → 9 scientific modules → tool executor → evidence → critic → decision → `TherapeuticStrategy` | [CANONICAL_STACK.md](CANONICAL_STACK.md) |
| **⚡ Workflows & CLI** | CLI workflows (`design`, `structure`, `dose`, `context`, `validate`, `contract`, `ask`/`learn`, `api`/`ui`) | [WORKFLOWS.md](WORKFLOWS.md) |
| **🔌 API & CLI Reference** | Complete Python API (`protacxtend`), REST endpoints, and CLI interface | [API_REFERENCE.md](API_REFERENCE.md) |
| **🐙 GitHub & Collaboration** | Repository details (`the-ahuja-lab/PROTACXtend`), Saveena Solanki collaborator setup | [GITHUB_AND_COLLABORATION.md](GITHUB_AND_COLLABORATION.md) |
| **🔬 Deep research memo** | Research positioning & design rationale | [DEEP_RESEARCH.md](DEEP_RESEARCH.md) |

---

## 🌐 Web Interface

Explore the interactive web landing page and local science workbench in the [`website/`](../website/) directory:
- Open [`website/index.html`](../website/index.html) directly in your browser.
- Or launch via python local web server:
  ```bash
  python -m http.server 8000 --directory website
  ```
- Or launch the Streamlit science workbench UI:
  ```bash
  protacxtend serve
  ```

Website status audits live beside the site: [`website/SCIENTIFIC_CLAIM_AUDIT.md`](../website/SCIENTIFIC_CLAIM_AUDIT.md) · [`website/SITE_COHERENCE_AUDIT.md`](../website/SITE_COHERENCE_AUDIT.md) · [`website/WEBSITE_AUDIT.md`](../website/WEBSITE_AUDIT.md) · [`website/WEBSITE_CHANGELOG.md`](../website/WEBSITE_CHANGELOG.md).

---

## 🔗 Official Repository

- **GitHub Repository**: [`https://github.com/the-ahuja-lab/PROTACXtend`](https://github.com/the-ahuja-lab/PROTACXtend)
- **Live site / GitHub Pages**: [`https://the-ahuja-lab.github.io/PROTACXtend/`](https://the-ahuja-lab.github.io/PROTACXtend/)
- **Primary Maintainer**: Saveena Solanki ([@SaveenaSolanki](https://github.com/SaveenaSolanki))
- **Organization**: Ahuja Lab ([@the-ahuja-lab](https://github.com/the-ahuja-lab))
