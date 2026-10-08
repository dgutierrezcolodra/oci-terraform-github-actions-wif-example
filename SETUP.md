# RPST reference implementation runbook

This runbook configures OCI Workload Identity Federation for GitHub Actions
with ephemeral resource principal session tokens. Each demo creates one private
Object Storage bucket and deletes it in the same run. Terraform uses native
provider WIF; Ansible uses the OCI collection's resource principal authentication.

## 1. Prerequisites

You need:

- An OCI administrator who can create an Identity Domain, configure its
  applications and trusts, and create IAM policies.
- A compartment and region for the demo buckets.
- A GitHub repository containing these workflows, permission to set its Actions
  secrets, and permission to run workflows.
- Bash, OCI CLI, `jq`, and a browser for the trust configuration recipe below.

Choose the executing repository before configuring policies. The OIDC
`repository` claim is its actual `owner/repository`; a fork needs its own name
in the policy and its own Actions secrets.

Use a dedicated Identity Domain for the reference. OCI requires issuer
uniqueness within a domain. The Resource trust needs no runtime service user
or group membership.

## 2. Create the Identity Domain

In OCI Console, open **Identity & Security → Domains**, select the chosen
compartment, and create a domain. Use a name such as `github-rpst`, select
**Free** if available, and hide it from the sign-in page. Configure a domain
administrator if your administrator does not already have access.

Wait for **Active** and copy its HTTPS base URL without a trailing slash.
Do not include `/admin/v1` or `/oauth2/v1/token` in the secret.

Use the domain's home region for these demo buckets. Additional domains are
not automatically replicated to every subscribed region.
[Oracle domain creation instructions](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/to-create-new-identity-domain.htm).

## 3. Create the runtime OAuth application

Open the domain, then **Integrated applications → Add application →
Confidential Application → Launch workflow**.

1. Enter a name such as `github-rpst-client`.
2. Under **Configure OAuth**, configure it as a client with the **Client
   credentials** grant and client type **Confidential**.
3. Leave administrative app roles unassigned. The runtime application does not
   need Identity Domain Administrator or admin API access.
4. Finish, store the client ID and secret securely, and activate the application.

The administrator configures the trust and policies; the runtime client only
performs token exchange.
[Oracle confidential application instructions](https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm).

## 4. Create the Resource trust

Use these fields:

| Field | Value |
| --- | --- |
| `name` | `github-rpst-trust` |
| `type` | `JWT` |
| `issuer` | `https://token.actions.githubusercontent.com` |
| `publicKeyEndpoint` | `https://token.actions.githubusercontent.com/.well-known/jwks` |
| `subjectType` | `Resource` |
| `allowImpersonation` | `true` |
| `impersonatingResource` | `github_terraform` |
| `claimPropagations` | `["ext_repository", "ext_workflow_ref"]` |
| `oauthClients` | Array containing the runtime application's client ID |
| `active` | `true` |
| `schemas` | `["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"]` |

The resource type is a free string. `impersonatingResource`, the exchange's
`res_type`, and `RPST_RESOURCE_TYPE` must match. All demos can use this same
trust and client. Two claims are propagated here; OCI allows up to three.
The RPST payload exposes them as `var_ext_repository` and `var_ext_workflow_ref`;
IAM conditions use `request.principal.ext_repository`.
[Oracle RPST requirements](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/token_exchange_grant_type_workload_id-federation.htm),
[A-Team configuration example](https://www.ateam-oracle.com/oci-workload-identity-federation-using-ephemeral-rpst).

Run the following blocks in Bash. The recipe uses an administrator's signed
OCI CLI session, `jq`, and `raw-request` to send the complete trust configuration.
Keep debug logging and shell tracing disabled.
[OCI CLI raw-request reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/raw-request.html).

```bash
oci session authenticate --region eu-frankfurt-1 --profile-name rpst-admin
export RPST_BOOTSTRAP_PROFILE=rpst-admin
export RPST_DOMAIN_URL='https://<domain>.identity.oraclecloud.com'
```

Replace the region and URL with yours. A profile name is a label; permissions
come from the authenticated identity. The next block asks for the client ID
without displaying it. It sends the JSON through standard input, checks the
HTTP status, and prints only the trust ID. It needs no client secret and creates
no local credential or response file.

```bash
set -euo pipefail
read -r -s -p 'Runtime OAuth client ID: ' RPST_CLIENT_ID
printf '\n'
test -n "$RPST_CLIENT_ID"

jq -n --arg client_id "$RPST_CLIENT_ID" '{
  "schemas": ["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"],
  "name": "github-rpst-trust",
  "type": "JWT",
  "issuer": "https://token.actions.githubusercontent.com",
  "publicKeyEndpoint": "https://token.actions.githubusercontent.com/.well-known/jwks",
  "subjectType": "Resource",
  "allowImpersonation": true,
  "impersonatingResource": "github_terraform",
  "claimPropagations": ["ext_repository", "ext_workflow_ref"],
  "oauthClients": [$client_id],
  "active": true
}' |
  oci raw-request --profile "$RPST_BOOTSTRAP_PROFILE" --auth security_token \
    --http-method POST --target-uri "$RPST_DOMAIN_URL/admin/v1/IdentityPropagationTrusts" \
    --request-body file:///dev/stdin --output json --query id |
  jq -er 'if (.status | startswith("2")) then .data
          else error("Trust creation failed: " + .status) end'
unset RPST_CLIENT_ID
```

Run once per domain. Before retrying after an interruption, check whether the
trust exists. If the session expires, authenticate again with the same profile.
Any administrator OAuth client used for setup must be separate from the runtime
client; its credentials do not belong in the repository secrets.

### Verify the application and trust

After creation, verify the stored configuration rather than relying only on
wizard completion. Keep the administrator session active and the profile and
domain environment variables above. Set the two display names you created:

```bash
set -euo pipefail
export RPST_APPLICATION_NAME=github-rpst-client
export RPST_TRUST_NAME=github-rpst-trust

domain_read() {
  oci raw-request --profile "$RPST_BOOTSTRAP_PROFILE" --auth security_token \
    --http-method GET --target-uri "$RPST_DOMAIN_URL/admin/v1/$1" --output json --query "$2" |
    jq -e 'if (.status | startswith("2")) then .data
           else error("Administrative read failed: " + .status) end'
}

app_filter="$(jq -rn --arg name "$RPST_APPLICATION_NAME" '"displayName eq " + ($name | tojson) | @uri')"
trust_filter="$(jq -rn --arg name "$RPST_TRUST_NAME" '"name eq " + ($name | tojson) | @uri')"
app="$(domain_read "Apps?attributes=id,name,active,clientType,isOAuthClient,allowedGrants&filter=$app_filter" '{count:totalResults,app:Resources[0].{id:id,name:name,active:active,clientType:clientType,isOAuthClient:isOAuthClient,allowedGrants:allowedGrants}}')"
trust="$(domain_read "IdentityPropagationTrusts?filter=$trust_filter" '{count:totalResults,trust:Resources[0].{active:active,subjectType:subjectType,type:type,issuer:issuer,publicKeyEndpoint:publicKeyEndpoint,allowImpersonation:allowImpersonation,impersonatingResource:impersonatingResource,claimPropagations:claimPropagations,oauthClients:oauthClients}}')"
jq -ne --argjson app "$app" --argjson trust "$trust" \
  'if $app.count == 1 and $trust.count == 1 then true
   else error("Expected exactly one application and one trust") end' > /dev/null
app_id="$(jq -r '.app.id' <<< "$app")"
grant_filter="$(jq -rn --arg id "$app_id" '"grantee.value eq " + ($id | tojson) | @uri')"
grants="$(domain_read "Grants?filter=$grant_filter" totalResults)"

jq -ne --argjson app "$app" --argjson trust "$trust" --argjson grants "$grants" '
  $app.app as $a | $trust.trust as $t | {
    app_active: ($a.active == true),
    confidential_client: ($a.clientType == "confidential" and $a.isOAuthClient == true),
    client_credentials_only: ($a.allowedGrants == ["client_credentials"]),
    no_admin_roles: ($grants == 0),
    active_resource_trust: ($t.active == true and $t.subjectType == "Resource"),
    jwt_type: ($t.type == "JWT"),
    issuer: ($t.issuer == "https://token.actions.githubusercontent.com"),
    jwks: ($t.publicKeyEndpoint == "https://token.actions.githubusercontent.com/.well-known/jwks"),
    impersonation: ($t.allowImpersonation == true and $t.impersonatingResource == "github_terraform"),
    claim_propagations: ($t.claimPropagations == ["ext_repository", "ext_workflow_ref"]),
    client_binding: ($t.oauthClients == [$a.name])
  } | ., (if all(.[]; . == true) then empty else error("Correct the failed settings") end)'
unset app trust grants app_id app_filter trust_filter grant_filter
unset -f domain_read
```

All checks must be `true`; a failed check returns a nonzero exit status. The
application request selects its required fields with the API's `attributes`
parameter, excluding the client secret. The CLI then selects the fields used
by each check, keeps their values in shell variables, and prints only the
check results. Client IDs and full responses are not printed.
[Oracle application attributes parameter](https://docs.oracle.com/en/cloud/paas/iam-domains-rest-api/op-admin-v1-apps-get.html).

These commands were executed on macOS with OCI CLI **3.83.0** and `jq` **1.7.1**
on 8 October 2026. The creation command created a Resource trust in a dedicated
domain, and the verification returned all eleven checks as `true`. The same
verification also passed against the domain used by the three bucket demos.

## 5. Create IAM policies

In **Identity & Security → Policies**, select the tenancy root and create a
policy. Replace the repository and compartment placeholders:

```text
Allow any-user to read objectstorage-namespaces in tenancy where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
Allow any-user to manage buckets in compartment <compartment> where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
```

The first statement grants namespace access in the tenancy. The second grants
bucket access only in the named compartment. For this repository, the value is
`dgutierrezcolodra/oci-terraform-github-actions-wif-example`.
Allow time for IAM propagation. Token issuance alone does not grant bucket access.

Read back the domain and policy with the administrator profile. Copy their
OCIDs from the Console details pages and replace the placeholders:

```bash
oci iam domain get --domain-id '<domain_ocid>' --profile rpst-admin --auth security_token \
  --query 'data.{name:"display-name",state:"lifecycle-state",url:url,region:"home-region",compartment:"compartment-id"}'
oci iam policy get --policy-id '<policy_ocid>' --profile rpst-admin --auth security_token \
  --query 'data.{name:name,state:"lifecycle-state",compartment:"compartment-id",statements:statements}'
```

Confirm the domain is `ACTIVE`, the region and compartment are the ones you
selected, and the policy is `ACTIVE` in the tenancy root with exactly the two
statements above, using your repository and bucket compartment. The application,
trust, zero role grants, domain, and policy checks were performed against the
OCI configuration used by this reference.


## 6. Set GitHub repository secrets

Open **Settings → Secrets and variables → Actions → New repository secret**.
All workflows use the same six secrets:

| Secret | Value |
| --- | --- |
| `RPST_DOMAIN_BASE_URL` | Domain HTTPS base URL without trailing slash |
| `RPST_CLIENT_ID` | Runtime application's client ID |
| `RPST_CLIENT_SECRET` | Runtime application's client secret |
| `RPST_RESOURCE_TYPE` | `github_terraform`, matching the trust |
| `RPST_COMPARTMENT_ID` | Bucket compartment OCID |
| `OCI_REGION` | Bucket region; use the domain's home region |

The Orchestrator demo also needs `OCI_TENANCY`, containing your tenancy OCID.
This supplies the upstream `tenancy_ocid` input; it is not an API credential.

Enter credentials directly in the secrets UI or transfer them through a tool's
standard input. Never put secrets, JWTs, RPSTs, or private keys into commands,
commits, screenshots, logs, or job summaries.

## 7. Run the demos

GitHub requires the workflow file on the repository's default branch for manual
dispatch. In a customer repository, place the reference files on that branch.
[GitHub manual workflow requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

### Terraform simple

1. Open **Actions → Demo Terraform RPST Bucket → Run workflow**.
2. Select the branch and `plan`. The raw exchange checks OCI configuration;
   Terraform then plans one bucket using its own RPST and key.
3. Expect HTTP 200, claim names, selected diagnostic values, lifetime, and a plan
   for one private bucket. Payload inspection does not verify its signature.
4. Run again with `apply-and-destroy`. Check both outcomes in the summary and
   confirm the bucket is absent from the compartment.

### Terraform Orchestrator

1. Set the additional `OCI_TENANCY` repository secret.
2. Open **Actions → Demo Terraform Orchestrator RPST Bucket → Run workflow**.
3. Select the branch and `plan`. The workflow fetches the official Orchestrator
   commit, fills its bucket inputs, and checks that the plan creates exactly one
   private bucket. No other configuration family is enabled.
4. Run again with `apply-and-destroy`. Check plan, apply, and destroy in the
   summary and confirm bucket absence in OCI.

The [Orchestrator instructions](./examples/terraform/orchestrator/README.md)
describe the selected upstream commit and input format.

### Ansible

1. Open **Actions → Demo Ansible RPST Bucket → Run workflow**.
2. Select the branch and run. It exchanges credentials, reads the namespace,
   creates a private bucket, obtains fresh credentials, and deletes the bucket.
3. Check create and delete outcomes in the summary and confirm bucket absence.

## 8. Diagnose failures

| Observation | What to check |
| --- | --- |
| Manual dispatch unavailable | The workflow must exist on the default branch. |
| Input validation fails | All six shared secrets must exist; Orchestrator also needs `OCI_TENANCY`. |
| Raw exchange or Ansible exchange fails | Domain URL, active client, credentials, trust issuer uniqueness, JWKS endpoint, and matching `res_type`. |
| Raw exchange passes; Terraform authentication fails | Provider or SDK RPST handling; check the `tenant` claim. |
| Exchange passes; Object Storage access denied | IAM propagation, both policies, repository claim, compartment, and region. |
| Terraform checksum error | Check the committed lock; keep checksum validation enabled. |
| Delete or destroy fails after creation | Find the run's bucket in the compartment and remove it manually. |

The raw Terraform exchange uses `continue-on-error`; inspect its result and
Terraform's result separately. The raw exchange prints only HTTP status, permitted
error fields, claim names, selected diagnostic claims, and token lifetime.
The workflows do not request `rpst_exp`. Observe the issued lifetime; the recorded
Terraform execution received 1,200 seconds. These short demos obtain fresh
credentials before operations and do not require a background refresh process.

## 9. Runtime cleanup and teardown

All credential files stay under `$RUNNER_TEMP`: the source JWT in `oci-wif`,
simple Terraform data, plan, and local state in `rpst-terraform`, Orchestrator
source, inputs, data, plan, and local state in `rpst-orchestrator`, and Ansible RPST and
key in `oci-ansible-wif`. Sensitive files use mode 600 and directories mode 700.
Dependency executables retain their required executable permissions.

The raw exchange deletes its key and response on exit. Always-run cleanup
removes the runtime directories, including Ansible dependencies and temporary
files. Client secrets are step-level environment values and never written to
`GITHUB_ENV` or a file. Keep `TF_LOG`, shell tracing, Ansible verbosity, and HTTP
debugging disabled. Do not upload credentials, state, or plans as artifacts.

Simple Terraform's local backend receives an explicit runtime state path;
Orchestrator uses its local backend inside the temporary checkout. Cleanup
removes state even when destroy fails; another run cannot recover it. Use the
bucket name `rpst-terraform-<run_id>`, `rpst-orchestrator-<run_id>`, or
`rpst-ansible-<run_id>` for manual cleanup.

When retiring the reference:

1. Confirm all demo buckets are gone. Remove objects before deleting a nonempty
   bucket.
2. Remove the five `RPST_*` secrets; keep `OCI_REGION` and `OCI_TENANCY` if other
   consumers need them.
3. Deactivate and delete the runtime application and trust.
4. Delete only the IAM policy created for this reference.
5. Remove the dedicated domain when no longer needed, following Console
   requirements. Preserve shared compartments and unrelated resources.

## Execution record

Record tool versions, outcomes, and claim names. Never record full tokens or
credentials.

| Date | Demo | Tool / provider version | Exchange | Create / apply | Delete / destroy | RPST lifetime (s) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-08 | Terraform | Terraform 1.16.5 / OCI 9.8.0 | HTTP 200 | 1 bucket created | 1 bucket deleted | 1200 | [Execution](https://github.com/dgutierrezcolodra/oci-terraform-github-actions-wif-example/actions/runs/37766831245); Executed from `main`; [plan](https://github.com/dgutierrezcolodra/oci-terraform-github-actions-wif-example/actions/runs/37766762428) also passed; `tenant` present; bucket absence confirmed in OCI. |
| 2026-10-08 | Terraform Orchestrator | Orchestrator v2.1.4 / Terraform 1.16.5 / OCI 9.8.0 | Native WIF succeeded | 1 bucket created | 1 bucket deleted | Not logged | [Execution](https://github.com/dgutierrezcolodra/oci-terraform-github-actions-wif-example/actions/runs/37769008078); plan confirmed exactly one private bucket; the same two IAM policies were sufficient; bucket absence confirmed in OCI. |
| 2026-10-08 | Ansible | Core 2.15.13 / OCI SDK 2.182.1 / collection 5.5.0 | Success | 1 bucket created | 1 bucket deleted | Not logged | [Execution](https://github.com/dgutierrezcolodra/oci-terraform-github-actions-wif-example/actions/runs/37766766106); Executed from `main`; resource principal authentication; bucket absence confirmed in OCI. |
