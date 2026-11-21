# Proposed Azure resources — approval pending

**No resources have been provisioned.** This is a concrete reviewable POC plan, not a billing quote, spending cap or production architecture. There is no assumption of student credits, free-tier eligibility or a pre-existing subscription.

## Region and sizing

Proposed region: **East US 2 (`eastus2`)** for the app, PostgreSQL, storage and VNet. SWA serves static assets through its distributed platform. Private DNS is a global ARM resource. This common supported-region baseline simplifies the plan; it is **not a data-residency guarantee or a decision that India hosting is unnecessary**. Confirm the permitted geography before approval. If Central India or another region is required, change parameters, recheck SWA/backend support and reprice before provisioning.

| Proposed resource | Configuration | Approximate USD/month |
|---|---|---:|
| Azure Static Web Apps | Standard; linked App Service API | 9.00 |
| App Service Linux plan + web app | B1, one worker, Python 3.12 source deployment | 12.41 |
| PostgreSQL Flexible Server compute | B1ms Burstable, PostgreSQL 17, no HA | 12.41 |
| PostgreSQL storage | 32 GB, 7-day local backup policy | 3.68 |
| Blob Storage | Standard LRS / Hot; 5 GB planning volume | 0.09 |
| Blob private endpoint | One endpoint, 730 hours/month | 7.30 |
| Private DNS | Two zones, first pricing tier | 1.00 |
| VNet/subnets + managed identity + scoped role | Networking/identity configuration; no NAT/VM | No separately priced baseline item |
| **Estimated base** | 730-hour month, USD retail consumption rates | **45.89** |

Allow **US$50–60/month for planning**, before tax, currency conversion and workload-dependent overages. This range is not a guarantee or automatic shutdown threshold. Retail API meter IDs/rates and quantities are saved in `artifacts/azure/cost-estimate.json`, with raw snapshots beside it. Actual subscription agreement prices may differ. Reconfirm the quote with Azure Pricing Calculator and the subscription owner immediately before approval.

The source is the [Microsoft Azure Retail Prices API](https://prices.azure.com/api/retail/prices), accessed **22 October 2026**. Computation: Linux B1 `$0.017 × 730`; PostgreSQL B1ms `$0.017 × 730`; PG storage `$0.115 × 32`; Blob Hot LRS `$0.0184 × 5`; global Standard Private Endpoint `$0.01 × 730`; first-tier Private Zone `$0.50 × 2`; SWA Standard `$9/month`. No reservation, subscription discount, student benefit or free resource allowance was assumed. The private endpoint is the global commercial meter; DNS monthly-zone interpretation follows Azure DNS pricing. API effective dates are meter effective dates, not the access date.

## Exclusions and cost risks

Taxes, exchange rates, data transfer, Blob/API/DNS operations, backup growth, retained versions/soft-deleted blobs, AI usage, paid GitHub features/overages, monitoring add-ons, custom domains, enterprise support and HA are outside the base. Storage auto-grow is enabled and can raise the bill. Backups/versions can accumulate. Stopping the web app does not necessarily stop App Service plan charges; database/storage/network charges have separate lifecycles. Set subscription budget alerts, and agree on a POC end date/resource-retention policy before provisioning; a budget alert is not a spending cap.

**Private database administration requires network access.** An existing authorized VNet-connected operator environment is a prerequisite. If a new VM, VPN, Bastion or self-hosted runner is needed, its cost and access must be proposed separately; it is not hidden in the $45.89 baseline. This prerequisite must be resolved before approving the plan. No such host was provisioned.

Azure OpenAI and Document Intelligence are **optional and omitted from the template/base cost**. They stay disabled. Enabling them requires approved resources, model capacity/region, identity permissions and a separate usage budget; do not assume free AI capacity.

## Required subscription details before any paid action

1. Explicit approval of the region, listed resources, recurring-cost range, variable-cost exclusions and the intended POC duration.
2. Azure **subscription ID** and **tenant ID**, confirmation of billing-owner authorization and an approved dedicated **resource group** (or explicit authorization to create one).
3. Existing Entra database-administrator **group/user object ID and name**, its tenant owner approval, and an operator identity authorized to run the SQL-principal bootstrap from an approved private-network host.
4. Confirmation that required providers, Python/runtime/SKU capacity and regional policies permit this plan. Contributor-level deployment rights plus scoped role-assignment rights are needed; no subscription-wide runtime privilege is requested.
5. If GitHub deployment is desired: repository identity, approved OIDC deployment principal/client ID, protected `azure-poc` environment and its reviewers, nonsecret repository variables, and permission to configure/run the manual workflows. Runtime managed identity and GitHub deployment identity are separate.
6. Any required data geography, custom domain, retention/backup target, usage ceilings and resource naming constraints.

**Do not send passwords, API keys, deployment tokens, private keys or connection-string secrets in chat.** Setup uses managed identity where supported and interactive/operator-managed application passwords. This task prepared files and performed local tests only; the subscription was not accessed to provision or deploy.
