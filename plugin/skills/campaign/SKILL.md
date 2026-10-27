---
name: campaign
description: Shortcut - campaign post-mortem from GA4 (sessions, key events, revenue by source/medium, landing pages) for one client and campaign, in Thai.
argument-hint: <client> <campaign name or part of it> [start - end dates]
disable-model-invocation: true
---

# Campaign post-mortem (สรุปผลแคมเปญ)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules and follow its template "3. Campaign post-mortem" in references/report-templates.md.

1. Client = first words, campaign = the rest. Ask for whichever is missing. Find the property with `list_properties(search=...)`.
2. Campaign: `campaign_performance(campaign_contains=<name>)` over the last 90 days to find the exact UTM names and when sessions started/stopped; use that as the campaign window unless dates were given. Compare `previous_period`.
3. Calls for the window: `campaign_performance(campaign_contains=...)`, `key_event_breakdown`, `page_performance(mode="landing")`, `trend(granularity="day")`. Ask for the goal and budget if the user wants cost per key event; never assume a budget.
4. Thai post-mortem: result vs goal, by source/medium, landing pages, timeline, lessons (keep/stop/change), UTM data-quality notes.
