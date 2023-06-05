MAKEFLAGS += --silent
SHELL = /usr/bin/env bash

_IMAGE_NAME = duolingo/pre-commit-hooks

# Bumps this project's version number. Example:
#
#   $ make release V=1.0.3
#
# After running this, you should push master and tags to GitHub and create a
# corresponding GitHub release.
.PHONY: release
release: test
	# Validate
	[[ -n "${V}" ]]
	[[ -z "$$(git status --porcelain)" ]]

	# Update source files and commit
	git grep --cached -z -l '' | xargs -0 sed -E -i '' -e \
		"s@( rev: | entry: $(_IMAGE_NAME):)$$(git tag | tail -1)@\1${V}@g"
	git add -A
	git commit -m "Release ${V}" -n

	# Tag
	git tag "${V}"

# Pushes to Docker Hub. Should be run when creating a GitHub release. We don't
# use Docker Hub's autobuild feature anymore because it only supports amd64 :/
# https://github.com/docker/roadmap/issues/109
.PHONY: push
push: test
	grep -qF 'docker.io/' "$${HOME}/.docker/config.json" || docker login
	docker buildx inspect | grep -q docker-container || docker buildx create --use
	# https://stackoverflow.com/a/69987949
	docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
	docker buildx build --push --platform linux/amd64,linux/arm64 \
		-t "$(_IMAGE_NAME):$$(git tag | tail -1)" \
		-t "$(_IMAGE_NAME):latest" \
		.

# Opens a shell in the container for debugging
.PHONY: shell
shell:
	docker run --rm -it "$$(docker build --network=host -q .)" sh

# Runs tests
.PHONY: test
test:
	docker run --rm -v "$${PWD}/test:/test" "$$(docker build --network=host -q .)" sh -c \
		'cd /tmp \
			&& cp -r /test/before actual \
			&& cp -r /test/after expected \
			&& /entry actual/* \
			&& diff -r expected actual \
			&& echo "All tests passed!"'
