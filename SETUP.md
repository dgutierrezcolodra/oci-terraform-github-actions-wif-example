# OCI Configuration Setup Guide

This guide provides detailed, step-by-step instructions for configuring Oracle Cloud Infrastructure (OCI) to enable OIDC token exchange from GitHub Actions.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Create a Service User](#step-1-create-a-service-user)
3. [Step 2: Grant Permissions to Service User](#step-2-grant-permissions-to-service-user)
4. [Step 3: Register OAuth Client Application](#step-3-register-oauth-client-application)
5. [Step 4: Create Identity Propagation Trust Policy](#step-4-create-identity-propagation-trust-policy)
6. [Step 5: Configure GitHub Secrets](#step-5-configure-github-secrets)
7. [Step 6: Verify Configuration](#step-6-verify-configuration)
8. [Common Issues](#common-issues)

## Prerequisites

Before starting this setup, you need:

- **OCI Account** with administrator access
- **OCI Tenancy** OCID (from OCI Console → Profile → Tenancy)
- **OCI Identity Domain** (Default domain or custom)
- **Compartment** OCID where resources will be created
- **GitHub Repository** where you'll run workflows
- **Command line tools**:
  - `curl` for API calls
  - `jq` (optional, for JSON formatting)
  - `oci` CLI (optional, for verification)

## Step 1: Create a Service User

Service Users are specialized OCI accounts designed for non-interactive use cases like automation and API integrations.

### 1.1 Generate an Identity Domain Access Token

1. **Login to OCI Console**
   - Navigate to your OCI Identity Domain
   - Ensure you're in the correct domain (check top-right dropdown)

2. **Generate access token**:
   - Profile Menu → My Profile
   - Tokens and keys → My access tokens
   - Select "Invokes identity domains APIs"
   - Select `Identity Domain Administrator`
   - Choose an expiration long enough to finish setup
   - Download the generated token file
   - **IMPORTANT**: Copy only the access token value from the downloaded token file

Do not use an OAuth 2.0 client credential secret for this step. The SCIM API calls below require an `Authorization: Bearer <access_token>` header.

### 1.2 Create Service User via SCIM API

Replace placeholders in the command below:

- `<DOMAIN_URL>` → Your Identity Domain URL, including `https://`, without a trailing slash (e.g., `https://idcs-xxxxxxxxxxxx.identity.oraclecloud.com`)
- `<IDA_ACCESS_TOKEN>` → Access token from step 1.1
- `<SERVICE_USER_NAME>` → Desired username (e.g., `github-actions-prod`)

```bash
curl -X POST \
  "<DOMAIN_URL>/admin/v1/Users" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <IDA_ACCESS_TOKEN>" \
  -d '{
"schemas": [
  "urn:ietf:params:scim:schemas:core:2.0:User",
  "urn:ietf:params:scim:schemas:oracle:idcs:extension:user:User"
],
"urn:ietf:params:scim:schemas:oracle:idcs:extension:user:User": {
  "serviceUser": true
},
"userName": "<SERVICE_USER_NAME>"
}'
```

**Expected Response**:

```json
{
  "id": "...",
  "ocid": "ocid1.user.oc1..aaaaaaa...",
  "userName": "github-actions-prod",
  ...
}
```

**IMPORTANT**: Save the `id` value (the short GUID) - you'll need it for the trust policy in Step 4. The `ocid` is NOT used for the trust policy value.

### 1.3 Verify Service User Creation

Via OCI Console:

1. Navigate to Identity & Security → Domains → Default domain
2. Click "Users" in left menu
3. Search for your service user name
4. Verify "User Type" shows "Service User"

## Step 2: Grant Permissions to Service User

Service Users need permissions to create and manage OCI resources. This is accomplished through group membership and IAM policies.

### 2.1 Create or Identify an IAM Group

#### Option A: Create a New Group

1. **In OCI Console**:
   - Identity & Security → Domains → Default domain
   - Groups → Create Group
   - Name: `GitHubAutomationUsers`
   - Description: `Group for GitHub Actions service users`

2. **Add Service User to Group**:
   - Click the group name
   - Group members → Add user to group
   - Search for your service user
   - Click "Add"

#### Option B: Use Existing Group

If you have an existing group with appropriate permissions:

1. Navigate to the group
2. Add your service user as a member

### 2.2 Create IAM Policies

Create an IAM policy to grant the group permissions in your target compartment.

**For this example (Object Storage bucket creation)**:

1. **Navigate to Policies**:
   - Identity & Security → Policies
   - Select your compartment
   - Click "Create Policy"

2. **Policy Details**:
   - Name: `github-automation-objectstorage-policy`
   - Description: `Allows GitHub Actions to manage Object Storage`
   - Compartment: Select your target compartment

3. **Policy Statements**:

   ```
   Allow group GitHubAutomationUsers to manage buckets in compartment <compartment-name>
   Allow group GitHubAutomationUsers to manage objects in compartment <compartment-name>
   Allow group GitHubAutomationUsers to read objectstorage-namespaces in compartment <compartment-name>
   ```

   Replace `<compartment-name>` with your compartment name.

4. **Click "Create"**

**For broader access** (compute, networking, etc.):

```
Allow group GitHubAutomationUsers to manage all-resources in compartment <compartment-name>
```

⚠️ **Security Best Practice**: Grant only the minimum permissions required for your use case.

## Step 3: Register OAuth Client Application

The OAuth client represents the GitHub Action that will perform token exchange.

### 3.1 Create Confidential Application

1. **Navigate to Applications**:
   - Identity & Security → Domains → Default domain
   - Applications → Add application
   - Select "Confidential Application"

2. **Application Details**:
   - Name: `github-token-exchange-client`
   - Click "Next"

3. **Client Configuration**:
   - **Configure OAuth**:
     - Check "Configure this application as a client now"
     - **Allowed Grant Types**: Check "Client credentials"
     - **Client Type**: Confidential
   - Click "Next"

4. **Resources (Skip)**:
   - Click "Next" (no resources needed)

5. **Authorization (IMPORTANT)**:
   - **DO NOT assign any domain roles**
   - Leave all role assignments empty
   - This is a security best practice

6. **Finish**:
   - Click "Finish"

### 3.2 Save Client Credentials

After creation, you'll see:

- **Client ID**: `abc123def456...`
- **Client Secret**: Click "Show secret" to reveal

**Format for GitHub secret**:

```
Client ID:Client Secret
```

Example: If Client ID is `abc123` and Client Secret is `secret456`, the value is:

```
abc123:secret456
```

**IMPORTANT**: Save both values immediately. The secret cannot be retrieved later.

### 3.3 Verify OAuth Client Credentials

Before proceeding, verify your credentials work by testing with a simple token request:

```bash
curl -X POST "<DOMAIN_URL>/oauth2/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "<CLIENT_ID>:<CLIENT_SECRET>" \
  -d "grant_type=client_credentials&scope=urn:opc:idm:__myscopes__"
```

**Expected Response**: A JSON object containing `access_token`.

**If you get `invalid_client`**: The credentials are incorrect. Re-check the Client ID and Secret in the OCI Console, or regenerate the secret.

> **Note**: If you have multiple OAuth applications (e.g., `DomainAdminOAuthClient`, `TokenExchangeOAuthClient`), ensure you are using the credentials from the correct application intended for token exchange.

### 3.4 Long-Running Operations

OCI IAM Workload Identity Federation exchanges the GitHub OIDC JWT for a short-lived OCI UPST. Do not assume that changing an OAuth application's `accessTokenExpiry` changes the lifetime of the UPST returned by JWT-to-UPST token exchange.

For long-running Terraform jobs, enable the action's built-in token refresh:

```yaml
- name: Configure OCI Authentication
  uses: ./oci-token-exchange
  with:
    oidc_client_identifier: ${{ secrets.OIDC_CLIENT_IDENTIFIER }}
    domain_base_url: ${{ secrets.DOMAIN_BASE_URL }}
    oci_tenancy: ${{ secrets.OCI_TENANCY }}
    oci_region: ${{ secrets.OCI_REGION }}
    enable_token_refresh: true
    refresh_interval_minutes: 50
```

The repository includes the `Demo Terraform Token Refresh` workflow and the `examples/long-running-refresh/` Terraform example to demonstrate this pattern during a running `terraform apply`. This is intended for operations that keep Terraform active for a long time, such as VM Cluster provisioning or other resources that require extended polling.

## Step 4: Create Identity Propagation Trust Policy

This trust policy tells OCI to accept and validate OIDC tokens from GitHub Actions.

### 4.1 Prepare Information

You'll need:

- **Domain URL**: From Step 1.1
- **Access token**: Identity Domain access token from Step 1
- **OAuth Client ID**: From Step 3.2
- **Service User ID**: From Step 1.2 (the short GUID, e.g., `a2536435...`)
- **GitHub Repository**: Your org/repo name (e.g., `myorg/myrepo`)

**If you didn't save the Service User ID from Step 1.2**, retrieve it now:

```bash
curl --request GET \
  --url "<DOMAIN_URL>/admin/v1/Users?attributes=id,userName,ocid&filter=userName%20eq%20%22<SERVICE_USER_NAME>%22" \
  --header "authorization: Bearer <IDA_ACCESS_TOKEN>" \
  --header "content-type: application/scim+json"
```

Replace `<YOUR_SERVICE_USER_NAME>` with the username you created (e.g., `github-actions-prod`).

The response will include:

- `id` - **This is what you need** (short GUID like `a2536435...`)
- `ocid` - Not used in trust policy
- `userName` - The service user's name

### 4.2 Create Trust Policy via SCIM API

⚠️ **IMPORTANT**: The `value` field in `impersonationServiceUsers` must be the **Service User's ID** (short GUID), **NOT** the OCID.

Replace placeholders in the command below:

> 💡 **For first-time setup**: Use `"rule": "sub eq *"` (universal wildcard) to match ALL GitHub tokens. This simplifies initial testing. After confirming it works, switch to specific repository/branch rules for production.

**Option A: Universal Wildcard (Recommended for Testing)**

```bash
curl --request POST \
--url "<DOMAIN_URL>/admin/v1/IdentityPropagationTrusts" \
--header 'authorization: Bearer <IDA_ACCESS_TOKEN>' \
--header 'content-type: application/json' \
--data '{
"active": true,
"allowImpersonation": true,
"issuer": "https://token.actions.githubusercontent.com",
"name": "github-actions-trust",
"oauthClients": ["OAUTH_CLIENT_ID"],
"publicKeyEndpoint": "https://token.actions.githubusercontent.com/.well-known/jwks",
"subjectClaimName": "sub",
"subjectMappingAttribute": "userName",
"subjectType": "User",
"type": "JWT",
"schemas": ["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"],
"impersonationServiceUsers": [
{
"rule": "sub eq *",
"value": "YOUR_SERVICE_USER_ID"
}
]
}'
```

**Option B: Specific Repository Rules (Recommended for Production)**

```bash
curl --request POST \
--url "<DOMAIN_URL>/admin/v1/IdentityPropagationTrusts" \
--header 'authorization: Bearer <IDA_ACCESS_TOKEN>' \
--header 'content-type: application/json' \
--data '{
"active": true,
"allowImpersonation": true,
"issuer": "https://token.actions.githubusercontent.com",
"name": "github-actions-trust",
"oauthClients": ["OAUTH_CLIENT_ID"],
"publicKeyEndpoint": "https://token.actions.githubusercontent.com/.well-known/jwks",
"subjectClaimName": "sub",
"subjectMappingAttribute": "userName",
"subjectType": "User",
"type": "JWT",
"schemas": ["urn:ietf:params:scim:schemas:oracle:idcs:IdentityPropagationTrust"],
"impersonationServiceUsers": [
{
"rule": "sub eq '\''repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:ref:refs/heads/main'\''",
"value": "YOUR_SERVICE_USER_ID"
},
{
"rule": "sub eq '\''repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:*'\''",
"value": "YOUR_SERVICE_USER_ID"
}
]
}'
```

**Parameter Explanations**:

- `issuer`: Must exactly match GitHub's OIDC issuer
- `oauthClients`: Array containing your OAuth client ID from Step 3
- `publicKeyEndpoint`: GitHub's JWKS endpoint for JWT signature verification
- `impersonationServiceUsers`: Rules mapping JWT claims to Service Users
  - **IMPORTANT**: The `value` field must be the **Service User's ID** (the short GUID, e.g., `a2536435...`), **NOT** the OCID.

### 4.3 Impersonation Rule Syntax

Impersonation rules use a specific syntax to match JWT claims. Understanding this syntax is critical for successful token exchange.

#### Rule Format

```
claim_name operator value
```

| Component | Description | Examples |
|-----------|-------------|----------|
| `claim_name` | JWT claim to match | `sub`, `grp`, `aud` |
| `operator` | Comparison operator | `eq` (equals), `co` (contains) |
| `value` | Value to match against | `*`, `'repo:org/repo:*'` |

#### Operators

| Operator | Meaning | Wildcard Support |
|----------|---------|------------------|
| `eq` | Equals | ✅ Yes (`*` matches any value) |
| `co` | Contains | ❌ No |

> ⚠️ **CRITICAL**: Do NOT use `"rule": "true"` - this is **invalid syntax** and will cause "No rules matched" errors. The correct universal match rule is `"rule": "sub eq *"`.

### 4.4 Impersonation Rules Examples

**Match ALL tokens (universal wildcard - recommended for testing)**:

```json
{
  "rule": "sub eq *",
  "value": "a1b2c3d4e5f6..."
}
```

> **Note**: The universal wildcard `sub eq *` (without quotes around `*`) matches any GitHub token. Use this for initial testing, then restrict to specific repositories/branches for production.

**Match specific branch**:

```json
{
  "rule": "sub eq 'repo:myorg/myrepo:ref:refs/heads/main'",
  "value": "a1b2c3d4e5f6..."
}
```

**Match any branch in repo** (using wildcard in value):

```json
{
  "rule": "sub eq 'repo:myorg/myrepo:*'",
  "value": "a1b2c3d4e5f6..."
}
```

**Match specific environment**:

```json
{
  "rule": "sub eq 'repo:myorg/myrepo:environment:production'",
  "value": "a1b2c3d4e5f6..."
}
```

**Multiple rules** (first match wins):

```json
"impersonationServiceUsers": [
  {
    "rule": "sub eq 'repo:myorg/myrepo:ref:refs/heads/main'",
    "value": "a1b2c3d4e5f6111"
  },
  {
    "rule": "sub eq 'repo:myorg/myrepo:ref:refs/heads/develop'",
    "value": "a1b2c3d4e5f6222"
  },
  {
    "rule": "sub eq *",
    "value": "a1b2c3d4e5f6333"
  }
]
```

> **Tip**: Place more specific rules first. The universal wildcard `sub eq *` should be last as a fallback.

### 4.5 Verify Trust Policy Creation

**Via OCI Console**:

1. Identity & Security → Domains → Default domain
2. Security → Identity propagation
3. Look for "github-actions-trust"
4. Verify status is "Active"

**Via API - Verify Trust Policy exists**:

```bash
curl -s -H "Authorization: Bearer $IDA_ACCESS_TOKEN" \
  "$DOMAIN_URL/admin/v1/IdentityPropagationTrusts/<TRUST_ID>" | jq '{name, active, issuer}'
```

**Expected Response**:

```json
{
  "name": "github-actions-trust",
  "active": true,
  "issuer": "https://token.actions.githubusercontent.com"
}
```

> ⚠️ **CRITICAL VERIFICATION**: The `impersonationServiceUsers` field is **NOT returned in normal GET requests**. You MUST explicitly request it:

```bash
curl -s -H "Authorization: Bearer $IDA_ACCESS_TOKEN" \
  "$DOMAIN_URL/admin/v1/IdentityPropagationTrusts/<TRUST_ID>?attributes=impersonationServiceUsers" | jq .
```

**Expected Response with impersonationServiceUsers**:

```json
{
  "id": "...",
  "impersonationServiceUsers": [
    {
      "rule": "sub eq *",
      "value": "a2536435eade42dfa31be448e30b81ce",
      ...
    }
  ]
}
```

**If `impersonationServiceUsers` is `null` or missing**: The rules were not saved. Re-run the POST command from Step 4.2 with correct syntax.

## Step 5: Configure GitHub Secrets

### 5.1 Navigate to Repository Settings

1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions

### 5.2 Create Repository Secrets

Click "New repository secret" for each:

| Name | Value | Example |
|------|-------|---------|
| `OIDC_CLIENT_IDENTIFIER` | `client_id:client_secret` from Step 3.2 | `abc123:secret456` |
| `DOMAIN_BASE_URL` | Identity Domain URL (without trailing slash) | `https://idcs-xxxxxx.identity.oraclecloud.com` |
| `OCI_TENANCY` | Your tenancy OCID | `ocid1.tenancy.oc1..aaaaaaa...` |
| `OCI_REGION` | Your OCI region identifier | `us-ashburn-1` |
| `COMPARTMENT_ID` | Compartment OCID for resources | `ocid1.compartment.oc1..aaaaaaa...` |

**Note**: The included workflows use `OCI_TENANCY`. If you prefer the name `OCI_TENANCY_OCID`, update the workflow inputs to reference `secrets.OCI_TENANCY_OCID`.

**Finding OCIDs**:

- **Tenancy OCID**: Profile Menu → Tenancy → Copy OCID
- **Compartment OCID**: Identity & Security → Compartments → Select compartment → Copy OCID

### 5.3 Optional: Use Variables for Non-Sensitive Values

You can use **Repository Variables** instead of **Secrets** for non-sensitive configuration values. This makes them easier to view and manage without compromising security.

**Recommended as Variables** (Settings → Secrets and variables → Actions → Variables tab):

- `OCI_REGION` - Region identifier (e.g., `us-ashburn-1`)
- `DOMAIN_BASE_URL` - Identity Domain URL (e.g., `https://idcs-xxxx.identity.oraclecloud.com`)

**Must Remain as Secrets**:

- `OIDC_CLIENT_IDENTIFIER` - Contains client credentials
- `OCI_TENANCY` - Exposes account structure
- `COMPARTMENT_ID` - Potentially sensitive

**Key Differences**:

- **Secrets**: Values are masked in logs (`***`), cannot be viewed after creation
- **Variables**: Values are visible in repository settings and logs, easier to manage

⚠️ **Important**: If you use variables, update your workflow file to reference them with `${{ vars.VARIABLE_NAME }}` instead of `${{ secrets.VARIABLE_NAME }}`.

## Step 6: Verify Configuration

### 6.1 Test the Workflow

1. **Trigger Workflow**:
   - Go to Actions tab
   - Select "Demo Terraform Apply (Standard)"
   - Click "Run workflow"
   - Select branch: `main`
   - Select action: `plan`
   - Provide compartment_id (or use secret)
   - Click "Run workflow"

2. **Check Logs**:
   - Click on the running workflow
   - Expand "Configure OCI Authentication" step
   - Look for: `Got OCI session token`
   - Look for: `Config saved to`

3. **Verify Terraform**:
   - Expand "Terraform Plan" step
   - Should see: `Plan: 1 to add, 0 to change, 0 to destroy`
   - No authentication errors

### 6.2 Verify OCI Audit Logs

1. **Navigate to Audit**:
   - Observability & Management → Audit
   - Select your compartment

2. **Check for Events**:
   - Look for events with:
     - Principal ID: Your Service User OCID
     - Source: `oauth2`
     - Event Type: `com.oraclecloud.identitycontrolplane.createtoken`

3. **Verify Context**:
   - Audit logs should show the original GitHub context in additional details

## Common Issues

### Issue: "No rules matched from given token to find impersonation user"

**Error**: `{"error":"unauthorized_client","error_description":"No rules matched from given token to find impersonation user."}`

This is one of the most common errors when setting up OCI token exchange. It means OCI received your token but couldn't find a matching impersonation rule.

**Possible Causes**:

1. **Invalid rule syntax** - Using `"rule": "true"` instead of proper syntax
2. **Rule doesn't match the GitHub token's `sub` claim**
3. **impersonationServiceUsers not saved** (API silently fails sometimes)

**Solutions**:

1. **Use correct rule syntax**:

   ```json
   // ❌ WRONG - Invalid syntax
   {"rule": "true", "value": "..."}

   // ✅ CORRECT - Universal wildcard
   {"rule": "sub eq *", "value": "..."}

   // ✅ CORRECT - Specific repo
   {"rule": "sub eq 'repo:org/repo:*'", "value": "..."}
   ```

2. **Verify impersonationServiceUsers is actually saved**:

   ```bash
   curl -s -H "Authorization: Bearer $IDA_ACCESS_TOKEN" \
     "$DOMAIN_URL/admin/v1/IdentityPropagationTrusts/<TRUST_ID>?attributes=impersonationServiceUsers" | jq .
   ```

   > **Note**: The `impersonationServiceUsers` field is NOT returned in normal GET requests. You must explicitly request it with `?attributes=impersonationServiceUsers`.

3. **For testing, use the universal wildcard**:

   ```json
   {"rule": "sub eq *", "value": "YOUR_SERVICE_USER_ID"}
   ```

   This matches ALL GitHub tokens. Once confirmed working, switch to more specific rules.

4. **Check the GitHub token's actual `sub` claim** - Add a debug step to your workflow to see what claim value GitHub sends.

### Issue: "401 Unauthorized" during token exchange

**Possible Causes**:

- OAuth client credentials incorrect
- OAuth client not listed in trust policy
- Trust policy inactive

**Solutions**:

1. Verify `OIDC_CLIENT_IDENTIFIER` is formatted correctly: `client_id:client_secret`
2. Check OAuth client ID matches value in trust policy's `oauthClients` array
3. Verify trust policy `active` is `true`

### Issue: "invalid_client" - Client authentication failed

**Error**: `{"error":"invalid_client","error_description":"Client authentication failed."}`

**Cause**: The OAuth Client ID or Client Secret is incorrect.

**Solutions**:

1. **Verify the correct OAuth application**:
   - Navigate to Identity & Security → Domains → Default domain → Applications
   - If you have multiple applications (e.g., `DomainAdminOAuthClient`, `TokenExchangeOAuthClient`), ensure you're using the credentials from the **token exchange** application, not the admin client.

2. **Check Client Secret**:
   - Open the OAuth application → OAuth Configuration → Show secret
   - Compare with the value in your GitHub secret `OIDC_CLIENT_IDENTIFIER`
   - If the secret was regenerated, update the GitHub secret

3. **Regenerate and update**:
   - Click "Regenerate secret" in OCI Console
   - Copy the new Client ID and Client Secret
   - Update GitHub secret: `client_id:client_secret`

4. **Test credentials manually**:

   ```bash
   curl -X POST "<DOMAIN_URL>/oauth2/v1/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -u "<CLIENT_ID>:<CLIENT_SECRET>" \
     -d "grant_type=client_credentials&scope=urn:opc:idm:__myscopes__"
   ```

   If this returns `access_token`, the credentials are correct.

### Issue: "403 Forbidden" when creating resources

**Possible Causes**:

- Service User lacks permissions
- Trust policy impersonation rule doesn't match
- Wrong compartment OCID

**Solutions**:

1. Verify Service User is member of group with necessary IAM policies
2. Check impersonation rule matches your repository/branch exactly
3. Use `sub eq 'repo:org/repo:*'` wildcard rule for testing
4. Verify compartment OCID is correct

### Issue: Trust policy validation errors

**Error**: `Invalid issuer`

**Solution**: Issuer must be exactly `https://token.actions.githubusercontent.com`

**Error**: `Invalid public key endpoint`

**Solution**: Endpoint must be exactly `https://token.actions.githubusercontent.com/.well-known/jwks`

**Error**: `Invalid ID in impersonation rules`

**Solution**: Verify Service User ID format is a GUID (e.g., `a2536435...`) and NOT an OCID (`ocid1.user...`) or username.

### Issue: JWT token validation fails

**Possible Causes**:

- GitHub repository/ref doesn't match impersonation rule
- JWT expired (shouldn't happen in normal flow)
- Public key verification failed

**Solutions**:

1. Check workflow logs for actual `sub` claim value
2. Update impersonation rule to match exactly
3. Consider using wildcard rule: `sub eq 'repo:org/repo:*'`

### Issue: Identity Domain access token expired

**Symptoms**: SCIM API calls return 401

**Solution**:

1. Identity Domain access tokens expire after the configured duration
2. Generate a new access token (Step 1.1)
3. These access tokens are only needed for initial setup, not for runtime

### Issue: Can't find Identity Domain

**Problem**: Working in wrong domain or tenancy

**Solution**:

1. Verify you're in the correct OCI tenancy (top-right dropdown)
2. Check you're viewing the correct Identity Domain
3. Default domain is usually sufficient for most users

### Issue: Service User not showing up

**Problem**: Service User created but not visible

**Solutions**:

1. Refresh the Users page
2. Check you're in the correct Identity Domain
3. Try filtering by "Service" user type
4. Verify API call succeeded (check response)

## Security Best Practices

1. **Least Privilege**: Grant only required permissions to Service Users
2. **Scope Trust Policies**: Use specific impersonation rules, not wildcards in production
3. **Rotate Credentials**: Regularly rotate OAuth client secrets
4. **Monitor Audit Logs**: Set up monitoring for Service User activities
5. **Separate Environments**: Use different Service Users for dev/staging/prod
6. **Review Permissions**: Periodically audit Service User group memberships

## Additional Resources

- [OCI JWT-to-UPST Token Exchange](https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm)
- [OCI Identity Domains Documentation](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
- [SCIM API Reference](https://docs.oracle.com/en-us/iaas/Content/Identity/scim/scim-api.htm)
- [Identity Propagation Trust Policies](https://docs.oracle.com/en-us/iaas/Content/Identity/identitypropagationtrust/manage-identity-propagation-trust.htm)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

## Getting Help

If you encounter issues:

1. **Check this guide** - Most common issues are documented above
2. **Review workflow logs** - Often contain specific error messages
3. **Check OCI Audit logs** - Show what authentication attempts occurred
4. **Open an issue** - If you believe there's a bug or missing documentation

---

**Next Steps**: Once setup is complete, return to [README.md](./README.md) to run your first workflow.
