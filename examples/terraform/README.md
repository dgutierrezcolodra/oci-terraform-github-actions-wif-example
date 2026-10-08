# Terraform WIF examples for GitHub Actions

These GitHub Actions examples show Terraform using native OCI provider WIF.
The provider reads the GitHub JWT from `OCI_WORKLOAD_IDENTITY_TOKEN_PATH` and
creates and renews its own OCI token and key. Do not create an OCI private key
or security token for Terraform. The one-shot OIDC action is shared with
standard Ansible.

The standard example needs Terraform `>= 1.5.0` and OCI provider `>= 8.29.0, < 9.0.0`.
Its committed lock selects provider 8.29.0. The separate RPST demo locks provider 9.8.0.

## Examples

- [standard](./standard/README.md): checks WIF through the OCI Landing Zones
  Orchestrator and can create and remove one validation bucket.
- [RPST bucket demo](../../spike/rpst/README.md): the throwaway experiment
  creates and deletes one private bucket using RPST on `spike/rpst-terraform`.

## Run a demo

From `main`, open **Demo Terraform Apply (Standard)** in GitHub Actions:

1. Select `plan` to check WIF without creating a bucket.
2. Select `apply-and-destroy` for the full test. It removes the bucket.

Set these repository secrets: `CLIENT_ID`, `CLIENT_SECRET`, `DOMAIN_BASE_URL`,
`OCI_REGION`, `OCI_TENANCY`, and `COMPARTMENT_ID`. Read
[SETUP.md](../../SETUP.md) for the OCI trust and IAM policy. The trust must match
`repo:<owner>/<repository>:ref:refs/heads/main`.
