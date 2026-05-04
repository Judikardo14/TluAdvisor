import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from groq import Groq

# ── Configuration ──────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
WEBHOOK_URL  = os.environ["WEBHOOK_URL"]   # ex: https://ton-username-ton-space.hf.space

groq_client = Groq(api_key=GROQ_API_KEY)

# ── Chargement des règles ───────────────────────────────────────────────────────
with open("rules.txt", "r", encoding="utf-8") as f:
    RULES = f.read()

SYSTEM_PROMPT = f"""
Tu es le jury officiel et défenseur attitré de l'équipe dans un match de Génie en Herbe.
Tu maîtrises parfaitement le règlement officiel du club.

Tes missions :
1. Analyser toute réclamation ou situation litigieuse soumise pendant le match.
2. Défendre les intérêts de l'équipe en t'appuyant UNIQUEMENT sur les articles et clauses du règlement.
3. Citer précisément les articles concernés pour justifier chaque argument.
4. Rédiger des réclamations officielles claires et convaincantes si demandé.
5. Rester factuel, neutre dans la forme, mais ferme dans le fond.

Règlement officiel du club :
─────────────────────────────
{RULES}
─────────────────────────────

Réponds toujours en français. Sois concis mais rigoureusement argumenté.
Si une situation n'est pas couverte par le règlement, dis-le clairement.
"""

# ── Stockage de l'historique (mémoire en cours d'exécution) ────────────────────
# Structure : { chat_id: [ {role, content}, ... ] }
conversation_history: dict[int, list[dict]] = {}

MAX_HISTORY = 20  # Nombre max d'échanges conservés par match (pour ne pas dépasser le contexte)

# ── FastAPI ─────────────────────────────────────────────────────────────────────
app = FastAPI()

telegram_app = Application.builder().token(BOT_TOKEN).build()


# ── Handlers Telegram ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "⚖️ *Jury Génie en Herbe activé.*\n\n"
        "Je connais le règlement sur le bout des doigts. Décris-moi la situation ou la réclamation.\n\n"
        "Commandes disponibles :\n"
        "• /newmatch — Effacer l'historique et démarrer un nouveau match\n"
        "• /resume — Afficher le résumé des points discutés\n"
        "• /help — Aide",
        parse_mode="Markdown"
    )


async def cmd_newmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []
    await update.message.reply_text(
        "🔄 *Nouveau match démarré.* Historique effacé.\n\n"
        "Prêt pour les réclamations.",
        parse_mode="Markdown"
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    history = conversation_history.get(chat_id, [])

    if not history:
        await update.message.reply_text("Aucun échange enregistré pour ce match.")
        return

    # Demander à Groq de résumer
    summary_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {
            "role": "user",
            "content": "Fais un résumé structuré de toutes les réclamations et arguments discutés jusqu'ici dans ce match."
        }
    ]
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=summary_messages,
        max_tokens=800,
        temperature=0.2
    )
    summary = response.choices[0].message.content
    await update.message.reply_text(f"📋 *Résumé du match :*\n\n{summary}", parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Aide — Jury Génie en Herbe*\n\n"
        "Envoie simplement ta question ou décris la situation litigieuse.\n\n"
        "*Commandes :*\n"
        "• /start — Démarrer / réinitialiser\n"
        "• /newmatch — Nouveau match (efface l'historique)\n"
        "• /resume — Résumé des réclamations du match\n"
        "• /help — Cette aide\n\n"
        "*Exemples de questions :*\n"
        "— _L'adversaire a répondu après le buzzer, c'est valide ?_\n"
        "— _On conteste le thème tiré au sort, que dit le règlement ?_\n"
        "— _Rédige une réclamation officielle pour..._",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Initialiser l'historique si besoin
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []

    # Ajouter le message utilisateur à l'historique
    conversation_history[chat_id].append({"role": "user", "content": user_text})

    # Tronquer si trop long (garder les MAX_HISTORY derniers échanges)
    if len(conversation_history[chat_id]) > MAX_HISTORY * 2:
        conversation_history[chat_id] = conversation_history[chat_id][-(MAX_HISTORY * 2):]

    # Construire les messages pour Groq
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history[chat_id]
    ]

    # Appel Groq
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            max_tokens=800,
            temperature=0.3
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"⚠️ Erreur lors de la consultation du jury : {str(e)}"

    # Ajouter la réponse à l'historique
    conversation_history[chat_id].append({"role": "assistant", "content": reply})

    await update.message.reply_text(reply)


# ── Enregistrement des handlers ────────────────────────────────────────────────
telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CommandHandler("newmatch", cmd_newmatch))
telegram_app.add_handler(CommandHandler("resume", cmd_resume))
telegram_app.add_handler(CommandHandler("help", cmd_help))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# ── Démarrage ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    await telegram_app.start()
    print(f"✅ Webhook enregistré : {WEBHOOK_URL}/webhook")


@app.on_event("shutdown")
async def shutdown():
    await telegram_app.stop()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/")
def root():
    return {"status": "Jury Génie en Herbe — Bot actif ✅"}
