# OCI Ansible WIF extended-runtime checkpoint proof

This controller-local, single-play example shows the explicit checkpoint model
for a long-running `oracle.oci` workflow. It performs only read-only Object
Storage namespace facts calls; it creates no OCI resources and accepts no
compartment or resource identifier.

The playbook accepts only two proof durations: `120` seconds for a smoke test
and `3900` seconds for the opt-in extended proof. Before the pause it records
credential-file metadata and validates a namespace call. After the pause it
runs the trusted `.github/actions/ansible-oci-wif/main.py` adapter synchronously
in the same playbook, then verifies that the source JWT advanced and that the
OCI security token and private key were atomically rematerialized. It makes a
second read-only namespace call after that checkpoint.

This is deliberately an explicit boundary, not transparent mid-module token
rotation. For a long OCI operation, use `wait: false` and a later facts or
status-task pattern: allow the first task to return, checkpoint and
rematerialize credentials, then use a subsequent task to inspect status. One
already-running Ansible module retains its in-memory signer and cannot be
updated by this playbook.

## Copy set

Copy these paths together:

- `.github/actions/github-oidc-token-refresh/`
- `.github/actions/ansible-oci-wif/`
- `examples/ansible/requirements.yml`
- `examples/ansible/extended-runtime/`
- `.github/workflows/demo-ansible-extended.yml`

Install the pinned collection from `examples/ansible/requirements.yml`. Both
the `120`-second smoke proof and `3900`-second extended proof require a
one-minute source-JWT refresh interval. Do not rely on the action's default `3`
minutes: it cannot establish the required source-JWT change during the
`120`-second checkpoint. The canonical extended workflow sets the interval
explicitly:

```yaml
- name: Create a refreshable GitHub OIDC token file
  uses: ./.github/actions/github-oidc-token-refresh
  with:
    audience: https://cloud.oracle.com
    refresh_interval_minutes: "1"
```

Run that refreshable action before this playbook so its source JWT can change
during the selected pause; keep the adapter's credential files below
`RUNNER_TEMP` and remove them in always-run job cleanup. The playbook accepts
only the repository helper at
`$GITHUB_WORKSPACE/.github/actions/ansible-oci-wif/main.py`; a caller-supplied
arbitrary helper path is rejected before execution.

For a controller-local proof, run with a supported duration and the trusted
helper path, for example:

```bash
ansible-playbook \
  --extra-vars "wif_wait_seconds=120 wif_helper_path=$GITHUB_WORKSPACE/.github/actions/ansible-oci-wif/main.py" \
  examples/ansible/extended-runtime/playbook.yml
```
