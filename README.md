# ⚖️ Jury Génie en Herbe — Bot Telegram IA

Bot Telegram propulsé par **Groq (LLaMA 3 70B)**, déployé sur **Hugging Face Spaces (Docker)**.
Il connaît le règlement de ton club et défend les intérêts de ton équipe lors des réclamations.

---

## 📁 Structure du projet

```
genie_jury_bot/
├── app.py            → Code principal (FastAPI + Telegram + Groq)
├── rules.txt         → Règles officielles du club (à remplir)
├── requirements.txt  → Dépendances Python
├── Dockerfile        → Configuration du conteneur HF Spaces
└── README.md         → Ce fichier
```

---

## 🚀 Déploiement — Étape par étape

### Étape 1 — Créer le bot Telegram

1. Ouvre Telegram et cherche **@BotFather**
2. Envoie `/newbot`
3. Suis les instructions et note le **token** du bot (ex: `7312456789:AAFxxxxx...`)

---

### Étape 2 — Obtenir une clé API Groq

1. Va sur [console.groq.com](https://console.groq.com)
2. Crée un compte (gratuit)
3. Dans **API Keys**, génère une clé et note-la

---

### Étape 3 — Créer le Space sur Hugging Face

1. Va sur [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choisis :
   - **SDK** : `Docker`
   - **Visibility** : `Public` (recommandé pour avoir une URL stable)
3. Note l'URL de ton Space : `https://TON_USERNAME-TON_SPACE_NAME.hf.space`

---

### Étape 4 — Configurer les secrets

Dans ton Space HF → **Settings** → **Repository secrets**, ajoute :

| Nom              | Valeur                                          |
|------------------|-------------------------------------------------|
| `TELEGRAM_TOKEN` | Le token de ton bot BotFather                  |
| `GROQ_API_KEY`   | Ta clé API Groq                                 |
| `WEBHOOK_URL`    | `https://TON_USERNAME-TON_SPACE_NAME.hf.space`  |

---

### Étape 5 — Remplir les règles

Ouvre `rules.txt` et **remplace le contenu d'exemple** par le vrai règlement de ton club.
Structure recommandée :

```
ARTICLE 1 — TITRE
Description précise de la règle...

ARTICLE 2 — TITRE
...
```

> ⚠️ **Plus les règles sont précises, plus le jury sera redoutable.**

---

### Étape 6 — Pousser le code

```bash
# Clone ton Space HF
git clone https://huggingface.co/spaces/TON_USERNAME/TON_SPACE_NAME
cd TON_SPACE_NAME

# Copie les fichiers du projet
cp /chemin/vers/genie_jury_bot/* .

# Push
git add .
git commit -m "Initial deploy — Jury Génie en Herbe"
git push
```

Le Space se build automatiquement. Attends ~2 minutes.

---

### Étape 7 — Vérifier le déploiement

1. Va sur l'URL de ton Space : tu dois voir `{"status": "Jury Génie en Herbe — Bot actif ✅"}`
2. Ouvre ton bot Telegram, envoie `/start`
3. Le bot répond → **c'est bon** ✅

---

## 💬 Commandes disponibles

| Commande     | Action                                                    |
|--------------|-----------------------------------------------------------|
| `/start`     | Démarrer le bot / réinitialiser                          |
| `/newmatch`  | Effacer l'historique et démarrer un nouveau match        |
| `/resume`    | Résumé structuré des réclamations du match en cours      |
| `/help`      | Afficher l'aide et les exemples                          |

---

## 🧠 Exemples d'utilisation

```
Toi : L'équipe adverse a répondu après le buzzer, c'est valide ?
Bot : Selon l'Article 3 du règlement, toute réponse donnée après le signal
      de fin de temps est invalidée. La réponse adverse doit donc être annulée.

Toi : Et si l'arbitre n'avait pas encore levé la main ?
Bot : (en se souvenant du contexte) Dans ce cas, l'Article 3 alinéa 2 précise
      que c'est le signal de l'arbitre qui fait foi, pas le buzzer seul...

Toi : Rédige la réclamation officielle.
Bot : "Nous, l'équipe [Nom], contestons formellement la validation de la
      réponse de l'équipe adverse au motif que..."
```

---

## ⚙️ Configuration avancée

### Changer le modèle Groq

Dans `app.py`, ligne `model="llama3-70b-8192"`, tu peux utiliser :
- `llama3-70b-8192` — Le plus puissant (recommandé)
- `llama3-8b-8192` — Plus rapide, moins précis
- `mixtral-8x7b-32768` — Contexte plus long

### Ajuster la mémoire du bot

Dans `app.py`, `MAX_HISTORY = 20` = nombre d'échanges conservés par match.
Augmenter cette valeur = plus de mémoire, mais plus de tokens consommés.

---

## 🛠️ Dépannage

| Problème                        | Solution                                                              |
|---------------------------------|-----------------------------------------------------------------------|
| Bot ne répond pas               | Vérifie les secrets HF + rebuilde le Space                           |
| `TELEGRAM_TOKEN` introuvable    | Ajoute les secrets dans Settings → Repository secrets                |
| Webhook non enregistré          | Vérifie que `WEBHOOK_URL` ne se termine pas par `/`                  |
| Erreur Groq 429                 | Limite de débit atteinte — attends ou passe sur un plan payant Groq  |
| Réponses hors sujet             | Améliore `rules.txt` en ajoutant plus de détails au règlement        |

---

## 📄 Licence

Projet personnel — Judikardo / ENSGMM AI Club
