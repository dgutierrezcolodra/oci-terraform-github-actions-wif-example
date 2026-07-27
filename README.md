# OCI Workload Identity Federation references for GitHub Actions

*Technical example current on 27 July 2026*

This repository provides copyable GitHub Actions references for Oracle Cloud
Infrastructure (OCI) Workload Identity Federation (WIF). Terraform uses the
native `WorkloadIdentityFederation` authentication introduced in OCI Terraform
provider 8.24.0. No OCI user API key, browser login, generated OCI
configuration file, or external UPST wrapper is required for Terraform.

## Choose what to copy

Copy only the row that matches the workload you are adopting. The workflow
files are executable references; adapt their names and triggers to your
repository while retaining their credential cleanup and least-privilege
permissions.

| Adoption | Copy these paths | Notes |
|---|---|---|
| Standard Terraform | `.github/actions/github-oidc-token`, `examples/terraform/standard`, and `.github/workflows/demo-terraform-standard.yml` | One-shot GitHub OIDC source JWT with native Terraform WIF. |
| Extended Terraform | `.github/actions/github-oidc-token-refresh`, `examples/terraform/extended-runtime`, and `.github/workflows/demo-terraform-extended.yml` | Refreshes only the GitHub source JWT for a Terraform process that needs it. |
| Standard Ansible | `.github/actions/github-oidc-token`, `.github/actions/ansible-oci-wif`, `examples/ansible/namespace-validation`, and `.github/workflows/demo-ansible-standard.yml` | The adapter is needed only by the `oracle.oci` collection. |
| Terraform and Ansible | All three action directories, both Terraform example directories, the Ansible example directory, and the matching workflow references | Combine only the components your jobs use. |

The one-shot OIDC action is shared by standard Terraform and standard Ansible.
The refresh action replaces only the source JWT and is currently certified for
extended Terraform. Long-running Ansible is not transparently supported or
claimed. The Ansible adapter is a narrow compatibility bridge for
`oracle.oci`, not a second general WIF implementation.

Each publishable action would be extracted to its own repository before any
future GitHub Marketplace publication. This reference repository intentionally
keeps the actions together so customers can copy the small set they need.

## Native WIF provider baseline

OCI Terraform provider 8.24.0 performs the native flow:

1. Terraform reads the GitHub OIDC JWT from a protected file.
2. The provider generates an ephemeral RSA key pair.
3. The provider exchanges the JWT for an OCI UPST.
4. The provider signs OCI API requests with the matching private key.
5. The provider renews the UPST and key together when required.

The shared one-shot action uses official
`actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3` (`v9.0.0`)
to obtain the GitHub JWT. It writes the JWT atomically below `RUNNER_TEMP`,
exports only its path, does not refresh it, and never creates OCI credentials.

```yaml
- name: Create GitHub OIDC token file
  uses: ./.github/actions/github-oidc-token
  with:
    audience: https://cloud.oracle.com
```

## Prerequisites and GitHub configuration

Complete the one-time OCI configuration in [SETUP.md](./SETUP.md). You need an
OCI Identity Domain service user and least-privilege IAM policy, a confidential
token-exchange application, one active trust with exact audience and subject
restrictions, and `id-token: write` for the GitHub job.

Create these repository Actions secrets:

| Secret | Purpose |
|---|---|
| `CLIENT_ID` | Client ID of the OCI token-exchange application |
| `CLIENT_SECRET` | Client secret of the OCI token-exchange application |
| `DOMAIN_BASE_URL` | OCI Identity Domain URL |
| `OCI_REGION` | OCI region, for example `eu-madrid-1` |
| `COMPARTMENT_ID` | Repository Actions secret for the target compartment OCID |

These are the only repository secrets required by these references. Terraform
jobs read `COMPARTMENT_ID` only from the `secrets` context, so a workflow input
cannot redirect an apply to another compartment.

The existing trust authorizes the default GitHub subject
`repo:<owner>/<repository>:ref:refs/heads/main`. Real WIF executions must run
from `main`. Jobs intentionally declare no GitHub environment and do not
customize the OIDC subject, because either changes the subject and stops this
trust from matching. `apply-and-destroy` remains an explicit manual workflow
choice using the fixed repository secret for its compartment.

## Terraform configuration

```hcl
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 8.24.0, < 9.0.0"
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

## Extended Terraform operations

The OCI provider automatically renews its OCI UPST but cannot request a new
GitHub source JWT. The extended Terraform reference uses the refresh action to
replace only that source file:

```yaml
- name: Create refreshable GitHub OIDC token file
  uses: ./.github/actions/github-oidc-token-refresh
  with:
    audience: https://cloud.oracle.com
    refresh_interval_minutes: 1
```

The provider rereads the file when it needs another OCI token exchange and
continues to own the OCI UPST and proof-of-possession key. GitHub OIDC JWTs
have an observed lifetime of roughly five minutes; the refresh action therefore
accepts only one- through four-minute intervals.

**Demo Terraform Token Refresh** defaults to a 120-second smoke test and fails
unless the source-JWT file modification time has strictly increased. Set
`wait_duration` to `65m` only for the opt-in full OCI UPST-renewal proof. Its
always-run cleanup validates and stops the recorded daemon before deleting the
credential directory.

## Ansible namespace validation

**Demo Ansible WIF Namespace Validation** is a manual, read-only Object Storage
namespace check from `main`. It uses `CLIENT_ID`, `CLIENT_SECRET`,
`DOMAIN_BASE_URL`, and `OCI_REGION`.

The `oracle.oci` collection does not consume the native Terraform provider WIF
configuration directly. The `.github/actions/ansible-oci-wif` bridge exchanges
the same one-shot GitHub OIDC token and writes short-lived security-token
credentials only below `RUNNER_TEMP` for the job. The workflow removes those
credentials in always-run cleanup. It does not use an OCI API-key fallback.

## Repository structure

```text
.
├── .github/
│   ├── actions/
│   │   ├── ansible-oci-wif/
│   │   ├── github-oidc-token/
│   │   └── github-oidc-token-refresh/
│   └── workflows/
│       ├── demo-ansible-standard.yml
│       ├── demo-terraform-extended.yml
│       └── demo-terraform-standard.yml
├── examples/
│   ├── ansible/namespace-validation/
│   └── terraform/
│       ├── extended-runtime/
│       └── standard/
├── README.md
└── SETUP.md
```

## Security properties

- The trust must match the exact GitHub issuer, audience, and repository subject.
- Do not use `sub eq *` in production.
- The runtime OAuth application must not have Identity Domain Administrator privileges.
- JWT, private-key, and OCI configuration files are written atomically with mode `0600` below a `0700` runner-temporary directory.
- Workflows remove credential directories in independent always-run cleanup steps.
- Workflows never write an OCI UPST, OCI private key, client secret, or JWT to logs.
- Give the service user only the OCI permissions required by the copied workload.

## References

- [OCI Terraform provider 8.24.0 changelog](https://github.com/oracle/terraform-provider-oci/blob/v8.24.0/CHANGELOG.md)
- [OCI provider generic WIF implementation](https://github.com/oracle/terraform-provider-oci/blob/v8.24.0/internal/provider/workload_identity_federation.go)
- [OCI JWT-to-UPST exchange](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm)
- [GitHub OIDC token documentation](https://docs.github.com/en/actions/concepts/security/openid-connect)

## License

Copyright (c) 2026 Oracle and/or its affiliates. Licensed under the Universal
Permissive License v1.0.
