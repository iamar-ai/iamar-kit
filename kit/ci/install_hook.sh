#!/bin/sh
# Install kit/ci/pre-push as this clone's git pre-push hook (CI check, an internal task).
root=$(git rev-parse --show-toplevel) || exit 1
cp "$root/kit/ci/pre-push" "$(git rev-parse --git-path hooks)/pre-push" && chmod +x "$(git rev-parse --git-path hooks)/pre-push" && echo "pre-push hook installed"
