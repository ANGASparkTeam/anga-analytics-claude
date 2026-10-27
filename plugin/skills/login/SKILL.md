---
name: login
description: Shortcut - log in to (connect) the ANGA Marketing Analytics connector, or check who is logged in, and walk the user through signing in if they are not, in Thai.
argument-hint: (no arguments)
disable-model-invocation: true
---

# Login (เชื่อมต่อ / ตรวจสอบการล็อกอิน)

Answer in Thai. Claude cannot open the Google sign-in itself and must never ask for passwords, codes or tokens; the user signs in in their own browser.

1. Call the connector's `whoami` tool (it reads no analytics data).
2. If it returns `connected: true`:
   - Say: เชื่อมต่อแล้ว ล็อกอินในชื่อ `<signed_in_as>` · ข้อมูลอ่านผ่านบัญชีกลาง (อ่านอย่างเดียว)
   - If `signed_in_as` is not an @anga.co.th address, or looks like a shared mailbox rather than a person, say this account must not be used and to sign in again with their own @anga.co.th email.
   - Suggest a first try: `/anga-analytics:how-to` or `/anga-analytics:seo <ลูกค้า>`.
3. If the tool is missing, fails, or says it needs authorization, the user is not signed in. Give the steps for where they are (ask only if you cannot tell):
   - **Claude Code / Code tab ใน Claude Desktop:** พิมพ์ `/mcp` → เลือก `plugin:anga-analytics:analytics` → **Authenticate** → browser จะเปิดหน้า ANGA Marketing Analytics → กด Continue → เลือกบัญชี Google **@anga.co.th ของตัวเอง** → Allow → กลับมาที่ Claude (ถ้ารายการไม่มี analytics ให้รัน `/reload-plugins` ก่อน)
   - **claude.ai / แชทใน Claude Desktop:** Settings → Connectors → **analytics** → **Connect** → เลือกบัญชี @anga.co.th ของตัวเอง → Allow แล้วเปิด connector ในเมนู tools ของแชท
   - Then ask them to run `/anga-analytics:login` again to confirm.
4. Common problems:
   - "Access denied" / 403 หลังเลือกบัญชี: ใช้ Gmail ส่วนตัวหรือ บัญชีกลาง → ล็อกอินใหม่ด้วยอีเมล @anga.co.th ของตัวเอง
   - "Access blocked: app is restricted to users within its organization": บัญชีไม่ได้อยู่ใน Google Workspace ของ anga.co.th
   - เคยเชื่อมต่อแล้วแต่ใช้ไม่ได้: ทำขั้นตอนข้อ 3 ซ้ำ (session หมดอายุ) ถ้ายังไม่ได้ แจ้งทีม Spark (spark@anga.co.th)
