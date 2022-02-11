#!/bin/sh

set -e

FEATURE=${FEATURE:?}
VERSION=${VERSION:?}

# Merge feature (abort if there are no changes)
git switch main
git fetch
git merge
git merge --squash $FEATURE
git diff --cached --quiet && false

# Run code checks
make check

# Publish
git commit --author="$(git log main..$FEATURE --format="%aN <%aE>" | tail --lines=1)"
git tag $VERSION
git push origin main $VERSION

# Clean up
git branch --delete $FEATURE
git push --delete origin $FEATURE
