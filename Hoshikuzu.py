import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import os

# ===== ✅ MAINTENANCE EN LIGNE (FLASK / KEEP-ALIVE) =====
# Nécessaire pour les plateformes d'hébergement comme Render ou Heroku
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    """Route pour vérifier que le service Flask est actif."""
    return "✅ Le bot Hoshikuzu est en ligne et prêt à servir !"

def run():
    """Démarre le serveur Flask."""
    # Utilise la variable d'environnement PORT, par défaut 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Lance le serveur Flask dans un thread séparé."""
    thread = Thread(target=run)
    thread.start()

# ===== CONFIGURATION GLOBALE =====

# Utilisation d'un dictionnaire pour une meilleure gestion des IDs
CONFIG_CHANNELS = {
    # Anciens IDs de l'énoncé original
    "WELCOME_CHANNEL_ID": 1433096078311293032,
    "LEAVE_CHANNEL_ID": 1433096160800804894,
    "WELCOME_EMBED_CHANNEL_ID": None, 
    "WELCOME_SIMPLE_CHANNEL_ID": 1433120551865417738,
    "LOGS_CHANNEL_ID": None,  # 🆕 Nouveau : Salon de log pour les événements
}

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True # Indispensable pour les événements de membre et guild.members

bot = commands.Bot(command_prefix='+', intents=intents, help_command=None)

# Fonction utilitaire pour récupérer un salon par son ID
def get_channel_by_config(key):
    return bot.get_channel(CONFIG_CHANNELS.get(key))

# Fonction utilitaire pour envoyer un message aux logs
async def send_to_logs(guild, embed):
    """Envoie l'embed spécifié au salon de logs configuré."""
    logs_channel = get_channel_by_config("LOGS_CHANNEL_ID")
    if logs_channel:
        try:
            await logs_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"❌ Erreur: Le bot ne peut pas envoyer de message dans le salon de logs ({logs_channel.name}).")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi au salon de logs: {e}")


# ===== ÉVÉNEMENTS DU BOT (LIFECYCLE) =====

@bot.event
async def on_ready():
    """Se déclenche lorsque le bot est prêt."""
    print('=' * 60)
    print(f"🤖 Bot connecté: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Serveurs: {len(bot.guilds)}")
    print(f"👥 Utilisateurs globaux: {len(bot.users)}") 
    print('=' * 60)

    # Définit l'activité et le statut
    await bot.change_presence(
        activity=discord.Game(name="Hoshikuzu"),
        status=discord.Status.dnd
    )

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Gestion d'erreur globale pour les commandes."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ **Argument manquant** : Il manque un argument. Vérifie la commande `+help`.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ **Membre introuvable** : Impossible de trouver ce membre.")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ **Rôle introuvable** : Impossible de trouver ce rôle.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ **Salon introuvable** : Impossible de trouver ce salon.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ **Mauvais argument** : Un argument n'est pas au format attendu.")
    elif isinstance(error, commands.MissingPermissions):
        perms_needed = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ **Permissions manquantes** : Tu n'as pas la permission de `{perms_needed}`.")
    elif isinstance(error, commands.BotMissingPermissions):
        perms_needed = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ **Permissions du Bot manquantes** : Le bot a besoin de la permission de `{perms_needed}`.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Cette commande est en **cooldown**. Réessaie dans {error.retry_after:.2f}s.")
    else:
        print(f"Erreur non gérée dans la commande {ctx.command.name}: {error}")
        # await ctx.send("❌ **Erreur inconnue** : Une erreur est survenue lors de l'exécution.")


# ===== ÉVÉNEMENTS (BIENVENUE / DÉPART) =====

@bot.event
async def on_member_join(member: discord.Member):
    """Message de bienvenue élégant avec embed et message simple"""
    
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    
    # Message avec embed
    if embed_channel:
        member_count = len(member.guild.members)
        welcome_embed = discord.Embed(
            title="🌸 Bienvenue sur Hoshikuzu !",
            description=f"Salut {member.mention} ! 👋\nTu es notre **{member_count}ème** membre ! 🎉",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        welcome_embed.set_thumbnail(url=member.display_avatar.url)
        welcome_embed.set_footer(text="Équipe Hoshikuzu", icon_url=member.guild.icon.url if member.guild.icon else None)
        await embed_channel.send(embed=welcome_embed)
    
    # Message simple
    if simple_channel:
        await simple_channel.send(f"Bienvenue {member.mention} sur Hoshikuzu ! 💫")
    
    # MP de bienvenue
    try:
        dm_embed = discord.Embed(
            title="🎉 Bienvenue sur Hoshikuzu !",
            description=f"Salut **{member.display_name}** ! 👋 Nous sommes ravis de t'accueillir !",
            color=discord.Color.green(),
        )
        dm_embed.add_field(name="📝 Pour bien commencer", value="• Lis les règles\n• Amuse-toi bien !", inline=False)
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        pass

@bot.event
async def on_member_remove(member: discord.Member):
    """Message d'au revoir élégant avec embed"""
    leave_channel = get_channel_by_config("LEAVE_CHANNEL_ID")

    if leave_channel:
        member_count = len(member.guild.members)
        leave_embed = discord.Embed(
            title="👋 Au revoir...",
            description=f"**{member.display_name}** vient de quitter **Hoshikuzu**\nNous sommes maintenant **{member_count}** membres.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        leave_embed.set_thumbnail(url=member.display_avatar.url)
        joined_date = member.joined_at.strftime('%d/%m/%Y') if member.joined_at else "Inconnue"
        leave_embed.set_footer(text=f"Membre depuis le {joined_date}", icon_url=member.guild.icon.url if member.guild.icon else None)
        await leave_channel.send(embed=leave_embed)


# ===== 🆕 ÉVÉNEMENTS DE LOGS (Journalisation) =====

@bot.event
async def on_message_delete(message: discord.Message):
    """Log les messages supprimés"""
    if message.author.bot or not message.guild:
        return

    embed = discord.Embed(
        title="🗑️ Message Supprimé",
        color=discord.Color.dark_red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Auteur", value=message.author.mention, inline=True)
    embed.add_field(name="Salon", value=message.channel.mention, inline=True)
    
    content = message.content[:1024] if message.content else "*Contenu vide (Image/Embed/etc)*"
    embed.add_field(name="Contenu", value=f"```\n{content}\n```", inline=False)
    embed.set_footer(text=f"ID: {message.id}")
    
    await send_to_logs(message.guild, embed)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Log les messages modifiés"""
    if before.author.bot or before.content == after.content or not before.guild:
        return

    embed = discord.Embed(
        title="📝 Message Modifié",
        color=discord.Color.dark_teal(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Auteur", value=before.author.mention, inline=True)
    embed.add_field(name="Salon", value=before.channel.mention, inline=True)
    
    embed.add_field(name="Avant", value=f"```\n{before.content[:500]}\n```", inline=False)
    embed.add_field(name="Après", value=f"```\n{after.content[:500]}\n```", inline=False)
    embed.set_footer(text=f"ID: {before.id}")
    
    await send_to_logs(before.guild, embed)

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    """Log les bannissements"""
    embed = discord.Embed(
        title="🔨 Membre Banni",
        description=f"**{user.display_name}** a été banni du serveur.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    # L'API ne donne pas directement la raison ici, on se base sur le log d'audit
    # Pour avoir la raison, il faudrait analyser le log d'audit, mais c'est complexe.
    # On se contente du fait.
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=False)
    
    await send_to_logs(guild, embed)

@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    """Log les débannissements"""
    embed = discord.Embed(
        title="🔓 Membre Débanni",
        description=f"**{user.display_name}** a été débanni du serveur.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=False)
    
    await send_to_logs(guild, embed)


# ===== COMMANDES DE CONFIGURATION (Admin) =====

@bot.command(name='setlogs')
@commands.has_permissions(administrator=True)
async def set_logs_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon de logs pour la journalisation"""
    CONFIG_CHANNELS["LOGS_CHANNEL_ID"] = channel.id

    embed = discord.Embed(
        description=f"✅ Le salon de **Logs** a été configuré sur {channel.mention}. Les messages supprimés/modifiés, bans, etc. y seront envoyés.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='welcomechat')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon de bienvenue (ancien système)"""
    CONFIG_CHANNELS["WELCOME_CHANNEL_ID"] = channel.id
    await ctx.send(f"✅ Les messages de bienvenue (ancien ID) seront envoyés dans {channel.mention}")

@bot.command(name='welcomeembed')
@commands.has_permissions(administrator=True)
async def set_welcome_embed_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour le message de bienvenue avec embed"""
    CONFIG_CHANNELS["WELCOME_EMBED_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le message de bienvenue **avec embed** sera envoyé dans {channel.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='welcomesimple')
@commands.has_permissions(administrator=True)
async def set_welcome_simple_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour le message de bienvenue simple"""
    CONFIG_CHANNELS["WELCOME_SIMPLE_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le message de bienvenue **simple** sera envoyé dans {channel.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='leavechat')
@commands.has_permissions(administrator=True)  
async def set_leave_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon des départs"""
    CONFIG_CHANNELS["LEAVE_CHANNEL_ID"] = channel.id
    await ctx.send(f"✅ Les messages de départ seront envoyés dans {channel.mention}")

@bot.command(name='config')
@commands.has_permissions(administrator=True)
async def show_config(ctx: commands.Context):
    """Affiche la configuration des salons"""
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    leave_channel = get_channel_by_config("LEAVE_CHANNEL_ID")
    logs_channel = get_channel_by_config("LOGS_CHANNEL_ID") # Affichage du nouveau salon

    embed = discord.Embed(title="⚙️ Configuration du Bot", color=discord.Color.blue(), timestamp=datetime.now())

    embed.add_field(name="🏠 Bienvenue (Embed)", value=embed_channel.mention if embed_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="💬 Bienvenue (Simple)", value=simple_channel.mention if simple_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="👋 Salons des départs", value=leave_channel.mention if leave_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="📝 Salon de Logs", value=logs_channel.mention if logs_channel else "❌ Non configuré", inline=False)

    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)

# ===== MODÉRATION (Commandes complètes) =====

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_member(ctx: commands.Context, member: discord.Member, *, raison="Aucune raison fournie"):
    """Bannit un membre du serveur"""
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    
    try:
        await member.ban(reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="🔨 Membre banni", description=f"**{member.display_name}** a été banni", color=discord.Color.red())
        embed.add_field(name="📝 Raison", value=raison)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour bannir ce membre !")

# ... autres commandes de modération (kick, mute, unmute, clear) ...
# Les commandes 'kick', 'mute', 'unmute' et 'clear' ont été laissées du premier code (le plus complet)

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, raison="Aucune raison fournie"):
    """Expulse un membre du serveur"""
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même !")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.kick(reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="👢 Membre expulsé", description=f"**{member.display_name}** a été expulsé", color=discord.Color.orange())
        embed.add_field(name="📝 Raison", value=raison)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour expulser ce membre !")

@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute_member(ctx, member: discord.Member, duration: int = 10, *, raison="Aucune raison fournie"):
    """Timeout un membre (durée en minutes)"""
    if duration > 40320: return await ctx.send("❌ Durée maximale : 40320 minutes (28 jours) !")
    try:
        timeout_duration = timedelta(minutes=duration)
        await member.timeout(timeout_duration, reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="🔇 Membre timeout", description=f"**{member.display_name}** mis en timeout pour {duration} min", color=discord.Color.orange())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour timeout ce membre !")

@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute_member(ctx, member: discord.Member):
    """Retire le timeout d'un membre"""
    if member.timed_out_until is None: return await ctx.send("❌ Ce membre n'est pas en timeout !")
    try:
        await member.timeout(None, reason=f"Démuté par {ctx.author}")
        embed = discord.Embed(title="🔊 Membre démuté", description=f"**{member.display_name}** peut de nouveau parler", color=discord.Color.green())
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")

@bot.command(name='clear', aliases=['purge', 'clean'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    """Supprime un nombre de messages"""
    if amount > 100: return await ctx.send("❌ Maximum 100 messages à la fois !")
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ **{len(deleted) - 1}** messages supprimés !", delete_after=3)
        # Log l'action de clear
        embed = discord.Embed(
            title="🧹 Purge de messages",
            description=f"**{len(deleted) - 1}** messages supprimés par {ctx.author.mention} dans {ctx.channel.mention}.",
            color=discord.Color.blue()
        )
        await send_to_logs(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour supprimer des messages !")


# ===== UTILITAIRES (Commandes complètes) =====

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong ! Latence : **{latency}ms**")

@bot.command(name='avatar')
async def show_avatar(ctx, membre: discord.Member = None):
    membre = membre or ctx.author
    embed = discord.Embed(title=f"📸 Avatar de {membre.display_name}", color=discord.Color.blurple())
    embed.set_image(url=membre.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='userinfo', aliases=['ui'])
async def user_info(ctx, membre: discord.Member = None):
    membre = membre or ctx.author
    embed = discord.Embed(
        title=f"👤 Informations sur {membre.display_name}",
        color=membre.color if membre.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="ID", value=membre.id, inline=True)
    embed.add_field(name="Compte créé", value=membre.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="A rejoint", value=membre.joined_at.strftime("%d/%m/%Y"), inline=True)
    
    roles = [role.mention for role in membre.roles[1:]][:10]
    embed.add_field(name=f"Rôles ({len(membre.roles) - 1})", value=" ".join(roles) if roles else "Aucun", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='help', aliases=['aide', 'h'])
async def help_command(ctx: commands.Context):
    """Affiche toutes les commandes"""
    embed = discord.Embed(
        title="📚 Commandes du Bot Hoshikuzu",
        description="Voici toutes les commandes disponibles. Le préfixe est `+`",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="⚙️ Configuration (Admin)",
        value="`+setlogs #salon` - Salon pour la **journalisation** 🆕\n`+welcomeembed #salon` - Salon pour message **embed**\n`+welcomesimple #salon` - Salon pour message **simple**\n`+leavechat #salon` - Salon des départs\n`+config` - Voir la configuration des salons",
        inline=False
    )

    embed.add_field(
        name="🛡️ Modération",
        value="`+ban @membre [raison]`\n`+kick @membre [raison]`\n`+mute @membre [minutes] [raison]`\n`+unmute @membre`\n`+clear [nombre]`",
        inline=False
    )

    embed.add_field(
        name="🔧 Utilitaires",
        value="`+ping`\n`+avatar [@membre]`\n`+userinfo [@membre]`",
        inline=False
    )

    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)

# ===== DÉMARRAGE DU BOT =====

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')

    if not TOKEN:
        print("❌ ERREUR : Token Discord non trouvé !")
        print("📝 Assure-toi que la variable d'environnement 'DISCORD_TOKEN' est correctement définie.")
        exit(1)

    # 1. Lance le serveur Flask dans un thread pour maintenir le bot actif
    keep_alive()  

    # 2. Démarre le bot Discord
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ ERREUR : Le token est invalide. Vérifie sa valeur.")
        exit(1)
    except Exception as e:
        print(f"❌ Erreur de démarrage inattendue : {e}")
        exit(1)
