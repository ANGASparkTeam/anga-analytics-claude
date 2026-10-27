# GA4 Marketing MCP — build contract

Shared agreement between the three workstreams. Change it only by asking the lead.

## Decisions (from user)
- Clients: claude.ai / Claude Desktop, added once by the org owner as a **custom connector** (remote MCP, Streamable HTTP, OAuth).
- Users sign in with Google; only emails in the company Google Workspace domain(s) are allowed (`ALLOWED_DOMAINS`, comma-separated).
- GA4 is read with **one shared service account** (Cloud Run runtime identity, ADC, `analytics.readonly`). No key files in prod.
- Deploy target: Google Cloud Run. This round = code + local tests + deploy script/README. Nothing is deployed for real.
- Stack: Python 3.12, uv, FastMCP 4.x (installed: see `uv.lock`; read installed source under `.venv/lib/python3.12/site-packages/fastmcp` when docs disagree), `google-analytics-data`, `google-analytics-admin`.

## Layout
```
src/ga4_mcp/
  config.py        # (Workstream A) Settings from env + properties.yaml loader
  ga_client.py     # (A) thin wrapper over Data/Admin API, cache, quota/sampling flags
  reports.py       # (A) pure functions: build requests, shape responses, period compare
  tools.py         # (A) def register_tools(mcp: FastMCP) -> None
  auth.py          # (B) def build_auth() -> AuthProvider | None   (None when AUTH_DISABLED=true for local dev)
  server.py        # (B) creates FastMCP("marketing-analytics", auth=build_auth()), calls register_tools, /healthz, main()
tests/             # A: test_reports.py, test_tools.py ; B: test_auth.py
properties.example.yaml   # (A)
Dockerfile, deploy/ (B), README.md (B, Thai + English commands)
plugin/skills/marketing-report/  # (C) main skill; plugin/skills/<shortcut>/ = slash shortcuts
```
Entry point in pyproject: `ga4-mcp = "ga4_mcp.server:main"` (B adds it).

## properties.yaml
```yaml
default: main
properties:
  main:   { id: "123456789", name: "เว็บไซต์หลัก", timezone: "Asia/Bangkok", currency: "THB",
            key_events: ["purchase", "generate_lead"] }
  app:    { id: "987654321", name: "แอป", key_events: ["sign_up"] }
```
Every tool takes `property: str | None` = alias or numeric id; None → `default`.

## Tools (names and params are fixed; Skill C relies on them)
All read-only. Dates: `start_date`/`end_date` accept `YYYY-MM-DD` or GA relative (`today`, `yesterday`, `NdaysAgo`). `compare` ∈ `previous_period` | `previous_year` | `none` (default `previous_period`).
Every response is a JSON dict with: `property` {alias,id,name}, `date_range`, `compare_range` (or null), `rows` / summary fields, and `meta` {`sampled`: bool, `thresholded`: bool, `row_count`, `truncated`: bool, `cached`: bool, `currency`, `notes`: [str]}.
Numbers are raw numbers (not strings); rates as fractions 0–1; for each metric with a comparison include `{value, previous, change_pct}`.

1. `list_properties(search=None, limit=30)` — configured aliases + accessible properties flattened as {property_id, display_name, account_name, account}, filtered by search words (account/property name or id).
2. `kpi_summary(property, start_date, end_date, compare)` — totals: activeUsers, newUsers, sessions, engagedSessions, engagementRate, averageSessionDuration, screenPageViews, keyEvents, sessionKeyEventRate, totalRevenue, ecommercePurchases.
3. `channel_performance(property, start_date, end_date, compare, dimension="sessionDefaultChannelGroup", limit=20)` — dimension ∈ sessionDefaultChannelGroup | sessionSourceMedium | sessionSource; metrics sessions, activeUsers, engagementRate, keyEvents, sessionKeyEventRate, totalRevenue + share_of_sessions.
4. `campaign_performance(property, start_date, end_date, compare, campaign_contains=None, limit=50)` — by sessionCampaignName (+ sessionSourceMedium); same metrics.
5. `page_performance(property, start_date, end_date, compare, mode="landing", path_contains=None, limit=50)` — mode `landing` (landingPagePlusQueryString… use `landingPage`) or `pages` (`pagePath`); metrics sessions/screenPageViews, activeUsers, engagementRate, keyEvents, bounceRate.
6. `key_event_breakdown(property, start_date, end_date, compare, event_names=None, by=None)` — counts per eventName for configured key events (or given list), optional `by` dimension (e.g. sessionDefaultChannelGroup, deviceCategory).
7. `trend(property, start_date, end_date, metrics=["sessions","activeUsers","keyEvents"], granularity="day")` — granularity day|week|month (date|isoYearIsoWeek|yearMonth).
8. `realtime_overview(property)` — activeUsers last 30 min by country, deviceCategory, unifiedScreenName (top 10 each).
9. `get_metadata(property, search=None)` — available dims/metrics incl. custom ones, filtered by substring.
10. `run_report(property, start_date, end_date, dimensions, metrics, dimension_filter=None, order_by=None, limit=100)` — escape hatch; validates names against metadata first and returns helpful error listing close matches. `dimension_filter` simple form: `{"field": "...", "match": "exact|contains|begins_with|regex", "value": "..."}` or list of those (AND).

0. `whoami()` — connection check: {connected, signed_in_as (connector login email), data_access (shared identity)}; reads no analytics data.

### Search Console tools (`gsc_tools.py`)
Same identity as GA4 with scope `webmasters.readonly`. Responses use `property` = {site_url}; metrics clicks, impressions (ints), ctr (0–1), position (avg rank, lower is better; with a comparison it also has `change` = absolute difference). Default range `30daysAgo`–`3daysAgo` (GSC lags 2–3 days; days are Pacific Time). `site` = exact site_url or a domain (resolved to the domain property `sc-domain:` first, then https, then http URL prefix; a subdomain falls back to its domain property; `siteUnverifiedUser` sites are rejected). `device` ∈ desktop|mobile|tablet, `country` = ISO alpha-3 (`tha`).

11. `gsc_list_sites(search=None, limit=30)` — sites as {site_url, type: domain|url_prefix, permission, queryable}.
12. `gsc_performance(site, start_date, end_date, compare, granularity="none", device=None, country=None, search_type="web")` — totals; `granularity` day|week|month adds `rows` (date|isoYearIsoWeek|yearMonth).
13. `gsc_top_queries(site, start_date, end_date, compare, query_contains=None, page_contains=None, device=None, country=None, order_by="clicks", limit=50)` — rows by `query`.
14. `gsc_top_pages(site, start_date, end_date, compare, page_contains=None, query_contains=None, device=None, country=None, order_by="clicks", limit=50)` — rows by `page` (full URL).
15. `gsc_page_queries(site, page, start_date, end_date, compare, device=None, country=None, order_by="clicks", limit=50)` — queries for one page; `page` starting with http(s) = exact URL, else contains.

Limits: hard cap 1000 rows returned; set `meta.truncated`. Cache: TTL 15 min for ranges ending before today, 3 min otherwise; key = full request. On GA quota errors return a clear message (not a stack trace). Request `returnPropertyQuota=True` and surface tokens remaining in `meta.quota` when low (<20%).

## Env vars
`GA4_PROPERTIES_FILE` (default `properties.yaml`), `ALLOWED_DOMAINS`, `BASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `JWT_SIGNING_KEY`, `STORAGE_ENCRYPTION_KEY`, `AUTH_DISABLED` (local only), `PORT` (default 8080).
