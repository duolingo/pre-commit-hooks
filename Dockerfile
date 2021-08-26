FROM alpine:3.14.1

# Dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    npm \
    python3-dev \
  && apk add --no-cache \
    clang-extra-tools \
    nodejs \
    openjdk11-jre-headless \
    py3-pip \
    python3 \
  && pip3 install --no-cache-dir --upgrade pip \
  && pip3 install --no-cache-dir \
    autoflake==1.4 \
    black==21.7b0 \
    isort==5.9.3 \
  && npm install -g \
    @types/node@16.6.2 \
    prettier@2.3.2 \
    svgo@1.3.2 \
    typescript@4.3.5 \
  && apk del .build-deps \
  && wget https://github.com/google/google-java-format/releases/download/v1.11.0/google-java-format-1.11.0-all-deps.jar -O google-java-format \
  && wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.28/ktfmt-0.28-jar-with-dependencies.jar -O ktfmt \
  && wget https://github.com/mvdan/sh/releases/download/v3.3.1/shfmt_v3.3.1_linux_amd64 -O shfmt \
  && chmod +x shfmt \
  && wget https://releases.hashicorp.com/terraform/0.12.29/terraform_0.12.29_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && mv terraform terraform0.12 \
  && wget https://releases.hashicorp.com/terraform/0.11.14/terraform_0.11.14_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && wget https://github.com/coursier/coursier/releases/download/v2.0.6/coursier -O /bin/coursier \
  && chmod +x /bin/coursier \
  && coursier bootstrap org.scalameta:scalafmt-cli_2.13:2.7.5 \
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
