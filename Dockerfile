# syntax=docker/dockerfile:1

FROM alpine:3.23.4 AS entry
RUN apk add --no-cache npm && npm install -g typescript@6.0.2 @types/node@25.6.0
COPY entry.ts .
RUN tsc \
    --noUnusedLocals \
    --noUnusedParameters \
    --strict \
    --types node \
    --typeRoots /usr/local/lib/node_modules/@types \
    entry.ts \
  && chmod +x entry.js

# "Creating a JRE using jlink" at https://hub.docker.com/_/eclipse-temurin
# List of required modules is determined by starting with `docker run --rm
# eclipse-temurin:21-alpine java --list-modules`, then removing modules by trial
# and error until `make test` throws ClassNotFoundException. When first
# implemented, this custom JRE reduced our image size from 574 MB to 469 MB
FROM amazoncorretto:21.0.10-alpine3.23 AS jre
RUN apk add binutils && jlink \
  --add-modules java.se,jdk.compiler,jdk.unsupported \
  --compress zip-9 \
  --dedup-legal-notices=error-if-not-same-content \
  --no-header-files \
  --no-man-pages \
  --output /jre \
  --strip-debug

FROM alpine:3.23.4
ARG TARGETARCH
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
RUN <<EOF
set -eu

# Map TARGETARCH to per-tool arch slugs
case "$TARGETARCH" in
  amd64) TAPLO_ARCH=x86_64 ;;
  arm64) TAPLO_ARCH=aarch64 ;;
  *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;;
esac

# Install Alpine dependencies
apk add --no-cache --virtual .build-deps \
  gcc \
  musl-dev \
  npm \
  openjdk17-jre-headless \
  py3-pip \
  python3-dev
apk add --no-cache \
  nodejs \
  python3
pip3 install --break-system-packages \
  autoflake==1.7.8 \
  clang-format==20.1.8 \
  isort==5.13.2 \
  ruff==0.15.10 \
  'PyYAML>=6.0'

# Install Python dependencies
python3 -m venv /black21-venv
source /black21-venv/bin/activate
pip3 install black==21.12b0 click==8.0.4
deactivate
echo 'source /black21-venv/bin/activate && black "$@"' > /usr/bin/black21
chmod +x /usr/bin/black21

# Install Node dependencies
npm install -g \
  @eslint/compat@2.0.5 \
  @prettier/plugin-xml@3.4.2 \
  eslint@10.2.0 \
  eslint-plugin-jsdoc@62.9.0 \
  eslint-plugin-perfectionist@5.8.0 \
  eslint-plugin-sort-keys@2.3.5 \
  eslint-plugin-unicorn@64.0.0 \
  prettier@3.8.3 \
  svgo@4.0.1 \
  typescript-eslint@8.58.2

# Install Scala dependencies
wget https://github.com/coursier/coursier/releases/download/v2.1.24/coursier -O /bin/coursier
chmod +x /bin/coursier
coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.11.0 \
  -r sonatype:snapshots --main org.scalafmt.cli.Cli \
  --standalone \
  -o scalafmt

# Install static binaries
wget https://github.com/google/google-java-format/releases/download/v1.35.0/google-java-format-1.35.0-all-deps.jar -O google-java-format
wget https://repo1.maven.org/maven2/com/facebook/ktfmt/0.62/ktfmt-0.62-with-dependencies.jar -O ktfmt
wget https://repo1.maven.org/maven2/com/squareup/sort-gradle-dependencies-app/0.16/sort-gradle-dependencies-app-0.16-all.jar -O gradle-dependencies-sorter
wget "https://github.com/mvdan/sh/releases/download/v3.13.1/shfmt_v3.13.1_linux_${TARGETARCH}" -O shfmt
chmod +x shfmt
wget "https://github.com/tamasfe/taplo/releases/download/0.10.0/taplo-linux-${TAPLO_ARCH}.gz" -O taplo.gz
gzip -d taplo.gz
chmod +x taplo
wget "https://releases.hashicorp.com/terraform/1.14.8/terraform_1.14.8_linux_${TARGETARCH}.zip" -O tf.zip
unzip tf.zip
rm tf.zip LICENSE.txt
wget "https://releases.hashicorp.com/packer/1.15.1/packer_1.15.1_linux_${TARGETARCH}.zip" -O packer.zip
unzip packer.zip
rm packer.zip LICENSE.txt

# Create an empty file for the linters that need one for some reason
touch /emptyfile

# Strip unused metadata from node_modules
find /usr/local/lib/node_modules \
  \( -name '*.md' -o -name '*.markdown' -o -name '*.map' -o -name '*.d.ts' \
     -o -name 'LICENSE*' -o -name 'CHANGELOG*' -o -name 'HISTORY*' \
     -o -name 'AUTHORS*' -o -name 'CONTRIBUTORS*' \) -type f -delete
find /usr/local/lib/node_modules -type d \
  \( -name 'test' -o -name 'tests' -o -name '__tests__' -o -name '.github' \) \
  -exec rm -rf {} +

# Delete unused files found by running `apk add ncdu && ncdu` inside `make shell`
apk del .build-deps
rm -rf \
  /bin/coursier \
  /black21-venv/bin/Activate.ps1 \
  /black21-venv/bin/activate.csh \
  /black21-venv/bin/activate.fish \
  /black21-venv/bin/pip \
  /black21-venv/bin/pip3 \
  /black21-venv/bin/pip3.12 \
  /black21-venv/lib/python3.12/site-packages/pip \
  /black21-venv/lib/python3.12/site-packages/pkg_resources \
  /black21-venv/lib/python3.12/site-packages/setuptools \
  /root/.cache \
  /root/.npm \
  /usr/bin/lto-dump \
  /usr/lib/python3.12/ensurepip \
  /usr/lib/python3.12/lib2to3 \
  /usr/lib/python3.12/site-packages/test_autoflake.py \
  /usr/lib/python3.12/turtle.py \
  /usr/lib/python3.12/turtledemo \
  /var/cache
EOF
# https://stackoverflow.com/a/59485924
COPY --from=golang:1.26.2-alpine3.23 /usr/local/go/bin/gofmt /gofmt
ENV PATH="/jre/bin:${PATH}"
COPY --from=jre /jre /jre
COPY . .
COPY --from=entry /entry.js /entry
# https://github.com/coursier/coursier/issues/1955#issuecomment-956697764
ENV COURSIER_CACHE=/tmp/coursier-cache
ENV COURSIER_JVM_CACHE=/tmp/coursier-jvm-cache
ENV NODE_PATH=/usr/local/lib/node_modules
# .mjs import resolution doesn't respect NODE_PATH
RUN ln -s /usr/local/lib/node_modules /node_modules
