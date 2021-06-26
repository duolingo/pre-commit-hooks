FROM alpine:3.12.1

# Alpine packages
RUN apk update && apk upgrade && apk add --no-cache \
  bash \
  build-base \
  clang \
  git \
  nodejs-npm \
  openjdk11 \
  py3-pip \
  python3-dev \
  R \
  R-dev

# R packages
RUN Rscript -e '\
    install.packages("remotes", repos = "https://cloud.r-project.org"); \
    remotes::install_github("r-lib/styler@v1.4.1", Ncpus = 8)'

# Python packages
RUN pip3 install --upgrade pip && pip3 install \
  autoflake==1.4 \
  black==20.8b1

# Standalone binaries
RUN wget https://github.com/google/google-java-format/releases/download/google-java-format-1.9/google-java-format-1.9-all-deps.jar
RUN wget https://search.maven.org/remotecontent?filepath=com/facebook/ktfmt/0.25/ktfmt-0.25-jar-with-dependencies.jar
RUN wget https://github.com/mvdan/sh/releases/download/v3.2.0/shfmt_v3.2.0_linux_amd64 -O shfmt \
  && chmod +x shfmt
RUN wget https://releases.hashicorp.com/terraform/0.12.29/terraform_0.12.29_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip \
  && mv terraform terraform0.12
RUN wget https://releases.hashicorp.com/terraform/0.11.14/terraform_0.11.14_linux_amd64.zip -O tf.zip \
  && unzip tf.zip \
  && rm tf.zip

# Scala packages
RUN wget https://github.com/coursier/coursier/releases/download/v2.0.6/coursier -O /bin/coursier \
  && chmod +x /bin/coursier
RUN coursier bootstrap org.scalameta:scalafmt-cli_2.13:2.7.5 \
      -r sonatype:snapshots --main org.scalafmt.cli.Cli \
      --standalone \
      -o scalafmt

# NPM packages
# https://github.com/npm/npm/issues/20861#issuecomment-400786321
RUN npm config set unsafe-perm true && npm install -g \
    prettier@2.1.2 \
    svgo@1.3.2 \
    typescript@4.0.5 \
  && npm install \
    @types/node@14.14.7

# Local files
COPY . .
RUN tsc --noUnusedLocals --noUnusedParameters --strict entry.ts \
  && mv entry.js entry && chmod +x entry && touch /emptyfile
