---
name: why-drop
description: Shortcut - diagnose why GA4 traffic or key events dropped (or spiked) for one client, drilling down channel, source, page, device and Search Console, in Thai.
argument-hint: <client or site> [period, e.g. "สัปดาห์ที่แล้ว"]
disable-model-invocation: true
---

# Why did traffic drop (ทำไมทราฟฟิกตก)

Request: $ARGUMENTS

Use the `marketing-report` skill: its references/analysis-playbook.md (drill-down order) and template "4. Ad-hoc: why did traffic drop".

1. Client: first words; ask if missing. `list_properties(search=...)`.
2. Period: as given, else the last 7 full days; compare `previous_period` and also `previous_year` for seasonality.
3. Drill down, stop when ~70% of the change is explained: `kpi_summary` -> `trend(granularity="day")` (start date) -> `channel_performance` -> `channel_performance(dimension="sessionSourceMedium")` -> `page_performance(mode="landing")` -> device (`key_event_breakdown(by="deviceCategory")`).
4. If Organic Search explains the drop, confirm with Search Console: `gsc_list_sites(search=...)`, `gsc_performance(granularity="day")`, then `gsc_top_pages` and `gsc_page_queries` for the pages that lost most. GSC flat while GA organic fell = tracking/attribution, not SEO.
5. Thai answer: short answer with confidence, steps checked with numbers, facts vs สมมติฐาน, actions now.
