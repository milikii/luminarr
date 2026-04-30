# BT Source Contracts

> Executable contracts for adult BT source roles, active-provider wiring, and candidate metadata.

## Scenario: Adult BT Source Roles

### 1. Scope / Trigger

- Trigger: this project now treats adult BT sources as role-bearing integrations instead of a flat list of interchangeable site names.
- Why code-spec depth is required: the change crosses env wiring (`BT_WEB_SOURCES`), service composition (`main.py`), search candidate payloads (`btSourceName` / `btSourceRole`), and read-only ranking behavior.

### 2. Signatures

- `app.clients.web_source.get_configured_web_source_rule(source_name: str) -> WebSourceRule | None`
- `app.services.bt_sources.canonicalize_bt_source_name(value: str) -> str`
- `app.services.bt_sources.get_bt_source_profile(name: str) -> BtSourceProfile | None`
- `app.services.bt_sources.is_active_bt_source(name: str) -> bool`
- `app.services.bt_sources.get_bt_source_priority(name: str) -> float`
- `app.services.bt_sources.attach_bt_source_profile(candidate: Mapping[str, Any]) -> dict[str, Any]`
- `app.main._build_bt_source_providers(*, configured_web_source_names: tuple[str, ...], proxy_url: str) -> list[BtSourceProvider]`

### 3. Contracts

#### Source-role contract

- `primary`: main adult BT source, eligible for active provider wiring and highest adult sort weight.
- `supporting`: active provider, but ranked below primary.
- `helper_only`: may enrich read-only display, but must not be wired into active search/download provider lists.

#### Current canonical profiles

- `nyaa` -> `supporting`
- `tokyotosho` -> `primary`
- `sukebei` -> `primary`
- `javbus` -> `supporting`
- `prowlarr` -> `supporting`
- `javlibrary` -> `helper_only`

#### Alias contract

- Aliases must canonicalize before any role lookup or sort lookup.
- Current aliases include:
  - `offkab`, `sukebei.nyaa.si`, `nyaa.si` -> `sukebei`
  - `tokyotosho.info`, `www.tokyotosho.info` -> `tokyotosho`
  - `javbus.com`, `www.javbus.com` -> `javbus`
  - `javlibrary.com`, `www.javlibrary.com` -> `javlibrary`

#### Env wiring contract

- `BT_WEB_SOURCES` may only create active `BtSourceProvider` entries for roles other than `helper_only`.
- A supported web-source rule is still inactive until it has an explicit entry in the BT source profile registry.
- A helper-only source remains a supported rule for read-only helper logic, but it is not a valid active provider for downloader-facing search composition.

#### Candidate payload contract

- Normalized BT candidates may carry:
  - `btSourceName`: canonical source name
  - `btSourceRole`: `primary` / `supporting` / `helper_only`
- `attach_bt_source_profile()` is the reuse point for adding these fields when only `sourceProvider` / `indexerName` are present.

#### Adult-only fallback display contract

- `成人搜` adult-only fallback must require both exact adult identity metadata (`adult_content_id` or `read_only_adult_content_id`) and configured adult source proof.
- Adult web-source proof may come from `btSourceName`, `sourceProvider`, or `indexerName` canonicalizing to a known adult web source such as `tokyotosho`, `sukebei`, or `javbus`.
- `prowlarr` is an aggregator, not source proof by itself. A Prowlarr candidate is adult-only only when its underlying `indexerName` canonicalizes to a known adult web source.
- Generic Prowlarr / PT indexer results must be treated as empty for `成人搜` adult-only replies even if their title contains an adult-looking identifier.

### 4. Validation & Error Matrix

- Unknown `BT_WEB_SOURCES` name -> operational log + skip provider.
- Supported-but-unmodeled `BT_WEB_SOURCES` name -> skip provider until a role profile is added.
- Known helper-only source in `BT_WEB_SOURCES` -> operational log + skip provider.
- Provider HTTP / parsing failure -> operational log + continue with remaining providers.
- Missing source profile for a candidate -> keep candidate usable; do not invent a role.
- Read-only display ranking lookup -> canonicalize aliases before reading priority.
- Adult-only fallback sees `sourceProvider=prowlarr` with `indexerName=IndexerPT` -> do not show it in `成人搜`; continue fallback variants and eventually return the explicit adult-source-empty text if no adult source proof exists.

### 5. Good / Base / Bad Cases

- Good: `BT_WEB_SOURCES=tokyotosho,javbus` -> both become active providers; candidates get canonical names and roles.
- Base: `BT_WEB_SOURCES=tokyotosho,javlibrary` -> `tokyotosho` is active; `javlibrary` is skipped from active wiring but can still appear as helper-only enrichment in read-only display.
- Bad: treating `javlibrary` as an active download source because it exists in `SUPPORTED_WEB_SOURCE_RULES`.

### 6. Tests Required

- Source registry tests:
  - aliases canonicalize to the right source
  - each canonical source returns the expected role
  - helper-only sources return `False` from `is_active_bt_source()`
  - supported-but-unmodeled sources return `False` from `is_active_bt_source()`
- Wiring tests:
  - `_build_bt_source_providers()` skips helper-only configured sources
  - `_build_bt_source_providers()` also skips supported-but-unmodeled configured sources
- Search/display tests:
  - read-only display keeps using role-based priority lookup
  - helper-only metadata does not leak into cached candidate payloads unless explicitly persisted by design
  - adult-only fallback rejects generic Prowlarr / PT indexers
  - adult-only fallback allows Prowlarr results whose `indexerName` canonicalizes to a known adult web source
  - adult-only fallback returns explicit configured-adult-source-empty text when only non-adult source candidates exist

### 7. Wrong vs Correct

#### Wrong

- Read `SUPPORTED_WEB_SOURCE_RULES` directly in composition code and assume every supported rule is an active provider.
- Duplicate source-name alias maps inside display code.

#### Correct

- Resolve configured provider eligibility through `get_configured_web_source_rule()`.
- Reuse `canonicalize_bt_source_name()` and role/priority helpers from `app.services.bt_sources`.
