# UX Spec: Onboarding Token Step Friction Reduction
**Author:** botbuilder-frontend  
**Date:** 2026-04-14  
**Task:** #7235  
**Status:** Draft for review

---

## Current Flow (as-is)

```
PREVIEW  →  LAUNCH click  →  _handle_launch()
                               ├─ Wizard Steps 1-4 (BotFather instructions)
                               ├─ Pre-token card (Step 5): confirm/edit + FAQ/Booking
                               └─ returns TOKEN
                              
TOKEN state → user pastes token OR clicks "✅ Ready—continue"
             → _handle_deploy_confirm() → Wizard Steps 1-4 again
             → TOKEN state accepts token input
```

**Funnel data (old, 12 users):**
- `preview_shown`: 5 unique users
- `token_step_opened`: 3 unique users (40% drop)
- `token_submitted`: 4 unique users
- `deploy_succeeded`: 4 users

**Current pain point:** Users see the wizard + pre-token card but if they don't have a BotFather token yet, they have no explicit "how to get started" guidance inline on that card. They either figure it out or drop.

---

## Proposed Improvements

### 1. Progress Indicator on Pre-token Card

**What:** Add "Шаг 3 из 4: Добавьте токен бота" to the pre-token card (Step 5).

**Where:** `_handle_launch()` line ~1050, in the pre-token card text.

**Current text (RU):**
```
✅ <b>Всё готово!</b>\n\nВаш бот собран и готов к запуску. Нажмите кнопку ниже чтобы продолжить.
```

**Proposed (RU):**
```
📋 <b>Шаг 3 из 4: Добавьте токен бота</b>\n\n
Ваш бот собран и готов к запуску. Нажмите кнопку ниже чтобы продолжить.
```

**Why:** Sets expectation that this is step 3 of an overall 4-step process. Reduces anxiety about "how many more steps."

**Note:** Pre-token card is effectively the confirmation step before the token input step. Labeling it as "step 3 of 4" keeps the mental model consistent with the earlier wizard steps.

**Files touched:** `meta_bot.py` — TEXTS dict entries `deploy_confirm_title` + `deploy_confirm_title_en`, plus the inline text at line ~1051.

---

### 2. Inline "Need a bot token?" Helper on Pre-token Card

**What:** Below the confirm/edit buttons, add a compact helper block:
```
💡 <b>Ещё нет токена?</b>\n
Откройте @BotFather → отправьте /newbot → скопируйте токен\n
👉 <a href='https://t.me/BotFather?start=create'>Открыть @BotFather</a>
```

**Placement:** After the main pre-token card message, before the FAQ/Booking quick-start row.

**Purpose:** Users who don't have a BotFather token yet get inline guidance without scrolling or clicking "Как получить токен." Reduces the 40% drop between preview and token submission.

**Files touched:** `meta_bot.py` — new TEXTS key `need_token_helper` / `need_token_helper_en`; added to `_handle_launch()` message sequence.

---

### 3. Copy `/newbot` Template Button (Optional — Low Priority)

**What:** Add an inline button "📋 Копировать /newbot" that copies the text `/newbot` to clipboard via Telegram's `switch_inline_query` or a pre-filled input field.

**Status:** **Low priority.** Telegram's ReplyKeyboard/InlineKeyboard does not support clipboard copy directly. Workaround options:
- Use `InputTextMessageContent` with `switch_inline_query` — requires user to click and then send
- Show the `/newbot` text in a copyable `<code>` block
- Use Telegram's "share" mechanic

**Recommendation:** Implement as `<code>/newbot</code>` block with label "Нажмите и удержите чтобы скопировать" (Telegram supports long-press copy on code-formatted text). No new button needed — just make the existing step 3 instruction more prominent.

---

### 4. Quick Verify Step for Users Who Already Have a Bot (Out of Scope)

**What:** Allow users to test their existing bot before deploying.

**Status:** **Out of scope for this task.** Requires test bot pool (#6902, blocked on Peter). Covered by #6884.

---

## UX Flow After Changes

```
PREVIEW
    ↓ [LAUNCH]
_handle_launch()
    ├─ Wizard Steps 1-4 (unchanged)
    └─ Pre-token card:
         ├─ 📋 Шаг 3 из 4: Добавьте токен бота
         ├─ ✅ Ready—continue  ✏️ Edit Description
         ├─ 💡 Ещё нет токена? → @BotFather /newbot inline helper
         └─ (FAQ/Booking quick-start row — unchanged)
    ↓ [Ready—continue]
_handle_deploy_confirm()
    ├─ Wizard Steps 1-4 (unchanged)
    └─ returns TOKEN
TOKEN
    ↓ [paste token]
_handle_token_submit() → deploy
```

---

## Implementation Plan

### Phase 1 (This task — UX polish, no backend changes)

| # | Change | File | Lines |
|---|--------|------|-------|
| 1a | Add step indicator to `deploy_confirm_title` (RU) | `meta_bot.py` | ~268 |
| 1b | Add step indicator to `deploy_confirm_title_en` | `meta_bot.py` | ~599 |
| 2a | Add `need_token_helper` text key (RU) | `meta_bot.py` | TEXTS dict |
| 2b | Add `need_token_helper_en` text key (EN) | `meta_bot.py` | TEXTS dict |
| 2c | Insert helper message after pre-token card | `meta_bot.py` | ~1055 |

**Estimated effort:** ~20 lines of code, 1-2 hours.

### Phase 2 (Blocked on #6902)
- Test bot pool for "try without token"
- `preview_test_opened` event instrumentation

---

## Open Questions

1. **Step numbering accuracy:** The pre-token card says "Step 3 of 4" but the wizard before it shows Steps 1-4, and then the pre-token card is a 5th element. Is "Step 3 of 4" the right label, or should it be "Step 3 of 5: Confirm & Add Token"?
   - **Recommendation:** "Step 3 of 4" is fine — the 4 steps are: (1) Open BotFather, (2) Start chat, (3) Get token, (4) Paste token. The pre-token card is part of Step 3-4.

2. **Localization:** All texts added need RU + EN variants.

---

## Out of Scope

- Test bot pool (#6884 / #6902)
- Bot verification step
- Changes to deployment logic
- Landing page changes

---

## Files to Modify

| File | Change |
|------|--------|
| `projects/bot-builder/meta_bot.py` | TEXTS dict additions; `_handle_launch()` message sequence |

**No new files.** No database changes. No events changes.
