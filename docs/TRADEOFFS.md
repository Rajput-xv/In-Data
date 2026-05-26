# TRADEOFFS.md - Three things I deliberately did not build

Three things I would normally have built and didn't, with the reason and the cost of leaving them out.

---

## 1. Async ingestion pipeline (Celery / RQ)

### What I didn't build
A worker that picks up uploaded files, processes them off the request thread, and reports progress via webhook or polling.

### What I did instead
`ingestion.services.ingest()` parses, normalizes, validates, and saves inside the request - the analyst's upload returns the completed batch. A 500-row SAP file finishes in under a second on SQLite.

### Why
- **No real load profile.** The brief is for a prototype with hand-fabricated sample files. The largest file is 14 rows. Introducing Celery for that workload is infrastructure theatre.
- **Async makes the failure surface bigger, not smaller.** With sync ingest the failure mode is "HTTP 500, retry the upload." With Celery it's "task got queued, worker crashed mid-row, batch is half-ingested, analyst doesn't know." That's a worse experience for any file size that doesn't strictly need a worker.
- **The function signature doesn't change when this gets promoted.** `ingest(source, content, filename, uploaded_by)` is the same call whether it runs in-thread or behind `delay()`. Switching costs are bounded.

### Where this hurts
- Files over ~10k rows will time out behind Render's default gunicorn timeout. Triggers: a real SAP year-end dump (~50k rows of postings) or a procurement spend export.
- Re-ingestion is synchronous too. Hammering the upload endpoint at scale would block the dev server. For the prototype this is fine; for GA it's the day-one promotion.

### When I'd add it
- First client with a recurring batch > ~5k rows.
- Or first time a parser needs to call an external service (e.g., FX rate lookup per row) - that's an I/O profile sync can't justify.

---

## 2. Real authentication and authorisation

### What I didn't build
SSO via Okta / Azure AD / Google Workspace. Role-based permissions (junior analyst vs senior auditor). Password storage. CSRF beyond Django defaults. Session expiry / refresh tokens.

### What I did instead
- A single-email gate on the SPA. Route `/` shows a login card; the entered email is compared against `VITE_ANALYST_EMAIL` and, on match, persisted in `sessionStorage`. Closing the tab logs out.
- The three protected routes (`/batches`, `/review`, `/upload`) are wrapped in a `<Protected>` element that redirects to `/` if the session has no email.
- Every API call carries the session email as `X-Analyst-Email`. The backend reads this header (falling back to `ANALYST_EMAIL` env if the header is absent) and stamps it onto `ApprovalAction.analyst`.
- No impersonation check - the backend trusts whatever the header asserts. The gate is a demo affordance, not a security boundary.

### Why
- **Auth is a half-day, the data model is the brief.** The hard part of the work - and the part being evaluated - is shape, lineage, and defensibility. Building login forms doesn't make the data model better; it just consumes the runway.
- **Single-tenant means there's no cross-tenant blast radius.** The only person who can attack this prototype is someone with network access to it, and the prototype isn't internet-exposed during review.
- **Auth shape depends on the client's identity provider.** Building it speculatively in Django allauth without knowing whether the real answer is Okta SAML, Azure AD OIDC, or a corporate Keycloak means re-doing it later.

### Where this hurts
- Approval lineage is honest about whoever the header says they are. If someone changes the header to a colleague's email, the action goes in under that name.
- No write protection against unauthenticated callers. The prototype trusts the network.
- Audit logs aren't tied to an authenticated session - they're tied to a self-asserted email. Real auditors would reject this.

### When I'd add it
- Day one of any external deployment beyond demo. Not before.

---

## 3. Emission factor calculation

### What I didn't build
A library of emission factors (per fuel type, per kWh by grid region, per flight km, per hotel night by city), the math that multiplies `NormalizedActivity.quantity` by the factor to get `kgCO2e`, and the reporting UI that aggregates those numbers by Scope.

### What I did instead
Stored the inputs the carbon engine needs: canonical quantity, canonical unit, scope, period, location, currency, raw payload. Nothing here prevents a downstream service from doing the math; everything here makes that math reproducible.

### Why
- **The brief is explicit.** "The hard part of our job isn't computing carbon - it's that every client's data lives somewhere different." Investing the prototype's surface area into computing carbon contradicts the framing.
- **Emission factors are a separate problem with its own data model.** DEFRA, EPA, IEA, ecoinvent - each is a different source with different versioning. The right shape is `EmissionFactor(scope, activity_type, region, valid_from, valid_to, value, unit, source)` joined at report time. Embedding that into `NormalizedActivity` would make every row larger and tie ingestion to a factor library version.
- **Computed-on-the-fly hides versioning bugs.** If we stored kgCO2e alongside the quantity at ingest time, and a year later DEFRA updates their fuel factor, we'd have rows in the DB that look authoritative but were computed with stale factors. Keeping the math out keeps the inputs honest.

### Where this hurts
- The analyst dashboard shows "1,245 L of diesel" but cannot show "0.92 tCO2e". For a non-technical reviewer this might feel like the thing missing.
- Demoability suffers - there is no "total emissions" tile on the dashboard. I made the call that defensibility beats demo polish.

### When I'd add it
- Once the factor data model is its own design exercise (probably its own service). The interface from this app stays the same: ship approved `NormalizedActivity` rows to the factor service, get back per-row kgCO2e.

