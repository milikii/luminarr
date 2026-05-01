# Adult Metadata Source Probe — 2026-05-01

## Probe method

- Environment: repo `.env` with `OUTBOUND_PROXY_URL`
- Command shape: `curl -L -sS -x "$OUTBOUND_PROXY_URL" <url>`
- Goal: lightweight reachability + page-shape signal only
- Non-goal: full scraper correctness

## Results

| Source | URL probed | Result | Signal |
|---|---|---|---|
| avbase | `https://www.avbase.net/` | reachable shell, but returns `Just a moment...` | Cloudflare gate |
| jav321 | `https://www.jav321.com/` | response body returns `JAV321...`, but also appears Cloudflare-gated / degraded | unstable |
| avsox | `https://avsox.click/cn` | reachable | metadata-like |
| caribbeancom | `https://www.caribbeancom.com/index2.htm` | reachable | metadata-like |
| missav | `https://missav123.com/dm194/cn` | returns `Just a moment...` | Cloudflare gate |
| javbus | `https://www.javbus.com/` | reachable | metadata-like / age gate page shell |
| javlibrary | `https://www.javlibrary.com/` | returns `Just a moment...` | Cloudflare gate |
| fanza / dmm | `https://www.dmm.co.jp/` | reachable | age gate / region-sensitive shell |

## Implications

### 1. Not all named sources are equal

The user-named list must be split by realistic execution role:

- **Likely viable helper / metadata candidates in current environment**
  - `avsox`
  - `caribbeancom`
  - `javbus`
- **Existing helper chain already implemented**
  - `avmoo`
  - `javlibrary` (but Cloudflare-gated in this environment; still useful as fallback when reachable)
- **Likely unstable / gated / conditional**
  - `avbase`
  - `jav321`
  - `missav`
  - `fanza`

### 2. "Add all sources" cannot mean "all as active BT providers"

The probe supports the reviewed architecture split:

- `BT providers`
  - `tokyotosho`
  - `sukebei`
  - `javbus`
  - adult `Prowlarr` indexers
- `metadata/helper`
  - `avmoo`
  - `avsox`
  - `caribbeancom`
  - `javlibrary`
  - conditional / best-effort: `avbase`, `jav321`, `missav`, `fanza`

### 3. Minimum viable implementation order

1. Keep `avmoo -> javlibrary` chain intact
2. Add `avsox` helper if page shape is simple enough
3. Add `javbus` metadata/detail enrichment only if it can be done without confusing it with BT provider role
4. Add `caribbeancom` as conditional uncensored helper if exact-ID lookup is tractable
5. Leave `avbase`, `jav321`, `missav`, `fanza` as policy-known but runtime-conditional/deferred unless a stable probe path is found

## Recommendation

For this task, the realistic "complete enough" bar is:

- PT relevance-first fully shipped
- adult BT resource providers truly usable by default
- adult helper metadata chain expanded beyond `avmoo/javlibrary` where current environment makes that tractable

Do **not** block the whole task on making every named metadata source fully scriptable in one pass; several are clearly protected by Cloudflare, region gates, or unstable shells in this environment.
