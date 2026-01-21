# syntax=docker/dockerfile:1

FROM alpine:3.23.2 AS entry
RUN apk add --no-cache npm && npm install -g typescript@5.9.3 @types/node@25.0.9
COPY entry.ts .
RUN tsc \
    --noUnusedLocals \
    --noUnusedParameters \
    --strict \
    --typeRoots /usr/local/lib/node_modules/@types \
    entry.ts \
  && chmod +x entry.js

# "Creating a JRE using jlink" at https://hub.docker.com/_/eclipse-temurin
# List of required modules is determined by starting with `docker run --rm
# eclipse-temurin:21-alpine java --list-modules`, then removing modules by trial
# and error until `make test` throws ClassNotFoundException. When first
# implemented, this custom JRE reduced our image size from 574 MB to 469 MB
FROM amazoncorretto:21.0.9-alpine3.22 AS jre
RUN apk add binutils && jlink \
  --add-modules java.se,jdk.compiler,jdk.unsupported \
  --compress zip-6 \
  --no-header-files \
  --no-man-pages \
  --output /jre \
  --strip-debug

FROM alpine:3.23.2
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
RUN <<EOF
set -eu

# Install Alpine dependencies
apk add --no-cache --virtual .build-deps \
  gcc \
  musl-dev \
  npm \
  openjdk17-jre-headless \
  py3-pip \
  python3-dev
apk add --no-cache \
  libxslt \
  nodejs \
  python3
pip3 install --break-system-packages \
  autoflake==1.7.8 \
  isort==5.13.2 \
  ruff==0.14.13 \
  PyYAML>=6.0

# Install Python dependencies
python3 -m venv /black21-venv
source /black21-venv/bin/activate
pip3 install black==21.12b0 click==8.0.4
deactivate
echo 'source /black21-venv/bin/activate && black "$@"' > /usr/bin/black21
chmod +x /usr/bin/black21

# Install Node dependencies
#
# We stay on eslint-plugin-unicorn 56.0.1 because 57+ removed support for
# importing this plugin into the ESLint config as CommonJS. (We use CommonJS
# instead of ESM in the ESLint config mainly because the latter requires a new
# local package.json file that declares `"type": "module"`, which interferes
# with other tools like SVGO). I couldn't get the `deasync` hack to work - it
# just hung forever. TODO: Try updating this plugin after updating Node.js to
# v22+, which has experimental support for synchronously require()-ing ESM?
# https://github.com/sindresorhus/eslint-plugin-unicorn/releases/tag/v57.0.0
# https://gist.github.com/sindresorhus/a39789f98801d908bbc7ff3ecc99d99c
# https://nodejs.org/en/blog/announcements/v22-release-announce#support-requireing-synchronous-esm-graphs
# https://github.com/eslint/eslint/issues/13684#issuecomment-722949152
npm install -g \
  @prettier/plugin-xml@3.4.2 \
  eslint@9.39.2 \
  eslint-plugin-jsdoc@62.0.0 \
  eslint-plugin-sort-keys@2.3.5 \
  eslint-plugin-unicorn@56.0.1 \
  prettier@3.8.0 \
  svgo@4.0.0 \
  typescript-eslint@8.53.1

# Install Scala dependencies
wget https://github.com/coursier/coursier/releases/download/v2.1.24/coursier -O /bin/coursier
chmod +x /bin/coursier
coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.10.4 \
  -r sonatype:snapshots --main org.scalafmt.cli.Cli \
  --standalone \
  -o scalafmt

# Install static binaries
wget https://github.com/muttleyxd/clang-tools-static-binaries/releases/download/master-796e77c/clang-format-20_linux-amd64 -O clang-format
chmod +x clang-format
wget https://github.com/google/google-java-format/releases/download/v1.33.0/google-java-format-1.33.0-all-deps.jar -O google-java-format
wget https://repo1.maven.org/maven2/com/facebook/ktfmt/0.61/ktfmt-0.61-with-dependencies.jar -O ktfmt
wget https://repo1.maven.org/maven2/com/squareup/sort-gradle-dependencies-app/0.16/sort-gradle-dependencies-app-0.16-all.jar -O gradle-dependencies-sorter
wget https://github.com/mvdan/sh/releases/download/v3.12.0/shfmt_v3.12.0_linux_amd64 -O shfmt
chmod +x shfmt
wget https://github.com/tamasfe/taplo/releases/download/0.10.0/taplo-linux-x86_64.gz -O taplo.gz
gzip -d taplo.gz
chmod +x taplo
wget https://releases.hashicorp.com/terraform/1.14.3/terraform_1.14.3_linux_amd64.zip -O tf.zip
unzip tf.zip
rm tf.zip
rm LICENSE.txt
wget https://releases.hashicorp.com/packer/1.14.3/packer_1.14.3_linux_amd64.zip -O packer.zip
unzip packer.zip
rm packer.zip

# Create an empty file for the linters that need one for some reason
touch /emptyfile

# Delete unused files found by running `apk add ncdu && ncdu` inside `make shell`
apk del .build-deps
rm -rf \
  /bin/coursier \
  /black21-venv/lib/python3.12/site-packages/pip \
  /black21-venv/lib/python3.12/site-packages/pkg_resources \
  /black21-venv/lib/python3.12/site-packages/setuptools \
  /root/.cache \
  /root/.npm \
  /usr/bin/lto-dump \
  /var/cache
EOF
# https://stackoverflow.com/a/59485924
COPY --from=golang:1.25.6-alpine3.23 /usr/local/go/bin/gofmt /gofmt
ENV PATH="/jre/bin:${PATH}"
COPY --from=jre /jre /jre
COPY . .
COPY --from=entry /entry.js /entry
# https://github.com/coursier/coursier/issues/1955#issuecomment-956697764
ENV COURSIER_CACHE=/tmp/coursier-cache
ENV COURSIER_JVM_CACHE=/tmp/coursier-jvm-cache
ENV NODE_PATH=/usr/local/lib/node_modules
