# Extended Terraform WIF demo

This GitHub Actions demo checks source-JWT refresh during one long Terraform
process. It reads the OCI namespace, waits, and reads it again. It creates no
OCI resource.

The module needs Terraform `>= 1.5.0`. Its lockfile selects OCI provider 8.26.0.
The provider owns the OCI token and key. The refresh action changes only the
GitHub JWT file.

## Run in GitHub Actions

Complete [SETUP.md](../../../SETUP.md), then run **Demo Terraform Token
Refresh** from `main`.

- Use `120s` for a quick test.
- Use `65m` for the full provider-renewal test.

The workflow fails if the source JWT file is not refreshed during the run.

## Local check

```bash
terraform -chdir=examples/terraform/extended-runtime init -backend=false
terraform -chdir=examples/terraform/extended-runtime validate
```

The related Ansible example uses a separate task-boundary adapter. See
[Ansible extended runtime](../../ansible/extended-runtime/README.md).
