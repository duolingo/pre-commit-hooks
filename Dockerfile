FROM alpine:3.20.3 as entry
RUN apk add --no-cache npm && npm install -g typescript@5.6.3 @types/node@22.9.0
COPY entry.ts .
RUN tsc \
    --noUnusedLocals \
    --noUnusedParameters \
    --strict \
    --typeRoots /usr/local/lib/node_modules/@types \
    entry.ts \
  && chmod +x entry.js

FROM alpine:3.20.3
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
# Install all dependencies. As the last step of this RUN, we delete unused files
# found by running `apk add ncdu && ncdu` inside `make shell`
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    npm \
    py3-pip \
    python3-dev \
  && apk add --no-cache \
    libxslt \
    nodejs \
    openjdk17-jre-headless \
    python3 \
  && pip3 install --break-system-packages \
    autoflake==1.7.8 \
    isort==5.13.2 \
    ruff==0.7.3 \
  && python3 -m venv /black21-venv \
  && source /black21-venv/bin/activate \
  && pip3 install black==21.12b0 click==8.0.4 \
  && deactivate \
  && echo 'source /black21-venv/bin/activate && black "$@"' > /usr/bin/black21 \
  && chmod +x /usr/bin/black21 \
  && npm install -g \
    @prettier/plugin-xml@3.4.1 \
    prettier@3.3.3 \
    svgo@3.3.2 \
  && apk del .build-deps \
  && wget https://github.com/muttleyxd/clang-tools-static-binaries/releases/download/master-32d3ac78/clang-format-18_linux-amd64 -O clang-format \
  && chmod +x clang-format \
  && wget https://github.com/google/google-java-format/releases/download/v1.24.0/google-java-format-1.24.0-all-deps.jar -O google-java-format \
  && wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.53/ktfmt-0.53-jar-with-dependencies.jar -O ktfmt \
  && wget https://github.com/mvdan/sh/releases/download/v3.10.0/shfmt_v3.10.0_linux_amd64 -O shfmt \
  && chmod +x shfmt \
  && wget https://github.com/tamasfe/taplo/releases/download/0.9.3/taplo-linux-x86_64.gz -O taplo.gz \
  && gzip -d taplo.gz \
  && chmod +x taplo \
  && wget https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && wget https://github.com/coursier/coursier/releases/download/v2.1.17/coursier -O /bin/coursier \
  && chmod +x /bin/coursier \
  && coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.8.3 \
    -r sonatype:snapshots --main org.scalafmt.cli.Cli \
    --standalone \
    -o scalafmt \
  && touch /emptyfile \
  && rm -rf \
    /bin/coursier \
    /black21-venv/lib/python3.11/site-packages/pip \
    /black21-venv/lib/python3.11/site-packages/pkg_resources \
    /black21-venv/lib/python3.11/site-packages/setuptools \
    /root/.cache \
    /root/.npm \
    /usr/bin/lto-dump \
    /var/cache
# https://stackoverflow.com/a/59485924
COPY --from=golang:1.23.3-alpine3.20 /usr/local/go/bin/gofmt /gofmt
COPY . .
COPY --from=entry /entry.js /entry
