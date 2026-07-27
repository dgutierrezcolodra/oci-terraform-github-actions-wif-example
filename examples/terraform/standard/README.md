# Standard Terraform native OCI WIF example

This root module creates one private Object Storage bucket and validates native OCI Workload Identity Federation authentication.

Generic WIF support first appeared in OCI provider 8.22.0. This module requires
and locks provider 8.24.0 as the repository's validated baseline.
Authentication settings come from the GitHub workflow environment; no
`~/.oci/config`, OCI API key, or externally generated OCI session token is
used.

Use this generic WIF example for GitHub-hosted runners or self-hosted runners
outside OCI. Prefer Instance Principals for a runner on OCI Compute and OKE
Workload Identity for a runner pod in an enhanced OKE cluster.

## Files

- `versions.tf`: pins the supported OCI provider 8.x range.
- `provider.tf`: selects `WorkloadIdentityFederation` authentication.
- `variables.tf`: defines the compartment, region, and bucket name.
- `main.tf`: reads the namespace and creates the bucket.
- `outputs.tf`: returns information about the planned or created bucket.

## Required environment

```text
OCI_WORKLOAD_IDENTITY_TOKEN_PATH
OCI_TOKEN_EXCHANGE_DOMAIN_URL
OCI_TOKEN_EXCHANGE_AUTH=OAuthClientCredentials
OCI_TOKEN_EXCHANGE_CLIENT_ID
OCI_TOKEN_EXCHANGE_CLIENT_SECRET
OCI_TOKEN_EXCHANGE_REQUESTED_TOKEN_TYPE=urn:oci:token-type:oci-upst
OCI_TOKEN_EXCHANGE_SUBJECT_TOKEN_TYPE=jwt
```

Use `.github/workflows/demo-terraform-standard.yml` and
`.github/actions/github-oidc-token` to populate these values in GitHub Actions.
For local validation, provide a valid external JWT file and matching OCI
Identity Propagation Trust before running `terraform plan`.

From the repository root, initialize and validate this example with:

```bash
terraform -chdir=examples/terraform/standard init -backend=false
terraform -chdir=examples/terraform/standard validate
```

The standard and extended Terraform workflows remove their protected source-JWT
directory in an independent always-run cleanup. The extended workflow also
validates and stops the exact refresh daemon recorded by
`.github/actions/github-oidc-token-refresh` before removing that directory.

The checked-in trust example matches
`repo:<owner>/<repository>:ref:refs/heads/main`. When copying it, replace the
owner, repository, and protected branch consistently. The workflow intentionally
declares no GitHub environment, preserving the default branch-ref subject. It
passes `CLIENT_SECRET` only to the Terraform provider steps and does not persist
that secret through `GITHUB_ENV`.
