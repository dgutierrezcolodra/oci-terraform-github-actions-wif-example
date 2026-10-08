# RPST Terraform demo runbook

This throwaway demo tests provider-native OCI Workload Identity Federation with an ephemeral RPST. It plans one private Object Storage bucket and can optionally create and delete it. It is a reference experiment, not a production deployment pattern.

Phase 2 performs a raw curl exchange to check the OCI configuration. Phase 3 lets the Terraform provider exchange its own GitHub JWT for an RPST. Terraform never receives the raw exchange's token or private key.

| Action | What it does |
| --- | --- |
| `plan` | Runs both phases and plans one bucket. Creates no OCI resources. |
| `apply-and-destroy` | Applies the saved plan and attempts to destroy the bucket afterward, including after a failed apply. |

The workflow uses Terraform **1.16.5** and locks `oracle/oci` **9.8.0**, with hashes for `linux_amd64` and `darwin_arm64`. The question this demo must answer is whether the provider can use the issued RPST, including its tenancy claim.

On `spike/rpst-terraform`, a push changing this workflow or `spike/rpst/main.tf` runs `apply-and-destroy` automatically. This branch-scoped trigger makes the demo executable without changing `main`. It uses the same steps as the manual action. Documentation-only pushes do not run the demo.

## 1. Before starting

You need an OCI administrator who can create an Identity Domain, configure its applications and trusts, and create IAM policies. Choose a test compartment and region. In GitHub, you need a repository containing the demo, access to set Actions secrets, and permission to run workflows. The trust recipe below also needs OCI CLI, Python 3, and a browser.

Use a **separate test Identity Domain**. OCI expects a unique issuer within each domain, and the existing UPST setup already has a GitHub trust with `subjectType: User`. Keep that domain and its configuration in place. The RPST demo needs no service user or group membership for its runtime identity.

Choose the executing GitHub repository before writing the policies. Its OIDC `repository` claim is the actual `owner/repository` of the run. A fork or separate test repository needs its own repository name in the policies and its own Actions secrets.

GitHub requires the workflow file on the repository's default branch before `workflow_dispatch` is available. This reference uses the restricted push trigger for its branch-only demo. A client can use a separate test repository with the workflow on its default branch to select `plan` and `apply-and-destroy` manually. Changes to this reference's `main`, default branch, or PRs require maintainer approval. [GitHub manual workflow requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## 2. Create the test Identity Domain

In OCI Console, open **Identity & Security → Domains**, select the test compartment, and create a domain. Use a distinct name such as `rpst-spike-terraform`, select **Free** if available in your tenancy, and hide it from the sign-in page. Set up a domain administrator if your existing administrator does not already have access.

Wait for **Active**, then copy the domain URL from its details page. Use its HTTPS base URL without a trailing slash. Do not include `/admin/v1` or `/oauth2/v1/token` in the GitHub secret.

For this demo, use the domain's home region for the bucket. Additional domains are not automatically replicated to every subscribed region. [Oracle domain creation instructions](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/to-create-new-identity-domain.htm).

## 3. Create the runtime OAuth application

Open the test domain, then **Integrated applications → Add application → Confidential Application → Launch workflow**.

1. Enter a name such as `rpst-spike-terraform-client`.
2. On **Configure OAuth**, configure the application as a client and select **Client credentials** as its allowed grant.
3. Use client type **Confidential**. Leave administrative app roles unassigned; do not grant Identity Domain Administrator or admin API access to this runtime client.
4. Finish the wizard, store the client ID and secret securely, and activate the application.

The identity used to configure the demo has administrative permissions. The runtime application has none. [Oracle confidential application instructions](https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm).

## 4. Create the Resource trust

The trust must contain these settings:

| Field | Value |
| --- | --- |
| `name` | A distinct name, for example `rpst-spike-terraform-github` |
| `type` | `JWT` |
| `issuer` | `https://token.actions.githubusercontent.com` |
| `publicKeyEndpoint` | `https://token.actions.githubusercontent.com/.well-known/jwks` |
| `subjectType` | `Resource` |
| `allowImpersonation` | `true` |
| `impersonatingResource` | `github_terraform` |
| `claimPropagations` | `["ext_repository", "ext_workflow_ref"]` |
| `oauthClients` | An array containing the runtime application's client ID |
| `active` | `true` |
| `schemas` | `["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"]` |

The resource type is a free string, but `impersonatingResource`, the exchange's `res_type`, and `RPST_RESOURCE_TYPE` must match exactly. This demo propagates two source claims; OCI allows up to three.

`allowImpersonation: true` is included in the Oracle RPST requirements and the A-Team example. Oracle documents the propagated RPST payload names as `var_ext_*`. The workflow prints all claim names, while its selected-value filter prints the claims listed in the original spike specification: `ttype`, `iss`, `res_type`, `tenant`, `res_tenant`, `sub`, and names starting with `ext_`. [Oracle RPST documentation](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/token_exchange_grant_type_workload_id-federation.htm), [A-Team example](https://www.ateam-oracle.com/oci-workload-identity-federation-using-ephemeral-rpst).

The following recipe uses an administrator's signed OCI CLI session. This route was used for the reference bootstrap: OCI CLI 3.83.0's typed trust command does not expose the RPST fields and only accepts `User` or `App` for `--subject-type`, so the recipe uses `raw-request`.

Authenticate locally, replacing the region and domain URL as needed:

```bash
oci session authenticate --region eu-frankfurt-1 --profile-name rpst-bootstrap-admin
export RPST_BOOTSTRAP_PROFILE=rpst-bootstrap-admin
export RPST_TEST_DOMAIN_URL='https://<test-domain>.identity.oraclecloud.com'
```

A profile name is only a label; permissions come from the authenticated identity. Run the following in a local terminal. It requests the client ID without displaying it, holds the OCI response in memory, and prints only the status and trust ID. It does not need the client secret.

```bash
python3 - <<'PY'
import getpass
import json
import os
import subprocess
import sys
from urllib.parse import urlsplit

profile = os.environ["RPST_BOOTSTRAP_PROFILE"]
domain_url = os.environ["RPST_TEST_DOMAIN_URL"].rstrip("/")
parsed = urlsplit(domain_url)
if parsed.scheme != "https" or not parsed.hostname or parsed.path:
    sys.exit("Use the HTTPS domain base URL without a path")
client_id = getpass.getpass("Runtime OAuth client ID: ")
if not client_id:
    sys.exit("Client ID is required")
body = {
    "schemas": ["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"],
    "name": "rpst-spike-terraform-github",
    "type": "JWT",
    "issuer": "https://token.actions.githubusercontent.com",
    "publicKeyEndpoint": "https://token.actions.githubusercontent.com/.well-known/jwks",
    "subjectType": "Resource",
    "allowImpersonation": True,
    "impersonatingResource": "github_terraform",
    "claimPropagations": ["ext_repository", "ext_workflow_ref"],
    "oauthClients": [client_id],
    "active": True,
}
result = subprocess.run(
    ["oci", "raw-request", "--profile", profile, "--auth", "security_token",
     "--http-method", "POST", "--target-uri", domain_url + "/admin/v1/IdentityPropagationTrusts",
     "--request-body", json.dumps(body)],
    capture_output=True, text=True,
)
if result.returncode:
    sys.exit("OCI CLI request failed. Check session validity and administrator permissions; response suppressed.")
response = json.loads(result.stdout)
print("HTTP status:", response["status"])
if not response["status"].startswith("2"):
    sys.exit("Trust creation failed. Check issuer uniqueness and trust settings; response suppressed.")
print("Trust ID:", response["data"]["id"])
PY
```

Run this once per domain. Before retrying after an interruption, check whether the trust already exists. If the CLI session expires, authenticate again with the same bootstrap profile. Keep debug logging disabled.

If you use an administrator OAuth application instead of signed CLI requests, keep it separate from the runtime client and follow Oracle's admin API authentication procedure. Its credentials do not belong in this demo's GitHub secrets.

## 5. Create the OCI policies

In **Identity & Security → Policies**, select the tenancy root compartment and create a policy for the demo. Replace the placeholders in these statements:

```text
Allow any-user to read objectstorage-namespaces in tenancy where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
Allow any-user to manage buckets in compartment <test-compartment> where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
```

Use tenancy level because the namespace statement grants access in the tenancy. The bucket statement grants access only in the named test compartment. Use the repository that will execute the workflow; for this reference it is `dgutierrezcolodra/oci-terraform-github-actions-wif-example`.

Allow time for IAM changes to propagate. A successful token exchange does not by itself grant access to Object Storage.

## 6. Set GitHub Actions secrets

In the executing repository, open **Settings → Secrets and variables → Actions → New repository secret** and set:

| Secret | Value |
| --- | --- |
| `RPST_DOMAIN_BASE_URL` | Test domain HTTPS base URL, no trailing slash |
| `RPST_CLIENT_ID` | Runtime application's client ID |
| `RPST_CLIENT_SECRET` | Runtime application's client secret |
| `RPST_RESOURCE_TYPE` | `github_terraform`, matching the trust |
| `RPST_COMPARTMENT_ID` | Test compartment OCID |
| `OCI_REGION` | Bucket test region; use the test domain's home region for this demo |

Use an existing `OCI_REGION` only if it is correct for the test. GitHub cannot return secret values after they are stored, so confirm the region with the repository maintainer. Preserve the UPST secrets used by the existing workflows.

Enter credentials directly in the secrets UI or transfer them through a tool's standard input. Keep client secrets, JWTs, RPSTs, and private keys out of commands, files, commits, screenshots, and job summaries.

## 7. Validate and run the demo

For a local checkout:

```bash
terraform fmt -check -recursive spike/rpst
terraform -chdir=spike/rpst init -backend=false -input=false
terraform -chdir=spike/rpst validate
actionlint .github/workflows/spike-rpst.yml
```

Init and validate need no OCI credentials and create no bucket. The workflow uses `-lockfile=readonly`; do not hand-edit the provider hashes. To regenerate the lock deliberately, use `terraform -chdir=spike/rpst providers lock -platform=linux_amd64 -platform=darwin_arm64` and review the selected version.

Once the workflow is available on the executing repository's default branch:

1. Open **Actions → Spike RPST Terraform → Run workflow**.
2. Select the branch containing the demo, choose **`plan`**, and run it.
3. Review **Phase 2 - raw RPST exchange**. Expect a 2xx status, sorted claim names, selected claim values, and `lifetime_seconds`. Payload inspection is not signature verification. Check whether `tenant` exists; the provider's tenancy handling is the main open question.
4. Review **Terraform Plan**. Expect one private bucket named `rpst-spike-<run_id>` and the namespace output.
5. Run again with **`apply-and-destroy`**, then check both outcomes in the job summary and confirm that the bucket is absent from the test compartment.
6. Record the results below.

For this reference's branch-only demo, push a change to `.github/workflows/spike-rpst.yml` or `spike/rpst/main.tf` on `spike/rpst-terraform`, then inspect the **Spike RPST Terraform** run in Actions. It runs plan, apply, and destroy in that order. The Terraform extended-runtime example and its token-refresh workflow have been removed from this branch; this demo uses a fresh source JWT before each short Terraform command.

Phase 2 has `continue-on-error`: Terraform can still run after the raw exchange fails. Read each phase's outcome separately.

## 8. Diagnose failures

| Observation | What to check |
| --- | --- |
| Dispatch unavailable | The workflow must exist on the executing repository's default branch for manual runs. Use the restricted push trigger for this branch-only demo. |
| Input validation fails | All six secrets must be set in the repository running the job. |
| Phase 2 fails | Read the printed `error` and `error_description`. Check the domain URL, active OAuth client, credentials, trust issuer uniqueness, JWKS endpoint, and `res_type` match. |
| Phase 2 passes; plan fails during authentication | Check provider or SDK RPST handling and whether `tenant` is present, or only `res_tenant`. |
| Phase 2 passes; Object Storage access is denied | Check IAM propagation, both policies, the executing repository name, and the test compartment. |
| Init reports a checksum error | Check the committed lock and Linux hashes; keep checksum validation enabled. |
| Plan and apply pass | RPST works with Terraform for this bucket demo. Record the version and check destroy separately. |
| Destroy fails or is skipped after an apply attempt | Find `rpst-spike-<run_id>` in the test compartment and remove any remaining bucket manually with an administrator account. |

Keep `TF_LOG`, shell tracing, and HTTP debug output disabled. Do not upload token responses, private keys, state, or plans as artifacts.

## 9. Clean up

The OIDC token is under `$RUNNER_TEMP/oci-wif`. The raw exchange's private key and response, Terraform data, plan, and local state are under `$RUNNER_TEMP/rpst-spike`. Sensitive files use mode 600, directories use 700, and Terraform commands use `umask 077`. Provider binaries retain the executable permissions Terraform needs.

Phase 2 removes its key and response on exit. The always-run cleanup removes both runtime directories. The client secret is supplied only to the steps that need it and is never written to `GITHUB_ENV` or a file.

The local backend's `-state` flag keeps state in the runtime directory. It is deprecated but supported by the tested CLI. Cleanup removes state even if destroy fails, so a later run cannot recover the previous run's state. Use the logged bucket name for manual cleanup.

After the demo:

1. Confirm that every demo bucket is gone. Remove any objects before deleting a bucket that is not empty.
2. Remove the five `RPST_*` repository secrets. Keep `OCI_REGION` if another workflow uses it.
3. Deactivate the test application and trust, then delete them through the domain's administration interface or documented REST API.
4. Delete only the IAM policy created for this demo.
5. Remove the test domain if it is no longer needed, following the Console's deletion requirements. Preserve the shared test compartment and pre-existing resources.

## Reference setup on 8 October 2026

The following configuration was created for this branch. The bootstrap created no bucket.

| Item | Configuration |
| --- | --- |
| Tenancy / compartment | `cloudopstenancy` / `dgcTesting` |
| Region | `eu-frankfurt-1` |
| Identity Domain | `rpst-spike-terraform`, Free, Active, hidden on sign-in page |
| Runtime application | `rpst-spike-terraform-client`, confidential, active, `client_credentials`, zero role grants |
| Trust | `rpst-spike-terraform-github`, active, `Resource`, `allowImpersonation: true` |
| Resource type / propagated claims | `github_terraform` / `ext_repository`, `ext_workflow_ref` |
| IAM policy | `rpst-spike-terraform`, tenancy root, restricted to the reference repository and `dgcTesting` |
| GitHub secrets | Five `RPST_*` secrets created; existing secrets preserved |

The domain, application settings, zero role grants, and trust were read back to verify setup. This does not prove RPST issuance or Terraform authentication. The pre-existing `OCI_REGION` value cannot be read back from GitHub. The workflow remains branch-only; Phase 2, plan, apply, and destroy have not been run.

## Results

Fill this table after each run. Record claim names and permitted diagnostic values, never complete tokens or credentials.

| Date | Provider version | Phase 2 | Plan | Apply | Destroy | RPST lifetime (s) | Claims observed | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |
