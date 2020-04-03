FROM alpine:3.11.5

# Alpine base packages
RUN apk update && apk upgrade && apk add --no-cache \
  bash \
  build-base \
  git \
  nodejs-npm \
  openjdk8 \
  python3-dev

# Alpine tool packages
RUN apk update && apk upgrade && apk add --no-cache \
  clang

# Python packages
RUN pip3 install --upgrade pip && pip3 install \
  autoflake==1.3.1 \
  black==19.10b0

# Individual binaries
RUN wget https://github.com/google/google-java-format/releases/download/google-java-format-1.7/google-java-format-1.7-all-deps.jar
RUN wget https://github.com/shyiko/ktlint/releases/download/0.36.0/ktlint \
  && chmod +x ktlint
RUN wget https://github.com/mvdan/sh/releases/download/v3.0.2/shfmt_v3.0.2_linux_amd64 -O shfmt \
  && chmod +x shfmt
RUN wget https://releases.hashicorp.com/terraform/0.11.7/terraform_0.11.7_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip

# NPM packages
# https://github.com/npm/npm/issues/20861#issuecomment-400786321
RUN npm config set unsafe-perm true && npm install -g \
    prettier@2.0.2 \
    svgo@1.3.2 \
    typescript@3.8.3 \
  && npm install \
    @types/node@12.7.8

# Local files
COPY . .
RUN tsc --noUnusedLocals --noUnusedParameters --strict entry.ts \
  && mv entry.js entry && chmod +x entry && touch /emptyfile
