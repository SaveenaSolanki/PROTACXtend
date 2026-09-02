#!/usr/bin/env bash
# Installs a pre-commit hook that blocks commits containing secrets.
# Usage: ./scripts/install_gitleaks_hook.sh [path-to-gitleaks-binary]
set -euo pipefail
GITLEAKS="${1:-$(command -v gitleaks || echo /tmp/gitleaks)}"
HOOK=".git/hooks/pre-commit"
cat > "$HOOK" << 'HOOKEOF'
#!/usr/bin/env bash
set -uo pipefail
GITLEAKS="${GITLEAKS_BIN:-$(command -v gitleaks)}"
if [ -z "$GITLEAKS" ]; then
  echo "gitleaks not found — install it (https://github.com/gitleaks/gitleaks) or set GITLEAKS_BIN. Skipping secret check."
  exit 0
fi
if ! "$GITLEAKS" protect --staged --no-banner --redact=100; then
  echo "✗ SECRET DETECTED in staged changes. Commit blocked."
  exit 1
fi
HOOKEOF
chmod +x "$HOOK"
echo "installed pre-commit hook: $HOOK (binary: $GITLEAKS)"
