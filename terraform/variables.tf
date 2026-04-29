variable "compartment_id" {
  description = "OCID of the compartment where resources will be created"
  type        = string
}

variable "oci_region" {
  description = "OCI region identifier"
  type        = string
  default     = "us-ashburn-1"
}

variable "oci_profile" {
  description = "OCI CLI profile name to use for authentication"
  type        = string
  default     = "DEFAULT"
}

variable "bucket_name" {
  description = "Name of the Object Storage bucket to create"
  type        = string
  default     = "terraform-validation-bucket"
}
