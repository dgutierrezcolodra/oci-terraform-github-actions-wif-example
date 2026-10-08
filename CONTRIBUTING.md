# Contributing

Keep contributions focused on GitHub Actions OIDC, OCI Resource trusts, and
RPST authentication for the Terraform and Ansible bucket demos.

## Contributions and commits

Contributors may need to sign the
[Oracle Contributor Agreement](https://oca.opensource.oracle.com/) before
source code or documentation contributions can be accepted. Include your name
and email in each commit's `Signed-off-by` line:

```bash
git commit --signoff
```

Use a focused branch and describe the change and its verification. Update the
[setup runbook](./SETUP.md) and demo instructions when behavior, inputs, or
secrets change. Use Conventional Commits where practical.

## Development checks

```bash
terraform fmt -check -recursive examples/terraform
terraform -chdir=examples/terraform/simple init -backend=false -input=false
terraform -chdir=examples/terraform/simple validate
actionlint .github/workflows/*.yml
ansible-playbook --syntax-check examples/ansible/bucket/playbook.yml
git diff --check
```

Install the pinned Ansible dependencies listed in its
[demo instructions](./examples/ansible/bucket/README.md) before checking the
playbook. Verify local documentation links and workflow names. Keep local
verification scripts outside tracked automation.

## Reporting issues

Include the affected workflow or setup step, expected result, actual result,
current tool versions, and sanitized error messages. Never include client
secrets, tokens, private keys, state, plans, or confidential tenancy details.

Report security vulnerabilities privately to a maintainer or through GitHub
private vulnerability reporting when available.

Keep reviews respectful and focused on correctness, security, and clarity.
