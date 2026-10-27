---
name: keywords
description: Shortcut - SEO keyword opportunities from Search Console for one client - high-impression low-CTR queries, positions 4-15, rising and falling keywords, in Thai.
argument-hint: <client or domain> [topic word to filter, e.g. "สินเชื่อ"]
disable-model-invocation: true
---

# Keyword opportunities (โอกาสคีย์เวิร์ด)

Request: $ARGUMENTS

Use the `marketing-report` skill for all rules (GSC formatting).

1. Client = first words (ask if missing), optional topic = the rest. Site with `gsc_list_sites(search=...)`.
2. Period: last 28 days ending 3 days ago, compare `previous_period`.
3. Calls: `gsc_performance` (site average ctr and position), `gsc_top_queries(order_by="impressions", limit=200, query_contains=<topic>)`, `gsc_top_queries(limit=50, query_contains=<topic>)`.
4. From the returned rows only, list:
   - Quick wins: position 4-15 with high impressions (moving to top 3 gains most clicks).
   - CTR gaps: ctr well below the site average at a similar position (rewrite title/meta).
   - Rising and falling keywords by clicks change.
   - For the top 3 opportunities, `gsc_page_queries` on their landing page (from `gsc_top_pages(query_contains=...)`) to name the page to improve.
5. Thai answer: a table per group (คีย์เวิร์ด, คลิก, อิมเพรสชัน, CTR, อันดับ, หน้า), then concrete actions per page. Never invent search volume; GSC has impressions, not volume.
