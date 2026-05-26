# MODEL.md - Data model and why

The data model is the part I had to get right. Parsers, validators, the UI - all replaceable. The table shape is what auditors and the next analyst live with for years.

This doc covers the five tables, why each exists, and how I handled the four requirements in the brief: multi-tenancy, Scope 1/2/3, source-of-truth tracking, unit normalization, and audit trail.

---

## 1. The five tables

```
IngestionBatch ────────── 1───* ── RawRecord ────── 1───1 ── NormalizedActivity
       (upload event)        (verbatim row)             (the unified row)
                                                             │
                                                             ├── 0───* ── ActivityFlag
                                                             │             (why suspicious)
                                                             └── 0───* ── ApprovalAction
                                                                           (lock event)
```

| Table | Purpose | Owner app |
|---|---|---|
| `IngestionBatch` | One upload event. Tracks what was loaded, when, by whom, status. | `ingestion` |
| `RawRecord` | Verbatim source row stored as JSON. Never mutated. | `ingestion` |
| `NormalizedActivity` | One unified row per source row. Canonical unit + Scope tag. | `normalize` |
| `ActivityFlag` | Reason a row looks suspicious. Many per activity. | `review` |
| `ApprovalAction` | Analyst decision + timestamp + override note. Approval locks. | `review` |

I resisted adding `Location`, `CostCenter`, `Vendor`, or `EmissionFactor` as their own tables.

- `Location` / `CostCenter` are weakly-shaped per-client identifiers. Storing the code verbatim and presenting the lookup via static JSON is the right contract; promoting to tables forces an onboarding step nobody asked for.
- `EmissionFactor` is downstream of this system. The brief is explicit - computing carbon isn't the hard part. This app feeds the carbon engine, it doesn't host it.

When any of those grows teeth (multi-region cost centres, dynamic vendors, tenant-specific factors), they earn a table. Until then they live as fields.

---

## 2. Scope 1/2/3 categorization

```python
# normalize/models.py
class Scope(TextChoices):
    SCOPE_1 = "1"  # direct emissions
    SCOPE_2 = "2"  # purchased energy
    SCOPE_3 = "3"  # value chain

SCOPE_FOR_ACTIVITY = {
    ActivityType.FUEL:             Scope.SCOPE_1,
    ActivityType.ELECTRICITY:      Scope.SCOPE_2,
    ActivityType.PROCUREMENT:      Scope.SCOPE_3,
    ActivityType.FLIGHT:           Scope.SCOPE_3,
    ActivityType.HOTEL:            Scope.SCOPE_3,
    ActivityType.GROUND_TRANSPORT: Scope.SCOPE_3,
}
```

The mapping is deterministic from `activity_type`, but `scope` is stored on the row, not computed on read. Two reasons:

- **Indexability.** Analysts filter by scope (`?scope=2` is "show me all electricity"); a stored column with an index is the right tool.
- **Stability under code change.** If the mapping changes - e.g. a client reclassifies some procurement spend as Scope 1 because it's combusted on-site - historic rows keep the scope they were ingested with. The alternative (computed-on-read) silently rewrites history.

Scope distribution on sample data after ingestion: `{Scope 1: 11 fuel rows, Scope 2: 10 electricity rows, Scope 3: 12 procurement + travel rows}`.

### What's not handled

- **Scope 2 market-based vs location-based.** Real reporting needs both; the prototype stores one number. The fix is a second column `scope_2_method` ∈ {market, location} plus a duplicate row per method. Documented and skipped.
- **Scope 3 categories 1–15.** GHG Protocol breaks Scope 3 into fifteen sub-categories (purchased goods, capital goods, business travel, etc.). The prototype lumps them all under "3". The shape extension is one optional `scope_3_category` enum on `NormalizedActivity`.

---

## 3. Multi-tenancy

**Status: schema designed, not wired.** I ran the prototype single-tenant because the brief says "we're onboarding a new enterprise client" - singular. Wiring tenant scoping when there's only ever one tenant creates a false sense of isolation without the test surface to prove it works.

When the second client lands, the change is bounded:

```python
class Organization(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    default_currency = models.CharField(max_length=3, default="EUR")
    # Scope 2 method preference, FX rate provider, etc.

class IngestionBatch(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    # ... rest unchanged
```

Only `IngestionBatch` carries the FK. `RawRecord`, `NormalizedActivity`, `ActivityFlag`, `ApprovalAction` inherit tenancy transitively through `batch` - every read query already joins to batch, and adding a `batch__organization_id = X` filter at the view layer is one line.

The lookup tables (`plant_codes.json`, `airports.json`) graduate from static files to `OrganizationLookup` rows keyed by `(organization, kind, code)`. The cost is one more table and a per-request cache; the lookup loader keeps the same interface.

Currency handling becomes per-tenant: `DEFAULT_CURRENCY` in the validator moves from a module constant to `request.user.organization.default_currency`.

**Why not implement now?** Multi-tenant scoping has to be enforced everywhere - one missing filter and tenant A sees tenant B's data. The right time to add it is when the second tenant is real and I have rows to test isolation against.

---

## 4. Source-of-truth tracking

Three columns answer "where did this number come from?":

```python
class NormalizedActivity:
    raw_record   = OneToOneField(RawRecord)   # the original row
    batch        = ForeignKey(IngestionBatch) # the upload event
    source_ref   = CharField(...)             # the source-system id
```

- **`raw_record.payload`** is the verbatim row dict, never mutated. If a normalizer turns out to be wrong six months later - wrong unit conversion, wrong activity-type classification - I can re-run normalize against the payloads, no client re-export required.
- **`batch.uploaded_at` / `batch.uploaded_by` / `batch.filename`** answer "when did it come in, from whom, in which file". This is the audit question.
- **`source_ref`** is the source-system identifier (SAP `Belegnummer`, utility `invoice_number`, Concur `Id`). It survives renaming and re-ingestion; it's what the `DUPLICATE_LIKELY` validator rule keys on.

### Was a row edited?

The prototype takes a strong stance: **post-decision, rows are not edited.** Once an `ApprovalAction` lands - `APPROVE` or `REJECT` - the row's status flips to `APPROVED` or `REJECTED` and both endpoints refuse to act on it (HTTP 409). Rejection is just as terminal as approval; soft "un-reject" or "un-approve" would muddy the trail.

If an analyst wants to "correct" a decided row, the workflow is re-ingest with a corrected source export - the new row, the old row, and both `ApprovalAction` rows are visible. Nothing gets silently overwritten.

For the undecided case (PENDING / FLAGGED), there's no edit API either. If I add an "edit before decide" surface later, the right shape is `ActivityEdit(activity_fk, analyst, field, old_value, new_value, edited_at)` - append-only, sibling to `ApprovalAction`. The normalized row holds the current view; the history table holds the trail.

---

## 5. Unit normalization

Three columns, one canonical representation, no information loss:

```
RawRecord.payload     →   {"quantity": "0,80", "unit": "MWh", ...}    (verbatim)
NormalizedActivity    →   quantity=800.0000  unit="kWh"               (canonical)
```

The conversion is driven by [`normalize/units.py`](../backend/normalize/units.py), a flat dict from lowercased source-unit-string to `(canonical_unit, multiplier)`. Picked over `pint`:

- The unit zoo we see is small and predictable (~25 strings).
- A dict is grep-able in a PR. Adding a unit is one line, reviewable.
- No dependency.

Canonical units per dimension:

| Dimension | Canonical | Sources we map from |
|---|---|---|
| Liquid | `L` | `L`, `Liter`, `LTR`, `ml`, `gal`, `galuk` |
| Mass | `kg` | `kg`, `g`, `t`, `To` (German), `tonne`, `MT` |
| Energy | `kWh` | `Wh`, `kWh`, `MWh`, `GWh` |
| Distance | `km` | `m`, `km`, `mi`, `mile` |
| Count | `night`, `trip` | self |

If a unit is *not* in the table, the normalizer keeps the raw values verbatim and the validator raises `UNIT_UNKNOWN`. The system prefers "flag for human" over "silently coerce".

---

## 6. Audit trail

The audit handoff to a client's external auditor needs three things to be true:

1. Every approved row points to the exact source bytes it came from (`raw_record.payload`).
2. Every approved row records who approved it, when, and why if an error-severity flag was overridden (`ApprovalAction.analyst`, `decided_at`, `note`).
3. Approved rows are not editable. (Enforced at the API layer; HTTP 409 on second approve, no edit endpoint exists.)

There is intentionally no "unapprove" or "void" action. If something needs to change after approval, you ingest a new batch with the correction and the trail shows both versions plus both approval events. That's how SAP, NetSuite, and every auditable system handles it. The prototype follows the same discipline.

---

## 7. What this model does NOT carry (and where it'd go later)

| Concern | Where it belongs | Why not here yet |
|---|---|---|
| Emission factors | Separate `EmissionFactor` table joined at report time. | Brief is explicit - computing carbon isn't the hard part. |
| FX rates | Separate `FxRate(currency, on_date, rate)` table. | Multi-currency is one warning flag right now (`CURRENCY_MISMATCH`); single client doesn't justify more. |
| Custom client fields | A `NormalizedActivity.extras` JSON field. | `raw_record.payload` already holds them. Promoting is a per-client decision. |
| Per-meter / per-vehicle assets | `Asset` table FK'd from `NormalizedActivity`. | Analyst-facing review doesn't need it; aggregate analytics work without it. |

The principle I followed: a column earns its place when at least two of (audit, validation, reporting) need it. Anything that doesn't lives in `raw_record.payload` until it does.
