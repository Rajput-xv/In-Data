# DECISIONS.md - Ambiguities I resolved

Every place the brief didn't pin down. Each entry is **what I chose**, **why**, and **what I'd ask the PM** if I had fifteen minutes.

Each call is mine. If I get asked "why X?" in the interview, the answer is here - not "AI suggested it".

---

## A. Scope of the prototype

### A1. Single-tenant or multi-tenant?
- **Chose:** single. One client, one workspace. No `Organization` table.
- **Why:** the brief says "we're onboarding a new enterprise client" - singular. Wiring tenant scoping for one tenant creates a false sense of isolation without the test surface to prove it works.
- **Ask PM:** *"At GA, will this be one workspace per client or one workspace with several clients side-by-side? The schema change is bounded if I know now."*

### A2. Who is the analyst?
- **Chose:** a single-email gate on the SPA. Route `/` shows a login card; the entered email is compared to `VITE_ANALYST_EMAIL`, and on match stored in `sessionStorage`. The three protected routes (`/batches`, `/review`, `/upload`) redirect back to `/` if no session email is present. Every API request carries `X-Analyst-Email` from the session; backend falls back to `ANALYST_EMAIL` env if the header is absent. `ApprovalAction.analyst` records whichever email the request asserted.
- **Why:** SSO / JWT / allauth is a half-day distraction from the data model, which is what the brief weighs. The gate is enough to (a) demo who's making decisions and (b) tag every `ApprovalAction` with a real email for the audit trail. It is **not** a security boundary - anyone with the env value can sign in.
- **Ask PM:** *"Is analyst SSO via Okta, Azure AD, or whatever the client brings? Will analysts have role tiers (junior approves warnings, senior approves errors)?"*

---

## B. SAP source

### B1. IDoc, OData, BAPI, or flat file?
- **Chose:** flat-file CSV (semicolon-delimited).
- **Why:** SAP Gateway / OData access requires SAP Basis admin work that enterprise IT doesn't grant inside an onboarding window. IDoc requires a partner profile and a network landing zone. The realistic onboarding deliverable is the SAP consultant running `SE16N` or `SQ01` and emailing a file.
- **Ask PM:** *"When we land a client, who do we talk to - the SAP consultant directly, or facilities relaying messages? That decides whether we can ever expect OData."*

### B2. Which SAP modules / tables?
- **Chose:** posting-style flat exports with `Belegnummer`, `Buchungsdatum`, `Werk`, `Materialnummer`, `Menge`, `Mengeneinheit`, `Nettowert`, `Währung`, `Kostenstelle`. Subset of FI / MM data.
- **Why:** these are the columns every SAP consultant can produce without custom ABAP. Asking for asset-level postings or per-vehicle consumption needs a custom query per client.
- **Ask PM:** *"Do any of our existing clients use SAP's Environmental Compliance module or a specific sustainability table? If yes, that's the right contract long-term."*

### B3. German vs English headers?
- **Chose:** both, via a header-alias map (`HEADER_ALIASES` in `parsers/sap.py`). Lowercased, trimmed, unknown headers raise a parse-time error.
- **Why:** SAP localisation is per-user-config, not per-tenant. The same client might send German headers from Hamburg and English from the UK subsidiary. A bilingual alias map costs almost nothing.
- **Ask PM:** *"Do you have clients we anticipate in Spanish/French/Polish SAP installs? If so, I'll need their translation pass."*

### B4. Activity type from material number or text?
- **Chose:** keyword match in `material_text` (`diesel`/`benzin`/`petrol`/`gasoline`/`fuel`/`kraftstoff`/`heizöl` → fuel; else procurement).
- **Why:** material-number → activity-type lookup needs a per-client master table that nobody hands over at onboarding. Keyword matching is transparent and defensible. The few false positives (a procurement line that says "diesel pump spare part") are caught by quantity and unit not making sense for fuel.
- **Ask PM:** *"Will the client share their MM material master? That's the upgrade from keyword to lookup. Also: do we ever see Scope 1 natural gas in SAP procurement, or only liquid fuel?"*

### B5. Period semantics - posting date as start = end?
- **Chose:** `period_start = period_end = posting_date` for every SAP row.
- **Why:** SAP postings are point-in-time events, not period events. Forcing them into the same period shape as utility (which is genuinely ranged) lets the overlap detector treat them uniformly.
- **Ask PM:** *"Do auditors want SAP fuel rolled up to month / quarter, or per-posting? The aggregation can happen at report time without changing the model."*

### B6. EU vs US decimal separators?
- **Chose:** handle both. Heuristic - last separator wins; trailing three-digit group with `.` and no `,` → thousands.
- **Why:** the same client's German plant ships `1.234,56` and their US plant ships `1,234.56`. The parser shouldn't care.

---

## C. Utility (electricity) source

### C1. Portal CSV, PDF bill, or API?
- **Chose:** portal CSV upload.
- **Why:** PDF parsing is fragile across providers (every utility's layout drifts), eats engineering hours, and pulls focus from the data model. Commercial APIs barely exist outside a few EU/US providers and require per-utility integration. Facilities teams already click "Download CSV" once a month.
- **Ask PM:** *"What share of your existing clients can do CSV vs are stuck on PDFs only? If >20% are PDF-only, OCR becomes worth funding."*

### C2. Billing period mid-month vs calendar?
- **Chose:** store the period as-given. Don't reshape into calendar months.
- **Why:** auditors want what was billed, not what we synthesised. Calendar-aligned aggregation is a report-time concern.
- **Ask PM:** *"Do downstream emission factors come in per-calendar-month buckets? If yes, we need a prorate step at report time, not at ingest."*

### C3. Peak / off-peak split rows?
- **Chose:** treat each as a separate `NormalizedActivity` keyed by `(meter_id, period_start, rate)`.
- **Why:** lossless. Aggregating loses information; separate rows can always be summed.
- **Ask PM:** *"Will Scope 2 reporting need tariff-bucket detail or just total kWh? That decides whether the rate field promotes to a column."*

### C4. Multiple meters per site?
- **Chose:** each meter is its own `location_code`.
- **Why:** the period-overlap detector keys on `location_code` and would false-positive if I rolled meters up to site.
- **Ask PM:** *"Do clients ever rename meters mid-contract? If yes, we need an alias table."*

---

## D. Travel source

### D1. Concur API or upload?
- **Chose:** JSON file upload, shaped like Concur Expense Report v3.
- **Why:** Concur partner OAuth is a multi-week approval dance and requires a sandbox tenant we don't have. Matching the response shape means the upload path *is* the parse-and-validate path; swapping to a poll loop later is changing one wrapper.
- **Ask PM:** *"Of our pipeline clients, how many use Concur, Navan, TravelPerk, or in-house? Knowing the mix decides which adapter ships next."*

### D2. Which Concur fields?
- **Chose:** `Id`, `ExpenseTypeName`, `TransactionDate`, `TransactionAmount`, `TransactionCurrencyCode`, `VendorDescription`, `LocationName`, `OriginIataCode`, `DestinationIataCode`, `CheckInDate`, `CheckOutDate`.
- **Why:** narrow projection. Concur's full payload includes per-attendee detail, tax breakdown, itinerary objects - none are load-bearing for emissions accounting.
- **Ask PM:** *"Does the carbon engine need vendor-level granularity, or just category totals?"*

### D3. Distance: routing API or great-circle?
- **Chose:** great-circle from IATA → lat/lon, no external call.
- **Why:** GHG Protocol and DEFRA both use great-circle for air travel. Within ~3% of actual flight path; the rounding noise is smaller than the emission-factor uncertainty.
- **Ask PM:** *"Any tier of client where the routing-API uplift is worth it? My guess: no."*

### D4. Non-travel expenses (Meals, Office Supplies)?
- **Chose:** skip with a parse-error note that says which entry and why.
- **Why:** silent drops are how data gets lost. The batch shows we considered every row.
- **Ask PM:** *"Do we ever need spend-based Scope 3 emissions on, e.g., meals? If yes, those rows become `activity_type=procurement` instead of getting dropped."*

### D5. Hotel / ground transport - no distance, what do we store?
- **Chose:** hotels store `quantity=nights, unit=night`; ground transport stores `quantity=1, unit=trip`, with `amount + currency` carrying the spend signal.
- **Why:** lets the carbon engine pick night-based or spend-based factors per category without re-ingesting.
- **Ask PM:** *"Is spend-based emission factor for hotels acceptable or do you have per-night kgCO2e factors keyed by city?"*

---

## E. Validation

### E1. Eight rules and not more (or fewer)?
- **Chose:** eight rules, each tied to a specific real-world failure mode (see [MODEL.md](MODEL.md) and `backend/review/validators.py`).
- **Why:** every rule I can defend with "I've seen this go wrong" or "this catches double-counting". Adding more just to look thorough dilutes the analyst's attention.
- **Ask PM:** *"Are there rules from your audit experience I'm missing - e.g., 'fuel quantity per posting > vehicle tank capacity'?"*

### E2. Error vs warning severity?
- **Chose:** `UNIT_UNKNOWN`, `QUANTITY_NONPOSITIVE`, `PERIOD_INVALID` → error. Rest → warning.
- **Why:** errors are "I cannot interpret this row safely". Warnings are "this is unusual; you decide". Errors require an override note at approve time; warnings don't.
- **Ask PM:** *"What's your policy on overrides? Do they need a manager signature, or is a note from the approving analyst enough?"*

### E3. Quantity range bounds?
- **Chose:** wide bands per `activity_type` (e.g., fuel: `0.1` to `200,000` L). Deliberately permissive.
- **Why:** we'd rather under-flag than spam analysts with false alarms. The cost of a missed UNIT_RANGE is one wrong row; the cost of alert fatigue is the analyst ignoring all warnings.
- **Ask PM:** *"Should these bounds be per-client (a small office vs a refinery)? That promotes them to a per-tenant config table."*

---

## F. Approval workflow

### F1. Locking semantics post-decision?
- **Chose:** both `APPROVED` and `REJECTED` rows are immutable. No "unapprove" / "unreject" endpoint. To correct, re-ingest with a fix and both rows + both `ApprovalAction` events remain visible.
- **Why:** a rejection is a decision too - telling the auditor "we threw this out for reason X" is no less load-bearing than "we approved it". Allowing the analyst to silently un-reject later would let the same row reappear under a new decision without an audit breadcrumb. Symmetric locking keeps the trail honest.
- **Ask PM:** *"Is this the right discipline for both directions, or do you have a sanctioned un-decide flow with two-person sign-off?"*

### F2. Bulk approve / reject?
- **Chose:** single-row only. No "approve all flagged" button.
- **Why:** bulk approve normalises clicking-through, which defeats the point of the review surface. If the bulk shape is needed, the right primitive is "approve all rows matching this filter" with an explicit note required.
- **Ask PM:** *"Is per-row clicking sustainable at 5k rows/month, or do we need a saved-filter bulk approve from day one?"*

---

## G. What I didn't decide and would refuse to without input

- **FX-rate source.** ECB? Bloomberg? Client's accounting system? Posting-date FX or invoice-date FX? Without a PM call, the `CURRENCY_MISMATCH` flag stays a warning and no rate is applied.
- **Whether re-ingesting overwrites or adds.** The current code adds and flags `DUPLICATE_LIKELY`. Some clients will want "always overwrite the previous", others "always preserve both". This is a config call.
- **Retention.** How long do `RawRecord` payloads stay around? GDPR-wise some Concur fields are person-identifiable. No retention policy yet.
