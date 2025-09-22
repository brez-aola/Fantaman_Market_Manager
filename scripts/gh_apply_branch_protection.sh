#!/usr/bin/env bash
set -euo pipefail

# Apply GitHub branch protection to the `main` branch using `gh api`.
# Usage:
#   ./scripts/gh_apply_branch_protection.sh         -> interactive confirm
#   ./scripts/gh_apply_branch_protection.sh --yes   -> run non-interactive
# Environment:
#   REQUIRED_CHECKS (optional) - comma-separated list of status check contexts (default: CI)

REPO_URL=$(git config --get remote.origin.url || true)
if [ -z "$REPO_URL" ]; then
  echo "Unable to read remote.origin.url. Run this from a git repo with an origin remote." >&2
  exit 1
fi

if [[ "$REPO_URL" =~ ^git@github.com:(.*)/(.*)(\.git)?$ ]]; then
  owner=${BASH_REMATCH[1]}
  repo=${BASH_REMATCH[2]}
elif [[ "$REPO_URL" =~ ^https://github.com/(.*)/(.*)(\.git)?$ ]]; then
  owner=${BASH_REMATCH[1]}
  repo=${BASH_REMATCH[2]}
else
  echo "Unsupported remote URL format: $REPO_URL" >&2
  exit 1
fi

FULL="$owner/$repo"

# Normalize repo name: strip trailing .git if it got captured
repo=${repo%.git}
FULL="$owner/$repo"

REQUIRED_CHECKS=${REQUIRED_CHECKS:-CI}
IFS=',' read -r -a contexts <<< "$REQUIRED_CHECKS"

contexts_json="["
first=true
for c in "${contexts[@]}"; do
  c_trimmed=$(echo "$c" | sed 's/^ *//;s/ *$//')
  if [ "$first" = true ]; then
    contexts_json="$contexts_json\"$c_trimmed\""
    first=false
  else
    contexts_json="$contexts_json,\"$c_trimmed\""
  fi
done
contexts_json="$contexts_json]"

echo "Repository: $FULL"
echo "Branch: main"
echo "Required status checks: $REQUIRED_CHECKS"
echo

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install from https://cli.github.com/ and authenticate (gh auth login)." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh not authenticated. Run: gh auth login" >&2
  exit 1
fi

if [ "${1:-}" != "--yes" ]; then
  read -p "Proceed to apply branch protection to $FULL:main? (y/N) " ans
  case "$ans" in
    [Yy]*) ;;
    *) echo "Aborted."; exit 1;;
  esac
fi

echo "Applying branch protection..."

# Backup existing protection (if any)
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="$(dirname "$0")"
backup_path_env=${BACKUP_PATH:-}
if [ -n "$backup_path_env" ]; then
  backup_path="$backup_path_env"
else
  backup_path="$backup_dir/branch_protection_backup_${timestamp}.json"
fi

echo "Backing up current branch protection (if exists) to: $backup_path"
set +e
existing_protection=$(gh api "/repos/$FULL/branches/main/protection" --silent 2>/dev/null)
rc=$?
set -e
if [ $rc -ne 0 ] || [ -z "$existing_protection" ]; then
  echo "No existing branch protection found or failed to fetch (status code $rc). Continuing."
else
  echo "$existing_protection" | jq . > "$backup_path" 2>/dev/null || echo "$existing_protection" > "$backup_path"
  echo "Saved existing protection to $backup_path"
fi

gh api --method PUT "/repos/$FULL/branches/main/protection" \
  -F "required_status_checks={\"strict\":true,\"contexts\":$contexts_json}" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews={\"dismiss_stale_reviews\":true,\"require_code_owner_reviews\":false,\"required_approving_review_count\":1}" \
  -F "restrictions=null" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false"

echo "Branch protection applied to $FULL:main"
