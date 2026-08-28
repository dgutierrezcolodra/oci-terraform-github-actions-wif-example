# Standard Terraform WIF demo

This GitHub Actions demo checks OCI WIF through the [OCI Landing Zones
Orchestrator](https://github.com/oci-landing-zones/terraform-oci-modules-orchestrator).
The workflow runs the unmodified v2.1.3 upstream checkout as Terraform's root
module, pinned to commit `34202e837e9df015ddaaa4fce0ab62bb6e3883de`. It does
not wrap the Orchestrator as a child module.

The workflow copies `orchestrator.lock.hcl` into its temporary upstream root,
which selects OCI provider 8.29.0. It creates the Object Storage configuration
only in `RUNNER_TEMP` with mode 0600. Terraform retains native provider WIF and
does not use an OCI API key, OCI config file, or OCI security token.

## Run in GitHub Actions

Complete [SETUP.md](../../../SETUP.md), add the repository secrets, and run
**Demo Terraform Apply (Standard)** from `main`.

- Select `plan` for the normal WIF check. It does not create a bucket.
- Select `apply-and-destroy` for the full test. It creates one private bucket
  and removes it in the same job.

The workflow reads `TENANCY_OCID`, `OCI_REGION`, and `COMPARTMENT_ID` from
repository secrets. A workflow input cannot change the target compartment.
`orchestrator-inputs.json.example` shows the temporary input shape with
placeholders only.
