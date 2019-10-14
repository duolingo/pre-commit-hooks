#!/usr/bin/env bash
#
# This is a helper script that calls `pre-commit run --all-files` on a GitHub pull request.
#
# It expects the following environment variables:
# - ghprbActualCommit : sha1 of the git commit for the pull request
# - ghprbActualCommitAuthorEmail : commit author's email
# - ghprbGhRepository : repo name
# - GITHUB_TOKEN : GitHub token used to update the status check

set +x
set -eu
echo

# Posting pending status on PR
curl -s -X POST \
  "https://api.github.com/repos/${ghprbGhRepository}/statuses/${ghprbActualCommit}" \
  -H "Authorization: bearer ${GITHUB_TOKEN}" \
  -d @- > /dev/null << EOF
    {
      "context": "duolingo/pre-commit",
      "description": "Running \`pre-commit run --all-files\`",
      "state": "pending",
      "target_url": "${BUILD_URL}console"
    }
EOF

# Downloading code at revision (faster than clone + checkout)
curl -sL -o code.zip \
  -H "Authorization: bearer ${GITHUB_TOKEN}" \
  "https://github.com/${ghprbGhRepository}/archive/${ghprbActualCommit}.zip"
unzip code.zip > /dev/null
cd "$(printf %s "${ghprbGhRepository}" | cut -d/ -f2-)-${ghprbActualCommit}"

# Create Git repo
git init > /dev/null
git add -A
git commit -m 'Initial commit' > /dev/null

# Run pre-commit on all files
if [[ -f '.pre-commit-config.yaml' ]]; then
  args='run --all-files'
else
  args='try-repo https://github.com/duolingo/pre-commit-hooks.git duolingo --all-files'
fi
if pre-commit $args; then
  readonly description='All checks passed!'
  readonly state='success'
else
  readonly description='See Details link →'
  readonly state='failure'
  git diff
fi

# Post state to PR
curl -s -X POST \
  "https://api.github.com/repos/${ghprbGhRepository}/statuses/${ghprbActualCommit}" \
  -H "Authorization: bearer ${GITHUB_TOKEN}" \
  -d @- > /dev/null << EOF
    {
      "context": "duolingo/pre-commit",
      "description": "${description}",
      "state": "${state}",
      "target_url": "${BUILD_URL}console"
    }
EOF

# Propagate exit code
if [[ "${state}" = 'failure' ]]; then
  exit 1
fi
