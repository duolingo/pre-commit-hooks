FROM alpine:3.16.0

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
    openjdk11-jre-headless \
    py3-pip \
    python3 \
  && pip3 install \
    autoflake==1.4 \
    black==22.3.0 \
    isort==5.10.1 \
  && python3 -m venv /black21-venv \
  && source /black21-venv/bin/activate \
  && pip3 install black==21.12b0 click==8.0.4 \
  && deactivate \
  && echo 'source /black21-venv/bin/activate && black "$@"' > /usr/bin/black21 \
  && chmod +x /usr/bin/black21 \
  && npm install -g \
    @prettier/plugin-xml@2.0.1 \
    @types/node@17.0.23 \
    prettier@2.6.2 \
    svgo@2.8.0 \
    typescript@4.6.3 \
  && apk del .build-deps \
  && wget https://github.com/google/google-java-format/releases/download/v1.15.0/google-java-format-1.15.0-all-deps.jar -O google-java-format \
  && wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.35/ktfmt-0.35-jar-with-dependencies.jar -O ktfmt \
  && wget https://github.com/mvdan/sh/releases/download/v3.4.3/shfmt_v3.4.3_linux_amd64 -O shfmt \
  && chmod +x shfmt \
  && wget https://releases.hashicorp.com/terraform/1.1.8/terraform_1.1.8_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && wget https://github.com/coursier/coursier/releases/download/v2.0.16/coursier -O /bin/coursier \
  && chmod +x /bin/coursier \
  && coursier bootstrap org.scalameta:scalafmt-cli_2.13:3.5.1 \
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
