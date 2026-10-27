---
name: marketing-report
description: Turns Google Analytics 4 and Google Search Console data from the GA4 MCP connector into marketing analysis and reports for a Thai marketing team - KPI summaries, channel and campaign performance, landing pages, key events/conversions, trends, SEO (organic search keywords, clicks, impressions, CTR, ranking), and "why did traffic drop" diagnosis, always with period comparison and data-quality caveats. Use when the user asks in Thai or English for รายงาน GA, ยอดเข้าเว็บ, ทราฟฟิก, traffic, แคมเปญ, campaign, conversion, key event, ลีด, ยอดขายเว็บ, ช่องทาง, weekly/monthly report, รายงานประจำสัปดาห์/เดือน, สรุปผลแคมเปญ, ทำไมทราฟฟิกตก, SEO, Search Console, GSC, คีย์เวิร์ด, keyword, อันดับ Google, ranking, organic search, or GA4 numbers.
---

# Marketing Report (GA4 + Search Console)

Turn GA4 and Search Console (GSC) connector data into analysis a marketing team can act on. User-facing output is in Thai (keep standard terms like sessions, engagement rate, key event in English in parentheses on first use).

Reference files (load only when needed):
- [references/metrics-glossary.md](references/metrics-glossary.md) - Thai definitions + pitfalls. Read when explaining a metric or when numbers look odd.
- [references/report-templates.md](references/report-templates.md) - weekly, monthly, campaign post-mortem, "traffic drop" skeletons with exact tool calls. Read before building any report.
- [references/analysis-playbook.md](references/analysis-playbook.md) - drop/spike diagnosis, UTM hygiene, sanity thresholds. Read for any "why" question.
- [references/report-design.md](references/report-design.md) - layout, KPI strip, chart choice, tables, colour, Thai type, tells to avoid. Read before any visual output (HTML/artifact, dashboard, slides, Excel charts).
- [references/company-config.md](references/company-config.md) - property aliases, key events, KPI targets, campaign naming. Read FIRST in each conversation; if it still contains `TODO`, say so and rely on `list_properties` / `get_metadata` instead.

## Workflow

1. **Clarify** (ask only what is missing, max 2 questions): which property (alias; default if user does not care), which period, which goal (monitor / explain a change / evaluate a campaign). If the user says "สัปดาห์ที่แล้ว" etc., convert to explicit dates yourself (Bangkok time, Mon-Sun weeks) and state them. If property is unknown, call `list_properties(search="<client or site name>")` - the shared account sees hundreds of clients, so always search by name; if several properties match, ask which one. For SEO / Search Console questions find the site with `gsc_list_sites(search="<name>")` (the GA property and GSC site usually share the domain; prefer the `domain` type).
2. **Pick tools** with the table below. Prefer curated tools; use `run_report` only when no curated tool has the dimension/metric (check with `get_metadata` first).
3. **Always compare periods.** Default `compare="previous_period"`; use `previous_year` for monthly/seasonal views. Use `compare="none"` only when the user asks. Never compare a partial period to a full one - if `end_date` is today/yesterday, note GA data lag (~24-48h) and prefer ending at least 2 days ago for finals.
4. **Check `meta`** of every response: `sampled`, `thresholded`, `truncated`, `cached`, `notes`, `quota`. If any is true/low, add a one-line caveat in Thai (see "Caveats"). Do not hide it.
5. **Present**: (1) headline numbers, (2) what changed (biggest movers up and down), (3) why (drill down one level at a time - see playbook), (4) recommendations with owner/next step. Lead with the answer, not the method.
6. **Offer export** at the end: ตารางสรุป (markdown table), หน้ารายงาน HTML แบบ ANGA ONE (the `report` command's template: ANGA logo, orange #FF5300, Poppins + IBM Plex Sans Thai), ไฟล์ Excel (.xlsx), or สไลด์ (.pptx). Only produce if the user says yes; use the available artifact/xlsx/pptx skills with the numbers already fetched (do not re-query), and follow [references/report-design.md](references/report-design.md): title = the finding, KPI strip, one question per chart, deltas coloured good/bad, no AI-template tells.

## Which tool for which question

| Question (Thai / English) | Tool |
|---|---|
| มี property อะไรบ้าง / หา property ของลูกค้า | `list_properties(search=...)` |
| ภาพรวม ผู้ใช้ เซสชัน ยอดขาย / overall KPIs | `kpi_summary` |
| ช่องทางไหนดี / channel mix, source/medium | `channel_performance` (`dimension`: `sessionDefaultChannelGroup` default, `sessionSourceMedium`, `sessionSource`) |
| แคมเปญ X ผลเป็นอย่างไร / campaign results | `campaign_performance` (`campaign_contains`) |
| หน้าไหนคนเข้า / landing page, top pages | `page_performance` (`mode="landing"` or `"pages"`, `path_contains`) |
| Conversion / ลีด / ซื้อ แยกตามอีเวนต์ | `key_event_breakdown` (`event_names`, `by` e.g. `deviceCategory`) |
| แนวโน้ม รายวัน/สัปดาห์/เดือน / trend, when did it drop | `trend` (`granularity` day/week/month) |
| ตอนนี้มีคนอยู่กี่คน / right now | `realtime_overview` |
| ไม่แน่ใจว่ามี dimension/metric ไหน | `get_metadata` (`search`) |
| อย่างอื่นที่ไม่มีในข้างบน (เช่น device x region) | `run_report` (last resort) |
| หาเว็บใน Search Console / which GSC site | `gsc_list_sites(search=...)` |
| SEO ภาพรวม คลิก อิมเพรสชัน CTR อันดับ / organic search overview | `gsc_performance` (`granularity` none/day/week/month, `device`, `country`) |
| คีย์เวิร์ดไหนพาคนมา / top keywords, brand vs non-brand | `gsc_top_queries` (`query_contains`, `order_by` clicks/impressions) |
| หน้าไหนได้ทราฟฟิกจาก Google / top organic pages | `gsc_top_pages` (`page_contains`) |
| หน้านี้ติดคีย์เวิร์ดอะไร / why did this page lose clicks | `gsc_page_queries` (`page` = full URL or path) |

Tool names are used as the connector exposes them (a client may show them prefixed with the connector name). All tools are read-only. GA4 tools take `property` (alias or numeric id; omit for default); `gsc_*` tools take `site` (a site_url from `gsc_list_sites`, or a domain).

## Rules (never break)

- **Never invent numbers.** Every figure comes from a tool response in this conversation. If a call failed or data is missing, say so; do not estimate. Derived values (sums, shares, differences) must be computed from returned numbers and be correct.
- **Quote context** in every report: property name (alias + id), exact date range, compare range, and "ข้อมูล ณ วันที่ ..." Timezone is Asia/Bangkok; currency THB (use the `meta.currency` if different and say so).
- **Format**: rates and `share_of_sessions` are fractions in the API (0.0432) - show as percent `4.32%`. `change_pct` is already a percentage (12.4 means +12.4%) - do not multiply it by 100; `null` means previous was 0. Use thousands separators `12,345`; THB as `฿12,345` or `12,345 บาท`; change as `+12.4%` / `-8.1%` with an up/down word (เพิ่มขึ้น/ลดลง). Round to 1-2 decimals for rates, whole numbers for counts. If `previous` is 0, write "ใหม่/ไม่มีข้อมูลเทียบ" instead of a percentage.
- **Separate fact from hypothesis.** Label causes you could not verify with GA data as "สมมติฐาน" and say what to check.
- **Search Console**: `ctr` is a fraction (show as %); `position` is the average Google rank where **lower is better** - report it with the `change` field (e.g. "อันดับเฉลี่ย 14.3 แย่ลง 5.1 อันดับ"), not `change_pct`. GSC clicks are not GA sessions (different counting); never add or subtract them. Totals in `gsc_performance` include anonymized queries, so they exceed the sum of `gsc_top_queries` rows.
- **Small numbers**: do not make claims from fewer than ~100 sessions per row; call it "ตัวอย่างน้อย".
- **Names**: key events (not "conversions") is the GA4 term; map to business meaning via company-config.
- Read-only: the connector cannot change GA settings; tell the user to do tracking fixes in GA/GTM.

## Caveats (add when triggered)

| `meta` / situation | Say (Thai) |
|---|---|
| `sampled: true` | ข้อมูลบางส่วนเป็นการสุ่มตัวอย่าง (sampling) ตัวเลขอาจคลาดเคลื่อนเล็กน้อย - ลองช่วงเวลาสั้นลง |
| `thresholded: true` | GA ซ่อนแถวที่มีผู้ใช้น้อยเพื่อความเป็นส่วนตัว (thresholding) ผลรวมอาจต่ำกว่าจริง |
| `truncated: true` | แสดงเฉพาะ N แถวแรก ยังมีแถวที่ไม่ได้แสดง - ผลรวมของแถวไม่เท่ากับยอดรวม |
| `cached: true` | ข้อมูลจากแคช (ไม่เกิน ~15 นาที) |
| `meta.quota` present | โควตา GA API ใกล้หมด ลดจำนวนการดึงข้อมูล |
| range includes today/yesterday | ข้อมูล 1-2 วันล่าสุดอาจยังไม่ครบ (GA ประมวลผลช้า 24-48 ชม.) |
| `(not set)` > 5% of rows | ดู analysis-playbook: UTM / tracking |
| GSC range ends within 3 days of today | ข้อมูล Search Console 2-3 วันล่าสุดยังไม่ครบ |
| `meta.notes` non-empty | relay each note |

## Example

User: "ขอรายงานทราฟฟิกสัปดาห์ที่แล้วหน่อย ทำไมยอดตก"

1. Read company-config; property default = `main`. Today is Tue 2026-10-27 -> last full week 2026-10-19 to 2026-10-25 (state it).
2. `kpi_summary(start_date="2026-10-19", end_date="2026-10-25", compare="previous_period")` -> sessions 41,200 vs 48,900 (-15.7%), keyEvents flat.
3. `channel_performance(...)` -> Organic Search 18,300 vs 24,100 (-24.1%) is most of the drop. Drill: `channel_performance(dimension="sessionSourceMedium")`, then `page_performance(mode="landing")`, `trend(granularity="day")` to find the date.
4. Answer in Thai:

> **สรุป (เว็บไซต์หลัก, 19-25 ต.ค. 2026 เทียบ 12-18 ต.ค.)**: เซสชัน 41,200 (-15.7%), key events 1,030 (+0.4%)
> **เปลี่ยนอะไร**: Organic Search ลดลง 5,800 เซสชัน (-24.1%) คิดเป็น ~75% ของยอดที่หาย
> **ทำไม**: ลดลงเริ่ม 21 ต.ค. และกระจุกที่หน้า /blog/... (ข้อเท็จจริงจาก GA); สาเหตุ (เช่น อันดับ SEO เปลี่ยน) = สมมติฐาน (ตรวจต่อด้วย `gsc_top_pages` / `gsc_page_queries`)
> **แนะนำ**: 1) ตรวจอันดับคีย์เวิร์ดหน้า blog 2) ... 
> ข้อควรระวัง: ไม่มี sampling/thresholding
> ต้องการส่งออกเป็นตาราง / Excel / สไลด์ไหมครับ

More skeletons in [references/report-templates.md](references/report-templates.md). (The numbers above are illustrative of format only; never reuse them.)
