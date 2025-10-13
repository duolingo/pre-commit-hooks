# syntax=docker/dockerfile:1

FROM alpine:3.20.3 AS entry
RUN apk add --no-cache npm && npm install -g typescript@5.6.3 @types/node@22.9.0
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
FROM amazoncorretto:21.0.6-alpine3.21 AS jre
RUN apk add binutils && jlink \
  --add-modules java.se,jdk.compiler,jdk.unsupported \
  --compress zip-6 \
  --no-header-files \
  --no-man-pages \
  --output /jre \
  --strip-debug

FROM alpine:3.20.3
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
  ruff==0.7.3 \
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
  @prettier/plugin-xml@3.4.1 \
  eslint@9.23.0 \
  eslint-plugin-jsdoc@50.6.9 \
  eslint-plugin-sort-keys@2.3.5 \
  eslint-plugin-unicorn@56.0.1 \
  prettier@3.5.3 \
  svgo@3.3.2 \
  typescript-eslint@8.29.0

# Install Scala dependencies
wget https://github.com/coursier/coursier/releases/download/v2.1.17/coursier -O /bin/coursier
chmod +x /bin/coursier
coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.8.3 \
  -r sonatype:snapshots --main org.scalafmt.cli.Cli \
  --standalone \
  -o scalafmt

# Install static binaries
wget https://github.com/muttleyxd/clang-tools-static-binaries/releases/download/master-32d3ac78/clang-format-18_linux-amd64 -O clang-format
chmod +x clang-format
wget https://github.com/google/google-java-format/releases/download/v1.24.0/google-java-format-1.24.0-all-deps.jar -O google-java-format
wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.53/ktfmt-0.53-jar-with-dependencies.jar -O ktfmt
wget https://repo1.maven.org/maven2/com/squareup/sort-gradle-dependencies-app/0.14/sort-gradle-dependencies-app-0.14-all.jar -O gradle-dependencies-sorter
wget https://github.com/mvdan/sh/releases/download/v3.10.0/shfmt_v3.10.0_linux_amd64 -O shfmt
chmod +x shfmt
wget https://github.com/tamasfe/taplo/releases/download/0.9.3/taplo-linux-x86_64.gz -O taplo.gz
gzip -d taplo.gz
chmod +x taplo
wget https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip -O tf.zip
unzip tf.zip
rm tf.zip
rm LICENSE.txt
wget https://releases.hashicorp.com/packer/1.14.2/packer_1.14.2_linux_amd64.zip -O packer.zip
unzip packer.zip
rm packer.zip

# Create an empty file for the linters that need one for some reason
touch /emptyfile

# Delete unused files found by running `apk add ncdu && ncdu` inside `make shell`
apk del .build-deps
rm -rf \
  /bin/coursier \
  /black21-venv/lib/python3.11/site-packages/pip \
  /black21-venv/lib/python3.11/site-packages/pkg_resources \
  /black21-venv/lib/python3.11/site-packages/setuptools \
  /root/.cache \
  /root/.npm \
  /usr/bin/lto-dump \
  /var/cache
EOF
# https://stackoverflow.com/a/59485924
COPY --from=golang:1.23.3-alpine3.20 /usr/local/go/bin/gofmt /gofmt
ENV PATH="/jre/bin:${PATH}"
COPY --from=jre /jre /jre
COPY . .
COPY --from=entry /entry.js /entry
# https://github.com/coursier/coursier/issues/1955#issuecomment-956697764
ENV COURSIER_CACHE=/tmp/coursier-cache
ENV COURSIER_JVM_CACHE=/tmp/coursier-jvm-cache
ENV NODE_PATH=/usr/local/lib/node_modules
