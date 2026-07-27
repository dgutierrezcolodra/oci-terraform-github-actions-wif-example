# Extended-runtime native WIF example

This module performs an OCI read, waits, and performs another OCI read in the same Terraform process.

The repository requires, locks, and validates OCI provider 8.24.0 for this
example. The provider owns the OCI UPST and ephemeral RSA key. The
`.github/actions/github-oidc-token-refresh` action refreshes only
`OCI_WORKLOAD_IDENTITY_TOKEN_PATH`, using atomic replacement. When the provider
needs a new UPST, it rereads the current GitHub JWT and rotates the OCI token
and key together.

Run the **Demo Terraform Token Refresh** workflow. Its `wait_duration` input defaults to `120s`, which confirms that the source JWT file is refreshed while Terraform is active. Use `65m` for a full end-to-end UPST renewal test.

From the repository root, initialize and validate this example with:

```bash
terraform -chdir=examples/terraform/extended-runtime init -backend=false
terraform -chdir=examples/terraform/extended-runtime validate
```

No OCI resources are created by this example. The `time_sleep` resource exists only to keep the Terraform process active between the two OCI data-source calls.

This source-JWT refresh flow is the validated extended Terraform path.
Long-running Ansible uses the separate task-boundary adapter documented in
`examples/ansible/extended-runtime/README.md`.
