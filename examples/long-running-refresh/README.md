# Long-running native WIF example

This module performs an OCI read, waits, and performs another OCI read in the same Terraform process.

OCI provider 8.22.0 owns the OCI UPST and ephemeral RSA key. The local GitHub action refreshes only `OCI_WORKLOAD_IDENTITY_TOKEN_PATH`, using atomic replacement. When the provider needs a new UPST, it rereads the current GitHub JWT and rotates the OCI token and key together.

Run the **Demo Terraform Token Refresh** workflow. Its `wait_duration` input defaults to `120s`, which confirms that the source JWT file is refreshed while Terraform is active. Use `65m` for a full end-to-end UPST renewal test.

No OCI resources are created by this example. The `time_sleep` resource exists only to keep the Terraform process active between the two OCI data-source calls.
