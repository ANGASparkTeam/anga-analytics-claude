# Report design (การออกแบบรายงานให้ดูตั้งใจ ไม่ใช่ AI template)

Read before producing any visual output: an HTML page/artifact, a dashboard, slides (.pptx), or charts in Excel. Plain chat answers only need the formatting rules in SKILL.md.

Adapted for marketing reports from the app-screen and data rules of tasteskill v2 by Leonxlnx (MIT, github.com/Leonxlnx/taste-skill). Their scripts and site library are not included; the rules below are applied by eye.

## Contents
- The one idea
- Page structure
- KPI strip
- Deltas: colour means good or bad
- Charts
- Tables
- Colour and type
- Tells to avoid
- Check before delivering

## The one idea

A report answers one question. Write the answer as the title, not the report type: "ทราฟฟิก Organic ลด 24% จากหน้า /blog หลังอัปเดต 21 ต.ค." beats "รายงานประจำสัปดาห์". Everything on the page supports or qualifies that sentence; anything that does not goes to an appendix or is cut.

## Page structure

1. Title (the finding) + one line of context: client/property, site_url for GSC, exact date range, compare range, "ข้อมูล ณ วันที่ ...".
2. KPI strip (3-5 figures).
3. The evidence, one block per point, biggest effect first: a chart or table, each with a heading that states what it shows ("Organic เป็น 75% ของยอดที่หาย"), not "Channel performance".
4. Recommendations: 2-4, each with page/keyword/campaign, owner, next step.
5. Data notes (sampling, thresholding, GSC lag, truncated rows) in small text at the end, never hidden.

Left-aligned throughout; equal outer margins; one left edge for all text blocks. The gap between sections is clearly larger than gaps inside a section. No section numbering ("01 / 02") and no small uppercase label above headings.

## KPI strip

- 3-5 figures in one container split into equal columns (not a separate card per KPI, no icon in a coloured circle, no sparkline in the tile).
- Label above (sentence case, ~14px, grey), value below (~24-30px, regular or semibold), unit as a smaller grey suffix ("165 วินาที", "6.55%").
- When one figure is the answer to the title, it leads: about 1.3x the size of its siblings. No other number on the page is larger.
- A figure shown in the strip is not repeated in a legend or a duplicate card below.

## Deltas: colour means good or bad

- State the window in words: "เทียบ 13-19 ต.ค.", "เทียบปีก่อน".
- Colour only the delta number, and colour by meaning, not direction. Lower is better for: GSC `position`, bounceRate, cost per key event. A rise in those is negative-coloured.
- `change_pct: null` (previous was 0) -> write "ใหม่" in grey, never "+100%" or "∞". No change / nothing to compare -> grey dash.
- Sign on every change: "+12.4%", "-8.1%", "+5.1 อันดับ (แย่ลง)".

## Charts

| Question | Form | Tool data |
|---|---|---|
| เปลี่ยนไปอย่างไรตามเวลา | one line, straight segments, no point markers; fill at most a ~15% flat tint | `trend`, `gsc_performance(granularity=...)` |
| ปริมาณต่อช่วง (รายสัปดาห์/เดือน) | columns, square corners | `trend(granularity="week")` |
| ใครมากสุด (ช่องทาง, แคมเปญ, หน้า, คีย์เวิร์ด) | sorted horizontal bars, value labelled at the bar end | `channel_performance`, `gsc_top_queries` |
| สัดส่วน | 100% stacked bar or thin ring, five parts max (group the rest as "อื่นๆ"); never a pie with 8 slices | `share_of_sessions` |
| เทียบสองช่วง | paired bars per category (current in the accent, previous in light grey) or a table with a delta column | any tool with compare |
| ใกล้เป้าแค่ไหน | progress bar with both ends labelled, fill = true ratio | company-config targets |

- One series per chart, three at most. Another metric = another chart or a table, not a second y-axis.
- 3-5 horizontal gridlines, light grey; no y-axis line; round tick steps; bars and counts start at zero.
- 4-8 x labels, never rotated; dates on a time scale.
- Annotate the event that explains a spike or drop (1px marker + short label: "แคมเปญ 11.11 เริ่ม", "เว็บย้ายโดเมน") when the user or data confirms it; label hypotheses as สมมติฐาน.
- A forecast or target line is dashed and labelled at its end.
- Legend: none for one series (the heading names it); otherwise a small dot + label in the chart header, five items max.
- Few numbers -> no chart. Three KPIs do not need a donut.

## Tables

- Numbers right-aligned in tabular figures; identity column (page, keyword, campaign) left-aligned and widest; shorten long URLs to the path ("/loan/calculator").
- Fixed decimals per metric: counts 0, rates 1-2 (as %), money 0-2, position 1. Thousands separators everywhere.
- A delta column next to each compared metric, coloured per the delta rules.
- Lines inside real tables are fine (row dividers); no boxes around every cell. Top 10-20 rows; say how many were left out.

## Colour and type

- One ground (white or near-white), one ink (near-black, full strength for body text), one accent. The accent goes on the main data (current period, the series the title is about) and nowhere decorative. Previous period / context in light grey.
- Status colours (green/red) only on deltas. The same subject keeps the same colour on every chart (Organic Search is the same hue everywhere). More than four hues on a page is a smell.
- House style (default for every visual output): the **ANGA ONE design system** (one.anga.co.th, light theme), implemented in the `report` command's assets/template.html with the ANGA logo. Tokens: primary `#FF5300`, orange tint `#FFEEE5`, page `#FAFAFA`, card `#FFFFFF` with 1px `#E8E9ED` border, 14px radius and a very soft shadow, surface `#F4F4F5`, text `#111827` / `#657386` / `#9CA3B0`, good chip `#DFF6EB` on `#0E6243`, bad chip `#FCEEEE` on `#A02222`, neutral chip `#F3F4F6` on `#364463`, caveat `#FEF4E1` on `#8F4E14`; series after orange: `#2563EB`, `#059669`, `#D97706`, `#6B7280`; fixed channel colours (Organic Search `#059669`, Paid Search `#2563EB`, Direct `#6B7280`, ...). Fonts: Poppins (Latin, numbers) + IBM Plex Sans Thai. Where this system and the generic rules above differ (cards, rounded corners, soft card shadow, pill chips, doughnut for shares), the ANGA ONE system wins. Use a client's brand colour only when the user asks.
- Thai text needs a font with Thai glyphs: one family for everything, Poppins + IBM Plex Sans Thai by default (ANGA ONE; Google Fonts); others only if asked. Body 16-18px, line-height 1.6-1.7 for Thai (taller than for Latin). Two typefaces at most.
- Slides: one finding per slide, title = the finding, one chart or one table, big numbers; no bullet walls.

## Tells to avoid

These make a report read as generated: gradients (backgrounds, buttons, text); violet/indigo or cream-with-terracotta palettes; drop shadows and glows on cards; glassy blurred panels; emoji as icons or bullets (📈🚀); a row of identical icon cards; small uppercase letter-spaced labels; monospace outside code; 01/02/03 numbering; rainbow charts; 3D or exploded pies; smoothed curves that invent values between data points; invented or rounded-up numbers; "+100%" grown from zero; a full-width chart that is 85% empty; a styled accent word in the title.

Removing ornament leaves space: fill it with the content made larger (the main chart, the key number), not with another ornament.

## Check before delivering

1. Does the title state the finding, and does every block support it?
2. Every number traceable to a tool response in this conversation; derived values recomputed.
3. Deltas coloured by good/bad (position and bounce inverted); "ใหม่" instead of percentages from zero.
4. Each chart: one question, zero baseline for bars, readable unrotated labels, accent on the main series only.
5. Thai renders (no tofu boxes), line height comfortable, numbers right-aligned in tables.
6. Data notes present (sampled/thresholded/truncated/GSC lag) and the date ranges stated.
7. If rendered (HTML/artifact), view it at desktop and phone width and fix what overlaps or overflows.
