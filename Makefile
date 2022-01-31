MAKEFLAGS += --silent
SHELL = /usr/bin/env bash

_IMAGE_NAME = duolingo/pre-commit-hooks

# Bumps this project's version number. Example:
#
#   $ make release V=1.0.3
#
# After running this, you should push master and tags to GitHub and create a
# corresponding GitHub release.
release: test
	# Validate
	[[ -n "${V}" ]]
	[[ -z "$$(git status --porcelain)" ]]

	# Update source files and commit
	git grep --cached -z -l '' | xargs -0 sed -E -i \
		"s@( rev: | entry: $(_IMAGE_NAME):)$$(git tag | tail -1)@\1${V}@g"
	git add -A
	git commit -m "Release ${V}" -n

	# Tag
	git tag "${V}"

# Pushes to Docker Hub. Should be run when creating a GitHub release. We don't
# use Docker Hub's autobuild feature anymore because it only supports amd64 :/
# https://github.com/docker/roadmap/issues/109
push: test
	docker buildx inspect | grep -q docker-container || docker buildx create --use
	docker buildx build --push --platform linux/amd64,linux/arm64 \
		-t "$(_IMAGE_NAME):$(git tag | tail -1)" \
		-t "$(_IMAGE_NAME):latest" \
		.

# Runs tests
test:
	docker run --rm "$$(docker build --network=host -q . | head -1)" sh -c \
		"echo 1 > /tmp/a.js && /entry /tmp/a.js && grep -q ';' /tmp/a.js"
