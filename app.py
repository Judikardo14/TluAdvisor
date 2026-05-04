import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import os
import httpx
import asyncio
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

async def forward_to_admin(text: str):
    if not ADMIN_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": ADMIN_CHAT_ID, "text": text[:3500]}
            )
    except Exception as e:
        logger.error("Failed to forward to admin: %s", e)

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

# FastAPI app must be defined before route decorators
app = FastAPI()

@app.on_event("startup")
async def startup():
    """Initialiser le bot au démarrage (timeout court pour éviter le freeze)"""
    try:
        # Essayer d'initializer le bot avec un timeout court
        import asyncio
        await asyncio.wait_for(telegram_app.initialize(), timeout=2.0)
    except asyncio.TimeoutError:
        print("Bot initialize timed out (HF Spaces network limit), continuing anyway...")
    except Exception as e:
        print(f"Bot initialize error: {e}, continuing anyway...")
    
    # Mark as initialized anyway so process_update works
    telegram_app._initialized = True

@app.get("/setup")
async def setup_webhook():
    """Enregistre manuellement le webhook auprès de Telegram (appel direct API)"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                data={"url": webhook_url}
            )
            result = response.json()
            if result.get("ok"):
                return {"status": "✅ Webhook enregistré", "url": webhook_url, "ok": True}
            else:
                error_msg = result.get("description", str(result))
                return {"status": "❌ Erreur Telegram", "error": error_msg, "ok": False}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {"status": "❌ Erreur exception", "error": str(e), "detail": error_detail}

# ── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"[cmd_start] User {update.effective_chat.id}: {update.message.text if update.message else 'no message'}")
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
    logger.info(f"[cmd_newmatch] User {update.effective_chat.id}")
    conversation_history[update.effective_chat.id] = []
    await update.message.reply_text(
        "🔄 *Nouveau match démarré.* Historique effacé.\nPrêt pour les réclamations.",
        parse_mode="Markdown"
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"[cmd_resume] User {update.effective_chat.id}")
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
    logger.info(f"[cmd_help] User {update.effective_chat.id}")
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
    logger.info(f"[handle_message] User {update.effective_chat.id}: {update.message.text if update.message else 'no text'}")
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
    try:
        logger.info("Webhook called")
        data = await request.json()
        logger.info(f"Webhook data: {data}")
        update = Update.de_json(data, telegram_app.bot)
        logger.info(f"Webhook update parsed: {update}")
        await telegram_app.process_update(update)
        logger.info("Webhook processed successfully")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        print(f"Webhook error: {e}")
        import traceback
        tb = traceback.format_exc()
        print(tb)
        try:
            await forward_to_admin(f"Webhook error:\n{str(e)}\n\n{tb}")
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


@app.get("/test")
async def test_message():
    """Endpoint de test pour simuler un message /start"""
    try:
        # Simuler un message /start
        from telegram import User, Chat, Message
        test_user = User(id=999, is_bot=False, first_name="Test")
        test_chat = Chat(id=999, type="private")
        test_msg = Message(message_id=1, date=None, chat=test_chat, from_user=test_user, text="/start")
        test_update = Update(update_id=1, message=test_msg)
        
        await telegram_app.process_update(test_update)
        return {"ok": True, "msg": "Test message processed"}
    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        tb = traceback.format_exc()
        print(tb)
        try:
            await forward_to_admin(f"Test endpoint error:\n{str(e)}\n\n{tb}")
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


@app.get("/")
def root():
    return {"status": "Jury Génie en Herbe — Bot actif ✅"}