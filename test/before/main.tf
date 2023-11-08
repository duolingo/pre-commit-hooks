# The default AWS provider, which will take actions in the account where Atlantis is deployed (duolingo)
provider "aws" {
  region  = "us-east-1"
  version = "~> 3.0"
}

terraform {
  backend "local" {}

  required_version = "0.12.31"
}

module "test1" {
  source     = "github.com/test1"
  subservice = "same_subservice"
}

module "infra-atlantis-api" {
  source     = "github.com/test2"
  subservice = "same_subservice"
  cpu        = 1024 # 1024 equals one core
}
