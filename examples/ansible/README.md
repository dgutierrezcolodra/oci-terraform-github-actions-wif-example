# Ansible WIF examples for GitHub Actions

Terraform has native WIF support in the OCI provider. The `oracle.oci`
collection does not have this support, so Ansible needs the
`.github/actions/ansible-oci-wif` adapter. The adapter exchanges the GitHub JWT
for a short-lived OCI security token, matching private key, and config below
`RUNNER_TEMP`. It exports their paths for the current job, and the workflow
removes the files at the end. The one-shot OIDC action is shared with standard
Terraform. The refresh action is shared with both extended examples.

[`requirements.yml`](./requirements.yml) pins `oracle.oci` 5.6.0 to an Oracle
Git commit. Installation needs `git` and does not use Galaxy signature checks.

## Examples

- [namespace-validation](./namespace-validation/README.md): reads the Object
  Storage namespace through WIF.
- [extended-runtime](./extended-runtime/README.md): renews credentials between
  module tasks.

## Run a demo

Run **Demo Ansible WIF Namespace Validation** from `main` for the read-only
check. Run **Demo Ansible WIF Credential Renewal** with `smoke` for 120 seconds
or `renewal-65m` for the full test.

Both workflows need `CLIENT_ID`, `CLIENT_SECRET`, `DOMAIN_BASE_URL`, and
`OCI_REGION`. Read [SETUP.md](../../SETUP.md) first. The workflow must run from
`repo:<owner>/<repository>:ref:refs/heads/main`.
