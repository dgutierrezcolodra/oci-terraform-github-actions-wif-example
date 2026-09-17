# Standard Terraform WIF demo

This GitHub Actions demo checks OCI WIF through the [OCI Landing Zones
Orchestrator](https://github.com/oci-landing-zones/terraform-oci-modules-orchestrator).
The workflow runs the unmodified v2.1.3 upstream checkout as Terraform's root
module. It does not wrap the Orchestrator as a child module.

The workflow copies `orchestrator.lock.hcl` into its temporary upstream root,
which selects OCI provider 8.29.0. It creates the Object Storage configuration
only in `RUNNER_TEMP` with mode 0600. Terraform retains native provider WIF and
does not use an OCI API key, OCI config file, or OCI security token.

To keep the one-shot source token current without adding a background process, the workflow requests a fresh GitHub OIDC JWT immediately before each separate Terraform process that calls OCI: `plan`, optional `apply`, and optional `destroy`. This standard demo does not use the background refresh daemon because the bucket operation is intentionally short. Use the extended-runtime example when one Terraform process may run long enough to require source-JWT refresh.

## Run in GitHub Actions

Complete [SETUP.md](../../../SETUP.md), add the repository secrets, and run
**Demo Terraform Apply (Standard)** from `main`.

- Select `plan` for the normal WIF check. It does not create a bucket.
- Select `apply-and-destroy` for the full test. It creates one private bucket
  and removes it in the same job.

The apply-and-destroy path stores Terraform state only on the temporary runner. This local state is ephemeral and is removed during the always-run cleanup. If destroy cannot start or fails after creating the bucket, manual OCI cleanup may be required.

The workflow reads `OCI_TENANCY`, `OCI_REGION`, and `COMPARTMENT_ID` from
repository secrets. A workflow input cannot change the target compartment.
`orchestrator-inputs.json.example` shows the temporary input shape with
placeholders only.
