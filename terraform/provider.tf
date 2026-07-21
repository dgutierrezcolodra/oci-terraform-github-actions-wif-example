provider "oci" {
  auth   = "WorkloadIdentityFederation"
  region = var.oci_region
}
