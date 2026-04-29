# Fetch the Object Storage namespace for the tenancy
data "oci_objectstorage_namespace" "ns" {
  # compartment_id is optional - defaults to root compartment
}

# Create an Object Storage bucket to validate authentication
resource "oci_objectstorage_bucket" "validation_bucket" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = var.bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Disabled"

  freeform_tags = {
    "Purpose"     = "Terraform-OIDC-Validation"
    "CreatedBy"   = "GitHub-Actions"
    "Environment" = "Validation"
  }
}
