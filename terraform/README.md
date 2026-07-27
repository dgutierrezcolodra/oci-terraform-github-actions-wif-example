# Terraform native OCI WIF example

This root module creates one private Object Storage bucket and validates native OCI Workload Identity Federation authentication.

The module requires OCI provider 8.24.0 or later. Authentication settings come from the GitHub workflow environment; no `~/.oci/config`, OCI API key, or externally generated OCI session token is used.

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

Use the included GitHub workflow to populate these values. For local validation, provide a valid external JWT file and matching OCI Identity Propagation Trust before running `terraform plan`.

The standard and long-running example workflows remove their protected source-JWT directory in an independent always-run cleanup. The long-running workflow also validates and stops the exact refresh daemon recorded by `github-oidc-token-refresh/` before removing that directory.

The existing trust matches `repo:<owner>/<repository>:ref:refs/heads/main`, so real WIF executions must run from `main`. The workflows use repository Actions secrets and intentionally declare no GitHub environment, preserving the default ref subject.
