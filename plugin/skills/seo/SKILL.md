---
name: seo
description: Shortcut - Search Console SEO report for one client (clicks, impressions, CTR, position, top keywords and pages, opportunities), in Thai.
argument-hint: <client or domain> [period, e.g. "เดือนที่แล้ว" or "28 วัน"]
disable-model-invocation: true
---

# SEO report (รายงาน SEO จาก Search Console)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules (GSC formatting: ctr as %, position lower is better, use `change`) and follow its template "5. SEO report (Search Console)" in references/report-templates.md.

1. Client: first words; ask if missing. `gsc_list_sites(search=...)`; prefer the `domain` type; if several url_prefix sites match (www, blog, landing), ask or report the main one and list the others.
2. Period: as given, else the last 28 days ending 3 days ago (tool default); compare `previous_period`; for a full month also `previous_year`.
3. Calls: `gsc_performance(granularity="week")`, `gsc_top_queries(limit=20)`, `gsc_top_queries(order_by="impressions", limit=30)`, `gsc_top_pages(limit=20)`, `gsc_page_queries` for the 1-2 pages that moved most. Brand terms from company-config split brand vs non-brand (`query_contains`).
4. Thai report: overview table, top keywords, biggest losers and why (rank / impressions / CTR), opportunities (high impressions, low CTR, position 4-15), pages, 2-4 recommendations, data notes (2-3 day lag, anonymized queries).
