# GitHub Details & Collaborator Setup

This document provides repository management, contribution guidelines, and collaborator setup instructions for **PROTACXtend**.

---

## 📌 Repository Information

- **Official Repository URL**: [`https://github.com/the-ahuja-lab/PROTACXtend`](https://github.com/the-ahuja-lab/PROTACXtend)
- **Organization**: Ahuja Lab ([@the-ahuja-lab](https://github.com/the-ahuja-lab))
- **Lead Developer & Maintainer**: Saveena Solanki ([@SaveenaSolanki](https://github.com/SaveenaSolanki))
- **Default Branch**: `main`
- **License**: MIT License

---

## 👥 Adding Saveena Solanki as Collaborator

To add Saveena Solanki (`@SaveenaSolanki` / `SaveenaSolanki`) as a collaborator with admin / push access on `the-ahuja-lab/PROTACXtend`:

### Method 1: Using GitHub CLI (`gh`)

If you have administrative access to the `the-ahuja-lab` organization:

```bash
# Invite SaveenaSolanki as a collaborator with push/admin permissions
gh api -X PUT /repos/the-ahuja-lab/PROTACXtend/collaborators/SaveenaSolanki \
  -f permission=admin
```

To accept the invitation automatically using the GitHub CLI authenticated as `@SaveenaSolanki`:

```bash
# List pending repository invitations
gh api user/repository_invitations

# Accept invitation for PROTACXtend repository
gh api -X PATCH /user/repository_invitations/{invitation_id}
```

---

### Method 2: Via GitHub Web Interface

1. Navigate to [`https://github.com/the-ahuja-lab/PROTACXtend/settings/access`](https://github.com/the-ahuja-lab/PROTACXtend/settings/access).
2. Click **Add people**.
3. Search for username **`SaveenaSolanki`** (or `saveenasolanki`).
4. Select role **Admin** or **Write (Push)** access.
5. Click **Add SaveenaSolanki to this repository**.
6. An invitation link will be sent to `@SaveenaSolanki`. Accept via [`https://github.com/the-ahuja-lab/PROTACXtend/invitations`](https://github.com/the-ahuja-lab/PROTACXtend/invitations).

---

## 🔄 Local Git Configuration & Syncing

Configure git remote settings to link your local workspace to `https://github.com/the-ahuja-lab/PROTACXtend`:

```bash
cd /storage/saveena/protacpilot

# Set origin remote to the official repository
git remote set-url origin https://github.com/the-ahuja-lab/PROTACXtend.git

# Verify remote configuration
git remote -v
```

### Push Code & Documentation Changes

```bash
# Stage changes
git add website/ documentation/ README.md PROTACXTEND_README.md

# Commit with descriptive message
git commit -m "feat: Add website UI, comprehensive documentation, and GitHub collaborator setup"

# Push to main branch
git push origin main
```

---

## 📜 Repository Structure Standard

```text
PROTACXtend/
├── website/                   # Web landing page & docs interface (feynman.is style)
│   ├── index.html             # HTML5 single page app
│   ├── styles.css             # HSL dark theme & layout styles
│   └── app.js                 # Interactive UI logic & simulator
├── documentation/             # Markdown documentation suite
│   ├── README.md              # Docs index hub
│   ├── GETTING_STARTED.md     # Installation & quickstart
│   ├── ARCHITECTURE.md        # 23-node Feynman stack
│   ├── WORKFLOWS.md           # Slash commands & CLI workflows
│   ├── API_REFERENCE.md       # Python & REST API reference
│   └── GITHUB_AND_COLLABORATION.md # GitHub & collaborator guide
├── synglue_agent/             # Core Python package & agents
├── PROTACXtend                # Executable CLI wrapper
├── pyproject.toml             # Package setup configuration
└── README.md                  # Main repository README
```
