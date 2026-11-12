#!/bin/sh
# Repo-local configuration (never touches the global git config).
# - neutral brand identity
# - versioned hooks in tools/hooks (PII guard on content, file names, identity and messages)
# - `git cu`: commit with UTC timestamps (the pre-commit hook refuses any other commit)
set -e
cd "$(git rev-parse --show-toplevel)"
git config user.name "Paper Trail Lab"
git config user.email "hello@papertraillab.invalid"
git config core.hooksPath tools/hooks
git config alias.cu '!f() { d=$(date -u +%Y-%m-%dT%H:%M:%S+0000); GIT_AUTHOR_DATE="$d" GIT_COMMITTER_DATE="$d" TZ=UTC git commit "$@"; }; f'
echo "configured: identity, hooks (tools/hooks), alias 'git cu'"
