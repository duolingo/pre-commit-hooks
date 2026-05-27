#!/usr/bin/env sh
# Adapted from https://github.com/pre-commit/pre-commit/compare/main...artnc:pre-commit:optimize-docker-image-pull

set -eu

# Abort if Docker not found
if ! command -v docker > /dev/null 2>&1; then
  exit
fi
export DOCKER_CLI_HINTS=false

# Collect Docker images provided as arguments
images="$@"

# Search .pre-commit-config.yaml for more Docker image usages
if [ -f .pre-commit-config.yaml ]; then
  # Fall back to dockerized yq if yq not found
  if ! command -v yq > /dev/null 2>&1; then
    echo "Local yq not found, using dockerized yq"
    yq() {
      docker run --init --network none --rm -v "${PWD}:/code" -w /code \
        mikefarah/yq:4.48.1 "$@"
    }
  fi

  # Extract image names
  images="${images} $(yq '.repos[].hooks[] |
      # Extract `entry` from hooks with language `docker_image`
      select(.language=="docker_image") | .entry |

      # Remove leading --entrypoint option
      sub("^ *--entrypoint(=| +)[^ ]+ +"; "") |

      # Extract first word as possible image name
      split(" ")[0] |

      # Lightly validate image name
      select(test("^[a-zA-Z0-9][a-zA-Z0-9.:/_-]*$"))' \
    .pre-commit-config.yaml 2> /dev/null | tr '\n' ' ')"
fi

# Trim, deduplicate, and sort image list
images="$(echo "${images}" | tr ' ' '\n' | sort -u | tr '\n' ' ' | xargs)"

# Pull images in parallel, skipping any that are already cached locally (`docker
# pull` on a cached image still round-trips to the registry to verify the
# digest, which takes ~400ms)
pids=""
for image in ${images}; do
  if docker image inspect "${image}" > /dev/null 2>&1; then
    continue
  fi
  docker pull --quiet "${image}" &
  pids="${pids} $!"
done
exit_code=0
for pid in ${pids}; do
  if ! wait "${pid}"; then
    exit_code=1
  fi
done
exit "${exit_code}"
