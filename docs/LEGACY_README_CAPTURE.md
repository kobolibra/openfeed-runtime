# OpenFeed Studio · consolidated engineering prototype

**A self-hosted Web-to-RSS workspace for investment research, news and job listings.**

> **Release status:** Locally tested **static HTML / existing-feed prototype** with real Chromium offline UI interaction tests. Not a hosted service or a production release. No official Readwise Reader ingest, real institutional site or Playwright-browser E2E has been claimed. No subscription number cap is implemented, but available capacity depends on source sites and compute.

## What's actually implemented

- Management workspace: source search and status filter, create/edit/pause/resume/delete, activity stats, latest stored items and run diagnostics.
- Static HTML → standard RSS 2.0 with CSS or XPath selectors; small Feed43 `{%}` capture/`{*}` skip subset; ranked repeat-container suggestions (including generic `.insight-card` structures); improved sanitized static HTML visual picker with match coverage (not live cross-domain picking).
- Native RSS, Atom and JSON Feed 1.0/1.1 ingestion; detect `rel="alternate"` RSS/Atom/JSON Feed links and recommend existing feeds.
- SQLite WAL, stable GUID from item permalink, distinct original publication date / first discovery date, failure-safe retention of previous good items, ETag cache, single-process scheduler with domain delay and consecutive-failure backoff.
- OPML import/export; atomic Recipe Bundle v1/v2 import + v2 export preserving original Feed ID. Authorized **full online SQLite backup export** includes article history, and should be treated as sensitive. Docker Compose single host/private port/healthcheck.
- Public-target URL restrictions with validation at socket resolution, redirected-target checking, conservative 2.5MB/timeout limits; non-root/read-only Docker deployment.

**Not production-ready:** browser worker has now been separated from the API with a Docker-internal network and public-only outbound proxy, but **actual Docker image builds, network firewall behavior and Chromium runtime remain unverified in this environment**. Also not validated: complete MV3 extension installation, live institutional sources, Reader cloud ingest, full Feed43 protocol parity, site-specific pagination, 7×24 operation, PDF binary enclosures, multi-user login or hosted production rollout. Implemented and locally tested: CSS/XPath, JSON API, linked PDF discovery, Feed43-inspired global/repeated patterns, opt-in job inventory observations, quality gates, stable RSS history and browser-rule handoff.

## Setup (Docker)

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Edit .env, replace OPENFEED_ADMIN_TOKEN with the generated random value.
# If you later publish HTTPS: set OPENFEED_PUBLIC_URL to the permanent public origin.
docker compose up --build -d
```

Open **http://localhost:8765**, enter `OPENFEED_ADMIN_TOKEN`, create a source, test a rule and save. The compose file binds to `127.0.0.1`; use a properly secured public HTTPS origin when Readwise Reader needs to poll the URL. The source database is held in a persistent named volume. The current job listing mode can optionally track disappeared postings; only select **Complete listing** when the source listing is exhaustive and all pagination/filters are covered. Disappearance is reported as *possibly closed*, never as a confirmed closure.

For development (Python 3.12):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export OPENFEED_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export OPENFEED_DB="$PWD/local-openfeed.sqlite3"
export OPENFEED_PUBLIC_URL='http://localhost:8765'
uvicorn openfeed.app:app --host 127.0.0.1 --port 8765
```

### Isolated JS/browser worker — opt-in Compose overlay (deployment validation required)

The main API **cannot launch Chromium**. Browser jobs are sent over a bounded,
short-lived file queue to a dedicated worker container. That container joins
only an **internal** Docker bridge; an independent forward proxy validates DNS
and pins public-IP TCP destinations before connecting externally. The worker
is not connected to the app's service network and never mounts the SQLite DB.

```bash
# Requires a properly configured Docker Engine with Compose support:
docker compose -f compose.yaml -f compose.browser.yaml config -q
docker compose -f compose.yaml -f compose.browser.yaml up --build -d
```

The overlay adds a named browser-jobs volume, one-time permission initializer,
browser worker and public-only forward proxy. **No proxy/worker port is
published.** Existing plain `docker compose up` stays HTTP-only. Do not claim
a secure deployment until the target host passes container reachability tests,
private/metadata-IP rejection tests, app restart, resource limits, and test
feeds on real public sites. The proxy supports HTTPS CONNECT and ordinary
HTTP GET/HEAD; some sites needing other behaviors may fail.

Run a read-only prerequisite assessment with:

```bash
python tools/preflight.py --json
```

This does not produce a production GO decision. It only identifies missing
local prerequisites; cloud publication and Reader ingestion require independent
validation. See `docs/CONSOLIDATED_RELEASE.zh-CN.md`.

Testing:

```bash
python -m pytest -q
node --check static/app.js
node --check static/picker.js
python -m compileall -q openfeed
```

## Actual validation scope

`tests/test_v03.py` includes real Chromium selector clicks and a complete UI → actual FastAPI ASGI transport → SQLite → RSS flow. **This browser runs with locally supplied HTML and an ASGI bridge because this execution environment blocks even localhost browser navigation. It is not a live external-site test.** Dynamic JavaScript execution is separately confirmed with a synthetic page. Public institutional websites, Docker image building and Readwise Cloud ingest remain release blockers. See [`docs/RELEASE_V03.zh-CN.md`](docs/RELEASE_V03.zh-CN.md).

## Data migration and portability

Export `OpenFeed Recipe Bundle v2` to preserve source names, rules, on/off states and opaque feed IDs; use OPML to import published URLs into readers. **Both formats exclude stored item history**. Download the full authorized `/api/export/database` online SQLite backup to preserve history and feed IDs, or make a trusted offline backup; follow [`docs/SECURITY_AND_RELEASE.zh-CN.md`](docs/SECURITY_AND_RELEASE.zh-CN.md). An empty new installation that imports v2 with the same `OPENFEED_PUBLIC_URL` can restore identical feed paths.

## Product and architecture package

- [`docs/PRODUCT_SPEC.zh-CN.md`](docs/PRODUCT_SPEC.zh-CN.md) — product requirements, user journeys, information architecture, quality gates.
- [`docs/ARCHITECTURE.zh-CN.md`](docs/ARCHITECTURE.zh-CN.md) — architectural decision records, data/model and API design, long-term scaling.
- [`docs/OPEN_SOURCE_DUE_DILIGENCE.zh-CN.md`](docs/OPEN_SOURCE_DUE_DILIGENCE.zh-CN.md) — PolitePol, Feed43/RSSWebAll, html2rss, RSSHub, RSS-Bridge and candidate licensing decisions.
- [`docs/SECURITY_AND_RELEASE.zh-CN.md`](docs/SECURITY_AND_RELEASE.zh-CN.md) — threats, SSRF, access controls, backup/recovery and release blockers.
- [`docs/RELEASE_V03.zh-CN.md`](docs/RELEASE_V03.zh-CN.md) — precise v0.3 engineering evidence, limitations and next release gates.
- [`docs/DELIVERY_REPORT.zh-CN.md`](docs/DELIVERY_REPORT.zh-CN.md) — previous v0.2 verification — verified changes, test scope and remaining gaps.
- [`samples/pilot_sources.csv`](samples/pilot_sources.csv) — 20 representative links from the supplied source list, categorized as **unverified pilot candidates**, not automatically proven feeds.

## Production cautions

This is a **private single-admin, single-process** prototype; Uvicorn multi-worker/multi-host mode would invalidate in-memory locks and domain limits. The current authentication is a token header, not full production IAM. Publishing the API on the Internet also requires HTTPS, proxy controls and independent *network-level outbound blocking* of private address ranges, regardless of the HTTP client's DNS checks. A real Playwright worker needs independent network isolation. Do not attempt to bypass paywalls, CAPTCHA or site terms.

**Source file navigation:** `openfeed/app.py` FastAPI routes/scheduler · `openfeed/security.py` bounded public-IP HTTP client · `openfeed/extract.py` selector engines/feeds · `openfeed/storage.py` SQLite persistence · `static/` management UI · `tests/` regressions.

## v0.4 incremental capabilities (2026-10-21)

- **Explicit, bounded pagination:** set `recipe.next_selector` to a CSS selector matching the next-page anchor and `recipe.max_pages` to 1, 2 or 3. The scheduler follows only same-origin links, rate-spaces pages (2 seconds by default, configurable through `OPENFEED_PAGE_DELAY_SECONDS`), prevents cycles, and deduplicates URLs across pages. No `next_selector` means no pagination. `/api/inspect` deliberately previews only page 1 to avoid unexpected extra network requests. The persisted RSS endpoint still emits the 100 newest available entries; collecting more is for change detection and archive history, not an unlimited reader payload.
- **Revision timeline and restore:** every created/imported/edited/restored source has a bounded 40-revision history in `feed_revisions`. `GET /api/feeds/{id}/revisions` lists records, and `POST /api/feeds/{id}/restore/{revision}` writes a new reversible revision. Management UI exposes the history and Restore actions. Existing v0.3 databases are automatically given a baseline snapshot without changing Feed IDs.
- **Stale fetch rejection:** if a rule is edited while the old configuration is still fetching, that old response is discarded rather than committed against the new rule. Successful history and reader URLs remain untouched.
- **Improved lifecycle:** background scheduler jobs are drained or canceled before SQLite shuts down; concurrency slots now cover every page of a multi-page run.
- **Additional proof:** `tests/test_v04.py` covers pagination origin/redirect scope, loops, repeated articles, partial failures, revision history, legacy database migration and stale in-flight rules. The Chromium UI integration additionally creates a paged source, deliberately saves a bad selector and restores the earlier revision.

**Important limits:** Do not enable the experimental Playwright browser without independent network isolation. Pagination does **not** support buttons requiring JavaScript, multiple hosts, page-number templates, login forms or infinite scrolling. Default Docker remains static HTTP only. Browser and public-site integrations are still not production validated.

### Example v0.4 Recipe (illustrative; selectors are not site-verified)

```json
{
  "mode": "css",
  "fetch_mode": "http",
  "item_selector": "article.research-card",
  "fields": {"title":"h2 a", "link":"h2 a@href", "date":"time@datetime"},
  "next_selector": "a[rel=next]",
  "max_pages": 3
}
```

`max_pages` is validated on input, not a claim that a website has 3 pages. On page-2 failure the entire refresh is treated as failed, with the last known good RSS retained. No partial results are committed. Any edited recipe should be inspected and monitored across multiple successful cycles before it is considered validated.

**Current release:** OpenFeed Studio v0.4 engineering preview. The base-feature listing above originates in v0.3; the new v0.4 features are documented in the following section. See `docs/RELEASE_V04.zh-CN.md` for a precise, current implementation and validation statement.


## v0.6: visual coverage feedback

In the sanitized HTML snapshot picker, selecting a repeated article card now highlights all matched cards and the configured title/link/date/summary fields, with per-field coverage counts. This is not a real cross-site browser extension. See `docs/RELEASE_V06.zh-CN.md`.

## v0.7 Live Website Picker (Chrome / Edge)

A Manifest V3 browser extension is included in `extension/`. Load that folder as an unpacked extension in developer mode; the extension requests temporary access to the active tab only after you click it. Select an article and its title/link/date/summary on the actual webpage, then select **Open in Studio** to populate a new feed rule. Always use **Test extraction** before saving; the browser's logged-in access does not transfer to the server crawler. See `docs/RELEASE_V07.zh-CN.md` for instructions and verification limits.

### JSON API 提取模式

新增 `JSON API fields`：公开 JSON URL → `data.items` 等数组路径 → 相对 `title` / `url` / `date` / `summary` 字段映射 → 预览 → 保存 → 订阅 RSS。参阅 `docs/JSON_API_MODE.zh-CN.md`。不支持需要个人账户凭据的 JSON 接口，也不会绕过网站访问限制。

### PDF publication feeds

Select **PDF publications** as extraction mode to monitor research-report listings.
Optionally scope `item_selector` to report cards (e.g. `article.report`) so navigation/footer PDFs are not included. PDF document URLs are emitted as RSS item links; the app does not download PDFs, bypass subscriptions, or claim verified enclosure metadata. See `docs/RELEASE_PDF_MODE.zh-CN.md`.

## Job lifecycle / monitoring (experimental)

Select **Job postings** as the content type. Leave inventory completeness as **Partial / unknown** for most sources. If and only if extraction covers the entire relevant job population on every successful refresh, enable **Complete listing**. Newly missing positions become `missing_once` after one successful complete refresh and `possibly_closed` after a second. Reappearing jobs reset to `observed`. Failing fetches do not advance disappearance status. Jobs are never automatically deleted. The authenticated `/api/feeds/{feed_id}/lifecycle` endpoint and editor diagnostics expose these observations.

This does not establish that a position is actually closed: pagination gaps, personalization, changed filter parameters and site-side rate limits can produce false absences. Use native job alerts where necessary.

## Feed43-inspired advanced capture rules

Select `Feed43 pattern`, optionally scope HTML with `global_pattern` such as
`<main>{%}</main>`, and match repeated entries with a second pattern such as
`<a href="{%}">{%}</a>`. Map fields using capture numbers (`1`, `2`) or
composite templates like `Research: {%2}`. Input length, match count, capture
size and execution time are bounded. This is a documented **subset**, not a
claim of byte-for-byte compatibility with every historic Feed43 rule.

## Consolidated engineering changes (current development snapshot)

- **Isolated browser execution path**: no in-process Chromium in the FastAPI service. Dedicated browser worker, private Docker network, bounded file-based IPC, and public-only forward proxy are implemented and tested with mocked upstream networking. Compose configuration and Docker image builds remain environment-dependent release checks.
- **Job change history**: optional full-inventory jobs mode records new/updated/missing-once/possibly-closed/reappeared transitions; existing jobs remain in the database. The lifecycle and `/events` APIs require admin authentication. Pagination hitting configured caps makes a job inventory incomplete rather than reporting closures.
- **Feed43-inspired capture patterns**: optional global region pattern and repeated-item pattern with numeric capture fields or `{%1}` templates; pattern timeouts and size caps apply. Not full historic Feed43 compatibility.
- **Read-only rule diagnosis**: detects empty/stale saved selectors and suggests candidate item rules using the current source structure, without writing to the saved recipe. All suggestions require preview and human confirmation.
- **Operational preflight and monitoring**: `tools/preflight.py` reports missing production prerequisites, `/api/monitor` flags stale and unhealthy sources, with no false production-GO claim.
- **PDF link handling**: supports explicit `type="application/pdf"` download endpoints in addition to filenames ending in `.pdf`. Does not retrieve or rehost PDF binaries.

See `docs/CONSOLIDATED_RELEASE.zh-CN.md` and `docs/ENGINEERING_AUDIT_CURRENT.zh-CN.md` for limitations.
