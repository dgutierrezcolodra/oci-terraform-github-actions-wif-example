# Example: Terraform Token Refresh During Long-Running Operations
#
# This example validates that the token refresh daemon can keep Terraform
# authenticated while an apply is still running.
#
# How it works:
# 1. Make an OCI API call (data source)
# 2. Wait 2 minutes (simulating a long operation)
# 3. Make another OCI API call
#
# If the second call succeeds after the wait, Terraform was able to continue
# using the refreshed OCI session token.

terraform {
  required_version = ">= 1.12.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 7.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9"
    }
  }
}

provider "oci" {
  auth                = "SecurityToken"
  config_file_profile = "DEFAULT"
  region              = var.oci_region
}

variable "oci_region" {
  description = "OCI Region"
  type        = string
}

# Step 1: API call BEFORE the wait
data "oci_objectstorage_namespace" "before_sleep" {}

# Step 2: Simulate a long operation (2 minutes)
resource "time_sleep" "wait_for_token_refresh" {
  create_duration = "120s"

  triggers = {
    # Force recreation each time
    timestamp = timestamp()
  }
}

# Step 3: API call AFTER the wait (uses refreshed token)
data "oci_objectstorage_namespace" "after_sleep" {
  depends_on = [time_sleep.wait_for_token_refresh]
}

output "test_result" {
  value = <<-EOT
    TOKEN REFRESH DEMO PASSED

    Before sleep: namespace = ${data.oci_objectstorage_namespace.before_sleep.namespace}
    After sleep:  namespace = ${data.oci_objectstorage_namespace.after_sleep.namespace}

    The second API call succeeded after the simulated long-running operation.
  EOT
}
