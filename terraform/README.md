## Terraform Example - OCI Provider with OIDC Session Token

This folder contains a minimal Terraform configuration used to validate that the OCI provider can authenticate using a short‑lived **session token** created via OIDC token exchange.

The configuration creates a single private Object Storage bucket with helpful outputs so you can confirm that authentication works end‑to‑end.

### Files

- `provider.tf` – Configures the OCI provider to use `auth = "SecurityToken"` and a CLI profile.
- `variables.tf` – Defines input variables such as `compartment_id`, `oci_region`, `oci_profile`, and `bucket_name`.
- `main.tf` – Reads the Object Storage namespace and creates the validation bucket.
- `outputs.tf` – Exposes bucket name, namespace, URL, ID, and a human‑readable validation status message.
- `terraform.tfvars.example` – Example values you can copy to `terraform.tfvars`.

### Prerequisites

- OCI session token and CLI configuration already created in `~/.oci/config` using this repository’s OIDC flow (GitHub Action or `simple.py`).
- Terraform CLI `>= 1.0.0`.

### Usage

1. **Ensure OCI CLI session is configured**

   From your local environment:

   ```bash
   oci session authenticate --region us-ashburn-1 --profile-name DEFAULT
   ```

   Or run the GitHub action / `simple.py` flow that writes `~/.oci/config` with `auth = SecurityToken`.

2. **Create your `terraform.tfvars` file**

   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your own values
   ```

3. **Run Terraform**

   ```bash
   terraform init
   terraform plan
   terraform apply  # Creates the validation bucket
   ```

4. **Cleanup**

   ```bash
   terraform destroy
   ```

### Notes

- The bucket name defaults to `terraform-validation-bucket`. For shared demo environments, you can override `bucket_name` in `terraform.tfvars` to avoid naming conflicts (for example, by adding a suffix).
- No data is stored in the bucket by this example, so there should be no Object Storage charges for simply running the validation.


