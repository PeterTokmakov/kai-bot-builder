# Kai Bot Builder — Onboarding UX Improvements

**Reference:** `bot-share-feature-design.md`, `bot-builder-ux-improvements.md`, `bot-builder-style-guide.md`
**Product:** Kai Bot Builder (Telegram bot)
**Version:** 1.0 — 2026-04-13

---

## 1. Overview

**Problem:** Based on botbuilder-tester past sessions, the first-bot walkthrough has three friction points:
1. Token wizard screen has no example suggestions — users who just want to explore don't know what to try
2. No preview of what the bot will do before they commit their token
3. After deploy, no clear next-steps — users don't know how to talk to their bot or what to do next

**Competitor benchmark:** Manychat/Chatfuel use guided onboarding with example templates and clear post-setup CTAs. The current Kai Bot Builder experience drops users into "paste your token" without context.

**Design principles (from style guide):**
- Dark navy palette, blue accent
- Bold headers + status emoji at message start
- `ReplyKeyboardMarkup` for persistent buttons, `InlineKeyboardMarkup` only for external deep links
- Copy-paste instructions for non-technical users

---

## 2. Token Wizard — Example Bot Suggestions

### Problem

The token wizard screen (`launch_token_ask`) currently shows only instructions for getting a token. Users who don't have a bot yet and just want to explore have no "try this now" affordance.

### Design: Example Bot Quick-Starter Buttons

**When:** Token step first shown (`_handle_launch`). After the main ask message, add example suggestion buttons on the same keyboard.

**Keyboard layout — new:**

```python
ReplyKeyboardMarkup([
    [BTN_TOKEN_HELP if locale == "RU" else BTN_TOKEN_HELP_EN],  # existing help button
    [BTN_EXAMPLE_FAQ if locale == "RU" else BTN_EXAMPLE_FAQ_EN],  # new
    [BTN_EXAMPLE_BOOKING if locale == "RU" else BTN_EXAMPLE_BOOKING_EN],  # new
], resize_keyboard=True, one_time_keyboard=False)
```

**New button labels:**
```python
BTN_EXAMPLE_FAQ = "❓ Попробовать FAQ-бота"
BTN_EXAMPLE_FAQ_EN = "❓ Try FAQ Bot"
BTN_EXAMPLE_BOOKING = "📅 Попробовать бота записи"
BTN_EXAMPLE_BOOKING_EN = "📅 Try Booking Bot"
```

**UX rationale:** Buttons, not links. These are actions — user clicks → bot fetches example description → generates preview → user sees "this is what your bot would look like" before they decide to commit.

### New handler: `handle_example_quick_start`

```python
async def handle_example_quick_start(update: Update, context: ContextTypes.DEFAULT_TYPE, template: str):
    """Generate and send a preview for a pre-defined example bot template."""
    example_map = {
        "faq": "...",
        "booking": "...",
    }
    description = example_map.get(template)
    if not description:
        return
    
    locale = _get_locale(update)
    user_id = update.effective_user.id
    
    # Generate preview (reuse existing generate_bot_code path)
    result = generate_bot_code(user_id, description)
    
    if result["ok"]:
        await send_preview(update, result, locale)
        context.chat_data["description"] = description
        context.chat_data["template"] = result["template"]
        return PREVIEW
    else:
        await update.message.reply_text(t("gen_error").format(error=result["error"]))
        return DESCRIBE
```

### Message flow when user clicks "Попробовать FAQ-бота"

**Before:** User is at TOKEN step with keyboard showing help + example buttons
**Action:** User clicks "❓ Попробовать FAQ-бота"

**Bot response:**
```
⏳ Пробую FAQ-бота для вас...

✨ <b>Ваш бот готов!</b>

📋 <b>Тип:</b> FAQ
📝 <b>Описание:</b> Бот для ответов на частые вопросы. Пользователь пишет вопрос → бот отвечает из списка.
📦 <b>Код:</b> 1420 символов

<b>Что умеет:</b>
• ❓ Отвечает на вопросы по ключевым словам
• 📝 Админ-панель для добавления вопросов
• 🔔 Уведомление админу о новом вопросе

<i>Пример обработчика:</i>
[code snippet]

ℹ️ Ваш бот работает 24/7 на серверах Kai. Вам нужен только бесплатный токен от @BotFather.

[InlineKeyboardMarkup: 🚀 Запустить | ✏️ Уточнить описание]

📋 Действия с ботом:
```

**Then immediately follow with:**
```
💡 Вам понравился результат?

Чтобы запустить этого бота — нажмите «🚀 Запустить» и получите токен @BotFather.
Или измените описание: нажмите «✏️ Уточнить описание».
```

### UX flow diagram

```
TOKEN step (user sees keyboard with help + FAQ + Booking buttons)
    │
    ├─ User pastes token → deploy flow
    │
    ├─ User clicks "❓ Попробовать FAQ-бота"
    │     → bot generates preview
    │     → PREVIEW step (same as normal flow)
    │     → user sees generated bot + CTA
    │     → user can edit description or deploy with token
    │
    └─ User clicks "📅 Попробовать бота записи"
          → same as above, booking template
```

**Key:** Example quick-start does NOT consume the user's free bot slot. It's a preview only. Deploy consumes the slot.

**Tracking:** `record_event("example_quickstart_click", user_id=user_id, template=template)` — telemetry for which examples are most popular.

---

## 3. Token Wizard — Bot Preview Before Token

### Problem

Users paste their token before seeing what the bot will do. This creates anxiety — they're committing something (their bot token) without seeing the result. Competitors (Manychat) show the canvas/welcome message before asking for credentials.

### Design: Show preview BEFORE asking for token

**When:** User is at the PREVIEW step (after `deploy_succeeded` shown, user clicked `🚀 Запустить`). Currently this immediately shows the token instructions. Instead:

**Modified PREVIEW → TOKEN transition:**

**Current flow:**
```
PREVIEW (user sees generated bot preview)
    → User clicks "🚀 Запустить"
    → TOKEN step: token instructions shown
```

**New flow:**
```
PREVIEW (user sees generated bot preview)
    → User clicks "🚀 Запустить"
    → TOKEN step: FIRST show a confirmation card with bot summary + "Next: get your token"
    → User confirms → token instructions shown
```

**New message: Pre-token confirmation card**

```
🚀 <b>Почти готово!</b>

Ваш бот: <b>{template}</b>
Описание: {description}

📋 <b>Что дальше:</b>
1️⃣ Получите токен бота в @BotFather (бесплатно)
2️⃣ Вставьте токен сюда
3️⃣ Бот запустится автоматически — работает 24/7

💡 Ваш токен хранится только в виде хеша. Никто не видит вашего токена.

[ReplyKeyboardMarkup: ✅ Всё готово — продолжить | ✏️ Изменить описание]
```

**Why:** Users see what their bot is (template + description) before being asked for credentials. The "1-2-3" next-steps list creates a mental roadmap. Security note (token stored as hash) reduces anxiety.

**Keyboard:** Two buttons — "Continue" (primary CTA) and "Edit description" (secondary, returns to DESCRIBE).

**Button labels:**
```python
BTN_CONFIRM_DEPLOY = "✅ Всё готово — продолжить"
BTN_CONFIRM_DEPLOY_EN = "✅ Ready — continue"
```

### Implementation note

The confirmation card replaces the first message shown at TOKEN step (`launch_token_ask`). The original 6-step token instructions become Message 2 (shown after user confirms).

```
TOKEN step structure (new):
  Message 1: Pre-token confirmation card (with bot summary)
  Message 2: Token ask + instructions (only after confirmation)
```

**Handler for confirmation:**
```python
async def _handle_deploy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User confirmed deploy — now ask for token."""
    locale = _get_locale(update)
    t = lambda k: _t(locale, k)
    await update.message.reply_text(
        t("launch_excellent") + "\n\n" + t("launch_token_ask"),
        parse_mode="HTML",
        reply_markup=make_help_keyboard(locale)
    )
    return TOKEN
```

This requires storing the `template` and `description` in `context.chat_data` before entering TOKEN state, which is already done (via `context.chat_data["description"]` and `context.chat_data["template"]`).

---

## 4. Post-Deploy Next-Steps

### Problem

After `deploy_succeeded`, users don't know what to do next. Do they open their bot? Share it? Configure it? There's no guidance.

### Design: Post-Deploy Next-Steps Card

**Current `deploy_succeeded` message (RU):**
```
✅ <b>Бот запущен!</b>

🆔 ID: {bot_id}
📊 Статус: 🟢 активен
🆓 Бесплатно до {expires_at}.

Управление:
/mybots — список ваших ботов
/stop {bot_id} — остановить
/delete {bot_id} — удалить
/share — текст, которым можно поделиться
```

**New `deploy_succeeded` message (RU):**
```
✅ <b>Ваш бот запущен!</b>

🆔 ID: {bot_id}
📊 Статус: 🟢 активен
🆓 Бесплатно до {expires_at}.

<b>Что дальше:</b>

① 📱 <b>Откройте вашего бота</b>
   Напишите в Telegram: <code>@{bot_username}</code>
   Бот работает 24/7 — отвечает на сообщения автоматически.

② 🧪 <b>Протестируйте</b>
   Отправьте боту сообщение — проверьте что он отвечает.
   Пример: «Привет! Что ты умеешь?»

③ 📤 <b>Поделитесь</b>
   Отправьте /share — получите текст для рекламы.
   Реферальная ссылка: вашим друзьям +1 бесплатный бот.

④ ⚙️ <b>Настройте</b>
   /mybots — список ваших ботов
   /stop {bot_id} — остановить
   /delete {bot_id} — удалить
```

**Keyboard:** `📤 Поделиться` button (inline, `InlineKeyboardMarkup`) — one-click share prompt. Also add a `📱 Открыть бота` button that opens `https://t.me/{bot_username}`.

```python
InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "📱 Открыть @{bot_username}",
            url=f"https://t.me/{bot_username}"
        )
    ],
    [
        InlineKeyboardButton(
            _t(locale, "share_inline_label"),
            url=f"https://t.me/share/url?url=https://t.me/KaiAiBotBuilderBot?start=ref_{user_id}&text={quote('Create your Telegram bot in minutes — free first month!')}"
        )
    ]
])
```

**Why this structure:**
- "① ② ③" are proactive steps — most important first (test the bot)
- "④" is reactive / management commands
- The inline buttons `Открыть бота` and `Поделиться` are one-tap actions (no command to type)
- Copy-paste instruction for testing ("send a message like...") — reduces "bot doesn't respond" confusion

**EN version:**
```
✅ <b>Your bot is live!</b>

🆔 ID: {bot_id}
📊 Status: 🟢 active
🆓 Free until {expires_at}.

<b>What to do next:</b>

① 📱 <b>Open your bot</b>
   Message <code>@{bot_username}</code> in Telegram
   Bot runs 24/7 and responds automatically.

② 🧪 <b>Test it</b>
   Send your bot a message — see how it responds.
   Example: "Hi! What can you do?"

③ 📤 <b>Share it</b>
   Send /share — get shareable text.
   Your referral link: friends get +1 free bot month.

④ ⚙️ <b>Manage</b>
   /mybots — list your bots
   /stop {bot_id} — stop
   /delete {bot_id} — delete
```

---

## 5. Implementation Notes

### Files to modify

**`meta_bot.py`:**
1. Add new button labels: `BTN_EXAMPLE_FAQ`, `BTN_EXAMPLE_FAQ_EN`, `BTN_EXAMPLE_BOOKING`, `BTN_EXAMPLE_BOOKING_EN`, `BTN_CONFIRM_DEPLOY`, `BTN_CONFIRM_DEPLOY_EN`
2. Add new TEXTS keys: `deploy_next_steps`, `deploy_next_steps_en`, `example_preview_label`, `example_preview_label_en`
3. `_handle_launch`: add example buttons to keyboard
4. `_handle_example_prompt` or new `handle_example_quick_start`: handle FAQ/Booking quick-start
5. Add `handle_deploy_confirm` handler: confirmation card → token instructions
6. Update `deploy_succeeded` TEXTS key: add next-steps card structure
7. Update `receive_token` trigger: show confirmation card first (before token ask)
8. Register new handlers

**`db.py`:**
- Add `record_event("example_quickstart_click", user_id=user_id, template=template)`

### New TEXTS keys

```python
"deploy_next_steps": "✅ <b>Ваш бот запущен!</b>\n\n"
                      "🆔 ID: <code>{bot_id}</code>\n"
                      "📊 Статус: 🟢 активен\n"
                      "🆓 Бесплатно до {expires_at}.\n\n"
                      "<b>Что дальше:</b>\n\n"
                      "① 📱 <b>Откройте вашего бота</b>\n"
                      "   Напишите в Telegram: <code>@{bot_username}</code>\n\n"
                      "② 🧪 <b>Протестируйте</b>\n"
                      "   Отправьте боту сообщение — проверьте ответ.\n"
                      "   Пример: «Привет! Что ты умеешь?»\n\n"
                      "③ 📤 <b>Поделитесь</b>\n"
                      "   Отправьте /share — получите текст для рекламы.\n\n"
                      "④ ⚙️ <b>Настройте:</b>\n"
                      "/mybots — список ботов\n"
                      "/stop {bot_id} — остановить\n"
                      "/delete {bot_id} — удалить",
"deploy_next_steps_en": "✅ <b>Your bot is live!</b>\n\n"
                        "🆔 ID: <code>{bot_id}</code>\n"
                        "📊 Status: 🟢 active\n"
                        "🆓 Free until {expires_at}.\n\n"
                        "<b>What to do next:</b>\n\n"
                        "① 📱 <b>Open your bot</b>\n"
                        "   Message <code>@{bot_username}</code> in Telegram\n\n"
                        "② 🧪 <b>Test it</b>\n"
                        "   Send your bot a message — see how it responds.\n"
                        "   Example: \"Hi! What can you do?\"\n\n"
                        "③ 📤 <b>Share it</b>\n"
                        "   Send /share — get shareable text.\n\n"
                        "④ ⚙️ <b>Manage:</b>\n"
                        "/mybots — list bots\n"
                        "/stop {bot_id} — stop\n"
                        "/delete {bot_id} — delete",
"example_preview_label": "<b>Вот что получается:</b>",
"example_preview_label_en": "<b>Here's what you get:</b>",
```

### New TEXTS keys (continued — deploy confirmation card)

```python
"deploy_confirm_title": "🚀 <b>Почти готово!</b>\n\n"
                       "Ваш бот: <b>{template}</b>\n"
                       "Описание: {description}\n\n"
                       "<b>Что дальше:</b>\n"
                       "1️⃣ Получите токен бота в @BotFather (бесплатно)\n"
                       "2️⃣ Вставьте токен сюда\n"
                       "3️⃣ Бот запустится автоматически — работает 24/7\n\n"
                       "💡 Ваш токен хранится только в виде хеша. Никто не видит вашего токена.",
"deploy_confirm_title_en": "🚀 <b>Almost ready!</b>\n\n"
                            "Your bot: <b>{template}</b>\n"
                            "Description: {description}\n\n"
                            "<b>Next steps:</b>\n"
                            "1️⃣ Get your bot token from @BotFather (free)\n"
                            "2️⃣ Paste the token here\n"
                            "3️⃣ Bot launches automatically — runs 24/7\n\n"
                            "💡 Your token is stored as a hash only. Nobody sees it.",
```

### Estimated implementation effort

| Item | Hours | Notes |
|---|---|---|
| Token wizard example buttons | 0.5 | New keyboard + handler |
| Example quick-start preview generation | 1.0 | Reuses generate_bot_code, adds handler |
| Pre-token confirmation card | 1.0 | New TEXTS + confirm handler + flow change |
| Post-deploy next-steps card | 0.5 | Update TEXTS + add inline buttons |
| Testing | 1.0 | Edge cases, RU/EN |
| **Total** | **~4 hours** | Backend only |

---

*Maintained by: botbuilder-designer*
*Reference: `bot-share-feature-design.md`, `bot-builder-ux-improvements.md`, `bot-builder-style-guide.md`*
