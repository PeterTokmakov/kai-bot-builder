# Kai Bot Builder — Interactive Demo
# Gradio web interface for Kai Bot Builder
# https://github.com/PeterTokmakov/kai-bot-builder

import gradio as gr

BOT_LINK = "https://t.me/KaiAiBotBuilderBot?start=hfspace"

BOT_TYPES = [
    "Lead / Contact Form Bot",
    "FAQ Bot",
    "Appointment Booking Bot",
    "Reminder / Notification Bot",
    "Customer Support Bot",
    "Product Catalog Bot",
]

AI_MODELS = [
    "GPT-4o (most capable)",
    "GPT-4o-mini (fast, cost-effective)",
    "Claude 3.5 Sonnet (creative, detailed)",
    "Claude 3 Haiku (fast, affordable)",
    "Gemini 1.5 Flash (free tier)",
]

PERSONALITY_STYLES = [
    "Professional & Formal",
    "Friendly & Casual",
    "Technical & Precise",
    "Helpful & Educational",
]


def generate_bot_config(bot_description, bot_type, ai_model, personality_style, include_ai, custom_instructions):
    bot_description = bot_description.strip() if bot_description else "A helpful Telegram bot"
    bot_type = bot_type or "FAQ Bot"
    ai_model = ai_model or "GPT-4o-mini (fast, cost-effective)"
    personality_style = personality_style or "Friendly & Casual"
    custom_instructions = custom_instructions.strip() if custom_instructions else ""

    keywords = [w for w in bot_description.split() if len(w) > 3][:5]
    name_words = [w.capitalize() for w in keywords[:2]]
    suggested_name = "".join(name_words) + "Bot" if name_words else "MyBot"

    welcome_map = {
        "Professional": "Hello! I am here to assist you professionally. How may I help you today?",
        "Friendly": "Hey there! Great to see you! What can I help you with today?",
        "Technical": "System initialized. Bot ready. Awaiting input parameters.",
        "Educational": "Welcome! I am here to help you learn and accomplish your goals.",
    }

    for key in welcome_map:
        if key in personality_style:
            welcome = welcome_map[key]
            break
    else:
        welcome = welcome_map["Friendly"]

    code = """# Kai Bot Builder — Generated Configuration
# Model: {ai_model}
# Type: {bot_type}

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_NAME = "{suggested_name}"
BOT_TOKEN = "YOUR_BOTFATHER_TOKEN_HERE"
AI_MODEL = "{ai_model}"
SYSTEM_PROMPT = \"\"\"{personality_style}

You are {suggested_name}, a {bot_type}.
Your task: {bot_description}

{custom_instructions}
\"\"\"

async def start(update, context):
    await update.message.reply_text("Hello! Type /help for commands.")

async def help_cmd(update, context):
    await update.message.reply_text("Commands: /start, /help, /ask")

async def handle_message(update, context):
    user_text = update.message.text
    response = f"Processing: {user_text[:50]}... (AI response via Kai Bot Builder)"
    await update.message.reply_text(response)

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info(f"{BOT_NAME} started - powered by Kai Bot Builder")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
""".format(
        ai_model=ai_model, bot_type=bot_type,
        suggested_name=suggested_name,
        personality_style=personality_style,
        bot_description=bot_description,
        custom_instructions=custom_instructions
    )

    summary = """## {name} - Bot Configuration Preview

**Suggested name:** {name}
**Type:** {bot_type}
**AI model:** {ai_model}
**Personality:** {personality}

### What it will do
> {desc}

### Welcome message
> {welcome}

### Deployment steps
1. Get a BotFather token -> @BotFather
2. Paste it into @KaiAiBotBuilderBot
3. Your bot is live in ~60 seconds
4. First 3 bots are FREE
""".format(
        name=suggested_name, bot_type=bot_type,
        ai_model=ai_model, personality=personality_style,
        desc=bot_description, welcome=welcome
    )

    return code, summary


def build_demo():
    with gr.Blocks(
        title="Kai Bot Builder - AI Telegram Bot Generator",
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="blue"),
        css=""".gradio-container {max-width: 1100px !important; margin: auto;}
               .hero {text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 16px; margin-bottom: 20px;}"""
    ) as demo:

        gr.Markdown("""
        <div class="hero">
            <h1>Kai Bot Builder - Demo</h1>
            <p>Create AI-powered Telegram bots by describing what you want in plain language.</p>
            <p><a href="https://t.me/KaiAiBotBuilderBot?start=hfspace">Open the Bot on Telegram</a></p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Bot Configuration")
                bot_description = gr.Textbox(
                    label="What should your bot do?",
                    placeholder="e.g. A FAQ bot that answers questions about our SaaS pricing",
                    lines=4, value=""
                )
                bot_type = gr.Dropdown(choices=BOT_TYPES, label="Bot type", value="FAQ Bot")
                ai_model = gr.Dropdown(choices=AI_MODELS, label="AI model", value="GPT-4o-mini (fast, cost-effective)")
                personality_style = gr.Dropdown(choices=PERSONALITY_STYLES, label="Personality", value="Friendly & Casual")
                include_ai = gr.Checkbox(label="Include AI responses (recommended)", value=True)
                custom_instructions = gr.Textbox(
                    label="Additional instructions (optional)",
                    placeholder="e.g. Always suggest a follow-up product at the end",
                    lines=2, value=""
                )
                generate_btn = gr.Button("Generate Bot Configuration", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### Generated Output")
                code_output = gr.Code(label="Python Bot Code", language="python", lines=25)
                summary_output = gr.Markdown(label="Configuration Summary")

        gr.Markdown("""
        ---

        ### Deploy Your Real Bot

        To get a **live, hosted AI Telegram bot** in ~60 seconds:
        1. Get a BotFather token -> @BotFather -> /newbot
        2. Describe your bot -> @KaiAiBotBuilderBot
        3. Paste the token
        4. Your bot is live! First 3 bots are FREE.

        ---

        *Built with Gradio. Source: GitHub. Bot: @KaiAiBotBuilderBot*
        """)

        generate_btn.click(
            fn=generate_bot_config,
            inputs=[bot_description, bot_type, ai_model, personality_style, include_ai, custom_instructions],
            outputs=[code_output, summary_output]
        )

    return demo


demo = build_demo()
demo.launch()
