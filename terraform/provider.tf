provider "oci" {
  auth                = "SecurityToken"
  config_file_profile = var.oci_profile
  region              = var.oci_region
}
