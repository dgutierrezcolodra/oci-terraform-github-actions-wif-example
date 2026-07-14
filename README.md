# OCI Terraform Provider with Native WIF from GitHub Actions

*Technical example current on 14 July 2026*

This repository shows how a GitHub Actions workflow can call Oracle Cloud Infrastructure (OCI) through OCI IAM Workload Identity Federation (WIF). It uses the native `WorkloadIdentityFederation` authentication added in OCI Terraform provider 8.22.0. No OCI user API key, browser login, generated OCI configuration file, or external UPST wrapper is required.

## What changed in provider 8.22.0

The original version of this repository used provider 7.29 and a Python wrapper that created an RSA key, exchanged the GitHub JWT for an OCI UPST, and configured Terraform with `auth = "SecurityToken"`.

Provider 8.22.0 now performs those operations itself:

1. Terraform reads the GitHub OIDC JWT from a protected file.
2. The provider generates an ephemeral RSA key pair.
3. The provider exchanges the JWT for an OCI UPST.
4. The provider signs OCI API requests with the matching private key.
5. The provider renews the UPST and key together when required.

The small local action in `github-oidc-token/` only obtains the GitHub JWT and writes it atomically. It never creates OCI credentials.

## Architecture

```mermaid
flowchart LR
    A[GitHub Actions]
    B[GitHub OIDC endpoint]
    C[JWT file]
    D[OCI Terraform provider 8.22]
    E[OCI Identity Domain]
    F[OCI resources]

    A -->|Requests JWT| B
    B -->|Short-lived JWT| C
    C -->|Source identity| D
    D -->|JWT plus ephemeral public key| E
    E -->|OCI UPST| D
    D -->|Signed OCI API calls| F
```

## Prerequisites

Complete the one-time OCI configuration in [SETUP.md](./SETUP.md). You need:

- An OCI Identity Domain service user and least-privilege IAM policy.
- An OCI Identity Domain confidential application for token exchange.
- One active GitHub Identity Propagation Trust with exact audience and subject restrictions.
- A GitHub Actions workflow with `id-token: write` permission.
- OCI Terraform provider 8.22.0 or later in the 8.x series.

## GitHub configuration

Create these repository secrets:

| Secret | Purpose |
|---|---|
| `OCI_WIF_CLIENT_ID` | Client ID of the OCI token-exchange application |
| `OCI_WIF_CLIENT_SECRET` | Client secret of the OCI token-exchange application |
| `DOMAIN_BASE_URL` | OCI Identity Domain URL |
| `OCI_REGION` | OCI region, for example `eu-madrid-1` |
| `COMPARTMENT_ID` | Target compartment OCID |

For migration compatibility, the workflows also accept the original combined `OIDC_CLIENT_IDENTIFIER` secret in `client_id:client_secret` format. The separate `OCI_WIF_*` secrets take precedence.

The tenancy OCID is not required by the provider's WIF configuration. The provider obtains the principal and tenancy context from the OCI token.

## Terraform configuration

```hcl
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 8.22.0, < 9.0.0"
    }
  }
}

provider "oci" {
  auth   = "WorkloadIdentityFederation"
  region = var.oci_region
}
```

The workflows supply the remaining configuration through environment variables:

```text
OCI_WORKLOAD_IDENTITY_TOKEN_PATH
OCI_TOKEN_EXCHANGE_DOMAIN_URL
OCI_TOKEN_EXCHANGE_AUTH=OAuthClientCredentials
OCI_TOKEN_EXCHANGE_CLIENT_ID
OCI_TOKEN_EXCHANGE_CLIENT_SECRET
OCI_TOKEN_EXCHANGE_REQUESTED_TOKEN_TYPE=urn:oci:token-type:oci-upst
OCI_TOKEN_EXCHANGE_SUBJECT_TOKEN_TYPE=jwt
```

## Run the example

1. Fork the repository and complete [SETUP.md](./SETUP.md).
2. Add the GitHub secrets listed above.
3. Open **Actions** and select **Demo Terraform Apply (Standard)**.
4. Run `plan` first.
5. Run `apply` to create the private validation bucket.
6. Run `destroy` when the test is complete.

## Long-running Terraform operations

The OCI provider automatically renews its OCI UPST, but it cannot call GitHub to replace an expired source JWT. For a long Terraform process, the local action can refresh only the GitHub JWT file:

```yaml
- name: Create refreshable GitHub OIDC token file
  uses: ./github-oidc-token
  with:
    audience: https://cloud.oracle.com
    enable_token_refresh: true
    refresh_interval_minutes: 5
```

The provider rereads this file when it needs another OCI token exchange. It continues to own the OCI UPST and proof-of-possession key, so they cannot become mismatched.

The **Demo Terraform Token Refresh** workflow defaults to a two-minute smoke test. Set `wait_duration` to `65m` to exercise a complete OCI UPST renewal. The longer test consumes a GitHub runner for more than one hour.

## Repository structure

```text
.
├── .github/workflows/
│   ├── demo-terraform-apply.yml
│   └── demo-terraform-token-refresh.yml
├── examples/long-running-refresh/
├── github-oidc-token/
│   ├── action.yml
│   └── main.py
├── terraform/
├── tests/
├── README.md
└── SETUP.md
```

## Security properties

- The trust must match the exact GitHub issuer, audience, and repository subject.
- Do not use `sub eq *` in production.
- The runtime OAuth application must not have Identity Domain Administrator privileges.
- The JWT file is written atomically with mode `0600` under the runner temporary directory.
- The workflow never writes an OCI UPST, OCI private key, or client secret to logs.
- Use GitHub environments and environment protection rules for production deployments.
- Give the service user only the OCI permissions required by the Terraform module.

## References

- [OCI Terraform provider 8.22.0 changelog](https://github.com/oracle/terraform-provider-oci/blob/v8.22.0/CHANGELOG.md)
- [OCI provider generic WIF implementation](https://github.com/oracle/terraform-provider-oci/blob/v8.22.0/internal/provider/workload_identity_federation.go)
- [OCI JWT-to-UPST exchange](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm)
- [GitHub OIDC token documentation](https://docs.github.com/en/actions/concepts/security/openid-connect)

## License

Copyright (c) 2025 Oracle and/or its affiliates. Licensed under the Universal Permissive License v1.0.
