# Contributing to this repository

We welcome contributions to this example repository. Contributions can include
bug fixes, documentation improvements, Terraform example updates, GitHub Actions
workflow improvements, and security hardening.

This repository demonstrates GitHub Actions OIDC to OCI IAM Workload Identity
Federation using the OCI Terraform provider's native
`WorkloadIdentityFederation` authentication. Please keep changes focused on
that purpose.

## Table of Contents

- [Opening issues](#opening-issues)
- [Security issues](#security-issues)
- [Prerequisites for contributions](#prerequisites-for-contributions)
- [Commit messages](#commit-messages)
- [Development checks](#development-checks)
- [Pull request process](#pull-request-process)
- [Documentation standards](#documentation-standards)
- [Code of conduct](#code-of-conduct)

## Opening issues

Use GitHub issues to report bugs, request enhancements, or discuss proposed
changes before opening a larger pull request.

For bug reports, include:

- What you expected to happen
- What actually happened
- The workflow, Terraform command, or setup step involved
- Sanitized logs or error messages
- Your OCI region, Terraform version, and relevant GitHub Actions runner details

Do not include secrets, access tokens, private keys, OCI session tokens, client
secrets, real OCIDs that identify private resources, or downloaded token files.

## Security issues

If you believe you found a security vulnerability, do not open a public GitHub
issue with exploit details or credentials.

Use GitHub private vulnerability reporting if it is enabled for the repository,
or contact a maintainer privately. Keep any reproduction minimal and remove all
real credentials, tenancy identifiers, tokens, and private keys.

## Prerequisites for contributions

Before we can review or accept source code or documentation contributions, you
may need to digitally sign the
[Oracle Contributor Agreement (OCA)](https://oca.opensource.oracle.com/) using
the OCA Signing Service. This only needs to be done once; if you have already
signed it for another Oracle repository or project, you do not need to sign it
again.

All commit messages should include the following line using the same name and
email address you used to sign the OCA:

```text
Signed-off-by: Your Name <you@example.org>
```

You can add this automatically when committing:

```bash
git commit --signoff
```

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) where practical.

Format:

```text
<type>(<scope>): <short description>
```

Common types:

- `feat`: new behavior or example capability
- `fix`: bug fix
- `docs`: documentation-only change
- `test`: test or validation change
- `ci`: GitHub Actions workflow change
- `chore`: maintenance change

Useful scopes for this repository include:

- `action`
- `setup`
- `terraform`
- `examples`
- `workflows`
- `docs`

Examples:

```text
docs(setup): clarify identity domain token setup
fix(action): handle GitHub OIDC HTTP errors
ci(workflows): add Terraform refresh demo
```

## Development checks

Run the checks that match the files you changed.

### Python action

```bash
python3 -m py_compile github-oidc-token/main.py tests/test_github_oidc_token.py
python3 -m unittest discover -s tests -v
```

### Terraform examples

For formatting:

```bash
terraform fmt -check -recursive
```

For validation, run from each Terraform example directory after initializing
providers:

```bash
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

If you change `examples/long-running-refresh/`, validate that directory as well:

```bash
terraform -chdir=examples/long-running-refresh init -backend=false
terraform -chdir=examples/long-running-refresh validate
```

### Documentation

For documentation-only changes:

```bash
git diff --check
```

Also check that links, workflow names, secrets, and file paths match the current
repository contents.

## Pull request process

1. Open or reference an issue for the change unless it is a small documentation
   fix.
2. Fork the repository and create a focused branch.
3. Keep pull requests small enough to review.
4. Update `README.md`, `SETUP.md`, or `terraform/README.md` when behavior,
   inputs, secrets, setup steps, or workflow names change.
5. Run the relevant checks from [Development checks](#development-checks).
6. Explain what changed and how reviewers can validate it.
7. Include `Signed-off-by` in each commit when required.

## Documentation standards

This repository is intended to be copied and adapted by users. Documentation
must be precise and safe by default.

- Prefer official OCI and GitHub documentation links for setup or security
  claims.
- Do not document unverified token lifetime behavior as a guarantee.
- Do not recommend storing OCI API keys in GitHub for this flow.
- Do not add workflows that upload OIDC tokens, OCI security tokens, private
  keys, Terraform state, or token files as artifacts.
- Use placeholders such as `<DOMAIN_URL>`, `<IDA_ACCESS_TOKEN>`, and
  `ocid1.tenancy.oc1..aaaaaaa...` instead of real values.
- Keep examples aligned with the actual workflow names and action inputs in
  this repository.

## Code of conduct

Be respectful and constructive. Focus reviews on correctness, security,
maintainability, and whether the change helps users understand or safely run the
example.
