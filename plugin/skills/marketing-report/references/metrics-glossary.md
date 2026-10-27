# Metrics glossary (พจนานุกรมตัวชี้วัด GA4)

## Contents
- Metrics
- Dimensions
- Common pitfalls
- Data freshness and privacy
- Search Console (GSC) metrics

## Metrics

| API name | ภาษาไทย | ความหมาย |
|---|---|---|
| activeUsers | ผู้ใช้ที่ active | ผู้ใช้ที่มี engaged session หรือเปิดหน้าเว็บ/แอป คือ "Users" ใน GA4 UI |
| newUsers | ผู้ใช้ใหม่ | ผู้ใช้ที่เข้ามาครั้งแรก (first_visit) |
| sessions | เซสชัน | การเข้าใช้งานหนึ่งครั้ง (หมดอายุหลังไม่มีกิจกรรม 30 นาที) |
| engagedSessions | เซสชันที่มี engagement | เซสชันที่อยู่ >10 วินาที หรือมี key event หรือดู >=2 หน้า |
| engagementRate | Engagement rate | engagedSessions / sessions (เป็นสัดส่วน 0-1) |
| bounceRate | Bounce rate | 1 - engagementRate |
| averageSessionDuration | เวลาเฉลี่ยต่อเซสชัน | หน่วยเป็นวินาที - แปลงเป็น นาที:วินาที ตอนแสดง |
| screenPageViews | ยอดดูหน้า | page_view + screen_view รวมทุกครั้ง |
| keyEvents | Key events | จำนวนครั้งของอีเวนต์ที่ตั้งเป็น key event (เดิมเรียก conversions) |
| sessionKeyEventRate | อัตรา key event ต่อเซสชัน | สัดส่วนเซสชันที่มี key event อย่างน้อย 1 ครั้ง (0-1) |
| totalRevenue | รายได้รวม | purchase + subscription + ad revenue ตามสกุลเงินของ property (ปกติ THB) |
| ecommercePurchases | จำนวนคำสั่งซื้อ | จำนวนอีเวนต์ purchase |
| share_of_sessions | สัดส่วนเซสชัน | (จาก tool) แถวนี้ / ผลรวมเซสชัน |

## Dimensions

| API name | ความหมาย |
|---|---|
| sessionDefaultChannelGroup | กลุ่มช่องทาง (Organic Search, Paid Search, Direct, Referral, Organic Social, Paid Social, Email, Display, Affiliates, Unassigned...) ระดับ session |
| sessionSourceMedium | แหล่งที่มา / สื่อ เช่น google / cpc |
| sessionSource | แหล่งที่มาอย่างเดียว |
| sessionCampaignName | ชื่อแคมเปญจาก utm_campaign (หรือ auto-tag ของ Google Ads) |
| landingPage | หน้าแรกที่ผู้ใช้เข้าในเซสชัน |
| pagePath | path ของหน้าที่ถูกดู |
| deviceCategory | desktop / mobile / tablet |
| eventName | ชื่ออีเวนต์ |

## Common pitfalls

1. **Users vs Sessions**: ผู้ใช้ 1 คนมีหลายเซสชันได้ ห้ามเอา sessions ไปเรียกว่า "คน". ผลรวม activeUsers ของแต่ละแถว (เช่น รายช่องทาง) มากกว่ายอดรวมได้ เพราะคนเดียวเข้าหลายช่องทาง - ห้ามบวกแถวเอง.
2. **Engagement rate vs Bounce rate**: GA4 bounce rate = 1 - engagement rate. ไม่เท่ากับ bounce rate ของ Universal Analytics - ห้ามเทียบกับตัวเลขเก่า.
3. **Key events vs Conversions**: GA4 เปลี่ยนชื่อ "conversions" เป็น "key events" (ใน Google Ads ยังเรียก conversions). ใน GA4 API metric `keyEvents` นับทุก key event รวมกัน - ถ้าถามถึง "ลีด" หรือ "ซื้อ" ให้ใช้ `key_event_breakdown` แยกตามชื่ออีเวนต์ ไม่ใช่ `keyEvents` รวม.
4. **Attribution scope**: `session*` dimensions (sessionSource, sessionDefaultChannelGroup, sessionCampaignName) = ที่มาของเซสชันนั้น. `firstUser*` = ที่มาครั้งแรกของผู้ใช้ (ใช้ดู acquisition). ห้ามสลับ scope ในรายงานเดียวกันโดยไม่บอก; ตัวเลขช่องทางอาจไม่ตรงกับหน้า Acquisition ใน GA UI ที่เป็น user-scoped. Tools ของเราใช้ session-scoped.
5. **(not set)**: ค่าที่ GA ไม่รู้ - เกิดจาก UTM หาย, ข้อมูลยังไม่ประมวลผล, หรือ dimension ไม่เข้ากับ metric. ถ้า (not set) สูงผิดปกติ ให้เตือนและดู playbook. `Unassigned` channel = GA จัดกลุ่มไม่ได้ (ปกติ UTM medium ผิดมาตรฐาน).
6. **Direct สูง** มักแปลว่า UTM หาย, แอปแชท (LINE, Messenger) ไม่ส่ง referrer, หรือ redirect ตัด referrer - ไม่ได้แปลว่าคนพิมพ์ URL เอง.
7. **Revenue**: totalRevenue อาจรวมรายได้ที่ไม่ใช่ purchase; ตรวจ `meta.currency`. ไม่เท่ากับยอดขายในระบบหลังบ้าน (ยกเลิก/คืนเงิน/ภาษี) - บอกว่า GA คือ "ยอดที่วัดได้ในเว็บ".
8. **Cross-device / consent**: ผู้ใช้ที่ปฏิเสธ cookie อาจไม่ถูกนับ (Consent Mode จะ model บางส่วน) ตัวเลข GA ต่ำกว่าความจริงเสมอ.

## Data freshness and privacy

- ข้อมูล standard report ล่าช้า ~24-48 ชม.; ข้อมูล 1-2 วันล่าสุดอาจเพิ่มขึ้นภายหลัง. `realtime_overview` เป็นข้อมูล 30 นาทีล่าสุด ใช้เทียบกับ report ปกติไม่ได้.
- **Thresholding**: ถ้าเปิด Google Signals หรือมีข้อมูล demographics GA ซ่อนแถวที่ผู้ใช้น้อย -> `meta.thresholded=true`. ผลรวมแถวอาจน้อยกว่ายอดรวมจริง.
- **Sampling**: พบในการ explore/ช่วงยาวมาก; ลดช่วงเวลาหรือลดจำนวน dimension.
- ผู้ใช้ unique ต่างช่วงเวลาไม่สามารถบวกกันได้ (คนเดียวกันซ้ำ) - ให้ดึงช่วงรวมใหม่.

## Search Console (GSC) metrics

| Metric | ความหมาย |
|---|---|
| clicks | จำนวนคลิกจากผลการค้นหา Google มาที่เว็บ (ไม่ใช่ sessions ของ GA; ตัวเลขไม่เท่ากัน) |
| impressions | จำนวนครั้งที่ลิงก์ของเว็บแสดงในผลการค้นหา (แม้ผู้ใช้ไม่ได้เลื่อนไปเห็น) |
| ctr | clicks / impressions (0-1; แสดงเป็น %) |
| position | อันดับเฉลี่ยของผลการค้นหาที่สูงสุดของเว็บ; **ยิ่งน้อยยิ่งดี** (1 = อันดับแรก) |

- ข้อมูลช้า ~2-3 วัน และใช้เวลาแปซิฟิก (PT) ไม่ใช่เวลาไทย - ค่าเริ่มต้นของ tools จบที่ 3daysAgo.
- คิวรีที่มีคนค้นน้อยถูกซ่อน (anonymized): ผลรวมแถว `gsc_top_queries` < ยอดรวม `gsc_performance` เสมอ.
- position เฉลี่ยแย่ลงไม่ได้แปลว่าแย่เสมอ: ถ้าเว็บเริ่มติดคีย์เวิร์ดใหม่ที่อันดับต่ำ impressions จะเพิ่มและ position เฉลี่ยจะสูงขึ้น - ดูคู่กับ impressions และ clicks.
- Domain property (`sc-domain:`) รวมทุก subdomain และ http/https; URL-prefix property นับเฉพาะ prefix นั้น - ตัวเลขสองแบบไม่เท่ากัน ระบุ site_url ในรายงานเสมอ.
