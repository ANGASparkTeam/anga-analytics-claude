# Company configuration (ทีมต้องกรอก)

> TODO: ทีม marketing/analytics กรอกไฟล์นี้ แล้วอัปโหลด Skill ใหม่ (ลบ `TODO` ออกเมื่อกรอกเสร็จ).
> Claude: ถ้ายังเห็น `TODO` ในส่วนใด ให้บอกผู้ใช้ว่ายังไม่ได้ตั้งค่า และอย่าเดาค่า (ใช้ `list_properties` / `get_metadata` แทน).
> Do NOT put secrets, service-account keys, or personal data in this file.

## 1. Property aliases (ต้องตรงกับ properties.yaml ของ MCP server)

| alias | GA4 property ID | ชื่อเรียกในทีม | ใช้ทำอะไร | Timezone / สกุลเงิน |
|---|---|---|---|---|
| main | TODO | เว็บไซต์หลัก | TODO | Asia/Bangkok / THB |
| app | TODO | แอป | TODO | TODO |

Default property: TODO (alias)
คำที่ทีมใช้เรียก property (เช่น "เว็บ", "ช็อป" -> alias): TODO

## 2. Key events และความหมายทางธุรกิจ

| event name (ใน GA4) | ความหมายทางธุรกิจ | มูลค่า/ลีด (ถ้ามี) | หมายเหตุ (ยิงที่ไหน, ข้อควรระวัง) |
|---|---|---|---|
| purchase | TODO เช่น ซื้อสินค้าสำเร็จ | TODO | TODO |
| generate_lead | TODO เช่น กรอกฟอร์มติดต่อ | TODO | TODO |
| sign_up | TODO | TODO | TODO |

Primary key event ของบริษัท (ใช้เป็น "conversion" หลักในรายงาน): TODO

## 3. เป้าหมาย / KPI

| ตัวชี้วัด | เป้ารายสัปดาห์ | เป้ารายเดือน | หมายเหตุ |
|---|---|---|---|
| sessions | TODO | TODO | |
| key events (primary) | TODO | TODO | |
| อัตรา key event (sessionKeyEventRate) | TODO % | TODO % | |
| รายได้ (THB) | TODO | TODO | |
| Engagement rate | TODO % | TODO % | |

เกณฑ์ "ดี/แย่" ที่ทีมใช้ (override sanity thresholds ใน playbook): TODO
ช่วงเทศกาล/แคมเปญใหญ่ประจำปี (ใช้เทียบ YoY): TODO (เช่น Songkran, 11.11, 12.12, Black Friday)

## 4. Campaign naming convention

รูปแบบ utm_campaign: TODO (เช่น `{ปี}{เดือน}_{ผลิตภัณฑ์}_{วัตถุประสงค์}_{ช่องทาง}`)
ตัวอย่างที่ถูกต้อง: TODO
utm_source ที่อนุญาต: TODO (เช่น google, facebook, line, tiktok, newsletter)
utm_medium ที่อนุญาต: TODO (เช่น cpc, social, email, display, affiliate, organic)
กฎ: ตัวพิมพ์เล็กทั้งหมด / ไม่มีเว้นวรรค / ภาษาอังกฤษเท่านั้น (TODO ยืนยัน)
เจ้าของ UTM builder / sheet: TODO

## 5. อื่น ๆ

- ผู้รับรายงาน (ตำแหน่ง, ไม่ใส่ข้อมูลส่วนตัว) และรูปแบบที่ชอบ: TODO
- วันที่ตัดรอบ: สัปดาห์เริ่มวันจันทร์ (TODO ยืนยัน) / เดือนตามปฏิทิน (TODO ยืนยัน)
- Internal traffic / IP ที่กรองใน GA4 แล้วหรือยัง: TODO
- แหล่งข้อมูลนอก GA ที่ทีมมี (ยอดขาย backend, งบโฆษณา): TODO
- Search Console site ของแต่ละลูกค้า (ถ้าโดเมนไม่ตรงกับ GA): TODO (เช่น main -> sc-domain:example.co.th)
- คำแบรนด์สำหรับแยก brand vs non-brand ใน gsc_top_queries: TODO
