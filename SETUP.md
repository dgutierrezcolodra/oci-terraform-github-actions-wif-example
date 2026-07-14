# OCI setup for GitHub Actions native Terraform WIF

*Current on 14 July 2026*

This guide configures GitHub Actions as an external workload identity for OCI Terraform provider 8.22.0 or later. The runtime workflow is non-interactive and does not use OCI user API keys.

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

Use a personal administrator access token or a separate administrator application only for setup. Do not give the runtime token-exchange application an administrator role.

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

The `sub` claim depends on the workflow context. With GitHub's default subject format, common values include:

```text
repo:<owner>/<repository>:ref:refs/heads/main
repo:<owner>/<repository>:environment:production
```

For this repository, a workflow dispatched from the migration branch has this subject:

```text
repo:dgutierrezcolodra/oci-terraform-github-actions-wif-example:ref:refs/heads/feature/native-terraform-wif
```

After merge, a workflow dispatched from `main` has this subject:

```text
repo:dgutierrezcolodra/oci-terraform-github-actions-wif-example:ref:refs/heads/main
```

Use the exact repository name and ref, including case. If the job declares a GitHub environment, the environment replaces the ref in the default `sub`. If the organization or repository has customized its OIDC subject template, inspect the actual claims and configure the trust for that template instead.

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
    "<OCI_WIF_CLIENT_ID>"
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

The example authorizes `main`. To test the workflow from this feature branch before merge, temporarily add a second mapping to the same `impersonationServiceUsers` array:

```json
{
  "rule": "sub eq 'repo:dgutierrezcolodra/oci-terraform-github-actions-wif-example:ref:refs/heads/feature/native-terraform-wif'",
  "value": "<IDENTITY_DOMAIN_SERVICE_USER_ID>"
}
```

Remove the feature-branch mapping after the branch is merged. For production deployments, a protected GitHub environment gives a more stable subject and allows GitHub approval rules:

```json
{
  "rule": "sub eq 'repo:<owner>/<repository>:environment:production'",
  "value": "<IDENTITY_DOMAIN_SERVICE_USER_ID>"
}
```

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

Open **Settings → Secrets and variables → Actions** and create:

| Name | Type | Value |
|---|---|---|
| `OCI_WIF_CLIENT_ID` | Secret | Runtime token-exchange application client ID |
| `OCI_WIF_CLIENT_SECRET` | Secret | Runtime token-exchange application client secret |
| `DOMAIN_BASE_URL` | Secret or variable | Identity Domain URL without a trailing slash |
| `OCI_REGION` | Secret or variable | Region such as `eu-madrid-1` |
| `COMPARTMENT_ID` | Secret | Target compartment OCID |

The examples currently reference all five values through the `secrets` context. If you store non-sensitive values as repository variables, change their workflow references from `secrets.NAME` to `vars.NAME`.

For repositories migrated from the original example, the workflows also accept the legacy `CLIENT_ID` and `CLIENT_SECRET` secret names as fallbacks. `OCI_WIF_CLIENT_ID` and `OCI_WIF_CLIENT_SECRET` take precedence when both forms exist.

The old combined `OIDC_CLIENT_IDENTIFIER` and `OCI_TENANCY` secrets are no longer used.

## 7. Verify with a plan

Run **Demo Terraform Apply (Standard)** with action `plan`. A successful run should show:

- The GitHub OIDC token file was created.
- Terraform installed OCI provider 8.22.0 or a compatible 8.x release.
- Terraform completed the OCI data-source reads and produced a plan.
- No `~/.oci/config`, OCI private key, or OCI security-token file was created by the workflow.

Run `apply` only after the plan succeeds. Run `destroy` after the validation.

## Long-running processes

The provider renews the OCI UPST automatically and rotates the associated RSA key. It rereads `OCI_WORKLOAD_IDENTITY_TOKEN_PATH` when it needs another exchange.

GitHub JWTs are also short-lived. For a Terraform process that can exceed the OCI UPST lifetime, enable the local action's source-token refresh:

```yaml
- name: Create refreshable GitHub OIDC token file
  uses: ./github-oidc-token
  with:
    audience: https://cloud.oracle.com
    enable_token_refresh: true
    refresh_interval_minutes: 5
```

Do not externally replace the OCI UPST or private key. Those values are managed together inside the provider.

## Troubleshooting

### No matching impersonation rule

Decode the current GitHub JWT payload without logging the complete token. Compare its `iss`, `aud`, and `sub` with the trust. Repository names, refs, and environments must match exactly.

### No unique trust

Check for multiple active trusts with `https://token.actions.githubusercontent.com` as issuer. Consolidate the subject mappings into one uniquely selectable trust.

### `invalid_client`

Verify that `OCI_WIF_CLIENT_ID` and `OCI_WIF_CLIENT_SECRET` belong to the runtime application, the application is active, and its client ID is present in `oauthClients`.

### Terraform reports missing WIF configuration

Confirm the installed provider version and the environment:

```bash
terraform providers
env | grep '^OCI_\(AUTH\|REGION\|WORKLOAD_IDENTITY\|TOKEN_EXCHANGE\)' | sed 's/CLIENT_SECRET=.*/CLIENT_SECRET=***REDACTED***/'
```

Required provider variables are documented in [README.md](./README.md#terraform-configuration).

### Long run fails after the initial OCI token expires

Enable `enable_token_refresh`, keep the refresh interval shorter than the GitHub JWT lifetime, and confirm that the token file modification time changes. Never print the token contents.

## References

- [OCI JWT-to-UPST exchange](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm)
- [Oracle Core Technology blog: WIF with Microsoft Entra ID and Keycloak](https://blogs.oracle.com/coretec/oci-workload-identity-federation-wif-with-microsoft-entra-id-applications-and-keycloak)
- [OCI IdentityPropagationTrust model](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/identity_domains/models/oci.identity_domains.models.IdentityPropagationTrust.html)
- [OCI provider 8.22.0 WIF implementation](https://github.com/oracle/terraform-provider-oci/blob/v8.22.0/internal/provider/workload_identity_federation.go)
- [GitHub OIDC reference](https://docs.github.com/en/actions/reference/security/oidc)
- [GitHub OIDC discovery document](https://token.actions.githubusercontent.com/.well-known/openid-configuration)
