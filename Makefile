MAKEFLAGS += --silent
SHELL = /usr/bin/env bash

# Bumps this project's version number. Example:
#   $ make release V=1.0.3
release:
	[[ -n "${V}" ]]
	[[ -z "$$(git status --porcelain)" ]]
	git grep --cached -z -l '' | xargs -0 sed -i "s/ rev: $$(git tag | tail -1)/ rev: ${V}/g"
	git add -A
	git commit -m "Release ${V}" -n
	git tag "${V}"

# Runs tests
test:
	docker run --rm "$$(docker build --network=host -q . | head -1)" sh -c \
		"echo 1 > /tmp/a.js && /entry /tmp/a.js && grep -q ';' /tmp/a.js"
