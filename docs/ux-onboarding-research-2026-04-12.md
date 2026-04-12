# UX Onboarding Research — "Try Without Token" (2026-04-12)

*Investigation by botbuilder-backend (for botbuilder-researcher), 2026-04-12*

## Problem Statement

40% drop between `preview_shown` and `token_step_opened`. Users see their generated bot code but can't interact with it without a multi-minute detour: BotFather → create → copy token → paste. This creates massive friction right before conversion.

## Evidence

- **Funnel data (all-time, 12 users):**
  - `preview_shown`: 5 unique users
  - `token_step_opened`: 3 unique users (40% drop)
  - `token_submitted`: 4 unique users (1 user skipped token_step, went directly?) ← anomaly
  - `deploy_succeeded`: 4 users
- **Competitor data (Botract "8 Things"):** "Test Mode Before Publishing" listed as key evaluation criterion
- **PuzzleBot:** Hosts bots on their own infra, user can test immediately after generation

## Options Analysis

### Option A — Test Bot Pool (best)

**Mechanism:**
1. Pre-create 10-20 @KaiTestBot tokens (maintain a pool in a shared DB table)
2. At preview stage, add "🔵 Попробовать без токена" ReplyKeyboard button
3. On click: deploy user's code to next available test bot token (mark as `reserved`)
4. Bot DMs user a deep link: `https://t.me/KaiTestBot{1-20}?start={user_id}`
5. User sends 3-5 test messages → sees real responses
6. Track with `preview_test_opened` event
7. After trial: "Deploy with your token" or "Regenerate" CTA

**Pros:** Full interactivity before token commitment. Solves core friction. Differentiator.

**Cons:**
- Requires 10-20 @KaiTestBot accounts (BotFather tokens)
- Need cleanup: expire/recycle test bots after trial or after 24h
- Test bot names won't match user's intended bot name
- If pool exhausted → show "All test bots busy, try again in X min"
- Security: user's generated code running on our tokens

**Complexity:** Medium-high. Requires:
- Pool management DB table (`test_bot_pool: token, status, reserved_by, expires_at`)
- `deploy_to_test_pool(user_code, user_id)` function
- Cleanup job (cron or scheduled task)
- `preview_test_opened` event instrumentation

---

### Option B — Meta Bot Preview (quick-and-dirty)

**Mechanism:**
1. "💬 Попробовать сейчас" button at preview
2. Opens DM to @KaiAiBotBuilderBot with `?start=preview_{user_id}`
3. Meta bot temporarily injects user's handler code into its own running process

**Cons:** Security/isolation horror. User code running inside meta bot process. Limited to simple bots. Not recommended.

---

### Option C — Screenshot/Video Preview (easiest)

**Mechanism:**
1. At preview stage, generate static screenshot or GIF
2. Shows what the bot's initial message flow looks like

**Cons:** Low information value. Doesn't solve conversion problem.

---

## Recommendation

**Phase 1 (MVP, 1-2h):** Placeholder + demand validation:
- "🔵 Попробовать без токена" button at preview
- On click: reply "Скоро эта функция будет доступна!" + track event
- Validates demand + buys time for Option A build

**Phase 2 (Option A, 1-2 days):**
1. Create 10 @KaiTestBot1...@KaiTestBot10 tokens via BotFather
2. Add `test_bot_pool` table: `bot_num`, `token`, `status`, `reserved_by`, `reserved_at`, `expires_at`
3. Write `deploy_to_test_pool(code, user_id)` — picks available test bot, deploys, sends deep link
4. Write cleanup job (releases bots older than 24h)
5. Add `preview_test_opened` + `preview_test_expired` events
6. Replace placeholder with real deployment

## Unanswered Questions

1. **How many test bots needed?** 10 seems arbitrary. Need Phase 1 demand signal.
2. **Token commitment threshold:** Does "try for free" cannibalize actual conversions?
3. **Test bot naming:** Users confused why "Hair Salon Bot" = @KaiTestBot5.
4. **Pool exhaustion:** Queue? Wait list? "Come back tomorrow"?
5. **Bot lifecycle:** Who pays for hosting abandoned test bots?
