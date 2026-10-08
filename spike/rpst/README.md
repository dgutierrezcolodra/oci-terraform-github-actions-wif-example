# RPST Terraform spike

This is a throwaway test of provider-native OCI Workload Identity Federation with an ephemeral RPST. It is not for production.

Run **Spike RPST Terraform** manually in GitHub Actions. Phase 2 exchanges a GitHub OIDC JWT for an RPST with curl and reports the HTTP status, selected claim names and values, and lifetime. Phase 3 runs Terraform against one Object Storage bucket. The default `plan` action creates nothing. `apply-and-destroy` applies the saved plan and always attempts to destroy the bucket afterward.

| Observation | Likely area to investigate |
| --- | --- |
| Phase 2 fails | OCI trust, OAuth client, issuer uniqueness in the domain, or `res_type` mismatch. |
| Phase 2 passes; plan fails | Provider or SDK handling of RPST. Check whether the RPST has a `tenant` claim. |
| Plan and apply pass | Provider-native RPST works with Terraform for this bucket test. Confirm destroy separately. |

## OCI prerequisites

Use a **separate test Identity Domain** because OCI expects a unique issuer per domain and the production domain already has an active GitHub trust with `subjectType: User`.

1. Create and activate a confidential application with the Client Credentials grant and no admin roles.
2. Create an active Identity Propagation Trust with `type: JWT`, `issuer: https://token.actions.githubusercontent.com`, `publicKeyEndpoint: https://token.actions.githubusercontent.com/.well-known/jwks`, `subjectType: Resource`, `impersonatingResource: github_terraform`, `claimPropagations: ["ext_repository", "ext_workflow_ref"]`, and the application's client ID in `oauthClients`. The `ext_` names follow the [A-Team RPST example](https://www.ateam-oracle.com/oci-workload-identity-federation-using-ephemeral-rpst).
3. Create these policies, replacing `<owner>/<repo>` and `<test-compartment>`:

   ```text
   Allow any-user to read objectstorage-namespaces in tenancy where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
   Allow any-user to manage buckets in compartment <test-compartment> where all {request.principal.type='identityfederateddomainapp', request.principal.ext_repository='<owner>/<repo>'}
   ```

4. Set repository secrets `RPST_DOMAIN_BASE_URL` (test domain URL without a trailing slash), `RPST_CLIENT_ID`, `RPST_CLIENT_SECRET`, `RPST_RESOURCE_TYPE` (`github_terraform`), `RPST_COMPARTMENT_ID`, and `OCI_REGION`.

## Results

| Date | Provider version | Phase 2 | Plan | Apply | Destroy | RPST lifetime (s) | Claims observed | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |
