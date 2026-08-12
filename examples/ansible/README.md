# Ansible WIF examples for GitHub Actions

These GitHub Actions examples show Ansible using OCI WIF. The Ansible bridge is
needed because `oracle.oci` does not use the Terraform provider WIF
configuration. It exchanges the GitHub JWT for a short-lived OCI token, key,
and config below `RUNNER_TEMP`; the workflow removes these files at the end of
the job. The one-shot OIDC action is shared with standard Terraform. The refresh
action is shared with both extended examples.

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
