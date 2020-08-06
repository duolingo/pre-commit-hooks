FROM alpine:3.8

# Alpine base packages
RUN apk update && apk upgrade && apk add --no-cache \
  bash \
  git \
  nodejs-npm \
  openjdk8 \
  python3

# Alpine tool packages
RUN apk update && apk upgrade && apk add --no-cache \
  clang \
  terraform

# Python packages
RUN pip3 install --upgrade pip && pip3 install \
  black==19.3b0

# GitHub binaries
RUN wget https://github.com/google/google-java-format/releases/download/google-java-format-1.7/google-java-format-1.7-all-deps.jar
RUN wget https://github.com/shyiko/ktlint/releases/download/0.34.2/ktlint \
  && chmod +x ktlint
RUN wget https://github.com/mvdan/sh/releases/download/v3.0.1/shfmt_v3.0.1_linux_amd64 -O shfmt \
  && chmod +x shfmt

# Scala packages
RUN wget https://github.com/coursier/coursier/releases/download/v2.0.0-RC6-24/coursier -O /bin/coursier \
    && chmod +x /bin/coursier
RUN coursier bootstrap org.scalameta:scalafmt-cli_2.12:2.6.4 \
      -r sonatype:snapshots --main org.scalafmt.cli.Cli \
      --standalone \
      -o scalafmt

# NPM packages
# https://github.com/npm/npm/issues/20861#issuecomment-400786321
RUN npm config set unsafe-perm true && npm install -g \
    prettier@1.19.1 \
    svgo@1.3.0 \
    typescript@3.6.3 \
  && npm install \
    @types/node@12.7.8

# Local files
COPY . .
RUN tsc --noUnusedLocals --noUnusedParameters --strict entry.ts \
  && mv entry.js entry && chmod +x entry && touch /emptyfile
