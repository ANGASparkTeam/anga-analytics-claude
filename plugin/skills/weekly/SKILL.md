---
name: weekly
description: Shortcut - GA4 weekly marketing report (last full Mon-Sun week vs the week before) for one client, in Thai.
argument-hint: <client or site> [week, e.g. "สัปดาห์ที่แล้ว" or 2026-10-19]
disable-model-invocation: true
---

# Weekly report (รายงานประจำสัปดาห์)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules (formatting, caveats, never invent numbers) and follow its template "1. Weekly report" in references/report-templates.md.

1. Client: the first words of the request. If missing, ask which client. Find it with `list_properties(search=...)`; if several properties match, ask.
2. Period: the last full Monday-Sunday week in Asia/Bangkok unless the request names one; compare `previous_period`. State both ranges as dates.
3. Calls: `kpi_summary`, `channel_performance`, `campaign_performance(limit=10)`, `page_performance(mode="landing", limit=10)`, `key_event_breakdown`, `trend(granularity="day")`.
4. Answer in Thai with the weekly skeleton, lead with the 3 key observations, end with 2-4 recommendations and the export offer.
