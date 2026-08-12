# Ansible namespace validation

This is the smallest Ansible WIF demo. It reads the OCI Object Storage
namespace with `oracle.oci` and checks that it is not empty. It creates no OCI
resource.

Run **Demo Ansible WIF Namespace Validation** after you finish
[SETUP.md](../../../SETUP.md). The workflow installs the collection, gets a
GitHub OIDC token, runs the Ansible bridge, runs this playbook, and removes the
temporary credentials.

The result is marked `no_log: true`. The playbook does not print the namespace.
