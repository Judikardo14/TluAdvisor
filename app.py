import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes,
)
from groq import Groq

BOT_TOKEN    = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
WEBHOOK_URL  = os.environ["WEBHOOK_URL"]

groq_client = Groq(api_key=GROQ_API_KEY)

with open("rules.txt", "r", encoding="utf-8") as f:
    RULES = f.read()

SYSTEM_PROMPT = f"""
Tu es le jury officiel et défenseur de l'équipe dans un match de Génie en Herbe.
Tu maîtrises parfaitement le règlement officiel du club.

Tes missions :
1. Analyser toute réclamation ou situation litigieuse soumise pendant le match.
2. Défendre les intérêts de l'équipe en t'appuyant UNIQUEMENT sur les articles du règlement.
3. Citer précisément les articles concernés pour justifier chaque argument.
4. Rédiger des réclamations officielles claires si demandé.
5. Rester factuel, neutre dans la forme, mais ferme dans le fond.

Règlement officiel :
─────────────────────────────
{RULES}
─────────────────────────────

Réponds toujours en français. Sois concis mais rigoureusement argumenté.
Si une situation n'est pas couverte par le règlement, dis-le clairement.
"""

conversation_history: dict[int, list[dict]] = {}
MAX_HISTORY = 20

# ── Build Telegram app (sans initialize au démarrage) ─────────────────────────
telegram_app = Application.builder().token(BOT_TOKEN).build()
_initialized = False

# FastAPI app must be defined before route decorators
app = FastAPI()

async def ensure_initialized():
    global _initialized
    if not _initialized:
        await telegram_app.initialize()
        await telegram_app.start()
        _initialized = True

@app.get("/setup")
async def setup_webhook():
    """Enregistre manuellement le webhook auprès de Telegram via navigateur/curl"""
    await ensure_initialized()
    try:
        result = await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        return {"status": "✅ Webhook enregistré", "url": f"{WEBHOOK_URL}/webhook", "result": result}
    except Exception as e:
        return {"status": "❌ Erreur", "error": str(e)}

# ── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "⚖️ *Jury Génie en Herbe activé.*\n\n"
        "Décris-moi la situation ou la réclamation.\n\n"
        "• /newmatch — Nouveau match\n"
        "• /resume — Résumé des réclamations\n"
        "• /help — Aide",
        parse_mode="Markdown"
    )


async def cmd_newmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_chat.id] = []
    await update.message.reply_text(
        "🔄 *Nouveau match démarré.* Historique effacé.\nPrêt pour les réclamations.",
        parse_mode="Markdown"
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    history = conversation_history.get(chat_id, [])
    if not history:
        await update.message.reply_text("Aucun échange enregistré pour ce match.")
        return
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": "Fais un résumé structuré de toutes les réclamations et arguments discutés jusqu'ici."}
        ],
        max_tokens=800, temperature=0.2
    )
    await update.message.reply_text(
        f"📋 *Résumé du match :*\n\n{response.choices[0].message.content}",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Aide — Jury Génie en Herbe*\n\n"
        "Envoie ta question ou décris la situation litigieuse.\n\n"
        "• /start — Démarrer\n"
        "• /newmatch — Nouveau match\n"
        "• /resume — Résumé des réclamations\n"
        "• /help — Aide\n\n"
        "*Exemples :*\n"
        "— _L'adversaire a répondu après le buzzer ?_\n"
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
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *conversation_history[chat_id]],
            max_tokens=800, temperature=0.3
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"⚠️ Erreur : {str(e)}"
    conversation_history[chat_id].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)


telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CommandHandler("newmatch", cmd_newmatch))
telegram_app.add_handler(CommandHandler("resume", cmd_resume))
telegram_app.add_handler(CommandHandler("help", cmd_help))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.post("/webhook")
async def webhook(request: Request):
    await ensure_initialized()
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/")
def root():
    return {"status": "Jury Génie en Herbe — Bot actif ✅"}