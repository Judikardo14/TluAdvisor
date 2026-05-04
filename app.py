import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes,
)
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
BOT_TOKEN     = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY  = os.environ["GROQ_API_KEY"]
WEBHOOK_URL   = os.environ["WEBHOOK_URL"]

groq_client = Groq(api_key=GROQ_API_KEY)

with open("rules.txt", "r", encoding="utf-8") as f:
    RULES = f.read()

# ── Prompts système ────────────────────────────────────────────────────────────

PROMPT_PRESIDENT = f"""
Tu es le Président du Jury d'un match de Génie en Herbe.
Tu incarnes l'autorité suprême : impartial, rigoureux, définitif.

Tes missions :
1. Analyser toute réclamation ou situation litigieuse avec neutralité absolue.
2. Trancher en te fondant UNIQUEMENT sur les articles du règlement officiel.
3. Citer l'article applicable, énoncer ta décision, point final.
4. Ne jamais favoriser une équipe. Ta décision est sans appel.

Règlement officiel :
─────────────────────────────
{RULES}
─────────────────────────────

Format de réponse :
📋 Article(s) applicable(s) : [référence]
⚖️ Décision : [ta sentence, claire et brève]

Réponds toujours en français. Sois bref, précis, solennel.
Si la situation n'est pas couverte par le règlement, dis-le avec la même autorité.
"""

PROMPT_AVOCAT = f"""
Tu es l'Avocat officiel de l'équipe dans un match de Génie en Herbe.
Tu défends les intérêts de l'équipe qui te consulte avec conviction et professionnalisme.

Tes missions :
1. Analyser la situation du point de vue de l'équipe.
2. Construire les meilleurs arguments en ta faveur, en t'appuyant sur le règlement.
3. Citer précisément les articles qui soutiennent ta défense.
4. Si demandé, rédiger une réclamation officielle prête à soumettre au jury.
5. Rester factuel dans la forme, mais ferme et persuasif dans le fond.

Règlement officiel :
─────────────────────────────
{RULES}
─────────────────────────────

Format de réponse :
🛡️ Argument(s) : [tes arguments, article(s) à l'appui]
📝 Réclamation (si demandée) : [texte officiel]

Réponds toujours en français. Sois concis, professionnel, combatif mais courtois.
Si aucun article ne soutient la demande, dis-le honnêtement.
"""

# ── État des utilisateurs ──────────────────────────────────────────────────────

# mode : "president" | "avocat"
user_mode: dict[int, str] = {}
conversation_history: dict[int, list[dict]] = {}
MAX_HISTORY = 20

def get_prompt(chat_id: int) -> str:
    return PROMPT_PRESIDENT if user_mode.get(chat_id, "president") == "president" else PROMPT_AVOCAT

def get_mode_label(chat_id: int) -> str:
    return "⚖️ Président du Jury" if user_mode.get(chat_id, "president") == "president" else "🛡️ Avocat de l'équipe"

# ── Telegram app ───────────────────────────────────────────────────────────────

telegram_app = Application.builder().token(BOT_TOKEN).build()
app = FastAPI()

# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    try:
        await telegram_app.bot.initialize()
        telegram_app._initialized = True
        logger.info("Bot HTTP initialized ✅")
    except Exception as e:
        logger.error(f"Bot initialize error: {e}")
        telegram_app._initialized = True

    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook enregistré : {webhook_url} ✅")
    except Exception as e:
        logger.error(f"Échec enregistrement webhook : {e}")

# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    user_mode[chat_id] = "president"
    await update.message.reply_text(
        "⚖️ *Génie en Herbe — Assistant Officiel*\n\n"
        "Mode actuel : *Président du Jury*\n\n"
        "Commandes disponibles :\n"
        "• /president — Passer en mode Président du Jury\n"
        "• /avocat — Passer en mode Avocat de l'équipe\n"
        "• /mode — Afficher le mode actuel\n"
        "• /newmatch — Nouveau match (efface l'historique)\n"
        "• /resume — Résumé des échanges\n"
        "• /help — Aide",
        parse_mode="Markdown"
    )

async def cmd_president(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_mode[chat_id] = "president"
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "⚖️ *Mode Président du Jury activé.*\n\n"
        "Je tranche les réclamations avec impartialité, en vertu du règlement.\n"
        "Exposez la situation.",
        parse_mode="Markdown"
    )

async def cmd_avocat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_mode[chat_id] = "avocat"
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "🛡️ *Mode Avocat de l'équipe activé.*\n\n"
        "Je défends vos intérêts avec rigueur et conviction.\n"
        "Exposez votre situation ou demandez une réclamation officielle.",
        parse_mode="Markdown"
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    label = get_mode_label(chat_id)
    await update.message.reply_text(
        f"Mode actuel : *{label}*\n\n"
        "• /president — Basculer en Président du Jury\n"
        "• /avocat — Basculer en Avocat de l'équipe",
        parse_mode="Markdown"
    )

async def cmd_newmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    label = get_mode_label(chat_id)
    await update.message.reply_text(
        f"🔄 *Nouveau match démarré.* Historique effacé.\nMode actuel : {label}",
        parse_mode="Markdown"
    )

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    history = conversation_history.get(chat_id, [])
    if not history:
        await update.message.reply_text("Aucun échange enregistré pour ce match.")
        return
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": get_prompt(chat_id)},
            *history,
            {"role": "user", "content": "Fais un résumé structuré et bref de tous les échanges de ce match."}
        ],
        max_tokens=500, temperature=0.2
    )
    label = get_mode_label(chat_id)
    await update.message.reply_text(
        f"📋 *Résumé — {label}*\n\n{response.choices[0].message.content}",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Aide — Génie en Herbe*\n\n"
        "*Modes disponibles :*\n"
        "• /president — Président du Jury _(tranche impartialement)_\n"
        "• /avocat — Avocat de l'équipe _(défend vos intérêts)_\n"
        "• /mode — Mode actuel\n\n"
        "*Gestion du match :*\n"
        "• /newmatch — Nouveau match\n"
        "• /resume — Résumé des échanges\n\n"
        "*Exemples de situations :*\n"
        "— _L'adversaire a répondu après le buzzer_\n"
        "— _Un spectateur a soufflé la réponse_\n"
        "— _Rédige une réclamation officielle pour..._",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in conversation_history:
        conversation_history[chat_id] = []

    conversation_history[chat_id].append({"role": "user", "content": user_text})
    if len(conversation_history[chat_id]) > MAX_HISTORY * 2:
        conversation_history[chat_id] = conversation_history[chat_id][-(MAX_HISTORY * 2):]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": get_prompt(chat_id)},
                *conversation_history[chat_id]
            ],
            max_tokens=400,
            temperature=0.3
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"⚠️ Erreur : {str(e)}"

    conversation_history[chat_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

# ── Enregistrement des handlers ────────────────────────────────────────────────

telegram_app.add_handler(CommandHandler("start",     cmd_start))
telegram_app.add_handler(CommandHandler("president", cmd_president))
telegram_app.add_handler(CommandHandler("avocat",    cmd_avocat))
telegram_app.add_handler(CommandHandler("mode",      cmd_mode))
telegram_app.add_handler(CommandHandler("newmatch",  cmd_newmatch))
telegram_app.add_handler(CommandHandler("resume",    cmd_resume))
telegram_app.add_handler(CommandHandler("help",      cmd_help))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ── Routes FastAPI ─────────────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

@app.get("/setup")
async def setup_webhook():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                data={"url": webhook_url}
            )
            result = response.json()
            if result.get("ok"):
                return {"status": "✅ Webhook enregistré", "url": webhook_url}
            else:
                return {"status": "❌ Erreur Telegram", "error": result.get("description")}
    except Exception as e:
        return {"status": "❌ Exception", "error": str(e)}

@app.get("/")
def root():
    return {"status": "Génie en Herbe — Bot actif ✅"}
