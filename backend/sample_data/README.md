# Sample data - what I fabricated and why

Three files I hand-wrote, not pulled from a real client. Each matches the realistic export quirks I researched (see [docs/SOURCES.md](../../docs/SOURCES.md)) and deliberately trips multiple validator rules so the review dashboard has interesting rows to look at.

## `sap_fuel_q1_2026.csv`
- Semicolon-delimited, German headers (`Buchungsdatum`, `Werk`, `Menge`, `Mengeneinheit`, `Materialnummer`, `Kurztext`, `Nettowert`, `Währung`, `Kostenstelle`).
- European decimals (`1.234,56`) and `DD.MM.YYYY` dates.
- Mix of fuel (`Diesel B7`, `Benzin E10`) and non-fuel procurement (`Schmieröl`, `Filtersatz`).
- Deliberate trips:
  - Plant code `9999` (not in lookup) → `LOOKUP_MISSING`.
  - One row in `0,80 MWh` of Benzin → after conversion, `UNIT_RANGE`.
  - One row in `USD`, another in `GBP` → `CURRENCY_MISMATCH`.
  - One `Belegnummer` repeats at the end of the file → `DUPLICATE_LIKELY`.
  - One row with quantity `-50,00` → `QUANTITY_NONPOSITIVE` (error).
  - One row with unit `ST` (Stück, pieces) → `UNIT_UNKNOWN` (error).

## `utility_electric_jan2026.csv`
- Standard CSV, ISO dates, billing periods that cross calendar month boundaries.
- Two meters per site for the busy ones; peak / off-peak split rows preserved.
- Deliberate trips:
  - `15 MWh` on Manchester Yard (a small site) → `UNIT_RANGE`.
  - Period `2025-12-15` → `2026-04-01` (>90 days) → `PERIOD_INVALID`.
  - GBP rows alongside EUR → `CURRENCY_MISMATCH`.

## `travel_concur_jan2026.json`
- Shape: `{"Items": [...]}` mimicking the Concur Expense Report v3 response.
- Mix of `Airfare`, `Hotel`, `Car Rental`, `Taxi`, `Rail`, plus one non-travel `Meals` entry that the parser skips with a logged reason - I don't silently swallow non-travel expenses.
- Deliberate trips:
  - Flight with destination `ZZZ` (not in airport lookup) → `LOOKUP_MISSING`, quantity defaults to 0.
  - Hotel with `CheckOutDate < CheckInDate` → `PERIOD_INVALID` (error).
  - One Airfare in `USD`, one Hotel in `USD` → `CURRENCY_MISMATCH`.
