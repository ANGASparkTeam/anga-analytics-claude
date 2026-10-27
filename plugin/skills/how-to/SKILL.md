---
name: how-to
description: Shortcut - explains in Thai how to use the ANGA Marketing Analytics plugin - every slash command, examples, defaults, output formats and tips.
argument-hint: [command name or question, e.g. "seo" or "ทำ html ยังไง"]
disable-model-invocation: true
---

# How to use ANGA Marketing Analytics (วิธีใช้งาน)

Question: $ARGUMENTS

Answer in Thai from the guide below. If the question is empty, show the whole command table plus the "เริ่มต้นใช้งาน" and "เคล็ดลับ" parts, short. If it names a command or asks something specific, answer only that, with 1-2 examples. Do not call any data tool; this command only explains. Do not invent commands that are not in the table.

## เริ่มต้นใช้งาน

1. ติดตั้ง plugin "ANGA Marketing Analytics"
   - claude.ai / แชทใน Claude Desktop: org plugin library → Install
   - แท็บ Code ใน Claude Desktop / Claude Code: วางทีละบรรทัด
     ```text
     /plugin marketplace add ANGASparkTeam/anga-analytics-claude
     /plugin install anga-analytics@anga
     /reload-plugins
     ```
2. รัน `/anga-analytics:login` เพื่อเชื่อมต่อ ล็อกอินด้วยอีเมล @anga.co.th ของตัวเอง (ห้ามใช้ บัญชีกลาง - ระบบจะปฏิเสธ)
3. ถามเป็นภาษาธรรมดาได้เลย เช่น "ยอดเข้าเว็บ acme เดือนที่แล้วเป็นยังไง" หรือใช้คำสั่งลัดด้านล่าง

## คำสั่งลัด (พิมพ์ `/` แล้วตามด้วยคำสั่ง ใส่ชื่อลูกค้าต่อท้าย)

| คำสั่ง | ได้อะไร | ตัวอย่าง |
|---|---|---|
| `/anga-analytics:report` | รายงานตามที่สั่ง (GA4, SEO หรือทั้งคู่) ออกเป็นหน้า HTML แบบ ANGA ONE (มีโลโก้ ANGA) ถ้าไม่ระบุรูปแบบ | `/anga-analytics:report acme เดือน ต.ค. GA4+SEO` |
| `/anga-analytics:weekly` | รายงาน GA4 ประจำสัปดาห์ (สัปดาห์เต็มล่าสุด จ.-อา. เทียบสัปดาห์ก่อน) | `/anga-analytics:weekly acme` |
| `/anga-analytics:monthly` | รายงาน GA4 ประจำเดือน เทียบเดือนก่อน + ปีก่อน พร้อมสรุปผู้บริหาร | `/anga-analytics:monthly acme ก.ย. 2026` |
| `/anga-analytics:campaign` | สรุปผลแคมเปญจาก UTM campaign | `/anga-analytics:campaign acme songkran` |
| `/anga-analytics:why-drop` | หาสาเหตุทราฟฟิก/key events ตก (ไล่ ช่องทาง -> หน้า -> อุปกรณ์ -> Search Console) | `/anga-analytics:why-drop acme สัปดาห์ที่แล้ว` |
| `/anga-analytics:seo` | รายงาน SEO จาก Search Console: คลิก, impressions, CTR, อันดับ, คีย์เวิร์ด, หน้า | `/anga-analytics:seo acme` |
| `/anga-analytics:seo-drop` | หาสาเหตุ organic search ตก | `/anga-analytics:seo-drop acme` |
| `/anga-analytics:keywords` | โอกาสคีย์เวิร์ด: อันดับ 4-15, CTR ต่ำ, คีย์เวิร์ดขึ้น/ลง (ใส่หัวข้อกรองได้) | `/anga-analytics:keywords acme สินเชื่อ` |
| `/anga-analytics:login` | เชื่อมต่อ / เช็คว่าล็อกอินด้วยอีเมลไหน ถ้ายังไม่ได้ล็อกอินจะบอกขั้นตอน | `/anga-analytics:login` |
| `/anga-analytics:how-to` | คำอธิบายนี้ | `/anga-analytics:how-to seo` |
| `/anga-analytics:marketing-report` | เรียก skill หลักตรงๆ ด้วยคำถามอะไรก็ได้ | `/anga-analytics:marketing-report เทียบ Organic กับ Paid ของ acme` |

(บน claude.ai ถ้าเมนู `/` ไม่แสดงคำสั่งเหล่านี้ ให้พิมพ์เป็นประโยคแทน เช่น "ทำรายงาน SEO ของ acme" ได้ผลเหมือนกัน)

## ค่าเริ่มต้น

- ชื่อลูกค้า: ใส่ชื่อแบรนด์หรือโดเมนก็ได้ (acme, acme.co.th) ถ้าเจอหลาย property/เว็บ Claude จะถามว่าเอาอันไหน
- ช่วงเวลา: weekly = สัปดาห์เต็มล่าสุด, monthly = เดือนเต็มล่าสุด, SEO = 28 วันจบที่ 3 วันก่อน (ข้อมูล Search Console ช้า 2-3 วัน), อื่นๆ = 28 วันล่าสุด ระบุเองได้ เช่น "1-15 ต.ค.", "เดือนที่แล้ว", "Q3"
- เทียบกับช่วงก่อนหน้าเสมอ พิมพ์ "เทียบปีก่อน" ถ้าต้องการ YoY
- ข้อมูลอ่านอย่างเดียว ผ่านบัญชีกลาง จึงเห็นทุกลูกค้าที่บัญชีนั้นเห็น (GA4 ~1,000 properties, Search Console ~400 เว็บ)

## รูปแบบผลลัพธ์

- คำสั่ง `report`: ออกเป็นหน้า HTML ดีไซน์เดียวกับ ANGA ONE (โลโก้ ANGA, ส้ม #FF5300, การ์ดขาว, font Poppins + IBM Plex Sans Thai) ถ้าไม่ระบุ
- คำสั่งอื่น: ตอบในแชท แล้วถามว่าจะส่งออกเป็น HTML / Excel / สไลด์ไหม
- ระบุเองได้ท้ายคำสั่ง: "เป็น html", "เป็น excel", "เป็นสไลด์", "ตอบในแชท"

## เคล็ดลับ

- ถามต่อได้ในแชทเดิม เช่น "เจาะดูเฉพาะ mobile", "หน้า /loan ติดคีย์เวิร์ดอะไร", "เทียบปีที่แล้ว"
- ตัวเลขทุกตัวมาจาก GA4/Search Console จริง ถ้าข้อมูลมีข้อจำกัด (sampling, ข้อมูลยังไม่ครบ, แถวถูกตัด) Claude จะบอกไว้ท้ายรายงาน
- Clicks ของ Search Console กับ sessions ของ GA4 นับคนละแบบ ตัวเลขไม่เท่ากันเป็นเรื่องปกติ
- อันดับ (position) ยิ่งน้อยยิ่งดี
- ถ้าขึ้น error เรื่องสิทธิ์ (Permission denied) แปลว่าบัญชีกลางไม่มีสิทธิ์ใน property/เว็บนั้น ให้แจ้งทีม Spark
