FROM alpine:3.18.4

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

# Dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    npm \
    python3-dev \
  && apk add --no-cache \
    clang-extra-tools \
    libxslt \
    nodejs \
    openjdk17-jre-headless \
    py3-pip \
    python3 \
  && pip3 install \
    autoflake==1.7.8 \
    isort==5.12.0 \
    ruff==0.1.5 \
  && python3 -m venv /black21-venv \
  && source /black21-venv/bin/activate \
  && pip3 install black==21.12b0 click==8.0.4 \
  && deactivate \
  && echo 'source /black21-venv/bin/activate && black "$@"' > /usr/bin/black21 \
  && chmod +x /usr/bin/black21 \
  && npm install -g \
    @prettier/plugin-xml@3.2.2 \
    @types/node@20.9.0 \
    prettier@3.1.0 \
    svgo@3.0.3 \
    typescript@5.2.2 \
  && apk del .build-deps \
  && wget https://github.com/google/google-java-format/releases/download/v1.18.1/google-java-format-1.18.1-all-deps.jar -O google-java-format \
  && wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.46/ktfmt-0.46-jar-with-dependencies.jar -O ktfmt \
  && wget https://github.com/mvdan/sh/releases/download/v3.7.0/shfmt_v3.7.0_linux_amd64 -O shfmt \
  && chmod +x shfmt \
  && wget https://releases.hashicorp.com/terraform/1.6.3/terraform_1.6.3_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && wget https://github.com/coursier/coursier/releases/download/v2.1.7/coursier -O /bin/coursier \
  && chmod +x /bin/coursier \
  && coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.7.16 \
    -r sonatype:snapshots --main org.scalafmt.cli.Cli \
    --standalone \
    -o scalafmt \
  && rm /bin/coursier

# Local files
COPY . .
RUN tsc \
    --noUnusedLocals \
    --noUnusedParameters \
    --strict \
    --typeRoots /usr/local/lib/node_modules/@types \
    entry.ts \
  && mv entry.js entry \
  && chmod +x entry \
  && touch /emptyfile
