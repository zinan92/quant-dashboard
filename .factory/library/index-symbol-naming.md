# Index Symbol Naming in market.db

**What belongs here:** Factual knowledge about data layer symbol conventions.

---

## Symbol Conventions

- **market.db (via MarketReader)**: Index symbols use exchange suffixes — e.g., `000300.SH` (CSI 300 Shanghai), `399006.SZ` (ChiNext Shenzhen).
- **IndexFetcher**: Uses bare codes without suffix — e.g., `000300` (CSI 300). Stores data in its own `data/index_cache.db`.

## When to Use Which

- **MarketReader.get_index_klines()**: Use when CSI 300 data already exists in market.db (it does: `000300.SH`). Preferred for read operations since market.db is the canonical data source.
- **IndexFetcher**: Use only when you need to fetch fresh index data from AkShare (online API) and cache it locally. Creates/updates `data/index_cache.db`.

## Gotcha

Feature specs may reference bare symbol codes (e.g., `000300`), but MarketReader requires the `.SH`/`.SZ` suffix. Always check the actual symbol format in market.db before querying.
