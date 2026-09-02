#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
# release_to_ahuja_lab.sh — one-shot release of PROTACXtend to the
# official Ahuja Lab GitHub account:  github.com/the-ahuja-lab/PROTACXtend
#
# WHY: the-ahuja-lab account (user-type GitHub account) can only receive
# repository *creation* from its own login. SaveenaSolanki is already a
# collaborator with push rights on the-ahuja-lab repos (SynGlue, EvOlf, ...).
# This script performs the final mirror push + Pages enablement once the
# empty repository exists and the push permission is granted.
#
# PREREQUISITE (run once by the Ahuja Lab account owner, ~30 seconds):
#   gh repo create the-ahuja-lab/PROTACXtend --public --description \
#     "PROTACXtend — open-source agentic AI platform for PROTAC discovery & design (Saveena Solanki, Ahuja Lab, IIIT Delhi)" \
#     --homepage "https://the-ahuja-lab.github.io/PROTACXtend/"
#   gh api -X PUT /repos/the-ahuja-lab/PROTACXtend/collaborators/SaveenaSolanki \
#     -f permission=push
#
# USAGE:
#   gh auth login                     # as SaveenaSolanki (or the lab owner)
#   ./scripts/release_to_ahuja_lab.sh
#
# RESULT:
#   the-ahuja-lab/PROTACXtend  (final code, single clean history commit)
#   https://the-ahuja-lab.github.io/PROTACXtend/   (GitHub Pages site)
# ════════════════════════════════════════════════════════════════════
set -euo pipefail

OWNER="the-ahuja-lab"
REPO="PROTACXtend"
SOURCE_REMOTE="https://github.com/SaveenaSolanki/${REPO}.git"
TARGET="${OWNER}/${REPO}"

echo "→ Verifying write access to ${TARGET} ..."
if ! gh api "repos/${TARGET}" >/dev/null 2>&1; then
  echo "✗ Repository ${TARGET} not found (or no access)."
  echo "  Ask the Ahuja Lab owner to create it first — see header of this script."
  exit 1
fi
PERM=$(gh api "repos/${TARGET}" --jq '.permissions.push' 2>/dev/null || echo false)
if [ "$PERM" != "true" ]; then
  echo "✗ No push permission on ${TARGET} yet."
  echo "  Grant SaveenaSolanki push, or run this script from the lab owner account."
  exit 1
fi

echo "→ Mirroring release history from ${SOURCE_REMOTE}"
TMP="$(mktemp -d)"
git clone --bare "${SOURCE_REMOTE}" "${TMP}/rel.git" >/dev/null 2>&1
cd "${TMP}/rel.git"
git remote add ahuja "https://github.com/${TARGET}.git"

echo "→ Pushing main → ${TARGET}"
git push ahuja main:main --force 2>&1 | tail -3

echo "→ Enabling GitHub Pages (Actions source)"
gh api -X POST "repos/${TARGET}/pages" -f build_type=workflow >/dev/null 2>&1 \
  || echo "  (Pages may already be enabled)"

echo ""
echo "✔ DONE — https://github.com/${TARGET}"
echo "✔ Live site — https://${OWNER}.github.io/${REPO}/  (after the github-pages workflow finishes)"
echo "  Next: update the-ahuja-lab/PROTACXtend → Settings → Pages → URL shown above,"
echo "        and set the repository homepage to the live site."
rm -rf "${TMP}"
