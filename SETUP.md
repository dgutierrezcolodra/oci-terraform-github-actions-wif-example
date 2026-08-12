# OCI setup for GitHub Actions WIF

*Current on 12 August 2026*

This guide configures GitHub Actions as an external workload identity for the
repository's OCI Terraform provider 8.26.0 baseline. Generic WIF support first
appeared in provider 8.22.0, but this reference requires and locks 8.26.0. The
runtime workflow is non-interactive and does not use OCI user
API keys.

Use this setup for GitHub-hosted runners or self-hosted runners outside OCI. If
the runner is an OCI Compute instance, prefer [Instance
Principals](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm).
If it runs as a pod in an enhanced OKE cluster, prefer [OKE Workload
Identity](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contenggrantingworkloadaccesstoresources.htm).
Generic WIF is the safe external-runner alternative when neither OCI-native
identity is available.

## Before you start

You need:

- Administrator access to the OCI Identity Domain used for the trust.
- The Identity Domain URL, such as `https://idcs-<identifier>.identity.oraclecloud.com`, without a trailing slash.
- A target OCI compartment and permission to create IAM policies.
- An Identity Domain administrator bearer token for the one-time SCIM calls.

For a one-time setup, an administrator can generate a personal access token from **My profile → My access tokens**, selecting access to invoke Identity Domain APIs with the **Identity Domain Administrator** role. An alternative is a separate confidential application with that administrator application role. Do not reuse the runtime token-exchange application for administration.

## 1. Create a service user

In the OCI Identity Domain used for automation, create a service user such as `github-actions-terraform`. A service user cannot sign in interactively and cannot have API keys.

You can create it in the console or with an Identity Domain administrator access token:

```bash
curl --request POST \
  --url "<DOMAIN_URL>/admin/v1/Users" \
  --header "Authorization: Bearer <IDA_ACCESS_TOKEN>" \
  --header "Content-Type: application/json" \
  --data '{
    "schemas": [
      "urn:ietf:params:scim:schemas:core:2.0:User",
      "urn:ietf:params:scim:schemas:oracle:idcs:extension:user:User"
    ],
    "urn:ietf:params:scim:schemas:oracle:idcs:extension:user:User": {
      "serviceUser": true
    },
    "userName": "github-actions-terraform"
  }'
```

Save the response `id`. The Identity Propagation Trust needs the Identity Domain user ID, not the user's OCI OCID.

## 2. Grant least-privilege OCI permissions

Add the service user to an Identity Domain group. This repository creates and deletes one empty Object Storage bucket. It therefore needs bucket management in the target compartment and permission to read the tenancy-level Object Storage namespace:

```text
Allow group GitHubAutomationUsers to manage buckets in compartment <compartment-name>
Allow group GitHubAutomationUsers to read objectstorage-namespaces in tenancy
```

The `objectstorage-namespaces` statement must use `in tenancy` and must be created in the root compartment. The bucket statement can be created in the target compartment or a parent compartment. Add `manage objects` separately only if your Terraform configuration also manages objects.

For a non-default Identity Domain, qualify the group:

```text
Allow group '<identity-domain-name>'/'GitHubAutomationUsers' to manage buckets in compartment <compartment-name>
Allow group '<identity-domain-name>'/'GitHubAutomationUsers' to read objectstorage-namespaces in tenancy
```

Do not use `manage all-resources` for this example.

## 3. Create the runtime token-exchange application

In the same OCI Identity Domain, create a dedicated runtime application:

1. Add a confidential application.
2. Select **Configure this application as a client now**.
3. Enable the **Client credentials** grant.
4. Assign no Identity Domain administrator or application roles.
5. Activate the application.
6. Save its client ID and client secret.

This application authenticates the call to `<DOMAIN_URL>/oauth2/v1/token`. The token exchange itself uses the OAuth token-exchange grant; the OCI provider sends the runtime application's client ID and secret as client authentication. Its client ID must also appear in the trust's `oauthClients` list.

Use a different application with the **Identity Domain Administrator** application role, or a personal administrator access token, for the one-time SCIM setup. The runtime application must not have that role.

## 4. Determine the exact GitHub claims

This repository requests this audience:

```text
https://cloud.oracle.com
```

The GitHub issuer is:

```text
https://token.actions.githubusercontent.com
```

With GitHub's default subject format, a workflow running from a branch without
a job-level environment has this subject:

```text
repo:<owner>/<repository>:ref:refs/heads/<protected-branch>
```

The checked-in workflows use `main`, so their default subject is:

```text
repo:<owner>/<repository>:ref:refs/heads/main
```

Use the exact repository name and protected branch, including case. When
copying the reference, replace `main` consistently in the workflow invocation
and trust if you use another protected deployment branch. The cloud jobs
intentionally declare no GitHub environment and use no OIDC subject
customization. A job-level environment changes GitHub's default `sub`, so it
would not match this branch rule.

## 5. Create the Identity Propagation Trust

Create one active JWT trust for the GitHub issuer. OCI uses the issuer to identify the trust, so keep the issuer unique within the Identity Domain. If a trust for GitHub already exists, add the required OAuth client and exact subject mapping to that trust instead of creating a second active trust with the same issuer.

Replace the placeholders and submit the payload to:

```text
POST <DOMAIN_URL>/admin/v1/IdentityPropagationTrusts
```

```json
{
  "active": true,
  "allowImpersonation": true,
  "issuer": "https://token.actions.githubusercontent.com",
  "name": "GitHub Actions to OCI Terraform",
  "oauthClients": [
    "<CLIENT_ID>"
  ],
  "publicKeyEndpoint": "https://token.actions.githubusercontent.com/.well-known/jwks",
  "clientClaimName": "aud",
  "clientClaimValues": [
    "https://cloud.oracle.com"
  ],
  "impersonationServiceUsers": [
    {
      "rule": "sub eq 'repo:<owner>/<repository>:ref:refs/heads/main'",
      "value": "<IDENTITY_DOMAIN_SERVICE_USER_ID>"
    }
  ],
  "subjectType": "User",
  "type": "JWT",
  "schemas": [
    "urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"
  ]
}
```

The payload authorizes only `main`. Replace that branch consistently if your
deployment branch has another name. Do not add temporary branch mappings or
wildcards to make a run pass; update the single exact mapping through your
normal change-control process.

`clientClaimName` and `clientClaimValues` restrict the token audience. `impersonationServiceUsers` independently restricts which GitHub subjects may impersonate the service user. Both controls are intentional.

Do not use `sub eq *` in production. It would allow every accepted GitHub subject from the issuer and audience to impersonate the same OCI service user.

Verify the saved mapping explicitly because normal trust reads can omit it:

```bash
curl --silent \
  --header "Authorization: Bearer <IDA_ACCESS_TOKEN>" \
  "<DOMAIN_URL>/admin/v1/IdentityPropagationTrusts/<TRUST_ID>?attributes=impersonationServiceUsers" \
  | jq .
```

Also verify the trust metadata and audience restriction:

```bash
curl --silent \
  --header "Authorization: Bearer <IDA_ACCESS_TOKEN>" \
  "<DOMAIN_URL>/admin/v1/IdentityPropagationTrusts/<TRUST_ID>?attributes=name,active,issuer,oauthClients,publicKeyEndpoint,clientClaimName,clientClaimValues" \
  | jq .
```

The saved values must include the GitHub issuer, GitHub JWKS endpoint, runtime OAuth client ID, `clientClaimName` set to `aud`, and `https://cloud.oracle.com` in `clientClaimValues`.

## 6. Configure GitHub Actions

Add these repository Actions secrets under **Settings → Secrets and variables → Actions**:

| Name | Type | Value |
|---|---|---|
| `CLIENT_ID` | Secret | Runtime token-exchange application client ID |
| `CLIENT_SECRET` | Secret | Runtime token-exchange application client secret |
| `DOMAIN_BASE_URL` | Secret or variable | Identity Domain URL without a trailing slash |
| `OCI_REGION` | Secret or variable | Region such as `eu-madrid-1` |
| `COMPARTMENT_ID` | Secret | Target compartment OCID |

The workflows reference all five values through the `secrets` context.
`COMPARTMENT_ID` is a repository secret and is not a workflow-dispatch input,
so a caller cannot redirect an apply to an arbitrary compartment. The jobs do
not declare a GitHub environment and therefore have no Environment approval
gate. `apply-and-destroy` remains an explicit manual workflow choice. If you
store non-sensitive values as repository variables, change their workflow
references from `secrets.NAME` to `vars.NAME`.

Provider 8.26.0 obtains tenancy context from the exchanged UPST; do not add a
separate tenancy secret to these references.

The Terraform workflows pass `CLIENT_SECRET` only to the steps that call the
configured provider. They mask it before shell use and do not persist it
through `GITHUB_ENV`.

The standard Terraform and Ansible workflows obtain their source JWT once
through `.github/actions/github-oidc-token`. That action uses official
`actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3` (`v9.0.0`),
writes the JWT atomically below `RUNNER_TEMP`, exports only its path, and does
not refresh it. `.github/actions/ansible-oci-wif` remains the Oracle SDK
compatibility bridge for the Ansible collection.

The bridge exports `OCI_CONFIG_FILE`, `OCI_ANSIBLE_AUTH_TYPE=security_token`,
`OCI_ANSIBLE_SECURITY_TOKEN_FILE`, and `OCI_ANSIBLE_PRIVATE_KEY_FILE`; its safe
action outputs are the protected config, security-token, and private-key paths.

## 7. Verify with a plan

From the branch configured in the trust, run **Demo Terraform Apply
(Standard)** with action `plan`. In this repository that branch is `main`. A
successful run should show:

- The GitHub OIDC token file was created.
- Terraform selected the locked OCI provider 8.26.0 baseline.
- Terraform completed the OCI data-source reads and produced a plan.
- No `~/.oci/config`, OCI private key, or OCI security-token file was created by the workflow.

Run `apply-and-destroy` only after the plan succeeds. It creates and removes the validation bucket in the same job, while the local Terraform state is still available. Configure a remote backend before adapting this example to manage persistent infrastructure.

## 8. Verify Ansible collection access

From the branch configured in the trust, run **Demo Ansible WIF Namespace
Validation** as a manual, read-only check. It uses `CLIENT_ID`,
`CLIENT_SECRET`, `DOMAIN_BASE_URL`, and `OCI_REGION` described above.

`oracle.oci` does not consume the OCI Terraform provider's native WIF
configuration directly. The workflow uses the local
`.github/actions/ansible-oci-wif` bridge only for Ansible: it exchanges the
GitHub OIDC token for ephemeral security-token credentials used by the
collection's namespace facts module. This is not an OCI API-key fallback, and
no user API key or `~/.oci/config` is used.

The workflow installs `oracle.oci` 5.6.0 from the pinned Git commit in
`examples/ansible/requirements.yml` because that version is not published to
Ansible Galaxy. The runner therefore needs `git`, and this installation does
not use Galaxy collection-signature verification. Review the pinned source
commit before updating it.

For **Demo Ansible WIF Credential Renewal**, use
`.github/actions/github-oidc-token-refresh`, `.github/actions/ansible-oci-wif`,
`examples/ansible/requirements.yml`, and
`examples/ansible/extended-runtime`. The source-JWT refresher is shared with
extended Terraform. Between module tasks, the playbook runs the adapter again
and replaces the OCI UPST and matching private key together. Later `oracle.oci`
tasks load the renewed files. One already-running module retains its in-memory
signer and is not refreshed by file replacement.

The controller-local proof distributes no credentials to managed hosts and
creates, updates, or deletes no OCI resource. For a long service operation,
submit asynchronously with `wait: false`, renew at a later task boundary, then
use facts/status tasks. Its proof modes are 120 seconds and 65 minutes; the 65-minute
run is manual and opt-in. This remains an Ansible adapter pattern rather than
native WIF support in the collection.

## Long-running processes

The provider renews the OCI UPST automatically and rotates the associated RSA key. It rereads `OCI_WORKLOAD_IDENTITY_TOKEN_PATH` when it needs another exchange.

GitHub JWTs are also short-lived. For a Terraform process that can exceed the
OCI UPST lifetime, use the custom
`.github/actions/github-oidc-token-refresh` extension to refresh the source
token:

```yaml
- name: Create refreshable GitHub OIDC token file
  uses: ./.github/actions/github-oidc-token-refresh
  with:
    audience: https://cloud.oracle.com
    refresh_interval_minutes: 1
```

Do not externally replace the OCI UPST or private key. Those values are managed together inside the provider.

The refresh action stores its daemon PID in a protected file beside the source JWT. The token-refresh workflow validates that file and the daemon command before stopping the exact process in an always-run cleanup, then removes the credential directory. The standard Terraform workflow also removes its source-JWT directory independently of plan, apply, or destroy success.

## Troubleshooting

### No matching impersonation rule

Decode the current GitHub JWT payload without logging the complete token.
Compare its `iss`, `aud`, and `sub` with the trust. Confirm the workflow ran
from the configured protected branch, the repository name and ref match
exactly, and the job has no `environment:` declaration.

### No unique trust

Check for multiple active trusts with `https://token.actions.githubusercontent.com` as issuer. Consolidate the subject mappings into one uniquely selectable trust.

### `invalid_client`

Verify that `CLIENT_ID` and `CLIENT_SECRET` belong to the runtime application, the application is active, and its client ID is present in `oauthClients`.

### Terraform reports missing WIF configuration

Confirm the installed provider version and the environment:

```bash
terraform providers
env | grep '^OCI_\(AUTH\|REGION\|WORKLOAD_IDENTITY\|TOKEN_EXCHANGE\)' | sed 's/CLIENT_SECRET=.*/CLIENT_SECRET=***REDACTED***/'
```

Required provider variables are documented in
[Terraform examples](./examples/terraform/README.md).

### Long run fails after the initial OCI token expires

Use `.github/actions/github-oidc-token-refresh` only for **Demo Terraform
Token Refresh**, which records the initial token-file modification time and
fails unless the final time is strictly greater. GitHub OIDC JWTs expire roughly
5 minutes after issuance (observed behavior; GitHub does not document the
lifetime officially), which is why the extension accepts refresh intervals
between 1 and 4 minutes. Never print the token contents.

## References

- [OCI Terraform provider 8.22.0 changelog](https://github.com/oracle/terraform-provider-oci/blob/v8.22.0/CHANGELOG.md)
- [OCI JWT-to-UPST exchange](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm)
- [Oracle Core Technology blog: WIF with Microsoft Entra ID and Keycloak](https://blogs.oracle.com/coretec/oci-workload-identity-federation-wif-with-microsoft-entra-id-applications-and-keycloak)
- [OCI IdentityPropagationTrust model](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/identity_domains/models/oci.identity_domains.models.IdentityPropagationTrust.html)
- [OCI provider 8.26.0 WIF implementation](https://github.com/oracle/terraform-provider-oci/blob/v8.26.0/internal/provider/workload_identity_federation.go)
- [GitHub OIDC reference](https://docs.github.com/en/actions/reference/security/oidc)
- [GitHub OIDC discovery document](https://token.actions.githubusercontent.com/.well-known/openid-configuration)
