import os
import discord
from dotenv import load_dotenv


load_dotenv()
TOKEN = int(os.getenv('TOKEN'))

# Initialisation du client
# Si vous prévoyez d'utiliser des fonctionnalités d'intents (recommandé par discord.py)
intents = discord.Intents.default()
intents.message_content = True # Nécessaire pour lire le contenu des messages

client = discord.Client(intents=intents)

# Événement de démarrage
@client.event
async def on_ready():
    print(f'Bot connecté sous le nom : {client.user}')

# Événement de message
@client.event
async def on_message(message):
    # S'assurer que le bot ne répond pas à ses propres messages
    if message.author == client.user:
        return

    # Le coeur de la détection
    if "croissant" in message.content.lower() or "chocoblast" in message.content.lower():
        # Votre logique de chocoblast va ici
        # 1. Enregistrer le chocoblast (qui a fait la blague et qui a été "chocoblasté")
        # 2. Envoyer un message de confirmation
        # 3. Mettre à jour les classements

        # Exemple de message de confirmation simple
        await message.channel.send(f"⚠️ **CHOCOBLAST** ⚠️\n<@{message.author.id}> a été chocoblasté(e) ! Le score a été mis à jour.")

# Démarrer le bot
client.run(TOKEN)