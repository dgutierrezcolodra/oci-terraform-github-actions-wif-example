# Repository operating guide

This repository is a security-focused example of GitHub Actions authenticating
to Oracle Cloud Infrastructure (OCI) through Workload Identity Federation
(WIF). Keep it an example of short-lived, least-privilege credentials; do not
turn it into an API-key based deployment template.

## Component map

- `.github/actions/github-oidc-token/`: composite action that uses official
  GitHub Script to request a GitHub OIDC JWT once and write it atomically to a
  protected file.
- `.github/actions/github-oidc-token-refresh/`: custom extension that refreshes
  only the source JWT for the opt-in extended Terraform and Ansible workflows.
- `examples/terraform/standard/`: OCI bucket validation example. The provider
  uses native `WorkloadIdentityFederation` authentication.
- `examples/terraform/extended-runtime/`: Terraform workload used to exercise
  source-JWT refresh during a long operation.
- `.github/actions/ansible-oci-wif/`: composite action/helper for the OCI
  Ansible collection. It is intentionally a compatibility bridge, not a second
  WIF implementation.
- `examples/ansible/requirements.yml`: shared pinned collection requirements.
- `examples/ansible/namespace-validation/`: read-only Ansible Object Storage
  namespace validation.
- `examples/ansible/extended-runtime/`: controller-local proof that renews
  temporary Ansible credentials between module tasks.
- `tests/`: local-only test workspace. It must remain outside version control;
  do not add, commit, upload, or reference its files from tracked automation.
  Keep credential-handling checks deterministic and offline when running them
  locally.
- `.github/workflows/`: executable examples. Current workflow display names are
  `Demo Terraform Apply (Standard)`, `Demo Terraform Token Refresh`, and
  `Demo Ansible WIF Namespace Validation`, and `Demo Ansible WIF Credential
  Renewal` (`demo-ansible-extended.yml`).
- `README.md`, `SETUP.md`, `examples/terraform/standard/README.md`, and
  `examples/terraform/extended-runtime/README.md`: user-facing architecture,
  setup, and Terraform guidance. `CONTRIBUTING.md` is the contribution policy.

## Authentication architecture

Terraform is the primary path. The OCI Terraform provider reads the GitHub JWT
from `OCI_WORKLOAD_IDENTITY_TOKEN_PATH`, generates its own ephemeral key, and
exchanges the JWT for and renews the OCI UPST. Do not generate, persist, or
inject an OCI private key or security token for Terraform.

Use this generic WIF pattern for GitHub-hosted runners or self-hosted runners
outside OCI. Prefer Instance Principals for a runner on OCI Compute and OKE
Workload Identity for a runner pod in an enhanced OKE cluster.

The `oracle.oci` Ansible collection does not use that native provider flow. The
`ansible-oci-wif` helper reads the same short-lived GitHub JWT, uses the OCI
Python SDK token-exchange signer, and creates an OCI-collection-compatible
security token, matching ephemeral key, and config file for the job only. It
exports `OCI_CONFIG_FILE`, `OCI_ANSIBLE_AUTH_TYPE=security_token`,
`OCI_ANSIBLE_SECURITY_TOKEN_FILE`, and `OCI_ANSIBLE_PRIVATE_KEY_FILE` through
`GITHUB_ENV`, with protected config/token/key path action outputs. Between
module tasks it can replace the OCI UPST and matching private key together;
later tasks load the renewed files. An already-running module retains its
in-memory signer. Treat this as a narrow, controller-local adapter until the
collection supports WIF natively; never reuse or distribute its generated files
outside the runner/job.

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
  the existing `repo:<owner>/<repository>:ref:refs/heads/main` subject. Do not
  add a job-level GitHub environment or OIDC subject customization; either
  would stop the existing trust from matching. Never use `sub eq *`.
- Runtime token-exchange clients must have no Identity Domain administrator
  role. OCI policies must be least privilege.
- Real WIF executions must run from `main` to match the trust. `apply` and
  `destroy` remain manual-only operations, and the OCI values are repository
  Actions secrets. A manual input must not let a caller redirect an apply to an
  arbitrary compartment.

## GitHub configuration and workflow practice

Expected repository Actions secrets are `CLIENT_ID`, `CLIENT_SECRET`,
`DOMAIN_BASE_URL`, `OCI_REGION`, and `COMPARTMENT_ID`. `id-token: write` and
`contents: read` are the normal job permissions. Add no broader default
permissions.

Keep `plan` safe to run as a validation action. `apply-and-destroy` must create
only the temporary validation resource and clean it up in the same job. Do not
upload local state or credentials as artifacts. Changes to workflows must keep
every third-party action pinned to a full immutable commit SHA; update the
inline version comment at the same time.

The standard Terraform push trigger must cover only its example, its OIDC
action, and its own workflow file. Do not let unrelated workflow changes start
a real OCI plan. Pass `CLIENT_SECRET` only to steps that call the configured
provider; never persist it through `GITHUB_ENV`.

For the token-refresh demo, assert a real file timestamp change (not merely two
`stat` outputs) and keep the long, 65-minute provider-renewal test opt-in.

## Version and dependency policy

- Terraform: support the version declared in
  `examples/terraform/standard/versions.tf` (currently Terraform `>= 1.5.0`)
  and OCI provider `>= 8.24.0, < 9.0.0`. Generic WIF first appeared in 8.22.0,
  but 8.24.0 is this repository's validated minimum and locked baseline. Do
  not lower or raise that baseline without end-to-end validation.
- OCI Python SDK: pin it in the Ansible workflow to a version verified with
  `TokenExchangeSigner`; update its test coverage when changing it.
- Ansible: pin the `oracle.oci` collection in
  `examples/ansible/requirements.yml`. Do not silently float collection or SDK
  versions. Version 5.6.0 is installed from an exact Git commit because it is
  not published to Galaxy; document that this requires `git` and does not use
  Galaxy signature verification.
- When upstream OCI support changes, first verify whether native Ansible WIF is
  available. If it is, remove the bridge only after an end-to-end replacement
  is verified and documented.

Terraform dependency locks are committed artifacts. After changing provider
constraints, run
`terraform -chdir=examples/terraform/standard init -backend=false -upgrade`,
inspect the resulting `.terraform.lock.hcl`, and commit it with the constraint
change. Repeat for every Terraform example that has its own lockfile. Never
hand-edit lock hashes or leave a lock version below the declared minimum.

## Local checks

Run the checks applicable to the changed files before committing:

```bash
python3 -m py_compile \
  .github/actions/github-oidc-token-refresh/main.py \
  .github/actions/ansible-oci-wif/main.py
terraform fmt -check -recursive
terraform -chdir=examples/terraform/standard init -backend=false
terraform -chdir=examples/terraform/standard validate
terraform -chdir=examples/terraform/extended-runtime init -backend=false
terraform -chdir=examples/terraform/extended-runtime validate
ansible-playbook --syntax-check examples/ansible/namespace-validation/playbook.yml
ansible-playbook --syntax-check examples/ansible/extended-runtime/playbook.yml
PYTHONPYCACHEPREFIX=/private/tmp/oci-wif-ansible-extended-pycache \
  python3 -m unittest -v tests.test_repository_layout tests.test_ansible_extended_runtime
git diff --check
git status --short
```

Local tests must remain outside the repository (including under `tests/` after
it is ignored). Run them only from an untracked working directory or another
local test harness; do not add test files, test commands that require tracked
test files, test reports, or generated credentials to GitHub Actions artifacts
or Git. Never track `.superpowers/` or `tests/`. The 65-minute Ansible proof is
manual and opt-in; it remains controller-local and renews credentials between
tasks rather than inside a running OCI module.

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
`SETUP.md` for IAM/trust and GitHub configuration; the Terraform example
READMEs for Terraform-specific usage; and `CONTRIBUTING.md` when validation or
contributor policy changes. Ensure names, versions, secrets, paths, and
security claims match the executable files. Use placeholders only in docs and
issues.
