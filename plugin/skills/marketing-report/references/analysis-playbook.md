# Analysis playbook

## Contents
- Sanity thresholds
- Diagnosing a drop or spike
- UTM hygiene checks
- Tracking-issue signals
- Recommendations style

## Sanity thresholds

Use these as flags, not verdicts. Adjust with history from `trend`.

| Check | Flag when |
|---|---|
| Week-over-week session change | beyond +/-15% (normal weekly noise is ~5-10%) |
| Daily change vs same weekday last week | beyond +/-30% |
| Row too small to judge | < 100 sessions in the row |
| Engagement rate | < 30% on a content/landing page with > 500 sessions; site-wide change > 5 pts |
| (not set) share of sessions in a channel/campaign dimension | > 5% |
| Direct share of sessions | > 40% or +10 pts vs previous (likely lost UTMs/referrers) |
| Unassigned channel | > 2% |
| keyEvents falls but sessions flat (or vice versa) | tracking/form/checkout issue first, marketing second |
| key event rate = 0 for a configured key event over >= 3 days with traffic | tracking broken |
| New users share | sudden jump (> +15 pts) = campaign/bot burst; sudden fall = loss of acquisition |
| Single-day spike > 3x median | likely bot/referral spam or one-off campaign/push; check source and country |
| Revenue / purchases vs backend | GA 5-20% below backend is normal; > 30% off = tracking gap |

## Diagnosing a drop or spike

Work top-down; at each step compute each segment's contribution to the total change (segment delta / total delta) and move into the segment that explains most. Stop when >= ~70% is explained or segments are exhausted.

1. **Confirm and size it**: `kpi_summary` compare previous_period and previous_year. Is it traffic (sessions/users) or quality (engagement rate, key event rate)? Seasonality (Songkran, 11.11, 12.12, payday, long weekends, school terms) - check previous_year before alarming.
2. **When**: `trend(day)` -> exact start date; correlate with known events (deploy, campaign end/start, budget change, site migration, algorithm update). Ask the user for events - do not assume.
3. **Channel**: `channel_performance` default. Which group fell? Paid vs organic vs direct vs referral vs social vs email. If Organic Search fell, confirm with `gsc_performance` (same dates, `granularity="day"`): GSC clicks fell too = real search loss; GSC flat = GA tracking/attribution issue.
4. **Source / medium**: `channel_performance(dimension="sessionSourceMedium")`. Single source collapsing (e.g. google / organic, facebook / cpc) or a new junk source?
5. **Campaign** (if paid/email/social): `campaign_performance` - paused/ended campaigns, renamed campaigns (a rename shows as old falls + new rises: the total may be flat).
6. **Landing page**: `page_performance(mode="landing")` - which pages lost sessions? Whole site vs a section (blog, product category). Pages that lost organic traffic -> `gsc_top_pages` (compare previous_period) then `gsc_page_queries` on the losers: fewer impressions = ranking/indexing loss (check redirect/404/noindex), same impressions but lower ctr = SERP/title change or new competitor, lower position = ranking drop.
7. **Device / geo**: `key_event_breakdown(by="deviceCategory")` or `run_report` dims `deviceCategory`, `country`. Drop only on mobile -> mobile site/app/tag issue, or a mobile-heavy channel (LINE, Facebook) dropped.
8. **Tracking vs real**: see signals below. If traffic dropped but backend sales did not, suspect tracking.

For a spike: same order; check bot signals (very low engagement rate, one country/city, one device/browser, one referral source, 1-second sessions).

## UTM hygiene checks

Run on `campaign_performance` and `channel_performance(dimension="sessionSourceMedium")` output; compare to naming convention in [company-config.md](company-config.md).

- Case variants of the same campaign (`Summer_Sale` vs `summer_sale`) - GA4 is case-sensitive; merge mentally and tell the user to fix at the source.
- Spaces/Thai characters/special chars in campaign names; trailing characters; typos like `faceboook`.
- Inconsistent medium: standard mediums are `cpc`, `email`, `social`, `organic`, `referral`, `display`, `affiliate`. Non-standard (e.g. `paid-social`, `FB`) land in Unassigned/Other channel groups.
- Source naming variants: `facebook` vs `fb` vs `m.facebook.com` / `l.facebook.com`; `line` vs `line.me`.
- Missing `utm_campaign` -> `(not set)` campaign; paid sessions as Direct/Unassigned.
- Internal links tagged with UTMs (overwrite the true source) - sessionSource shows own domain or odd campaigns on internal pages.
- Self-referrals / payment gateways as referral (e.g. bank 3-D Secure, PromptPay pages) - new sessions after payment; flag if they are in top referral sources.
Report as a short table: issue | example (value from data) | impact (sessions) | fix.

## Tracking-issue signals

- Sudden zero or step change in a key event on one day while sessions are stable (tag removed, consent banner change, form redesign).
- `sessions` up, `engagementRate` collapsing + near-zero duration: bot traffic or double-firing tags.
- Pageviews per session jumps (~2x): duplicate page_view tags (double GTM + gtag).
- Revenue with ecommercePurchases = 0 or opposite; revenue per purchase absurd (currency/units issue).
- Direct share rises abruptly after site/domain/redirect/consent change.
- Landing pages show `(not set)` or very long query strings (use `landingPage`, not PlusQueryString - already handled by the tool).
- Property split: if the same content is measured in two properties (web vs app), do not add or compare them directly.
You cannot fix tracking from here; hand the user a precise checklist (what, where, since when).

## Recommendations style

- Max 3-5 actions, each: what, why (numbers), who/where (e.g. ทีม SEO, ทีม Ads), how to measure success.
- Prefer actions the data supports; mark experiments as ทดลอง.
- If the data cannot answer ("ทำไมคนไม่ซื้อ"), say what extra data is needed (Search Console, ad platform cost, heatmap, backend orders).
