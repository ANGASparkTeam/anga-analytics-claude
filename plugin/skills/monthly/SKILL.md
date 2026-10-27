---
name: monthly
description: Shortcut - GA4 monthly marketing report (last full month, MoM and YoY) for one client, in Thai, with an executive summary.
argument-hint: <client or site> [month, e.g. "ต.ค. 2026"]
disable-model-invocation: true
---

# Monthly report (รายงานประจำเดือน)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules and follow its template "2. Monthly report" in references/report-templates.md.

1. Client: first words of the request; ask if missing. `list_properties(search=...)`; ask if several match.
2. Period: the last full calendar month (Asia/Bangkok) unless named. Compare both `previous_period` (MoM) and `previous_year` (YoY). Check company-config for KPI targets.
3. Calls: `kpi_summary` x2 (MoM, YoY), `trend(granularity="week")`, `channel_performance`, `campaign_performance(limit=10)`, `page_performance(mode="landing", limit=10)`, `key_event_breakdown(by="deviceCategory")`.
4. Optional SEO line: if the client has a Search Console site (`gsc_list_sites(search=...)`), add one row from `gsc_performance` for the same month.
5. Thai report: executive summary (3-5 lines) first, then the monthly skeleton, recommendations for next month, export offer.
