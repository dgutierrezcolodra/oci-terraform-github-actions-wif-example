# OCI Workload Identity Federation for GitHub Actions

*Current on 12 August 2026*

This repository shows GitHub Actions authentication to Oracle Cloud
Infrastructure (OCI) with short-lived GitHub OIDC tokens and OCI Workload
Identity Federation (WIF). It does not use an OCI user API key.

- [Terraform examples](./examples/terraform/README.md)
- [Ansible examples](./examples/ansible/README.md)

Read [SETUP.md](./SETUP.md) first. It explains the OCI trust, IAM policy, and
GitHub secrets needed by both examples.

## Authentication flow

```mermaid
sequenceDiagram
    participant Job as GitHub Actions job
    participant GitHub as GitHub OIDC
    participant Provider as OCI Terraform provider 8.26.0
    participant Domain as OCI Identity Domain
    participant OCI as OCI APIs

    Job->>GitHub: Request JWT for https://cloud.oracle.com
    GitHub-->>Job: Short-lived JWT written below RUNNER_TEMP
    Job->>Provider: Pass protected JWT file path
    Provider->>Provider: Generate ephemeral RSA key
    Provider->>Domain: Exchange JWT and public key
    Domain-->>Provider: Short-lived OCI UPST
    Provider->>OCI: Sign API requests with matching private key
    Note over Job,Provider: Extended workflow refreshes only the source JWT file
    Provider->>Domain: Renew UPST and key together when required
```

The diagram shows the native Terraform WIF flow. GitHub issues a short-lived
JWT for the job. The OCI Terraform provider sends it to the OCI Identity
Domain, which checks the trust and returns a short-lived OCI token. The provider
creates the temporary key and renews the OCI token when needed. For long jobs,
the workflow refreshes only the GitHub JWT file.

## Important

- Run workflows from `main`. The OCI trust matches this exact branch.
- Never use `sub eq *` in the trust.
- Do not print or upload tokens, private keys, client secrets, or state files.

## License

Copyright (c) 2026 Oracle and/or its affiliates. Licensed under the Universal
Permissive License v1.0.
