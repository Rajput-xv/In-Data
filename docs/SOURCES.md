# SOURCES.md - Three source systems, three research notes

For each source the brief asked me to pick an ingestion mechanism and defend it against reality. This is my research log per source:

1. The real-world format options I read up on.
2. What I learned that shaped the parser.
3. What my sample file looks like and why each oddity is in it.
4. What would break in a real deployment.

---

## 1. SAP - fuel and procurement

### Real-world format options I researched

| Option | What it is | Why I rejected it |
|---|---|---|
| **IDoc** | SAP's structured XML / segmented record exchange format. Triggered from a transaction, delivered to a partner system over RFC or file drop. | Requires an IDoc partner profile, ALE setup, and a landing endpoint inside the client's SAP network zone. Not something we get on day one of onboarding. |
| **BAPI** | Function-module RPC into SAP via SAP NetWeaver RFC. | Needs a NetWeaver user with `S_RFC` privileges and the SAP NetWeaver RFC SDK on our side. Same access problem. |
| **OData** (SAP Gateway) | RESTful endpoints exposed by SAP Gateway. | Requires Gateway to be installed, services activated per table, and a user with the right authorisation objects. Many older clients haven't installed Gateway at all. |
| **Flat-file export** | Output of `SE16N`, `SQ01`, custom ABAP report, or "Save as text" from any list view. Semicolon-delimited by default. | **Chose this.** |

### What I learned

- **SAP exports are not Excel files.** The default delimiter is `;`, not `,`. The default encoding is UTF-16 LE with BOM (because `SE16N`'s "Spreadsheet" download targets German Excel). Loading one as a plain CSV without `utf-8-sig` / `utf-16` fallback throws a Unicode error on row zero.
- **Headers are localised to the user, not the system.** A German SAP user gets `Buchungsdatum`, `Werk`, `Menge`. The same query from an English-locale user logs `Posting Date`, `Plant`, `Quantity`. Same underlying table, two header rows. I built a `HEADER_ALIASES` dictionary that maps both sets to one internal key set.
- **Decimal format is per-user-config.** German users get `1.234,56` (period for thousands, comma for decimal). US users get `1,234.56`. Some configs add spaces. The number-parser disambiguates on "which separator is last" + a thousands-grouping heuristic.
- **Plant codes are four-digit and meaningless out of context.** `1000` could be Werk Hamburg, Plant Detroit, Werk Hannover - depends on the client's plant master. I ship a tiny `plant_codes.json` lookup with realistic fabricated entries; the validator flags `LOOKUP_MISSING` when a row's plant isn't in it.
- **Units are inconsistent in the same column.** Same export can carry `L`, `Liter`, `LTR`, `KG`, `T` (tonnes), `ST` (Stück, pieces). Conversion table in [`normalize/units.py`](../backend/normalize/units.py) maps the zoo to canonical `L` / `kg`.

### What the sample file looks like

[`backend/sample_data/sap_fuel_q1_2026.csv`](../backend/sample_data/sap_fuel_q1_2026.csv) - 14 rows, semicolon-delimited, German headers, EU decimals, `DD.MM.YYYY` dates. Includes:

| Row trick | Why it's there |
|---|---|
| Materials `Diesel B7` and `Benzin E10` | Tests fuel keyword classifier. |
| Materials `Schmieröl`, `Filtersatz` | Tests procurement path (no fuel keyword). |
| Plant `9999` | Not in lookup → triggers `LOOKUP_MISSING`. |
| Quantity `0,80` with unit `MWh` (on a fuel row) | Tests unit conversion (0.80 MWh → 800 kWh) and exposes a unit/activity mismatch. |
| Currency `USD` on one row, `GBP` on another | Triggers `CURRENCY_MISMATCH` (default = EUR). |
| Quantity `-50,00` | Triggers `QUANTITY_NONPOSITIVE` (error). |
| `Belegnummer 4900000123` duplicated at end of file | Triggers `DUPLICATE_LIKELY`. |
| Unit `ST` (Stück, "pieces") | Not in unit conversion table → triggers `UNIT_UNKNOWN` (error). |
| Unit `GAL` (US gallon) | Tests gallon → litre conversion (1100 GAL → 4163.95 L). |

### What would break in a real deployment

- **IDoc-only clients.** If a client says "we can only emit IDoc", the parser fails. The fix is a second parser module (`parsers/sap_idoc.py`) and a per-batch source-format flag. Bounded work.
- **Custom Z-fields.** A client might add `ZZ_CO2_FACTOR` as an SAP-side column. My parser raises a parse-time error for unknown columns rather than dropping them silently. That's the right default - a silent drop is how data gets lost - but it means every new field needs an alias added.
- **Multi-line text fields** (e.g., long material descriptions with embedded newlines). The `csv` module handles quoted multi-lines, but some SAP exports unquote them. If I see this in real data, the fix is to escape on the SAP side rather than complicate the parser.
- **Mixed locales in one file.** My parser handles per-row locale variation; probably overkill, but it doesn't cost much.

---

## 2. Utility (electricity)

### Real-world format options I researched

| Option | What it is | Why I rejected it |
|---|---|---|
| **PDF bill** | The standard customer-facing artefact. | Layout drifts per provider, per tariff, per redesign. OCR pipelines exist (Veritone, AWS Textract, Mindee) but adding one steals weeks from the data model. |
| **Provider API** | Exists for a few US ISOs (PJM, ERCOT, some retail) and a small share of EU green-tariff providers. | Coverage is too narrow to bet a generic ingestion path on. Each integration is bespoke. |
| **Green Button** (US standard XML) | Federally-mandated for some US providers; XML of meter intervals. | Not universal, and US-specific. Would build for the EU half of clients separately. |
| **Portal CSV** | What facilities teams actually click "Download" on. Provider-specific column layouts but consistently CSV. | **Chose this.** |

### What I learned

- **Billing periods don't align to calendar months.** A meter read on the 15th of each month gives periods like `2026-01-15` to `2026-02-14`. Pretending they do (e.g., bucketing by month) loses information and confuses downstream aggregation. Store as-given.
- **Multiple register reads per period.** A meter on a time-of-use tariff produces separate Peak / Off-Peak / (sometimes) Shoulder rows for the same period. Each is a real consumption number; rolling them up loses the tariff granularity that Scope 2 market-based reporting cares about.
- **Unit suffix lives in the header, not the column.** Many portals emit a column called `Consumption (kWh)` and don't repeat the unit per row. Some portals mix `kWh` and `MWh` in the same file. The parser pulls a unit hint from the header in parentheses, and falls back to it when no per-row `unit` exists.
- **Meter IDs are stable identifiers, sites are not.** A site can be renamed (`HQ` → `Hamburg HQ`). Meter MPAN/MPRN values are sticky. The overlap detector keys on `meter_id` for that reason.
- **Currency is on the invoice, not the meter.** The CSV typically has one currency column per file. Multi-currency utility exports are rare enough to not over-design for.

### What the sample file looks like

[`backend/sample_data/utility_electric_jan2026.csv`](../backend/sample_data/utility_electric_jan2026.csv) - 10 rows, four sites (Hamburg HQ, Manchester Yard, Lyon Site, Rotterdam Plant), two meters per site for the busy ones, peak/off-peak splits where realistic. Includes:

| Row trick | Why it's there |
|---|---|
| Period `2026-01-15` → `2026-02-14` | Crosses month boundary → realistic billing window. |
| Two rows for the same meter (`1900-2845-001`) - Peak and Off-Peak | Tests rate-split preservation. |
| One row of `15 MWh` for Manchester Yard (a small site) | Unit-likely-wrong scenario → triggers `UNIT_RANGE`. After conversion: 15000 kWh. |
| Period `2025-12-15` → `2026-04-01` (>90 days) | Triggers `PERIOD_INVALID`. |
| GBP and EUR currencies in one file | Triggers `CURRENCY_MISMATCH` on the non-EUR rows. |

### What would break in a real deployment

- **Provider-specific header sets I haven't seen.** Each new utility = one alias-map maintenance round. Eventually I'd ship a per-provider parser config instead of one global alias map.
- **Half-hourly interval data (HH MPAN feeds).** Some commercial UK meters emit 48 values per day instead of one summary. My current parser treats each row as a single consumption period; HH data needs a different shape (`MeterInterval` table) or aggressive aggregation at ingest.
- **Demand charges and reactive power.** Some bills mix energy consumption (kWh) with demand (kW) and reactive (kVArh) in adjacent columns. My parser would refuse to ingest demand columns; the right fix is a second activity type, not silent inclusion.
- **Tariff changes mid-period.** Some bills break a period into "before tariff change" and "after" sub-periods. My parser handles each as a separate row, but the validator's overlap detector would false-positive here. The fix is to weaken `PERIOD_OVERLAP` for utility specifically, or add a `sub_period` field. Documented and skipped.

---

## 3. Corporate travel - Concur-shaped

### Real-world format options I researched

| Option | What it is | Why I rejected it |
|---|---|---|
| **Concur Reporting API** | Concur's bulk reporting endpoint. Returns full report data with itinerary, attendees, etc. | Needs OAuth partner registration. Multi-week. |
| **Concur Expense Report API v3** | Per-report list and per-entry detail. | Same OAuth gate. I matched the **response shape** of this API for the upload format, so swapping in a real poller later is just adding a fetch loop. |
| **Concur Detail Reports CSV** | Native scheduled CSV export from Concur Reporting. | Possible, but the field set varies per client's report template. JSON shape is more stable. |
| **Navan API** | Newer travel platform; cleaner REST. | Real clients are split; building a Navan-only parser would miss the majority on Concur. |
| **JSON upload mimicking Concur Expense v3** | What I shipped. | Defensible as a stand-in for the real API; production swap is a one-file change. |

### What I learned

- **`ExpenseTypeName` is the category signal.** Not `Description`, not `VendorDescription`. `Airfare`, `Hotel`, `Car Rental`, `Taxi`, `Rail`, `Lodging`, `Train` are the names that map to emission categories. Everything else (`Meals`, `Office Supplies`, `Conference Fees`) is not travel and gets skipped with a logged reason.
- **Flight distance is rarely given.** Concur stores origin/destination airports as IATA codes (`OriginIataCode`, `DestinationIataCode`) when the booking source attached them. Distance is computed client-side. I ship a `airports.json` lookup with 15 realistic airports and a great-circle distance function. Missing airports trigger `LOOKUP_MISSING` with quantity defaulted to zero.
- **Hotel nights are inferred from dates.** `CheckInDate` and `CheckOutDate` give the period; nights = days delta. Some hotels in Concur have only `TransactionDate` (booking date) and no period - those rows fail normalisation with a clear error.
- **Multi-currency is the norm.** A US-headquartered client booking a European trip sees `EUR` for the hotel and `USD` for the flight on the same expense report. `CURRENCY_MISMATCH` flags rows whose currency isn't EUR (the company default); the FX-rate question is documented in [DECISIONS.md](DECISIONS.md) §G.
- **Concur has report-level approval state.** I deliberately ignore it. Carbon ingestion is a separate workflow from finance approval - I don't care whether the *traveller's* manager approved their expense report.

### What the sample file looks like

[`backend/sample_data/travel_concur_jan2026.json`](../backend/sample_data/travel_concur_jan2026.json) - 10 expense entries inside a `{"Items": [...]}` envelope, mimicking the Concur v3 response. Includes:

| Entry trick | Why it's there |
|---|---|
| `HAM → FRA` and `FRA → AMS` Airfare entries | Tests great-circle calc against real airport pairs (~414 km and ~365 km). |
| `Hotel` with `CheckInDate < CheckOutDate` | Tests night-count derivation. |
| `Car Rental` and `Taxi` and `Rail` | Tests three different ground-transport flavours all mapping to the same activity_type. |
| Airfare with `OriginIataCode = MUC`, `DestinationIataCode = ZZZ` | `ZZZ` not in airport lookup → `LOOKUP_MISSING`, quantity defaults to 0. |
| Hotel with `CheckOutDate < CheckInDate` | Triggers `PERIOD_INVALID` (error severity). |
| Two USD entries | Triggers `CURRENCY_MISMATCH`. |
| One `Meals` entry | Tests that non-travel categories are skipped with a logged parse error (not silently dropped). |

### What would break in a real deployment

- **Concur partner OAuth.** Switching from upload to poll means registering as a partner, requesting tenant access from each client, and managing refresh tokens. None of that is hard, but it's not prototype work.
- **Other platforms.** Navan, TravelPerk, Egencia, in-house portals. Each gets its own parser module. The normalize step doesn't change - different `parsers/<platform>.py`, same `normalize/travel.py`.
- **Multi-leg flights.** A `LAX → JFK → LHR` trip booked as one entry has only origin/destination in Concur, not the intermediate stop. My current calc treats it as a single great-circle which under-counts for connections. The fix is to ingest `Itinerary` objects per entry; shape extension is one new sub-table.
- **Hotel star rating / room type.** Affects emission factor on spend-based methodology. Concur exposes `RoomType` if the booking source provided it; I don't ingest it. Bounded extension.
- **Personally identifiable information (PII).** Real Concur payloads include traveller email, employee ID, sometimes home address. My parser doesn't extract them, but `raw_record.payload` would store whatever was sent. Real deployment needs a PII-scrub step before storage and a retention policy.
