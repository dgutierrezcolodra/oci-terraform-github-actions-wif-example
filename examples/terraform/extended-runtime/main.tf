# Example: Terraform native WIF during long-running operations
#
# The helper refreshes only the GitHub source JWT file. OCI provider 8.29.0+
# owns the OCI UPST and its proof-of-possession key and renews them together.
#
# How it works:
# 1. Make an OCI API call (data source)
# 2. Wait for the configured duration
# 3. Make another OCI API call

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 8.29.0, < 9.0.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.13.1, < 1.0.0"
    }
  }
}

provider "oci" {
  auth   = "WorkloadIdentityFederation"
  region = var.oci_region
}

variable "oci_region" {
  description = "OCI Region"
  type        = string
}

variable "wait_duration" {
  description = "Duration used to simulate a long-running Terraform operation"
  type        = string
  default     = "120s"
}

# Step 1: API call BEFORE the wait
data "oci_objectstorage_namespace" "before_sleep" {}

# Step 2: Simulate a long operation
resource "time_sleep" "wait_for_token_refresh" {
  create_duration = var.wait_duration

  triggers = {
    # Force recreation each time
    timestamp = timestamp()
  }
}

# Step 3: API call after the wait
data "oci_objectstorage_namespace" "after_sleep" {
  depends_on = [time_sleep.wait_for_token_refresh]
}

output "test_result" {
  value = <<-EOT
    NATIVE WIF LONG-RUN DEMO PASSED

    OCI API calls succeeded before and after waiting ${var.wait_duration}.
  EOT
}
