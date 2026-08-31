#!/usr/bin/env bash
# Install a pre-commit hook that regenerates _data/publications.yml from
# _bibliography/papers.bib, so the two can never drift apart.
#
#   bash bin/install-hooks.sh
#
# Safe to re-run. To remove:  rm .git/hooks/pre-commit
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hook="$repo_root/.git/hooks/pre-commit"

if [ ! -d "$repo_root/.git" ]; then
  echo "error: no .git directory at $repo_root" >&2
  exit 1
fi

if [ -e "$hook" ] && ! grep -q "bib2yml.py" "$hook" 2>/dev/null; then
  echo "A pre-commit hook already exists and is not ours:"
  echo "  $hook"
  echo "Back it up or merge by hand; refusing to overwrite."
  exit 1
fi

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Regenerate publications from BibTeX before each commit.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"

# Only act when the bibliography is part of this commit, or when the generated
# file is missing entirely.
if git diff --cached --name-only | grep -q '^_bibliography/papers\.bib$' \
   || [ ! -f "$root/_data/publications.yml" ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "pre-commit: python3 not found; skipping bib2yml." >&2
    echo "            Run 'python3 bin/bib2yml.py' before pushing." >&2
    exit 0
  fi
  echo "pre-commit: regenerating _data/publications.yml from papers.bib"
  python3 "$root/bin/bib2yml.py"
  git add "$root/_data/publications.yml"
fi
HOOK

chmod +x "$hook"
echo "Installed $hook"
echo
echo "From now on, committing a change to _bibliography/papers.bib will"
echo "regenerate and stage _data/publications.yml automatically."
echo "You can still run it by hand any time:  python3 bin/bib2yml.py"
