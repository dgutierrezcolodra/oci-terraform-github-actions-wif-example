# Long-Running Terraform Refresh Example

This example demonstrates the advanced path for Terraform operations that may
run longer than the initial OCI session token lifetime.

The workflow starts the local token refresh daemon, runs a Terraform apply, waits
for two minutes, and then performs another OCI API call. If the second data
source read succeeds, Terraform was able to continue after the session token file
was refreshed.

This is a small simulation of the same problem seen with long-running resources,
such as VM Cluster creation, where Terraform may keep polling OCI after the
initial token has aged.

## Workflow

Run the GitHub Actions workflow:

```text
Demo Terraform Token Refresh
```

The workflow uses:

```yaml
enable_token_refresh: true
refresh_interval_minutes: 1
```

The one-minute interval is intentionally short so the demo completes quickly. For
real Terraform jobs, use a refresh interval comfortably below the OCI session
token lifetime used by your environment.

## Terraform

The configuration does three things:

1. Reads the Object Storage namespace.
2. Waits for two minutes using the `time_sleep` provider.
3. Reads the Object Storage namespace again.

No OCI resources are created by this example.
