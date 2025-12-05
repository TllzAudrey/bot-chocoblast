import discord
from discord.ext import commands, tasks
from discord import app_commands 
import json
import os 
from datetime import datetime, timedelta
import glob 
import re 
from dotenv import load_dotenv


load_dotenv()
# Assurez-vous d'avoir bien défini ADMIN_ROLE_ID dans votre fichier .env
ADMIN_ROLE_ID = int(os.getenv('ADMIN_ROLE_ID')) 

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents) 

# stockage de l'horaire du dernier chocoblast de l'utilisateur (pour le cooldown de la commande /chocoblaste)
# Format : {user_id: datetime.datetime object}
LAST_CHOCOBLAST_TIME = {}

# --- FONCTIONS DE GESTION DES SCORES ---

def load_scores(filename):
    # Charge le fichier JSON ou retourne un dictionnaire vide
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_scores(data, filename):
    # Sauvegarde le dictionnaire dans le fichier JSON
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def perform_backup(archive_filename, base_dir='archives_chocoblast'):
    """Charge les scores actuels et les archive dans un fichier unique dans le répertoire spécifié."""
    
    archive_path = os.path.join(base_dir, archive_filename)

    # 1. Charger les données actuelles
    current_chocoblasteds = load_scores('chocoblasteds.json')
    current_blagueurs = load_scores('blagueurs.json')
    
    # 2. Combiner les données (sauvegarde unique)
    backup_data = {
        "date_archive": datetime.now().isoformat(),
        "chocoblasteds": current_chocoblasteds,
        "blagueurs": current_blagueurs
    }
    
    # 3. Sauvegarder l'archive
    # S'assurer que le répertoire de base existe
    os.makedirs(base_dir, exist_ok=True)
    with open(archive_path, 'w') as f:
        json.dump(backup_data, f, indent=4)
        
    return archive_filename

# --- TÂCHES AUTOMATIQUES ---

@tasks.loop(hours=24)
async def monthly_backup_check():
    """Vérifie si c'est le 1er du mois et effectue la sauvegarde."""
    # Note : Cette vérification se fait toutes les 24h. Si le bot n'est pas actif le 1er, elle se fera au redémarrage.
    if datetime.now().day == 1:
        
        today = datetime.now()
        month_year = today.strftime("%Y-%m")
        archive_name = f"chocoblast_01_{month_year}.json"
        archive_path = os.path.join('archives_chocoblast', archive_name)

        if not os.path.exists(archive_path):
            try:
                # Utilise le répertoire de base par défaut
                archived_file = await bot.loop.run_in_executor(None, perform_backup, archive_name)
                print(f"✅ SAUVEGARDE MENSUELLE RÉUSSIE : {archived_file}")
                
            except Exception as e:
                print(f"❌ ERREUR lors de la sauvegarde mensuelle : {e}")

# --- ÉVÉNEMENTS DU BOT ---

@bot.event
async def on_ready():
    print(f'Bot prêt sous le nom : {bot.user}')
    
    # Création du dossier d'archives et du sous-dossier de reset
    reset_dir = os.path.join('archives_chocoblast', 'reset_score')
    
    # Création des dossiers si nécessaires
    if not os.path.exists('archives_chocoblast'):
        os.makedirs('archives_chocoblast')
        print("Dossier 'archives_chocoblast' créé.")
        
    if not os.path.exists(reset_dir):
        os.makedirs(reset_dir)
        print("Sous-dossier 'archives_chocoblast/reset_score' créé.")
        
    # SYNCHRONISATION GLOBALE 
    print("Tentative de synchronisation globale...")
    try:
        await bot.tree.sync() 
        print("Synchronisation globale terminée. Vérifiez dans 5-10 minutes.")
    except Exception as e:
        print(f"Erreur lors de la synchronisation : {e}")

    # Démarrage de la tâche de sauvegarde
    if not monthly_backup_check.is_running():
        monthly_backup_check.start()
        print("Tâche de vérification de sauvegarde mensuelle démarrée.")

@bot.event
async def on_message(message):
    
    if message.author == bot.user:
        return

    # LOGIQUE DE DÉTECTION AUTOMATIQUE PAR MOT-CLÉS ET SCORING AUTOMATIQUE 
    # --> COMPLÈTEMENT SUPPRIMÉE. 
    # Les scores sont désormais attribués EXCLUSIVEMENT via la commande slash /chocoblaste.

    await bot.process_commands(message)

# --- SLASH COMMAND : LEADERBOARD ---

@bot.tree.command(name="leaderboard", description="Affiche le classement des chocoblastedes ou des blagueurs.") 
@app_commands.describe(category="Choisissez 'chocoblastedes' ou 'blagueurs'")
@app_commands.choices(category=[
    app_commands.Choice(name="Chocoblasté(e)s", value="chocoblastedes"),
    app_commands.Choice(name="Blagueurs du chocoblast", value="blagueurs"), 
])
async def leaderboard_command_slash(interaction: discord.Interaction, category: app_commands.Choice[str]):
    
    selected_category = category.value 
    emoji_icon = "" 

    if selected_category == 'chocoblastedes':
        filename = 'chocoblasteds.json'
        title = "🥐 CLASSEMENT DES CHOCOBLASTÉ(E)S 🥐"
        emoji_icon = "🥐" 
    elif selected_category == 'blagueurs': 
        filename = 'blagueurs.json'
        title = "🏆 CLASSEMENT DES BLAGUEURS DU CHOCOBLAST 🏆"
        emoji_icon = "🏆" 
    else:
        # Ne devrait pas arriver avec app_commands.choices
        return await interaction.response.send_message("Catégorie non valide. (Erreur interne)", ephemeral=True) 

    scores = load_scores(filename)
    # Tri par le nombre de points (item[1]) de manière décroissante
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    leaderboard_text = f"**{title}**\n\n"
    
    if not sorted_scores:
        leaderboard_text += "Le classement est vide pour le moment."
    else:
        for rank, (user_id, count) in enumerate(sorted_scores[:10], 1):
            try:
                # Utilisation de fetch_user pour obtenir l'utilisateur même s'il n'est pas en cache
                user = await interaction.client.fetch_user(int(user_id)) 
                username = user.display_name if user else f"Utilisateur ID {user_id}"
            except discord.NotFound:
                username = f"Utilisateur ID {user_id} (Introuvable)"
            except Exception:
                username = f"Utilisateur ID {user_id} (Erreur)"
            
            # Affichage du classement
            leaderboard_text += f"**{emoji_icon} {rank}.** {username} : **{count}**\n"

    await interaction.response.send_message(leaderboard_text)


# --- SLASH COMMAND : CHOCOBLASTE (NOUVELLE COMMANDE) ---

@bot.tree.command(name="chocoblaste", description="Déclare un chocoblast sur un ou plusieurs utilisateurs.") 
@app_commands.describe(
    blagueur1="Le premier utilisateur à créditer en tant que blagueur.",
    blagueur2="Le deuxième utilisateur (optionnel).",
    blagueur3="Le troisième utilisateur (optionnel)."
)
async def chocoblaste_command(
    interaction: discord.Interaction, 
    blagueur1: discord.User, 
    blagueur2: discord.User = None, # Paramètre optionnel
    blagueur3: discord.User = None  # Paramètre optionnel
):
    global LAST_CHOCOBLAST_TIME 
    user_id = str(interaction.user.id)
    chocoblasted = interaction.user
    
    # 1. Gestion du Cooldown (identique à on_message)
    cooldown_duration_s = 180 # 3 minutes pour la production
    
    if user_id in LAST_CHOCOBLAST_TIME:
        time_since_last_chocoblast = datetime.now() - LAST_CHOCOBLAST_TIME[user_id]
        
        if time_since_last_chocoblast.total_seconds() < cooldown_duration_s:
            remaining_time = cooldown_duration_s - time_since_last_chocoblast.total_seconds()
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            
            return await interaction.response.send_message(
                f"🛑 **CALMEZ-VOUS !** **{chocoblasted.display_name}** est sous cooldown de chocoblast (commande).\n"
                f"Prochain chocoblast possible dans **{minutes}m {seconds}s**.",
                ephemeral=True 
            )
            
    # 2. Création de la liste des blagueurs
    mentions = [blagueur1, blagueur2, blagueur3]
    # Filtre: enlève les None (optionnels non utilisés) et assure qu'on ne mentionne pas l'auteur
    blagueurs = [user for user in mentions if user is not None and user.id != chocoblasted.id]

    if not blagueurs:
        return await interaction.response.send_message(
            f"❌ Vous devez mentionner au moins un utilisateur différent de vous-même à créditer en tant que blagueur !",
            ephemeral=True
        )

    # 3. Traitement des scores
    
    # Démarrer le traitement
    await interaction.response.defer(thinking=True)
    
    # Mise à jour du temps (démarrage du cooldown)
    LAST_CHOCOBLAST_TIME[user_id] = datetime.now()

    # A. Mise à jour du score du Chocoblasté (+1)
    chocoblasteds = load_scores('chocoblasteds.json')
    chocoblasteds[user_id] = chocoblasteds.get(user_id, 0) + 1
    save_scores(chocoblasteds, 'chocoblasteds.json')

    # B. GESTION DES BLAGUEURS 
    blagueurs_scores = load_scores('blagueurs.json')
    blagueur_names = []
    
    for blagueur in blagueurs:
        blagueur_id = str(blagueur.id)
        blagueurs_scores[blagueur_id] = blagueurs_scores.get(blagueur_id, 0) + 1 
        blagueur_names.append(f"**{blagueur.display_name}**")
        
    save_scores(blagueurs_scores, 'blagueurs.json')
    blagueur_list = ", ".join(blagueur_names)

    # 4. Message de confirmation
    status_message = f"**{chocoblasted.display_name}** a été chocoblasté(e) via la commande /chocoblaste !!!!\n**Blagueur du chocoblast(s) :** {blagueur_list}."

    await interaction.followup.send(
        f"🚨 **CHOCOBLAST DÉTECTÉ !** 🚨\n"
        f"{status_message}\n"
        f"🥐 Son score est de **{chocoblasteds[user_id]}** chocoblasts subis. 🥐"
    )

# --- SLASH COMMANDS ADMIN ---

# 1. SAUVEGARDE MANUELLE
@bot.tree.command(name="sauvegarde", description="Déclenche une sauvegarde manuelle des scores.") 
@app_commands.checks.has_role(ADMIN_ROLE_ID) 
async def manual_backup_command(interaction: discord.Interaction):
    
    timestamp = datetime.now().strftime("%d_%m_%Y")
    archive_name = f"chocoblast_{timestamp}.json"
    
    await interaction.response.defer(thinking=True, ephemeral=True) 

    try:
        # Utilise le répertoire de base par défaut (archives_chocoblast)
        archived_file = await bot.loop.run_in_executor(None, perform_backup, archive_name)
        
        await interaction.followup.send(
            f"✅ **SAUVEGARDE MANUELLE RÉUSSIE !**\n"
            f"Fichier créé dans `/archives_chocoblast` : **{archived_file}**"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la sauvegarde : {e}")

# 2. RÉINITIALISATION DES SCORES
@bot.tree.command(name="reset_scores", description="Sauvegarde les scores actuels puis les met à zéro.") 
@app_commands.checks.has_role(ADMIN_ROLE_ID) 
async def reset_scores_command(interaction: discord.Interaction):
    
    # Étape 1 : Sauvegarde des scores avant réinitialisation dans le sous-dossier dédié
    timestamp = datetime.now().strftime("%Y_%m_%d")
    archive_name = f"sauv_mise_a_zero_{timestamp}.json"
    reset_dir = os.path.join('archives_chocoblast', 'reset_score') # Répertoire cible
    
    await interaction.response.defer(thinking=True, ephemeral=True) 

    try:
        # Passe le nom de fichier ET le sous-dossier à la fonction
        archived_file = await bot.loop.run_in_executor(None, perform_backup, archive_name, reset_dir)
        
        # Étape 2 : Réinitialisation des scores
        save_scores({}, 'chocoblasteds.json')
        save_scores({}, 'blagueurs.json')

        await interaction.followup.send(
            f"✅ **RÉINITIALISATION RÉUSSIE !**\n"
            f"Les classements chocoblasté(e)s et Blagueur du chocoblast ont été mis à zéro.\n"
            f"Sauvegarde avant reset effectuée dans `reset_score/` sous le nom : **{archived_file}**"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la réinitialisation : {e}")


# 3. RESTAURATION DE LA DERNIÈRE ARCHIVE
@bot.tree.command(name="restore_last", description="Restaure les scores avec les données de la dernière archive.") 
@app_commands.checks.has_role(ADMIN_ROLE_ID) 
async def restore_last_command(interaction: discord.Interaction):
    
    await interaction.response.defer(thinking=True, ephemeral=True) 

    # Cherche tous les fichiers JSON dans le dossier principal ET le sous-dossier de reset
    list_of_files = glob.glob('archives_chocoblast/*.json')
    list_of_files.extend(glob.glob('archives_chocoblast/reset_score/*.json'))
    
    if not list_of_files:
        return await interaction.followup.send("❌ **AUCUNE ARCHIVE TROUVÉE** dans les dossiers d'archives.", ephemeral=True)

    # Trouve le fichier le plus récent (en fonction du timestamp de modification)
    latest_file = max(list_of_files, key=os.path.getctime)
    
    try:
        with open(latest_file, 'r') as f:
            archive_data = json.load(f)

        if 'chocoblasteds' in archive_data and 'blagueurs' in archive_data:
            save_scores(archive_data['chocoblasteds'], 'chocoblasteds.json')
            save_scores(archive_data['blagueurs'], 'blagueurs.json')

            file_name = os.path.basename(latest_file)
            await interaction.followup.send(
                f"✅ **RESTAURATION RÉUSSIE !**\n"
                f"Les scores ont été restaurés à partir de l'archive : **{file_name}**."
            )
        else:
            await interaction.followup.send("❌ Erreur : La dernière archive est corrompue ou a un format invalide.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la restauration : {e}", ephemeral=True)


# 4. MODIFICATION MANUELLE (+/- POINTS)
@bot.tree.command(name="add_score", description="Ajoute un point au score d'un utilisateur (chocoblasté(e)s ou Blagueur du chocoblast).") 
@app_commands.checks.has_role(ADMIN_ROLE_ID) 
@app_commands.describe(
    utilisateur="L'utilisateur à créditer.",
    type_score="La catégorie (chocoblasté(e)s ou Blagueur du chocoblast).",
    points="Nombre de points à ajouter (par défaut: 1)"
)
@app_commands.choices(
    type_score=[
        app_commands.Choice(name="Chocoblasté(e)s", value="chocoblasteds"),
        app_commands.Choice(name="Blagueur du chocoblast", value="blagueurs"),
    ]
)
async def add_score_command(
    interaction: discord.Interaction, 
    utilisateur: discord.User, 
    type_score: app_commands.Choice[str], 
    points: app_commands.Range[int, 1, 10] = 1 
):
    
    filename = type_score.value + '.json'
    scores = load_scores(filename)
    user_id = str(utilisateur.id)
    
    current_score = scores.get(user_id, 0)
    new_score = current_score + points

    scores[user_id] = new_score
    save_scores(scores, filename)

    await interaction.response.send_message(
        f"✅ Succès ! **{points}** point(s) **ajouté(s)** au classement **{type_score.name}** de **{utilisateur.display_name}**.\n"
        f"Nouveau score : **{new_score}**."
    )


@bot.tree.command(name="remove_score", description="Enlève un point au score d'un utilisateur (chocoblasté(e)s ou Blagueur du chocoblast).") 
@app_commands.checks.has_role(ADMIN_ROLE_ID) 
@app_commands.describe(
    utilisateur="L'utilisateur à pénaliser.",
    type_score="La catégorie (chocoblasté(e)s ou Blagueur du chocoblast).",
    points="Nombre de points à enlever (par défaut: 1)"
)
@app_commands.choices(
    type_score=[
        app_commands.Choice(name="Chocoblasté(e)s", value="chocoblasteds"),
        app_commands.Choice(name="Blagueur du chocoblast", value="blagueurs"),
    ]
)
async def remove_score_command(
    interaction: discord.Interaction, 
    utilisateur: discord.User, 
    type_score: app_commands.Choice[str], 
    points: app_commands.Range[int, 1, 10] = 1
):
    
    filename = type_score.value + '.json'
    scores = load_scores(filename)
    user_id = str(utilisateur.id)
    
    current_score = scores.get(user_id, 0)

    # Assure que le score ne passe pas sous zéro
    new_score = max(0, current_score - points) 

    scores[user_id] = new_score
    save_scores(scores, filename)

    await interaction.response.send_message(
        f"✅ Succès ! **{points}** point(s) **retiré(s)** au classement **{type_score.name}** de **{utilisateur.display_name}**.\n"
        f"Nouveau score : **{new_score}**."
    )

# GESTION DES ERREURS POUR TOUTES LES COMMANDES ADMIN

@add_score_command.error
@remove_score_command.error
@manual_backup_command.error
@reset_scores_command.error
@restore_last_command.error
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            "🛑 Vous n'avez pas le rôle requis pour utiliser cette commande.", 
            ephemeral=True
        )
    else:
        # En cas d'autre erreur (ex: MissingPermissions, etc.)
        print(f"Erreur d'exécution de commande admin : {error}")
        await interaction.response.send_message(
             f"❌ Une erreur est survenue lors de l'exécution : {type(error).__name__}", 
             ephemeral=True
        )

# Démarrer le bot
# Assurez-vous d'avoir bien défini TOKEN dans votre fichier .env
bot.run(os.getenv('TOKEN'))