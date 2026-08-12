# Ansible WIF credential renewal

This example renews temporary credentials between `oracle.oci` tasks. It only
reads the Object Storage namespace and creates no OCI resource.

Use `120` seconds for a quick test or `3900` seconds for the full test. The
playbook checks the namespace before and after renewal. It also checks that the
source JWT, OCI token, and private key changed.

Renewal happens between tasks. It cannot change the signer inside a module that
is already running. For a long OCI operation, start the task asynchronously,
renew after it returns, and then check its status.

## Run in GitHub Actions

Complete [SETUP.md](../../../SETUP.md), then run **Demo Ansible WIF Credential
Renewal** from `main`. Select `smoke` for 120 seconds or `renewal-65m` for the
full test.

## Copy set

- `.github/actions/github-oidc-token-refresh/`
- `.github/actions/ansible-oci-wif/`
- `examples/ansible/requirements.yml`
- `examples/ansible/extended-runtime/`
- `.github/workflows/demo-ansible-extended.yml`

The requirements file pins `oracle.oci` to an exact Oracle Git commit. You need
`git` to install it. Galaxy signature checks are not used.

Both tests need a one-minute source-JWT refresh interval. Use this action before
the playbook:

```yaml
- name: Create a refreshable GitHub OIDC token file
  uses: ./.github/actions/github-oidc-token-refresh
  with:
    audience: https://cloud.oracle.com
    refresh_interval_minutes: "1"
```

Keep credential files below `RUNNER_TEMP` and remove them in always-run cleanup.
The playbook accepts only the repository helper at
`$GITHUB_WORKSPACE/.github/actions/ansible-oci-wif/main.py`.

For a local proof, run:

```bash
ansible-playbook \
  --extra-vars "wif_wait_seconds=120 wif_helper_path=$GITHUB_WORKSPACE/.github/actions/ansible-oci-wif/main.py" \
  examples/ansible/extended-runtime/playbook.yml
```
