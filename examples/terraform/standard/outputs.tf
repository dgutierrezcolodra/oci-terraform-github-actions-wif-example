output "bucket_name" {
  description = "Name of the created Object Storage bucket"
  value       = oci_objectstorage_bucket.validation_bucket.name
}

output "bucket_namespace" {
  description = "Object Storage namespace"
  value       = data.oci_objectstorage_namespace.ns.namespace
}

output "bucket_url" {
  description = "URL to view the bucket in OCI Console"
  value       = "https://cloud.oracle.com/object-storage/buckets/${data.oci_objectstorage_namespace.ns.namespace}/${oci_objectstorage_bucket.validation_bucket.name}"
}

output "bucket_id" {
  description = "OCID of the created bucket"
  value       = oci_objectstorage_bucket.validation_bucket.id
}
