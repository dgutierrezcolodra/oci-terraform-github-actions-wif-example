# Standard Terraform WIF demo

This GitHub Actions demo checks OCI WIF with Terraform. It reads the Object
Storage namespace and plans one private bucket. Terraform uses native provider
WIF. It does not use an OCI API key, OCI config file, or OCI security token.

The module needs Terraform `>= 1.5.0`. Its lockfile selects OCI provider 8.26.0.

## Run in GitHub Actions

Complete [SETUP.md](../../../SETUP.md), add the repository secrets, and run
**Demo Terraform Apply (Standard)** from `main`.

- Select `plan` for the normal WIF check. It does not create a bucket.
- Select `apply-and-destroy` for the full test. It creates one private bucket
  and removes it in the same job.

The workflow reads the compartment from `COMPARTMENT_ID`. A workflow input
cannot change the target compartment.
