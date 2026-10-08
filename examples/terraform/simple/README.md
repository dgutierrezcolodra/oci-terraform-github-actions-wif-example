# Terraform RPST bucket demo

This demo uses OCI provider-native `WorkloadIdentityFederation` authentication
to create and delete one private Object Storage bucket. Follow the
[setup runbook](../../../SETUP.md) before running it.

## Run

Open **Actions → Demo Terraform RPST Bucket → Run workflow**.

1. Select `plan` to inspect the proposed bucket without creating it.
2. Select `apply-and-destroy` to create the bucket and delete it afterward.
3. Check the raw exchange, plan, apply, and destroy outcomes in the job summary.

GitHub requires the workflow on the default branch for manual dispatch. The
runbook also describes the restricted push trigger used on this reference's
working branch.

The workflow uses Terraform **1.16.5** and OCI provider **9.8.0**. The committed
lock contains checksums for Linux AMD64 and macOS ARM64. The provider generates
its own key and exchanges a fresh GitHub JWT before each Terraform command.
The raw diagnostic exchange's token and key are separate from the provider.

The bucket is named `rpst-terraform-<run_id>` and has `NoPublicAccess`. Plans,
local state, and provider data stay under `$RUNNER_TEMP/rpst-terraform` and are
removed after the run. If destroy fails, delete the named bucket manually;
state is not retained for another run.

## Local validation

```bash
terraform fmt -check -recursive examples/terraform/simple
terraform -chdir=examples/terraform/simple init -backend=false -input=false
terraform -chdir=examples/terraform/simple validate
```

These commands need no OCI credentials. The Actions workflow initializes with
`-lockfile=readonly`.
