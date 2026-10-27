# ANGA Marketing Analytics (GA4 + Search Console)

MCP server แบบ remote (Streamable HTTP) สำหรับดึงรายงาน Google Analytics 4 และ Google Search Console แบบอ่านอย่างเดียว ให้ทีมการตลาดใช้ผ่าน **claude.ai / Claude Desktop** ในรูปแบบ *custom connector* ระดับองค์กร

- ผู้ใช้ล็อกอินด้วย Google และต้องเป็นบัญชี Google Workspace ของบริษัทเท่านั้น (ตั้งค่าใน `ALLOWED_DOMAINS`)
- ข้อมูล GA4 อ่านในนาม**บัญชีกลาง (shared mailbox)** (ผ่าน refresh token ที่มีแค่ scope `analytics.readonly` + `webmasters.readonly`) ไม่ได้ใช้สิทธิ์ GA ของผู้ใช้แต่ละคน ผู้ใช้จึงให้สิทธิ์แค่ `openid` + `email`
- Deploy บน Google Cloud Run

> **ผู้ใช้ (ทีม marketing): ดู [เริ่มใช้งาน](#เริ่มใช้งาน-สำหรับทีม-marketing)** · สเปกของ tools ทั้งหมดอยู่ที่ [`docs/CONTRACT.md`](docs/CONTRACT.md) และมี plugin สำหรับ Claude (Skill + connector) อยู่ใน [`plugin/`](plugin/) (ดูข้อ 7)

---

## เริ่มใช้งาน (สำหรับทีม marketing)

plugin **ANGA Marketing Analytics** (`anga-analytics`) ทำให้ Claude ดึงตัวเลขจาก Google Analytics 4 และ Google Search Console ของลูกค้าทุกรายที่บัญชีกลาง เห็น แล้วสรุปเป็นรายงานภาษาไทยได้ ข้อมูลอ่านอย่างเดียว แก้ค่าใน GA/GSC ไม่ได้

### 1) ติดตั้ง

| ใช้ Claude ผ่าน | สถานะ | ไปที่ |
|---|---|---|
| **Claude Code** (terminal) หรือ **แท็บ Code ใน Claude Desktop** | ใช้ได้เลย ไม่ต้องรอ admin | [ก) Claude Code](#ก-ติดตั้งใน-claude-code-แนะนำ) |
| **แชทใน claude.ai** หรือ **แท็บ Chat ใน Claude Desktop** | ต้องให้ admin ของ org อนุญาต connector ก่อน | [ข) claude.ai](#ข-ติดตั้งใน-claudeai--แชทใน-claude-desktop) |

#### ก) ติดตั้งใน Claude Code (แนะนำ)

**สิ่งที่ต้องมี**
- Claude Code ([วิธีติดตั้ง](https://docs.claude.com/en/docs/claude-code/setup)) หรือ Claude Desktop ที่มีแท็บ Code
- บัญชี GitHub ที่**อ่าน repo `ANGASparkTeam/anga-analytics-claude` ได้** (repo เป็น private) และ git บนเครื่องล็อกอิน GitHub แล้ว ถ้าไม่มีให้ใช้ [ทางเลือก: ติดตั้งจาก org library](#ทางเลือก-ติดตั้งจาก-org-library-ไม่ต้องใช้-github)
- อีเมล @anga.co.th ของตัวเอง

**ขั้นที่ 1 — ติดตั้ง plugin** (ทำครั้งเดียว) เปิด Terminal แล้ววาง:
```bash
claude plugin marketplace add ANGASparkTeam/anga-analytics-claude && claude plugin install anga-analytics@anga
```
ต้องเห็น `✔ Successfully added marketplace: anga` และ `✔ Successfully installed plugin: anga-analytics@anga`

หรือพิมพ์ในช่องแชทของ Claude Code / แท็บ Code ทีละบรรทัด:
```text
/plugin marketplace add ANGASparkTeam/anga-analytics-claude
/plugin install anga-analytics@anga
```

**ขั้นที่ 2 — เปิด Claude Code** แล้วโหลด plugin (ถ้าเปิดค้างไว้ก่อนติดตั้ง):
```text
/reload-plugins
```

**ขั้นที่ 3 — ล็อกอิน**
```text
/anga-analytics:login
```
ถ้ายังไม่ได้ล็อกอิน Claude จะบอกขั้นตอน:
1. พิมพ์ `/mcp`
2. เลือก **plugin:anga-analytics:analytics** → **Authenticate**
3. browser จะเปิดหน้า ANGA Marketing Analytics → กด Continue → เลือกบัญชี Google **@anga.co.th ของตัวเอง** → Allow (ห้ามใช้ บัญชีกลาง ระบบจะปฏิเสธ)
4. กลับมาที่ Claude แล้วรัน `/anga-analytics:login` อีกครั้ง ต้องขึ้นว่า "ล็อกอินในชื่อ ชื่อคุณ@anga.co.th"

**ขั้นที่ 4 — ลองใช้**
```text
/anga-analytics:how-to
/anga-analytics:seo acme
```

**อัปเดตเมื่อมีเวอร์ชันใหม่** (Claude Code ไม่อัปเดตเอง):
```bash
claude plugin marketplace update anga && claude plugin update anga-analytics@anga
```
แล้วปิด/เปิด Claude Code ใหม่ หรือ `/reload-plugins` · ดูเวอร์ชันที่ติดตั้ง: `claude plugin list`

**ถอนการติดตั้ง:**
```bash
claude plugin uninstall anga-analytics@anga && claude plugin marketplace remove anga
```

**ปัญหาที่พบบ่อยตอนติดตั้ง**

| อาการ | วิธีแก้ |
|---|---|
| `marketplace add` ขึ้น not found / authentication failed / ขอ username-password | บัญชี GitHub ยังไม่มีสิทธิ์อ่าน repo หรือ git ยังไม่ได้ล็อกอิน (`gh auth login`) ขอสิทธิ์จากทีม Spark หรือใช้ทางเลือก org library |
| พิมพ์ `/anga-analytics:` แล้วไม่มีคำสั่งขึ้น | `/reload-plugins` หรือปิด/เปิด Claude Code ใหม่ เช็คด้วย `claude plugin list` ว่า anga-analytics เป็น enabled |
| ใน `/mcp` ไม่เห็น analytics | `/reload-plugins` แล้วเปิด session ใหม่ |
| Authenticate แล้วขึ้น Access denied | ล็อกอินด้วยอีเมล @anga.co.th ของตัวเอง ไม่ใช่ Gmail หรือ บัญชีกลาง  |
| ใช้ได้แล้วแต่วันหลังขึ้นว่าต้อง authenticate ใหม่ | ทำขั้นที่ 3 ซ้ำ (session หมดอายุ) |

##### ทางเลือก: ติดตั้งจาก org library (ไม่ต้องใช้ GitHub)

plugin ถูก publish ไว้ใน org library ของ claude.ai แล้ว ใน Claude Code พิมพ์ `/plugin` → **Marketplaces** → เพิ่ม organization library จากนั้น:
```text
/plugin install anga-analytics@claudeai-organization-library
```
แล้วทำต่อจากขั้นที่ 2 (อัปเดตด้วย `/plugin` → Marketplaces → update)

#### ข) ติดตั้งใน claude.ai / แชทใน Claude Desktop

> ตอนนี้กด Connect แล้วยังไม่ผ่าน ต้องรอ admin ของ org อนุญาต connector ภายนอกก่อน ระหว่างนี้ใช้ทาง Claude Code

1. เปิดลิงก์ plugin ใน org library: https://claude.ai/customize/plugins/plugin_01PNPi6mUHGgtn22q4XL79g9 (หรือ claude.ai → Customize → Plugins แล้วค้นหา "ANGA Marketing Analytics")
2. กด **Install** — Claude Desktop ที่ล็อกอินบัญชีเดียวกันจะได้ plugin นี้ด้วย
3. ไปที่ **Settings → Connectors** หา connector **analytics** กด **Connect**
4. ล็อกอิน Google ด้วยอีเมล **@anga.co.th ของตัวเอง** แล้วกด Allow
5. ในแชท เปิด connector analytics ในเมนู tools แล้วพิมพ์ "ทำรายงาน SEO ของ acme" ได้เลย (claude.ai อัปเดต plugin จาก library ให้เอง)

### 2) ใช้งาน

ถามเป็นภาษาธรรมดาได้เลย เช่น "ยอดเข้าเว็บ acme เดือนที่แล้วเป็นยังไง", "คีย์เวิร์ดไหนของ acme ตกบ้าง" หรือใช้**คำสั่งลัด**: พิมพ์ `/` แล้วเลือกคำสั่ง ตามด้วยชื่อลูกค้า (ชื่อแบรนด์หรือโดเมนก็ได้) และรายละเอียดเพิ่มเติม

| คำสั่ง | ได้อะไร | ตัวอย่าง |
|---|---|---|
| `/anga-analytics:login` | เชื่อมต่อ / เช็คว่าล็อกอินด้วยอีเมลไหน ถ้ายังไม่ได้ล็อกอินจะบอกขั้นตอน | `/anga-analytics:login` |
| `/anga-analytics:how-to` | วิธีใช้งานทั้งหมด หรือถามเจาะเรื่องเดียว | `/anga-analytics:how-to seo` |
| `/anga-analytics:report` | รายงานตามสั่ง (GA4, SEO หรือทั้งคู่) ออกเป็นหน้า HTML ดีไซน์ ANGA ONE พร้อมโลโก้ ANGA ถ้าไม่ระบุรูปแบบ | `/anga-analytics:report acme เดือน ต.ค. GA4+SEO` |
| `/anga-analytics:weekly` | รายงาน GA4 ประจำสัปดาห์ (สัปดาห์เต็มล่าสุด เทียบสัปดาห์ก่อน) | `/anga-analytics:weekly acme` |
| `/anga-analytics:monthly` | รายงาน GA4 ประจำเดือน เทียบเดือนก่อน + ปีก่อน พร้อมสรุปผู้บริหาร | `/anga-analytics:monthly acme ก.ย. 2026` |
| `/anga-analytics:campaign` | สรุปผลแคมเปญจากชื่อ UTM campaign | `/anga-analytics:campaign acme songkran` |
| `/anga-analytics:why-drop` | หาสาเหตุทราฟฟิก / key events ตก (ไล่ช่องทาง → หน้า → อุปกรณ์ → Search Console) | `/anga-analytics:why-drop acme สัปดาห์ที่แล้ว` |
| `/anga-analytics:seo` | รายงาน SEO: คลิก, impressions, CTR, อันดับ, คีย์เวิร์ด, หน้า, โอกาส | `/anga-analytics:seo acme` |
| `/anga-analytics:seo-drop` | หาสาเหตุ organic search ตก | `/anga-analytics:seo-drop acme` |
| `/anga-analytics:keywords` | โอกาสคีย์เวิร์ด: อันดับ 4–15, CTR ต่ำ, คำที่ขึ้น/ลง (ใส่หัวข้อกรองได้) | `/anga-analytics:keywords acme สินเชื่อ` |
| `/anga-analytics:marketing-report` | เรียก skill หลักด้วยคำถามอะไรก็ได้ | `/anga-analytics:marketing-report เทียบ Organic กับ Paid ของ acme` |

บน claude.ai ถ้าเมนู `/` ไม่แสดงคำสั่งเหล่านี้ ให้พิมพ์เป็นประโยคแทน เช่น "ทำรายงาน SEO ของ acme เป็น html" ได้ผลเหมือนกัน

**ช่วงเวลา (ถ้าไม่ระบุ):** weekly = สัปดาห์เต็มล่าสุด (จ.–อา.), monthly = เดือนเต็มล่าสุด, SEO = 28 วันจบที่ 3 วันก่อน (Search Console ช้า 2–3 วัน), อื่นๆ = 28 วันล่าสุด ระบุเองได้ เช่น "1–15 ต.ค.", "เดือนที่แล้ว", "Q3", "เทียบปีก่อน"

**รูปแบบผลลัพธ์:** `report` = หน้า HTML (Claude Code บันทึกไว้ที่ `reports/` ซึ่งไม่ถูก commit, claude.ai แสดงเป็น artifact) · คำสั่งอื่นตอบในแชทแล้วถามว่าจะส่งออกไหม · ระบุเองได้ท้ายคำสั่ง: "เป็น html", "เป็น excel", "เป็นสไลด์", "ตอบในแชท"

**เคล็ดลับ**
- ถามต่อในแชทเดิมได้ เช่น "เจาะเฉพาะ mobile", "หน้า /loan ติดคีย์เวิร์ดอะไร", "เทียบปีที่แล้ว"
- ถ้าชื่อลูกค้าตรงกับหลาย property/เว็บ Claude จะถามว่าเอาอันไหน
- ตัวเลขทุกตัวมาจาก GA4/Search Console จริง ข้อจำกัดของข้อมูล (sampling, ข้อมูลล่าสุดยังไม่ครบ, แสดงเฉพาะแถวแรก) จะอยู่ท้ายรายงาน
- clicks ของ Search Console กับ sessions ของ GA4 นับคนละแบบ ไม่เท่ากันเป็นเรื่องปกติ; อันดับ (position) ยิ่งน้อยยิ่งดี

**ใช้ไม่ได้?**

| อาการ | ทำอย่างไร |
|---|---|
| กด Connect แล้วขึ้น "Access denied" | ต้องใช้อีเมล @anga.co.th ของตัวเอง ไม่ใช่ Gmail หรือ บัญชีกลาง  |
| Claude บอกว่าไม่มี tool / connector | รัน `/anga-analytics:login` แล้วทำตามขั้นตอน (claude.ai: เปิด connector analytics ในเมนู tools ของแชท) |
| `Permission denied` / `not verified` | บัญชีกลางไม่มีสิทธิ์ใน property/เว็บนั้น แจ้งทีม Spark (spark@anga.co.th) |
| ไม่เห็นคำสั่ง `/anga-analytics:...` | อัปเดต plugin แล้ว `/reload-plugins` (Claude Code) หรือพิมพ์เป็นประโยคแทน |

---

## สารบัญ

0. [เริ่มใช้งาน (สำหรับทีม marketing)](#เริ่มใช้งาน-สำหรับทีม-marketing)
1. [สถาปัตยกรรม](#1-สถาปัตยกรรม)
2. [พัฒนาบนเครื่อง (local dev)](#2-พัฒนาบนเครื่อง-local-dev)
3. [เตรียม GCP](#3-เตรียม-gcp)
4. [ให้ server อ่าน GA4 ในนามบัญชีกลาง](#4-ให้-server-อ่าน-ga4-ในนามบัญชีกลาง)
5. [สร้าง Google OAuth client](#5-สร้าง-google-oauth-client)
6. [Deploy](#6-deploy)
7. [เพิ่ม connector ใน claude.ai](#7-เพิ่ม-connector-ใน-claudeai)
8. [ความปลอดภัย: การจำกัดโดเมน](#8-ความปลอดภัย-การจำกัดโดเมน)
9. [การเก็บ OAuth state (persistence)](#9-การเก็บ-oauth-state-persistence)
10. [Environment variables](#10-environment-variables)
11. [Troubleshooting](#11-troubleshooting)
12. [ค่าใช้จ่าย](#12-ค่าใช้จ่าย)

---

## 1. สถาปัตยกรรม

```
 claude.ai / Claude Desktop
        │  (1) Dynamic Client Registration + OAuth 2.1 (PKCE)
        │  (4) MCP over Streamable HTTP  +  Bearer <FastMCP JWT>
        ▼
 ┌──────────────── Cloud Run: ga4-mcp ────────────────┐
 │ FastMCP 4 + GoogleProvider (OAuth proxy)            │
 │   /mcp                 MCP endpoint (ต้องมี token)  │
 │   /authorize /token /register /.well-known/...      │
 │   /auth/callback       ◄── (2) Google sign-in       │
 │   /health              health check (public)        │
 │                                                     │
 │ ตรวจโดเมน: callback → token exchange → ทุก request │
 └──────┬───────────────────────────┬──────────────────┘
        │ (3) OAuth state (เข้ารหัส  │ (5) GA4 Data/Admin API
        │     Fernet) ใน Firestore  │     ด้วย runtime service account (ADC)
        ▼                           ▼
   Firestore (Native)          Google Analytics 4
```

- **OAuth proxy**: FastMCP ทำตัวเป็น Authorization Server ให้ Claude (รองรับ DCR) แล้วส่งต่อไปล็อกอินที่ Google จากนั้นออก JWT ของตัวเองให้ Claude โดย token ของ Google ถูกเก็บแบบเข้ารหัสไว้ฝั่ง server
- **GA4**: server ใช้ refresh token ของ บัญชีกลาง (shared mailbox, ดูข้อ 4) จึงเห็นทุก property ที่บัญชีกลางเห็น
- **Audit log**: ทุกครั้งที่เรียก tool จะ log `user` (อีเมล), `tool`, `args`, `status`, `elapsed_ms` เป็น JSON ไปที่ Cloud Logging (ไม่ log token)

ไฟล์หลัก

| ไฟล์ | หน้าที่ |
|---|---|
| `src/ga4_mcp/server.py` | สร้าง `FastMCP("marketing-analytics")`, audit middleware, `/health`, `main()` |
| `src/ga4_mcp/auth.py` | `build_auth()`, ตรวจโดเมน, เลือก storage |
| `src/ga4_mcp/tools.py` ฯลฯ | tools ของ GA4 |
| `Dockerfile` | image แบบ multi-stage ด้วย uv, รันเป็น non-root, port 8080 |
| `deploy/setup-gcp.sh` | ตั้งค่า GCP ครั้งแรก (idempotent) |
| `deploy/deploy.sh` | build + deploy Cloud Run (idempotent) |

---

## 2. พัฒนาบนเครื่อง (local dev)

ต้องมี Python 3.12, [uv](https://docs.astral.sh/uv/), gcloud CLI

```bash
uv sync
cp properties.example.yaml properties.yaml     # แก้ property id ให้ถูก
cp .env.example .env                           # ค่าเริ่มต้นคือ AUTH_DISABLED=true
```

### สิทธิ์ GA4 บนเครื่อง (ADC)

เลือกอย่างใดอย่างหนึ่ง

```bash
# ก) ใช้บัญชีตัวเอง (บัญชีนี้ต้องมีสิทธิ์ดู GA4 property)
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform

# ข) impersonate service account ตัวจริง (ต้องมี roles/iam.serviceAccountTokenCreator บน SA)
gcloud auth application-default login \
  --impersonate-service-account=ga4-mcp-runtime@PROJECT_ID.iam.gserviceaccount.com \
  --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform
```

### รัน server แบบไม่ต้องล็อกอิน

```bash
set -a; source .env; set +a
AUTH_DISABLED=true uv run ga4-mcp          # http://localhost:8080/mcp
curl localhost:8080/health                # {"status":"ok"}
```

> `AUTH_DISABLED=true` จะถูกปฏิเสธอัตโนมัติถ้ารันบน Cloud Run (มี env `K_SERVICE`)

### ทดสอบด้วย MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

ในหน้า Inspector เลือก Transport = **Streamable HTTP**, URL = `http://localhost:8080/mcp` แล้วกด Connect → Tools → List Tools

### ทดสอบ login จริงบนเครื่อง (ไม่บังคับ)

ตั้ง `AUTH_DISABLED=false`, `BASE_URL=http://localhost:8080`, ใส่ `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `ALLOWED_DOMAINS`, `JWT_SIGNING_KEY` และเพิ่ม redirect URI `http://localhost:8080/auth/callback` ใน OAuth client (ดูข้อ 5) แล้วต่อด้วย Inspector (Inspector จะทำ OAuth ให้เอง)

### Tests

```bash
uv run pytest -q
```

---

## 3. เตรียม GCP

ต้องเป็น Owner (หรือมีสิทธิ์เทียบเท่า) ของ project

```bash
gcloud auth login
cp properties.example.yaml properties.yaml   # แก้ให้ถูกก่อน

PROJECT_ID=my-gcp-project \
PROPERTIES_FILE=properties.yaml \
./deploy/setup-gcp.sh
```

สคริปต์ทำสิ่งต่อไปนี้ (รันซ้ำได้ ไม่สร้างซ้ำ ไม่หมุน key เดิม)

- เปิด API: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore, Analytics Data, Analytics Admin
- สร้าง service account `ga4-mcp-runtime`
- สร้าง Firestore database `(default)` แบบ Native ใน `asia-southeast1` และให้ SA มี `roles/datastore.user`
- สร้าง secrets ใน Secret Manager แล้วให้ SA มี `roles/secretmanager.secretAccessor` เฉพาะ secret เหล่านี้
  - `ga4-mcp-jwt-signing-key` (สุ่มให้)
  - `ga4-mcp-storage-encryption-key` (Fernet key สุ่มให้)
  - `ga4-mcp-google-oauth-client-secret` (ถามตอนรัน หรือส่งผ่าน env `GOOGLE_OAUTH_CLIENT_SECRET`)
  - `ga4-mcp-properties` (เนื้อหา `properties.yaml`; เพิ่ม version ใหม่เมื่อไฟล์เปลี่ยน)

ตัวแปรที่ปรับได้: `REGION` (ค่าเริ่มต้น `asia-southeast1`), `SERVICE` (`ga4-mcp`), `SA_NAME`, `FIRESTORE_LOCATION`, `FIRESTORE_DATABASE`

> ถ้ายังไม่มี OAuth client secret ให้ทำข้อ 5 ก่อน หรือรันสคริปต์ซ้ำทีหลังด้วย `GOOGLE_OAUTH_CLIENT_SECRET=... ./deploy/setup-gcp.sh`

**แก้ properties ภายหลัง**: แก้ `properties.yaml` → รัน `setup-gcp.sh` อีกครั้ง → รัน `deploy.sh` (หรือ `gcloud run services update ga4-mcp --region asia-southeast1` เพื่อให้ revision ใหม่อ่าน `latest`)

---

## 4. ให้ server อ่าน GA4 ในนามบัญชีกลาง

server อ่าน GA4 ด้วยสิทธิ์ของบัญชีกลาง (shared mailbox) จึงเห็นทุก account และทุก property ที่บัญชีนี้เห็นอยู่แล้ว **ไม่ต้องไปเพิ่ม user ใน GA4 ทีละ account** เลือกได้ด้วย env `GA_AUTH_MODE`

### แบบ A: Refresh token ของบัญชีกลาง (`GA_AUTH_MODE=user_token`, ค่าเริ่มต้น, ใช้อยู่)

ไม่ต้องใช้ Workspace super admin สิ่งที่ server เก็บไว้คือ refresh token ของ บัญชีกลาง (shared mailbox) ที่มีแค่ scope `analytics.readonly` กับ `webmasters.readonly` (Search Console, สำหรับ tools `gsc_*`) และ `openid email` ไว้ยืนยันว่าเป็นบัญชีไหน ตอน consent ต้องติ๊กทั้ง Analytics และ Search Console

1. ที่ Google Auth Platform ของ project สร้าง client ชนิด **Desktop app** แล้วดาวน์โหลด JSON (consent screen ต้องเป็น **Internal** ไม่อย่างนั้น token หมดอายุใน 7 วัน)
2. สร้าง token: browser จะเปิดขึ้นมา ให้ **login เป็นบัญชีกลาง**
   ```bash
   uv run --with google-auth-oauthlib python deploy/mint_ga_token.py ~/Downloads/client_secret_XXX.json .ga-token.json
   ```
   > ไม่ใช้ `gcloud auth application-default login` เพราะ gcloud บังคับให้มี scope `cloud-platform` ติดมาด้วย ทำให้ token มีสิทธิ์ใน GCP เกินจำเป็น
3. ส่งเข้า Secret Manager แล้ว**ลบไฟล์ทิ้ง**
   ```bash
   GA_USER_TOKEN_FILE=.ga-token.json PROJECT_ID=your-project ./deploy/setup-gcp.sh && rm .ga-token.json
   ```
4. deploy โดยใส่ `DENIED_EMAILS=<shared-mailbox>` ด้วยเสมอ (สคริปต์บังคับ) เพื่อไม่ให้บัญชีกลาง login เข้า connector ได้

**token จะหยุดใช้ได้เมื่อ**มีคนกด revoke ที่ myaccount.google.com → Security → Third-party connections, เมื่อแอดมินลบหรือระงับ บัญชีกลาง  หรือเมื่อนโยบายของ Workspace บังคับ re-auth อาการคือ tool ตอบ `could not authenticate` วิธีแก้คือทำข้อ 2–3 ซ้ำ ไม่ต้อง deploy ใหม่ เพราะ Cloud Run อ่าน secret `latest` ตอน instance เริ่มทำงาน (หรือสั่ง `gcloud run services update ga4-mcp --region asia-southeast1` เพื่อบังคับ)

### แบบ B: Domain-wide delegation (`GA_AUTH_MODE=delegated`)

เสถียรกว่าเพราะไม่มี token หมดอายุ แต่ต้องให้ **Workspace super admin** เพิ่ม Client ID ของ SA (`gcloud iam service-accounts describe SA_EMAIL --format='value(oauth2ClientId)'`) ใน admin.google.com → Security → API controls → Domain-wide delegation โดยใส่ scope `https://www.googleapis.com/auth/analytics.readonly` จากนั้น deploy ด้วย `GA_AUTH_MODE=delegated GA_DELEGATED_SUBJECT=<shared-mailbox>` ซึ่ง `setup-gcp.sh` จะให้สิทธิ์ signJwt ที่ต้องใช้ให้เอง

### (ทางเลือกเดิม) `GA_AUTH_MODE=adc`

เพิ่ม `ga4-mcp-runtime@PROJECT_ID.iam.gserviceaccount.com` เป็น **Viewer** ที่ GA4 → Admin → **Account access management** ของทุก account

**ตรวจสอบ:** หลัง deploy ให้เรียก tool `list_properties` แล้วดูว่าเห็น account และ property ครบเท่ากับที่ บัญชีกลาง (shared mailbox) เห็นใน GA4 UI หรือไม่

---

## 5. สร้าง Google OAuth client

ทำใน project เดียวกัน

1. **Google Auth Platform → Branding / OAuth consent screen**
   - User type: **Internal** (เฉพาะคนใน Workspace ของบริษัท – เป็นด่านแรกที่กันคนนอก)
   - App name เช่น "GA4 Marketing for Claude", support email
   - Scopes: `openid`, `.../auth/userinfo.email` (ไม่ใช่ sensitive scope ไม่ต้อง verify)
2. **Clients → Create client** → Application type: **Web application**
3. **Authorized redirect URIs**
   - `https://ga4-mcp-PROJECT_NUMBER.asia-southeast1.run.app/auth/callback` (ค่านี้ `setup-gcp.sh` / `deploy.sh` พิมพ์ให้)
   - (ถ้าทดสอบบนเครื่อง) `http://localhost:8080/auth/callback`
4. เก็บ **Client ID** (ใช้ตอน deploy) และ **Client secret** (ใส่ Secret Manager ผ่าน `setup-gcp.sh`)

> หมายเหตุ: redirect URI ตรงนี้คือ callback ของ *server เรา* ส่วน callback ของ Claude (`https://claude.ai/api/mcp/auth_callback`) ไม่ต้องใส่ใน Google เพราะ FastMCP เป็นคนจัดการ

หาเลข project number:

```bash
gcloud projects describe PROJECT_ID --format='value(projectNumber)'
```

---

## 6. Deploy

```bash
PROJECT_ID=my-gcp-project \
ALLOWED_DOMAINS=anga.co.th \
GOOGLE_OAUTH_CLIENT_ID=1234567890-abc.apps.googleusercontent.com \
DENIED_EMAILS=<shared-mailbox> \
./deploy/deploy.sh
```

- build จาก source ด้วย Cloud Build (ใช้ `Dockerfile`) แล้ว deploy Cloud Run
- `BASE_URL` คำนวณเป็น URL แบบ deterministic `https://SERVICE-PROJECT_NUMBER.REGION.run.app` (override ได้ด้วย env `BASE_URL` เช่นถ้าใช้ custom domain)
- ตั้ง `STORAGE_BACKEND=firestore`, mount secrets เป็น env และ `properties.yaml` เป็นไฟล์ที่ `/config/properties.yaml`
- ค่าเริ่มต้น: `min-instances=0`, `max-instances=3`, `512Mi`, `concurrency=40`, `--cpu-boost`
- service เปิดเป็น public (`--allow-unauthenticated`) เพราะ claude.ai ต้องเรียกได้ ส่วน `/mcp` ถูกป้องกันด้วย OAuth ในแอป

หลัง deploy สคริปต์จะพิมพ์ Connector URL และ OAuth redirect URI ออกมา

ตรวจสอบ:

```bash
curl https://ga4-mcp-PROJECT_NUMBER.asia-southeast1.run.app/health   # ไม่ใช้ /healthz: Cloud Run สงวน path ที่ลงท้ายด้วย z
curl -i -X POST https://ga4-mcp-PROJECT_NUMBER.asia-southeast1.run.app/mcp   # ต้องได้ 401
curl https://ga4-mcp-PROJECT_NUMBER.asia-southeast1.run.app/.well-known/oauth-authorization-server
```

ดู log:

```bash
gcloud run services logs read ga4-mcp --region asia-southeast1 --limit 100
# หรือใน Logs Explorer: jsonPayload.event="tool_call"
```

### build image บนเครื่อง (ไม่บังคับ)

```bash
docker build -t ga4-mcp .
docker run --rm -p 8080:8080 -e AUTH_DISABLED=true \
  -e GA4_PROPERTIES_FILE=/config/properties.yaml \
  -v "$PWD/properties.yaml:/config/properties.yaml:ro" \
  -v "$HOME/.config/gcloud:/home/app/.config/gcloud:ro" ga4-mcp
```

### Deploy อัตโนมัติจาก GitHub (CI/CD ด้วย Cloud Build)

repo: `ANGASparkTeam/anga-analytics-claude` → Cloud Build trigger `ga4-mcp-deploy-main` (region `asia-southeast1`) → [`cloudbuild.yaml`](cloudbuild.yaml)

- **push เข้า `main`** → `test` (pytest) → `build` → `push` image → `deploy` (`deploy/deploy.sh` ใน `IMAGE` mode แล้วเช็ค `/health`) ถ้าขั้นใดไม่ผ่าน จะไม่ deploy
- ค่าใช้จ่ายไปลง billing ของ GCP ไม่ใช้ GitHub Actions
- build รันด้วย service account `ga4-mcp-deployer` (run.admin, artifactregistry.writer, logging.logWriter และ actAs เฉพาะ runtime SA) ซึ่งอ่าน secret ไม่ได้
- ค่าที่ไม่เป็นความลับ (โดเมน, OAuth client ID, DENIED_EMAILS) อยู่ใน `substitutions` ของ `cloudbuild.yaml`
- ดูผลได้ที่ Console → Cloud Build → History (region asia-southeast1)

ตั้งค่าครั้งเดียว (รันซ้ำได้):
```bash
PROJECT_ID=your-project GITHUB_REPO=ANGASparkTeam/anga-analytics-claude \
  ALLOWED_DOMAINS=anga.co.th DENIED_EMAILS=<shared-mailbox> GOOGLE_OAUTH_CLIENT_ID=<web-client-id> \
  ./deploy/setup-cloudbuild.sh
```
ค่าเฉพาะของ deployment (`ALLOWED_DOMAINS`, `DENIED_EMAILS`, `GOOGLE_OAUTH_CLIENT_ID`) เก็บเป็น substitution ของ trigger ไม่อยู่ใน `cloudbuild.yaml` เพราะ repo เป็น public

รันครั้งแรกสคริปต์จะพิมพ์ลิงก์ออกมา ให้เปิดลิงก์นั้น login GitHub กด authorize Cloud Build แล้วติดตั้ง **Google Cloud Build** GitHub App บน org `ANGASparkTeam` (ต้องเป็น org owner หรือให้ owner อนุมัติ) จากนั้นรันสคริปต์อีกครั้งเพื่อสร้าง trigger

deploy ทันทีโดยไม่ต้อง push:
```bash
gcloud builds triggers run ga4-mcp-deploy-main --region=asia-southeast1 --branch=main --project=PROJECT_ID
# หรือจากเครื่องโดยไม่ผ่าน GitHub:
gcloud builds submit --config cloudbuild.yaml --region asia-southeast1 --project PROJECT_ID \
  --service-account projects/PROJECT_ID/serviceAccounts/ga4-mcp-deployer@PROJECT_ID.iam.gserviceaccount.com
```

**สิ่งที่ CI ไม่ได้ทำ:** การแก้ `properties.yaml` และการต่ออายุ GA token ยังต้องรัน `setup-gcp.sh` บนเครื่อง เพราะเป็นความลับและไม่อยู่ใน git (ดูข้อ 3 และข้อ 4)

---

## 7. เพิ่ม connector ใน claude.ai

ต้องเป็น **Owner** ของ organization ใน claude.ai (แผน Team / Enterprise)

1. claude.ai → **Settings → Connectors** (Organization settings)
2. **Add custom connector**
3. Name: `ANGA Marketing Analytics`
4. Remote MCP server URL: `https://ga4-mcp-PROJECT_NUMBER.asia-southeast1.run.app/mcp`
5. Advanced settings (OAuth Client ID/Secret) **เว้นว่าง** – server รองรับ Dynamic Client Registration
6. Add

ผู้ใช้แต่ละคน: Settings → Connectors → ANGA Marketing Analytics → **Connect** → หน้า consent ของ server → เลือกบัญชี Google ของบริษัท → กลับมาที่ Claude แล้วเปิดใช้ connector ในแชท (เมนู tools) Claude Desktop จะใช้ connector เดียวกันจากบัญชี claude.ai โดยอัตโนมัติ

แนะนำให้ติดตั้ง plugin `anga-analytics` ด้วย (หัวข้อถัดไป) เพื่อให้ Claude ทำรายงานได้มาตรฐานเดียวกัน


### ติดตั้ง plugin `anga-analytics` (Skills + connector)

ใน repo มีโฟลเดอร์ [`plugin/`](plugin/) ซึ่งเป็น Claude plugin ที่รวม Skill หลัก `marketing-report`, skill ทางลัด (slash command) และการตั้งค่า MCP (`plugin/.mcp.json`) ที่ชี้ไปยัง server นี้ไว้ด้วยกัน

- **claude.ai / Desktop (ทีม marketing):** admin publish plugin เข้า **org plugin library** (ทำครั้งเดียว และทำซ้ำเมื่อมีเวอร์ชันใหม่) จากนั้นแต่ละคนติดตั้งจาก library แล้วไปกด **Connect** ที่ connector "analytics" แล้ว login ด้วยอีเมลของตัวเอง
- **Claude Code (คนที่มีสิทธิ์เข้า repo):**
  ```bash
  claude plugin marketplace add ANGASparkTeam/anga-analytics-claude
  claude plugin install anga-analytics@anga
  ```
  แล้วใน `claude` พิมพ์ `/mcp` เลือก `plugin:anga-analytics:analytics` แล้วกด Authenticate

วิธีติดตั้งและคำสั่งทั้งหมดสำหรับผู้ใช้ ดู [เริ่มใช้งาน](#เริ่มใช้งาน-สำหรับทีม-marketing) ด้านบน

**เมื่อแก้ Skill:** แก้ไฟล์ใน `plugin/skills/` แล้วเพิ่ม `version` ใน `plugin/.claude-plugin/plugin.json` จากนั้นตรวจด้วย `claude plugin validate ./plugin` และ publish เข้า org library ใหม่ (Cloud Build deploy เฉพาะ server ไม่ได้ publish plugin ให้)
---

## 8. ความปลอดภัย: การจำกัดโดเมน

ผ่านเมื่อครบทุกข้อ (fail closed)

- `email` มีอยู่และ `email_verified` เป็น true
- โดเมนของอีเมล **ตรงกันทุกตัวอักษร** (ไม่สนตัวพิมพ์เล็ก/ใหญ่) กับโดเมนใน `ALLOWED_DOMAINS` – ไม่จับคู่แบบ suffix ดังนั้น `evil-anga.co.th`, `sub.anga.co.th`, `anga.co.th.evil.com` ไม่ผ่าน; อีเมลที่มี `@` มากกว่า 1 ตัว ช่องว่าง หรือตัวอักษรที่ไม่ใช่ ASCII ไม่ผ่าน
- claim `hd` (hosted domain ของ Google Workspace) ต้องอยู่ใน `ALLOWED_DOMAINS` – บัญชี Google ส่วนตัว (รวม Gmail) ไม่มี `hd` จึงไม่ผ่าน (ปิดได้ด้วย `REQUIRE_WORKSPACE_HD=false` แต่ไม่แนะนำ)

ตรวจ 3 จุด

1. **Google callback** (`/auth/callback`): ตรวจทันทีหลังได้ token จาก Google ถ้าไม่ผ่านจะแสดงหน้า 403 และลบ authorization code ทิ้ง จึงไม่มีการออก MCP token เลย
2. **Token exchange** (`/token`): ตรวจซ้ำก่อนออก token (กันกรณี hook ข้อ 1 พัง)
3. **ทุก MCP request**: OAuth proxy ตรวจ Google token กับ Google ทุกครั้ง (cache 5 นาที) และตรวจโดเมนซ้ำ – ถ้าบัญชีถูกระงับใน Workspace หรือ token ถูก revoke จะใช้ไม่ได้ภายในไม่กี่นาที

เพิ่มเติม

- ตอน redirect ไป Google จะส่ง `hd=<domain>` (เมื่อมีโดเมนเดียว) และ `prompt=consent select_account` เพื่อให้เลือกบัญชีงานได้ง่าย (เป็นแค่ UI hint ไม่ใช่ security control)
- OAuth consent screen แบบ **Internal** เป็นด่านแรกอีกชั้น
- รับ redirect URI ของ client เฉพาะ `https://claude.ai/api/mcp/auth_callback`, `https://claude.com/api/mcp/auth_callback` และ `http://localhost:*` / `http://127.0.0.1:*` (สำหรับ Inspector / Claude Code) ปรับได้ด้วย `ALLOWED_CLIENT_REDIRECT_URIS`
- มีหน้า consent ของ FastMCP ก่อนไป Google (กัน confused-deputy)
- ทุก tool เป็น read-only และทุกคนที่ผ่านจะเห็นทุก property ใน `properties.yaml` (ไม่มีสิทธิ์ราย property ในรอบนี้)

---

### ห้ามบัญชีกลาง login

ทีมต้อง login ด้วยอีเมลของตัวเองเท่านั้น ส่วน บัญชีกลาง (shared mailbox) ใช้แค่ฝั่ง server สำหรับอ่าน GA4 และ**ถูกปฏิเสธเสมอ**ถ้าพยายาม login เข้า connector (ได้หน้า 403) เหตุผลคือให้ audit log ระบุตัวคนที่ดึงข้อมูลได้ทุกครั้ง

- โหมด `delegated`: `GA_DELEGATED_SUBJECT` ถูกบล็อกอัตโนมัติ / โหมด `user_token`: ต้องใส่ `DENIED_EMAILS=<shared-mailbox>` (deploy.sh บังคับ)
- บัญชีกลางอื่นๆ ใส่เพิ่มใน `DENIED_EMAILS` (คั่นด้วย comma) เช่น `DENIED_EMAILS=<shared-mailbox>,<other-shared-mailbox> ./deploy/deploy.sh`
- ตรวจทั้ง 3 จุดเหมือนการเช็คโดเมน (callback, token exchange และทุก request)

## 9. การเก็บ OAuth state (persistence)

OAuth proxy ต้องเก็บ: client ที่ลงทะเบียนผ่าน DCR, transaction ระหว่าง login, authorization code, token ของ Google (เข้ารหัส), JTI mapping, refresh token metadata
ถ้าเก็บใน memory: cold start หรือ request ไปตก instance อื่น = token ใช้ไม่ได้ ผู้ใช้ต้อง reconnect

| ตัวเลือก | ข้อดี | ข้อเสีย | ใช้เมื่อ |
|---|---|---|---|
| `memory` | ง่าย | หายทุก restart / ไม่แชร์ข้าม instance | local dev |
| `file` (`STORAGE_DIR`) | ไม่ต้องมี service อื่น | ใช้ได้แค่เครื่องเดียว; บน Cloud Run ถ้า mount GCS FUSE จะไม่มี locking/consistency ระหว่าง instance | dev บนเครื่องที่อยากให้ login ค้างไว้ |
| **`firestore`** (เลือกใช้) | serverless, แชร์ทุก instance, อยู่รอด cold start, free tier ครอบคลุมการใช้งานทีมเล็ก, ใช้ ADC ของ SA เดิม ไม่ต้องมี VPC | ต้องเปิด Firestore; เอกสารที่หมดอายุไม่ถูกลบอัตโนมัติ (ดูด้านล่าง) | **production บน Cloud Run** |
| Redis / Memorystore | เร็ว | ขั้นต่ำ ~$35+/เดือน + ต้องมี VPC connector | ไม่คุ้มสำหรับงานนี้ |

รายละเอียด

- ทุก backend ที่ไม่ใช่ memory **บังคับ** ห่อด้วย `FernetEncryptionWrapper` (`STORAGE_ENCRYPTION_KEY`) ข้อมูลใน Firestore จึงเป็น ciphertext
- หมุน key ได้: ใส่หลาย key คั่นด้วย comma, key แรกใช้เข้ารหัส ที่เหลือใช้ถอดรหัส ข้อมูลที่ถอดไม่ได้ถือว่าไม่มี (ผู้ใช้แค่ต้อง connect ใหม่ ไม่ error)
- `JWT_SIGNING_KEY` ต้องคงที่ข้าม restart/instance ไม่งั้น token ที่ออกไปแล้วจะใช้ไม่ได้ (เปลี่ยน key = บังคับทุกคน reconnect)
- collection ใน Firestore จะขึ้นต้นด้วย `ga4mcp` (เปลี่ยนได้ที่ `FIRESTORE_COLLECTION_PREFIX`)
- ข้อมูลที่หมดอายุถูกมองว่าไม่มีตอนอ่าน แต่เอกสารยังค้างใน Firestore (เก็บเวลาหมดอายุเป็น string จึงใช้ Firestore TTL policy ไม่ได้) – ปริมาณน้อยมาก หากต้องการล้างให้ลบ collection `ga4mcp*` ได้ทุกเมื่อ (ผู้ใช้ต้อง connect ใหม่)

---

## 10. Environment variables

| ตัวแปร | จำเป็น | คำอธิบาย |
|---|---|---|
| `GA4_PROPERTIES_FILE` | | path ของ properties.yaml (ค่าเริ่มต้น `properties.yaml`; บน Cloud Run = `/config/properties.yaml`) |
| `ALLOWED_DOMAINS` | ✓ (auth) | โดเมน Workspace คั่นด้วย comma |
| `BASE_URL` | ✓ (auth) | URL สาธารณะของ server (ไม่มี `/mcp`) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | ✓ (auth) | OAuth client แบบ Web application |
| `JWT_SIGNING_KEY` | ✓ (prod) | สตริงสุ่มยาว ต้องคงที่ |
| `STORAGE_BACKEND` | | `memory` (default) / `file` / `firestore` |
| `STORAGE_ENCRYPTION_KEY` | ✓ (file/firestore) | Fernet key(s) คั่นด้วย comma |
| `FIRESTORE_PROJECT`, `FIRESTORE_DATABASE`, `FIRESTORE_COLLECTION_PREFIX` | | ตั้งค่า Firestore |
| `STORAGE_DIR` | | โฟลเดอร์สำหรับ `file` |
| `REQUIRE_WORKSPACE_HD` | | ค่าเริ่มต้น `true` |
| `ALLOWED_CLIENT_REDIRECT_URIS` | | pattern ของ redirect URI ที่ MCP client ลงทะเบียนได้ |
| `AUTH_DISABLED` | | `true` = ไม่ต้องล็อกอิน (local เท่านั้น) |
| `PORT`, `HOST` | | ค่าเริ่มต้น `8080`, `0.0.0.0` |
| `MCP_STATELESS_HTTP` | | ค่าเริ่มต้น `true` (ไม่ต้องใช้ session affinity) |
| `LOG_LEVEL`, `LOG_FORMAT` | | `INFO`; `json` (บน Cloud Run เป็น JSON อัตโนมัติ) |

สร้าง key เอง:

```bash
openssl rand -base64 48                                                         # JWT_SIGNING_KEY
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # STORAGE_ENCRYPTION_KEY
```

---

## 11. Troubleshooting

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| Google แสดง `redirect_uri_mismatch` | redirect URI ใน OAuth client ต้องตรงกับ `${BASE_URL}/auth/callback` ทุกตัวอักษร (https, ไม่มี `/` ท้าย) และ `BASE_URL` ต้องเป็น URL ที่ผู้ใช้เข้าจริง |
| หน้า "Access denied" หลังเลือกบัญชี | บัญชีไม่ใช่ Workspace ของโดเมนใน `ALLOWED_DOMAINS` (หรือเป็น Gmail) ดู log `auth denied email=... reason=...` |
| Google แจ้ง "Access blocked: app is restricted to users within its organization" | consent screen เป็น Internal และผู้ใช้ไม่ได้อยู่ใน org – ถูกต้องตามที่ออกแบบ |
| ผู้ใช้ต้อง reconnect บ่อย | ตรวจว่า `STORAGE_BACKEND=firestore`, `JWT_SIGNING_KEY` / `STORAGE_ENCRYPTION_KEY` มาจาก secret เดิม (ไม่ถูกสร้างใหม่) และ SA มี `roles/datastore.user` |
| claude.ai เชื่อมต่อไม่ได้ / 401 ตลอด | เปิด `${BASE_URL}/.well-known/oauth-authorization-server` ต้องได้ JSON ที่มี `registration_endpoint`; URL ที่ใส่ใน connector ต้องลงท้าย `/mcp` |
| `invalid redirect uri` ตอน register | client ใช้ callback ที่ไม่อยู่ใน `ALLOWED_CLIENT_REDIRECT_URIS` ให้เพิ่ม pattern |
| deploy ไม่ผ่านเพราะ `allUsers` (org policy Domain restricted sharing) | ใช้ `PUBLIC_INVOKER_MODE=no-invoker-iam-check ./deploy/deploy.sh` |
| Cloud Build permission denied ตอน `--source` | ให้ build service account (โดยปกติ `PROJECT_NUMBER-compute@developer.gserviceaccount.com`) มี `roles/cloudbuild.builds.builder` หรือดูข้อความ error ของ gcloud |
| Tool ตอบ `PERMISSION_DENIED` / ไม่เห็น property | บัญชีกลางไม่มีสิทธิ์ property นั้น, domain-wide delegation ยังไม่มีผล (รอสูงสุด 30 นาที) หรือ property id ใน `properties.yaml` ผิด |
| Tool ตอบ `could not authenticate ... unauthorized_client` | ยังไม่ได้เพิ่ม Client ID ของ SA ใน Domain-wide delegation หรือใส่ scope ไม่ตรง (ข้อ 4) |
| Tool `gsc_*` ตอบ `could not authenticate to Search Console` | token ไม่มี scope `webmasters.readonly` ให้ mint token ใหม่ (ข้อ 4 แบบ A) และตรวจว่า Search Console API เปิดใน project แล้ว |
| Tool `gsc_*` ตอบ `Permission denied` / `not verified` | บัญชีกลางไม่ได้เป็น user ของ property นั้นใน Search Console หรือสถานะเป็น `siteUnverifiedUser` ให้เจ้าของเว็บเพิ่ม บัญชีกลาง  ใหม่ |
| แก้ properties แล้วไม่เปลี่ยน | ต้องเพิ่ม secret version ใหม่ (`setup-gcp.sh`) แล้วออก revision ใหม่ (`deploy.sh`) |
| `AUTH_DISABLED=true is not allowed on Cloud Run` | ตั้งใจไว้ ห้ามปิด auth บน Cloud Run |
| cold start ช้า (~3–6 วินาที) | ตั้ง `MIN_INSTANCES=1` (มีค่าใช้จ่ายเพิ่ม ดูข้อ 12) |

---

## 12. ค่าใช้จ่าย

ประมาณการสำหรับทีมการตลาด 5–30 คน (ราคา ณ วันเขียน ตรวจสอบหน้า pricing ล่าสุดอีกครั้ง)

- **Cloud Run** (request-based billing, `min-instances=0`): free tier ต่อเดือน 180,000 vCPU-second / 360,000 GiB-second / 2 ล้าน request – การใช้งานทีมเล็กมักอยู่ใน free tier ≈ **$0**
  - ถ้าตั้ง `MIN_INSTANCES=1` เพื่อตัด cold start: 1 vCPU / 512Mi idle ตลอดเดือนประมาณ **$10–15/เดือน**
- **Firestore**: free tier 50,000 reads / 20,000 writes / 20,000 deletes ต่อวัน + 1 GiB – ใช้ไม่กี่ read ต่อ MCP request ≈ **$0** (free tier ใช้ได้กับ database `(default)` หนึ่งตัวต่อ project)
- **Secret Manager**: 6 active versions + 10,000 access ฟรีต่อเดือน; เกินนั้น ~$0.06/version/เดือน ≈ **< $1**
- **Cloud Build / Artifact Registry**: 2,500 build-minutes ฟรี (e2-standard-2), เก็บ image ฟรี 0.5 GB ≈ **$0** (ลบ image เก่าใน repo `cloud-run-source-deploy` เป็นระยะ)
- **GA4 Data API**: ไม่มีค่าใช้จ่าย แต่มี quota ต่อ property (token ต่อชั่วโมง/วัน) – server มี cache 3–15 นาทีและแจ้งเตือนเมื่อ quota เหลือน้อย
- **Memorystore/Redis**: ไม่ใช้ (ขั้นต่ำ ~$35+/เดือน)
