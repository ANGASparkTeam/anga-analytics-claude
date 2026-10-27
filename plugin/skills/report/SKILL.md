---
name: report
description: Shortcut - build a GA4 and/or Search Console report for one client as an HTML page in the ANGA ONE design system (ANGA logo, orange #FF5300, Poppins + IBM Plex Sans Thai) unless the user asks for another format.
argument-hint: <client> [what: GA4 / SEO / ทั้งคู่ / แคมเปญ ...] [period] [format: html / excel / สไลด์ / แชท]
disable-model-invocation: true
---

# Report (รายงาน HTML แบบ ANGA ONE)

Request: $ARGUMENTS

Use the `marketing-report` skill for every rule (never invent numbers, period comparison, GSC formatting, caveats) and its references/report-templates.md and references/report-design.md. This command adds the default output: an HTML page in the ANGA ONE design system (one.anga.co.th): ANGA logo in the top bar and footer, white 14px-radius cards on a #FAFAFA page, orange #FF5300 for the main data, green/red change chips, Poppins + IBM Plex Sans Thai.

## 1. Understand the request

- Client = first words; ask if missing. GA4: `list_properties(search=...)`. SEO: `gsc_list_sites(search=...)`. Ask if several match.
- Scope: what the user named. "SEO"/"Search Console"/"คีย์เวิร์ด" -> SEO template; "แคมเปญ" -> campaign post-mortem; "ตก/ลด/ทำไม" -> why-drop; otherwise a GA4 overview (monthly template if the period is a month, weekly if a week). "ทั้งคู่"/"GA4+SEO" -> GA4 overview plus an SEO section.
- Period: as given; else last full month for monthly-style, last 28 days otherwise (SEO ends 3daysAgo). Compare `previous_period`; add `previous_year` for a month.
- Format: HTML unless the request says excel/xlsx, สไลด์/pptx, or แชท/ตอบในแชท. For those, use the xlsx/pptx skill or a chat answer and skip section 3.

## 2. Fetch, then decide the story

Run the calls of the matching template. Before writing any HTML, write down for yourself: the one finding (becomes the h1), 3-5 KPIs (one is the lead figure), and 3-5 evidence blocks ordered by size of effect, each with one chart or one table. Cut anything that does not support the finding.

## 3. Build the HTML

Start from [assets/template.html](assets/template.html) (read it; keep the `<style>` tokens, the two inline ANGA logo SVGs and the chart helpers unchanged) and replace every `{{...}}` placeholder and example block:

- `<title>`: short name, e.g. "acme ต.ค. 2026". `h1`: the finding in one sentence, at most two lines.
- Context line: client, GA4 property name + id and/or GSC site_url, exact date ranges, data date.
- Top bar: keep the logo; set `.doc-type` (e.g. "Monthly Report · GA4 + Search Console").
- KPI cards: 3-5 `.card.kpi`; the answer figure gets `.lead-figure`. Change `.chip` class by meaning: `good`/`bad`; position and bounce rate are inverted (lower = good); `change_pct` null -> chip text "ใหม่" without class; no comparison -> no chip. `.prev` shows the previous value.
- Evidence: one `section.card` per point (two related ones may sit in `<div class="grid-2">`); `h2` states what it shows ("Organic เป็น 75% ของยอดที่หาย"). Charts: one `<canvas>` per `.chart` div, drawn with the helpers at the bottom - `line(id, labels, current, previous)` for trends, `bars(id, labels, values, previousValues, {horizontal:true})` for rankings, `bars(...)` vertical for per-week/month columns, `share(id, labels, values)` (doughnut) for up to five parts. GA4 channel groups always use their fixed colours: pass `{colors: channelColors(labels)}` to `bars`, and `<span class="dot" style="background:...">` in tables. Add `{pct:true}` when values are 0-1 rates. Tables: numbers in `td.num`, names in `td.name` (shorten URLs to the path), change chips coloured like the KPIs, `tr.highlight` for the row the text talks about, top 10-20 rows plus a `.table-note` with how many were left out.
- Recommendations: 2-4 `li`, each naming the page/keyword/campaign and an owner.
- `.notes`: data sources (property id, site_url), every `meta.notes` / sampled / thresholded / truncated / GSC lag caveat.
- Paste numbers exactly as returned (rates as 0-1 into charts with `{pct:true}`; in text as %). Never round up or estimate; derived numbers recomputed from returned values.
- Thai text everywhere except metric names in parentheses on first use.
- Do not add gradients (the logo is the only one), heavier shadows, emoji, icons, extra colours, extra fonts, or decorative elements. Orange is for the main data, the lead KPI and the brand mark only.

## 4. Deliver

- Claude Code / where files can be written: save to `reports/<client>-<scope>-<YYYY-MM-DD>.html` in the working directory (create the folder), then open it in the browser pane or give the path.
- claude.ai / Desktop chat: deliver the page as an HTML artifact.
- Before delivering, search the finished HTML for `{{` and `}}`: there must be none. Every placeholder is filled with real data or its element is removed (the template's sample cards, rows and chart call are examples, not content), and the template's leading TEMPLATE comment is deleted.
- Tables: mark secondary columns (previous value, extra metrics) `hide-sm` so phones show name, value and change without sideways scrolling.
- Check it renders: Thai text shows (no boxes), charts appear, nothing overflows at phone width. Then give a 3-line summary in chat (the finding + 2 key numbers) and ask if they also want Excel or slides.
