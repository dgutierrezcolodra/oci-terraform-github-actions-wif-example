# Repository operating guide

This repository is a security-focused example of GitHub Actions authenticating
to Oracle Cloud Infrastructure (OCI) through Workload Identity Federation
(WIF). Keep it an example of short-lived, least-privilege credentials; do not
turn it into an API-key based deployment template.

## Component map

- `github-oidc-token/`: composite action that uses official GitHub Script to
  request a GitHub OIDC JWT once and write it atomically to a protected file.
- `github-oidc-token-refresh/`: custom extension that refreshes only the
  source JWT for the opt-in long-running Terraform workflow.
- `terraform/`: OCI bucket validation example. The provider uses native
  `WorkloadIdentityFederation` authentication.
- `examples/long-running-refresh/`: Terraform workload used to exercise source
  JWT refresh during a long operation.
- `ansible-oci-wif/`: composite action/helper for the OCI Ansible collection.
  It is intentionally a compatibility bridge, not a second WIF implementation.
- `tests/`: local-only test workspace. It must remain outside version control;
  do not add, commit, upload, or reference its files from tracked automation.
  Keep credential-handling checks deterministic and offline when running them
  locally.
- `.github/workflows/`: executable examples. Current workflow display names are
  `Demo Terraform Apply (Standard)` and `Demo Terraform Token Refresh`.
- `README.md`, `SETUP.md`, and `terraform/README.md`: user-facing architecture,
  setup, and Terraform guidance. `CONTRIBUTING.md` is the contribution policy.

## Authentication architecture

Terraform is the primary path. The OCI Terraform provider reads the GitHub JWT
from `OCI_WORKLOAD_IDENTITY_TOKEN_PATH`, generates its own ephemeral key, and
exchanges the JWT for and renews the OCI UPST. Do not generate, persist, or
inject an OCI private key or security token for Terraform.

The `oracle.oci` Ansible collection does not use that native provider flow. The
`ansible-oci-wif` helper reads the same short-lived GitHub JWT, uses the OCI
Python SDK token-exchange signer, and creates an OCI-collection-compatible
security token, matching ephemeral key, and config file for the job only. It
exports `OCI_CONFIG_FILE` and `OCI_ANSIBLE_AUTH_TYPE=security_token` through
`GITHUB_ENV`. Treat this as a narrow bridge until the collection supports WIF
natively; never reuse its generated files outside the runner/job.

## Non-negotiable security rules

- Never add OCI user API keys, long-lived private keys, UPSTs, GitHub OIDC JWTs,
  client secrets, real tenant/resource identifiers, or credential-bearing
  Terraform state to Git, artifacts, logs, documentation, issues, or PR text.
- All runtime credential material belongs below `RUNNER_TEMP`. Credential
  directories must be `0700`; token, private-key, and OCI config files must be
  written atomically with mode `0600` and deleted by job cleanup.
- Mask secrets before shell use. Do not use shell tracing while credentials are
  in scope, and never print a config file, token, JWT payload, or private key.
- Keep the Identity Propagation Trust restrictive: exact issuer, audience, and
  GitHub subject/environment. Never use `sub eq *` for a production trust.
- Runtime token-exchange clients must have no Identity Domain administrator
  role. OCI policies must be least privilege.
- `apply` and `destroy` must run only in a protected GitHub Environment (the
  intended environment is `oci-validation` unless deliberately renamed), with
  approval rules and the OCI secrets scoped to that environment. A manual input
  must not let a caller redirect an apply to an arbitrary compartment.

## GitHub configuration and workflow practice

Expected GitHub secrets are `OCI_WIF_CLIENT_ID`, `OCI_WIF_CLIENT_SECRET`,
`DOMAIN_BASE_URL`, `OCI_REGION`, and `COMPARTMENT_ID`. The legacy
`OIDC_CLIENT_IDENTIFIER` (`client_id:client_secret`) is migration-only; do not
add new use of it. `id-token: write` and `contents: read` are the normal job
permissions. Add no broader default permissions.

Keep `plan` safe to run as a validation action. `apply-and-destroy` must create
only the temporary validation resource and clean it up in the same job. Do not
upload local state or credentials as artifacts. Changes to workflows must keep
every third-party action pinned to a full immutable commit SHA; update the
inline version comment at the same time.

For the token-refresh demo, assert a real file timestamp change (not merely two
`stat` outputs) and keep the long, 65-minute provider-renewal test opt-in.

## Version and dependency policy

- Terraform: support the version declared in `terraform/versions.tf` (currently
  Terraform `>= 1.5.0`) and OCI provider `>= 8.24.0, < 9.0.0`. The minimum
  provider version must be the version that introduced native WIF support.
- OCI Python SDK: pin it in the Ansible workflow/requirements to a version
  verified with `TokenExchangeSigner`; update its test coverage when changing
  it.
- Ansible: pin the `oracle.oci` collection in `ansible/requirements.yml` when
  that integration is added. Do not silently float collection or SDK versions.
- When upstream OCI support changes, first verify whether native Ansible WIF is
  available. If it is, remove the bridge only after an end-to-end replacement
  is verified and documented.

Terraform dependency locks are committed artifacts. After changing provider
constraints, run `terraform -chdir=terraform init -backend=false -upgrade`,
inspect the resulting `.terraform.lock.hcl`, and commit it with the constraint
change. Repeat for every Terraform example that has its own lockfile. Never
hand-edit lock hashes or leave a lock version below the declared minimum.

## Local checks

Run the checks applicable to the changed files before committing:

```bash
python3 -m py_compile github-oidc-token-refresh/main.py ansible-oci-wif/main.py
terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
terraform -chdir=examples/long-running-refresh init -backend=false
terraform -chdir=examples/long-running-refresh validate
git diff --check
git status --short
```

Local tests must remain outside the repository (including under `tests/` after
it is ignored). Run them only from an untracked working directory or another
local test harness; do not add test files, test commands that require tracked
test files, test reports, or generated credentials to GitHub Actions artifacts
or Git.

`init` may download providers. Do not run `plan`, `apply`, or `destroy` locally
against a real tenancy unless that action is expressly authorized and the
environment is known to be disposable.

## Git and documentation expectations

Configure commits as `David Gutierrez Colodra
<david.gutierrez.colodra@oracle.com>`. Use Conventional Commits, for example
`fix(terraform): refresh OCI provider lockfile` or
`docs(setup): document Ansible WIF bridge`. Add a sign-off when the contribution
policy requires it. Never add automated-tool, model, or generated-by attribution
to commits, source files, or documentation.

Keep each commit focused and review `git diff --check` plus the staged diff
before committing. Do not overwrite unrelated work in a dirty worktree.

Whenever behavior changes, update the relevant user documentation in the same
change: `README.md` for architecture, workflows, prerequisites, and secrets;
`SETUP.md` for IAM/trust and GitHub configuration; `terraform/README.md` for
Terraform-specific usage; and `CONTRIBUTING.md` when validation or contributor
policy changes. Ensure names, versions, secrets, paths, and security claims
match the executable files. Use placeholders only in docs and issues.
