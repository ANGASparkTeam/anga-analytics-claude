# Report templates (แม่แบบรายงาน)

## Contents
- Common header and footer
- 1. Weekly report
- 2. Monthly report
- 3. Campaign post-mortem
- 4. Ad-hoc: why did traffic drop
- 5. SEO report (Search Console)

Fill `[ ]` only from tool results. Numbers formatted per SKILL.md rules (%, thousands separators, THB). Resolve dates first and write them out.

## Common header and footer

Header:
```
# [ชื่อรายงาน]
Property: [name] ([alias], ID [id]) | ช่วงเวลา: [start] - [end] | เปรียบเทียบกับ: [compare_start] - [compare_end] | เขตเวลา Asia/Bangkok, สกุลเงิน THB
```
Footer:
```
ข้อควรระวังข้อมูล: [sampling/thresholding/truncated/ข้อมูลล่าสุดยังไม่ครบ หรือ "ไม่พบข้อจำกัด"]
ที่มา: GA4 (ดึงเมื่อ [วันที่]) | ต้องการส่งออกเป็น ตาราง / Excel / สไลด์ ไหม?
```

## 1. Weekly report (รายงานประจำสัปดาห์)

Period: last full Mon-Sun week vs the week before (`compare="previous_period"`), end date <= 2 days ago when possible.

Calls:
1. `kpi_summary` - headline
2. `channel_performance` (default dimension, limit 10)
3. `campaign_performance` (limit 10; sort by sessions mentally)
4. `page_performance(mode="landing", limit 10)`
5. `key_event_breakdown` (configured key events)
6. `trend(granularity="day")` - for the daily chart/pattern

Skeleton:
```
## ภาพรวมสัปดาห์
| ตัวชี้วัด | สัปดาห์นี้ | สัปดาห์ก่อน | เปลี่ยนแปลง | เป้าหมาย |
(ผู้ใช้, เซสชัน, Engagement rate, key events, อัตรา key event, รายได้) - คอลัมน์เป้าหมายจาก company-config ถ้ามี
## 3 ข้อสังเกตสำคัญ
1. [เรื่องที่เปลี่ยนมากที่สุด + ตัวเลข]
2. ...
## ช่องทาง (Top 5)  | ช่องทาง | เซสชัน | สัดส่วน | เปลี่ยน | key events | อัตรา key event |
## แคมเปญเด่น / ต้องแก้ไข
## หน้า Landing Top 5 | หน้า | เซสชัน | Engagement rate | key events |
## Key events แยกตามชนิด
## วันที่ผิดปกติ (จาก trend: วันสูงสุด/ต่ำสุด)
## ข้อเสนอแนะสัปดาห์หน้า (2-4 ข้อ, ระบุว่าใครควรทำอะไร)
```

## 2. Monthly report (รายงานประจำเดือน)

Period: full calendar month. Compare: `previous_period` AND `previous_year` (two calls to `kpi_summary`; one `channel_performance` with previous_year if seasonal).

Calls: `kpi_summary` x2 (MoM, YoY), `channel_performance` (sessionDefaultChannelGroup, then sessionSourceMedium limit 10), `campaign_performance` limit 20, `page_performance` landing limit 15, `key_event_breakdown` (by `deviceCategory`), `trend(granularity="week")`.

Skeleton:
```
## สรุปผู้บริหาร (3-5 บรรทัด: ผลต่อเป้าหมาย, ตัวเลขหลัก, เรื่องที่ต้องตัดสินใจ)
## KPI เทียบเดือนก่อน (MoM) และปีก่อน (YoY) + ความคืบหน้าเทียบเป้า (% ของเป้า)
## แนวโน้มรายสัปดาห์ (อธิบาย pattern ไม่ต้องวาดกราฟถ้าไม่ได้ขอ)
## ช่องทาง: ใครโต ใครหด ใครคุ้ม (key event rate, revenue per session = totalRevenue / sessions)
## แคมเปญ Top/Bottom 5
## Landing pages: หน้าที่พาลูกค้ามาและหน้าที่ทำให้หลุด (engagement rate ต่ำ + sessions สูง)
## Key events แยกอุปกรณ์
## ความเสี่ยงด้านข้อมูล + ข้อเสนอแนะเดือนหน้า
```

## 3. Campaign post-mortem (สรุปผลแคมเปญ)

Need from user: campaign name (or part of it), start/end dates, goal key event, budget (optional, user-supplied only - never fetch/guess cost; GA4 connector has no ad cost data).
Period = campaign dates; compare = `previous_period` (same length before) unless `previous_year` fits seasonal campaigns.

Calls:
1. `campaign_performance(campaign_contains="<name>")` - also reveals naming variants/typos (list all matched names)
2. `channel_performance(dimension="sessionSourceMedium")` to see where traffic came from during the period (campaign-tagged rows only via campaign tool)
3. `page_performance(mode="landing", path_contains="<landing path>")`
4. `key_event_breakdown(event_names=["<goal event>"], by="sessionDefaultChannelGroup")` and by `deviceCategory`
5. `trend(granularity="day")` for ramp-up / decay

Skeleton:
```
## สรุปแคมเปญ: [ชื่อ] ([start]-[end])  เป้าหมาย: [key event / ตัวเลข] ผลลัพธ์: [ผ่าน/ไม่ผ่าน/ใกล้เคียง]
## ผลลัพธ์หลัก: เซสชัน, ผู้ใช้ใหม่, key events (เป้าหมาย), อัตรา key event, รายได้ | ค่าจริง | ช่วงก่อนหน้า | เปลี่ยน |
## แยกตาม source/medium (อันไหนพา key event มา ไม่ใช่แค่พาคนมา)
## Landing page และ device ที่ทำงานดี/ไม่ดี
## ช่วงเวลา: วันที่พีค, วันที่ลดลง, ผลหลังแคมเปญจบ
## ต้นทุนต่อ key event (เฉพาะถ้าผู้ใช้ให้งบ: งบ / key events) - ระบุว่างบมาจากผู้ใช้
## บทเรียน (ทำต่อ / หยุด / ปรับ) และคำแนะนำแคมเปญถัดไป
## คุณภาพข้อมูล: UTM ชื่อไม่ตรงกัน, (not set), ชื่อแคมเปญซ้ำ
```
Caveat: GA เห็นเฉพาะ traffic ที่มี UTM/auto-tag; ยอดที่มาจากการรับรู้ (view-through, offline) ไม่ถูกวัด.

## 4. Ad-hoc: why did traffic drop (ทำไมทราฟฟิกตก)

Follow the drill-down order in [analysis-playbook.md](analysis-playbook.md). Calls in order, stop when the cause is isolated:
1. `kpi_summary` (confirm the drop is real; compare to previous_period AND previous_year)
2. `trend(granularity="day")` - find the date it started
3. `channel_performance` -> `channel_performance(dimension="sessionSourceMedium")`
4. `page_performance(mode="landing")`
5. `key_event_breakdown(by="deviceCategory")` / `run_report` with `deviceCategory` x channel if needed
6. Tracking checks (see playbook)

Skeleton:
```
## คำตอบสั้น: [ตกเท่าไหร่ เริ่มวันไหน เพราะอะไรเป็นหลัก - ระบุความมั่นใจ สูง/กลาง/ต่ำ]
## ขั้นตอนที่ตรวจ (ช่องทาง -> source/medium -> landing page -> device -> tracking): ตัวเลขของแต่ละขั้น และสิ่งที่ตัดออกได้
## สาเหตุที่เป็นไปได้: [ข้อเท็จจริงจาก GA] / [ข้อเท็จจริงจาก Search Console ถ้าเป็น organic] / [สมมติฐานที่ต้องตรวจนอก GA เช่น งบโฆษณา, การเปลี่ยนเว็บ]
## สิ่งที่ควรทำทันที / ติดตามต่อ
```

## 5. SEO report (Search Console)

Calls (same date range for all; default ends 3daysAgo):
1. `gsc_list_sites(search=...)` - pick the site (prefer `domain` type)
2. `gsc_performance(compare="previous_period")` and, for monthly, `compare="previous_year"`; `granularity="week"` for the pattern
3. `gsc_top_queries(limit=20)` - winners/losers by clicks; `gsc_top_queries(order_by="impressions", limit=20)` - opportunities (high impressions, ctr below site average, position 4-15)
4. `gsc_top_pages(limit=20)` - pages gaining/losing clicks; `gsc_page_queries(page=...)` for the 1-2 biggest movers
5. Optional: GA4 `page_performance(mode="landing", path_contains=...)` for engagement/key events of the same pages

Skeleton:
```
## ภาพรวม SEO: คลิก, อิมเพรสชัน, CTR, อันดับเฉลี่ย | ค่าจริง | ช่วงก่อน | เปลี่ยน |  (site_url, ช่วงวันที่)
## คีย์เวิร์ดเด่น (Top 10 ตามคลิก) | คีย์เวิร์ด | คลิก | เปลี่ยน | อันดับ | เปลี่ยนอันดับ |
## คีย์เวิร์ดที่เสียคลิกมากที่สุด และสาเหตุ (อันดับตก / impressions หาย / CTR ลด)
## โอกาส: คีย์เวิร์ดอิมเพรสชันสูงแต่ CTR ต่ำ หรืออันดับ 4-15 (ปรับ title/meta, เนื้อหา, internal link)
## หน้าเด่น / หน้าที่ตก (Top 5 แต่ละฝั่ง)
## แบรนด์ vs ไม่ใช่แบรนด์ (ถ้า company-config มีคำแบรนด์: query_contains)
## ข้อเสนอแนะ (2-4 ข้อ ระบุหน้า/คีย์เวิร์ด และใครทำ)
```
