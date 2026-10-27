---
name: seo-drop
description: Shortcut - diagnose a drop in organic Google traffic using Search Console (and GA4 organic sessions) for one client, in Thai.
argument-hint: <client or domain> [period]
disable-model-invocation: true
---

# Why did organic search drop (ทำไม SEO / organic ตก)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules and its references/analysis-playbook.md.

1. Client: first words; ask if missing. Site with `gsc_list_sites(search=...)`; GA property with `list_properties(search=...)`.
2. Period: as given, else the last 28 days ending 3 days ago; compare `previous_period` and `previous_year` (seasonality).
3. Size and date it: `gsc_performance(granularity="day")`. Classify: impressions down = visibility/ranking/indexing loss; impressions flat but ctr down = SERP or title change, new competitor; position worse = ranking drop.
4. Locate it: `gsc_top_pages(compare=...)` sorted by clicks lost, then `gsc_page_queries` on the top losers; `gsc_top_queries` for lost keywords; split by `device="mobile"` / `"desktop"` if needed.
5. Cross-check GA4: `channel_performance` Organic Search for the same dates. GSC down + GA down = real; GSC flat + GA down = tracking/attribution.
6. Thai answer: how much and since when, which pages/keywords, likely cause (fact vs สมมติฐาน: algorithm update, redirect/404, noindex, content change), what to check and fix.
