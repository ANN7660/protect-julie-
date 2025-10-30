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
    "LOGS_CHANNEL_ID": None, 
    # IDs pour le système de tickets
    "TICKET_CATEGORY_ID": None, # Catégorie où les tickets seront créés
    # 🆕 ID pour le boost
    "BOOST_CHANNEL_ID": None, # Salon où envoyer le message de boost
}

# Nouvelle configuration pour les rôles
CONFIG_ROLES = {
    "SUPPORT_ROLE_ID": None, # Rôle des modérateurs/supports
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

# Fonction utilitaire pour récupérer un rôle par son ID
def get_role_by_config(key):
    role_id = CONFIG_ROLES.get(key)
    if role_id and bot.guilds:
        # On utilise le premier serveur disponible pour chercher le rôle
        return discord.utils.get(bot.guilds[0].roles, id=role_id)
    return None

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

# ===== ✅ VUE ET LOGIQUE DU TICKET (Bouton) (Aucun changement) =====

class TicketCreateView(discord.ui.View):
    """Vue contenant le bouton pour ouvrir un ticket."""
    def __init__(self, bot_instance):
        super().__init__(timeout=None) # Timeout=None rend le bouton permanent
        self.bot = bot_instance
        
    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.blurple, custom_id="ticket_button_create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        
        # 1. Vérifications
        category_id = CONFIG_CHANNELS.get("TICKET_CATEGORY_ID")
        support_role = get_role_by_config("SUPPORT_ROLE_ID")
        
        if not category_id or not support_role:
            await interaction.response.send_message(
                "❌ **Erreur Configuration** : La catégorie ou le rôle de support n'est pas configuré. Demandez à un administrateur.", 
                ephemeral=True
            )
            return

        category = self.bot.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ **Erreur Configuration** : La catégorie de ticket est invalide. Demandez à un administrateur.", 
                ephemeral=True
            )
            return

        # Vérifie si l'utilisateur a déjà un ticket ouvert (canaux nommés "ticket-...")
        for channel in category.text_channels:
            if channel.topic and str(user.id) in channel.topic: 
                await interaction.response.send_message(
                    f"❌ Vous avez déjà un ticket ouvert : {channel.mention}", 
                    ephemeral=True
                )
                return
        
        # 2. Définition des Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), 
            user: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True, 
                attach_files=True
            ), 
            support_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True, 
                manage_channels=True 
            ), 
            guild.me: discord.PermissionOverwrite(view_channel=True) 
        }
        
        # 3. Création du Canal
        channel_name = f"ticket-{user.name.lower().replace(' ', '-').replace('.', '')}"[:100]
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name, 
                category=category, 
                overwrites=overwrites,
                topic=f"Ticket ouvert par {user.name} ({user.id}) le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
            )

            # 4. Message de Bienvenue dans le Ticket
            embed = discord.Embed(
                title="🎫 Ticket Ouvert",
                description=f"Bienvenue {user.mention} ! L'équipe de support a été notifiée et vous répondra dès que possible.\n\nDécrivez votre problème en détail ci-dessous.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Rôle Support", value=support_role.mention)
            
            await ticket_channel.send(f"{user.mention} {support_role.mention}", embed=embed, view=TicketCloseView())
            await interaction.response.send_message(f"✅ Votre ticket est ouvert dans {ticket_channel.mention} !", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas les permissions nécessaires pour créer des canaux (Vérifiez les rôles/catégories).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur inattendue : {e}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    """Vue contenant le bouton pour fermer et supprimer le ticket."""
    def __init__(self):
        super().__init__(timeout=None) 
        
    @discord.ui.button(label="🔒 Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="ticket_button_close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        support_role = get_role_by_config("SUPPORT_ROLE_ID")
        is_staff = support_role and support_role in interaction.user.roles
        
        if not interaction.channel.name.startswith("ticket-"):
             await interaction.response.send_message("❌ Ce n'est pas un canal de ticket.", ephemeral=True)
             return
        
        is_ticket_owner = False
        if interaction.channel.topic:
            user_id_in_topic = interaction.channel.topic.split('(')[-1].split(')')[0] if interaction.channel.topic else None
            is_ticket_owner = str(interaction.user.id) == user_id_in_topic
            
        if not is_staff and not interaction.user.top_role.permissions.administrator and not is_ticket_owner:
            await interaction.response.send_message("❌ Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)
            return

        await interaction.response.send_message(f"🔒 Ticket fermé par {interaction.user.mention}. Suppression dans 5 secondes...")
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user.display_name}")
        except discord.Forbidden:
            logs_channel = get_channel_by_config("LOGS_CHANNEL_ID")
            if logs_channel:
                 await logs_channel.send(f"❌ Le bot n'a pas pu supprimer le canal de ticket {interaction.channel.name} par manque de permissions.")
        except Exception as e:
            print(f"Erreur lors de la suppression du ticket: {e}")


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

    # Ajout des vues persistantes pour les boutons de tickets
    bot.add_view(TicketCreateView(bot))
    bot.add_view(TicketCloseView())
    
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


# --- ÉVÉNEMENTS (BIENVENUE / DÉPART) ---

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
    
    # Message simple (MIS À JOUR)
    if simple_channel:
        # ✅ MODIFIÉ : Ajout de l'emoji animé au début des deux lignes, y compris le compte de membres
        member_count = len(member.guild.members)
        message = (
            f"<a:caarrow:1433143710094196997> **Bienvenue** {member.mention} sur Hoshikuzu ! Nous sommes ravis de t'accueillir ! 🎉\n"
            f"<a:caarrow:1433143710094196997> Nous sommes désormais **{member_count}** membres sur Hoshikuzu ! ✨"
        )
        await simple_channel.send(message)
    
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


# ===== 🆕 ÉVÉNEMENT DE BOOST (Nouveau) (Aucun changement) =====

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Détecte si un membre commence à booster le serveur."""
    
    # 1. Vérifie si le changement concerne le statut de boost (booster rôle)
    is_boosting_before = before.premium_since is not None
    is_boosting_after = after.premium_since is not None
    
    # Si le membre n'était pas booster et l'est devenu
    if not is_boosting_before and is_boosting_after:
        boost_channel = get_channel_by_config("BOOST_CHANNEL_ID")
        
        if boost_channel:
            # Récupère le nombre actuel de boosts pour le serveur
            boost_count = after.guild.premium_subscription_count
            
            embed = discord.Embed(
                title="✨ Nouveau Boost de Serveur !",
                description=f"🎉 Merci infiniment à {after.mention} pour le boost !\nVotre soutien aide le serveur à atteindre de nouveaux avantages.\n\nLe serveur a maintenant **{boost_count}** boosts au total !",
                color=discord.Color.from_rgb(244, 155, 237), # Couleur Discord Boost
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"{after.display_name} est un Nitro Booster !")
            
            try:
                await boost_channel.send(f"**Merci** {after.mention} pour le boost ! 💜", embed=embed)
            except discord.Forbidden:
                print(f"❌ Erreur: Le bot ne peut pas envoyer le message de boost dans le salon configuré.")


# ===== ÉVÉNEMENTS DE LOGS (Journalisation) (Aucun changement) =====

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


# --- COMMANDES DE CONFIGURATION (Admin) (Aucun changement) ---

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

# 🆕 Commande de configuration du boost
@bot.command(name='setboostchannel')
@commands.has_permissions(administrator=True)
async def set_boost_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour les messages de remerciement de boost."""
    CONFIG_CHANNELS["BOOST_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le salon des **Remerciements de Boost** a été configuré sur {channel.mention}.", color=discord.Color.green())
    await ctx.send(embed=embed)


# Commandes de configuration des tickets
@bot.command(name='setticketcategory')
@commands.has_permissions(administrator=True)
async def set_ticket_category(ctx: commands.Context, category: discord.CategoryChannel):
    """Configure la catégorie où les tickets seront créés."""
    CONFIG_CHANNELS["TICKET_CATEGORY_ID"] = category.id
    embed = discord.Embed(description=f"✅ La **Catégorie de Tickets** a été configurée sur **{category.name}**.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='setticketrole')
@commands.has_permissions(administrator=True)
async def set_ticket_role(ctx: commands.Context, role: discord.Role):
    """Configure le rôle qui aura accès aux tickets."""
    CONFIG_ROLES["SUPPORT_ROLE_ID"] = role.id
    embed = discord.Embed(description=f"✅ Le **Rôle de Support/Staff** a été configuré sur {role.mention}.", color=discord.Color.green())
    await ctx.send(embed=embed)


@bot.command(name='sendticketpanel')
@commands.has_permissions(administrator=True)
async def send_ticket_panel(ctx: commands.Context, channel: discord.TextChannel = None):
    """Envoie le message avec le bouton pour ouvrir un ticket."""
    
    if not CONFIG_CHANNELS.get("TICKET_CATEGORY_ID") or not CONFIG_ROLES.get("SUPPORT_ROLE_ID"):
          return await ctx.send("❌ Vous devez d'abord configurer la catégorie et le rôle de support avec `+setticketcategory` et `+setticketrole`.")
          
    target_channel = channel or ctx.channel
    
    embed = discord.Embed(
        title="Centre d'Aide et Support 📩",
        description="Cliquez sur le bouton ci-dessous pour ouvrir un **ticket privé** avec l'équipe de modération/support.\n\n*Veuillez décrire votre problème en détail.*",
        color=discord.Color.dark_purple()
    )
    
    await target_channel.send(embed=embed, view=TicketCreateView(bot))
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Le panneau de tickets a été envoyé dans {target_channel.mention}", delete_after=5)


# Commandes de bienvenue/départ
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
    """Affiche la configuration des salons (Mise à jour pour les tickets et boost)."""
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    leave_channel = get_channel_by_config("LEAVE_CHANNEL_ID")
    logs_channel = get_channel_by_config("LOGS_CHANNEL_ID") 
    ticket_category = get_channel_by_config("TICKET_CATEGORY_ID") 
    support_role = get_role_by_config("SUPPORT_ROLE_ID") 
    boost_channel = get_channel_by_config("BOOST_CHANNEL_ID")

    embed = discord.Embed(title="⚙️ Configuration du Bot", color=discord.Color.blue(), timestamp=datetime.now())

    embed.add_field(name="--- Bienvenue/Départ/Boost ---", value=" ", inline=False)
    embed.add_field(name="🏠 Bienvenue (Embed)", value=embed_channel.mention if embed_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="💬 Bienvenue (Simple)", value=simple_channel.mention if simple_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="👋 Salons des départs", value=leave_channel.mention if leave_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="✨ Salon de Boost", value=boost_channel.mention if boost_channel else "❌ Non configuré", inline=False)
    
    embed.add_field(name="--- Tickets et Logs ---", value=" ", inline=False) 
    embed.add_field(name="📝 Salon de Logs", value=logs_channel.mention if logs_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="🎫 Catégorie Ticket", value=ticket_category.mention if ticket_category else "❌ Non configuré", inline=False)
    embed.add_field(name="👮 Rôle Support", value=support_role.mention if support_role else "❌ Non configuré", inline=False)


    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)


# --- MODÉRATION (Commandes complètes) (Aucun changement) ---

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

# Commandes de gestion du ticket
@bot.command(name='close', aliases=['fermer'])
@commands.has_permissions(manage_channels=True)
async def close_ticket_command(ctx: commands.Context):
    """Ferme le ticket actuel (doit être utilisé dans un canal de ticket)"""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
    
    await ctx.send(f"🔒 Ticket fermé par {ctx.author.mention}. Suppression du canal dans 5 secondes...")
    await asyncio.sleep(5)
    await ctx.channel.delete(reason=f"Ticket fermé par commande par {ctx.author.display_name}")

@bot.command(name='add')
@commands.has_permissions(manage_channels=True)
async def add_member_to_ticket(ctx: commands.Context, member: discord.Member):
    """Ajoute un membre au ticket actuel."""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    await ctx.send(f"✅ {member.mention} a été ajouté au ticket.")


# --- UTILITAIRES (Commandes complètes) ---

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

@bot.command(name='serverinfo', aliases=['si'])
async def server_info(ctx: commands.Context):
    """Affiche les informations générales et statistiques du serveur."""
    guild = ctx.guild
    
    # Calcul des totaux
    member_count = guild.member_count
    online_members = len([m for m in guild.members if m.status != discord.Status.offline])
    bots_count = len([m for m in guild.members if m.bot])
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    
    # Niveaux de boost
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count
    
    # Création de l'embed
    embed = discord.Embed(
        title=f"🏛️ Informations sur le serveur : {guild.name}",
        color=discord.Color.from_rgb(255, 165, 0), # Orange
        timestamp=datetime.now()
    )

    # Propriétaire et date de création
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 Propriétaire", value=guild.owner.mention, inline=True)
    embed.add_field(name="🆔 ID du Serveur", value=guild.id, inline=True)
    embed.add_field(name="🗓️ Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    
    # Statistiques des membres
    embed.add_field(
        name="👥 Membres", 
        value=f"**Total :** {member_count}\n**En ligne :** {online_members}\n**Bots :** {bots_count}", 
        inline=True
    )

    # Statistiques des salons
    embed.add_field(
        name="💬 Salons", 
        value=f"**Textuels :** {text_channels}\n**Vocaux :** {voice_channels}\n**Catégories :** {len(guild.categories)}", 
        inline=True
    )
    
    # Boosts
    embed.add_field(
        name="✨ Boosts Nitro", 
        value=f"**Niveau :** {boost_level}\n**Total :** {boost_count} boosts", 
        inline=True
    )

    # Rôles
    roles_display = len(guild.roles) - 1 # Ne compte pas @everyone
    embed.add_field(name="🔖 Rôles", value=f"**Total :** {roles_display} rôles", inline=True)
    
    # Ajout du pied de page
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    
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
        value="`+config` - Affiche la configuration actuelle\n`+setlogs #salon` - Salon pour la **journalisation**\n`+setboostchannel #salon` - Salon des remerciements de boost ✨\n`+setticketcategory #catégorie` - Catégorie des tickets\n`+setticketrole @rôle` - Rôle support pour les tickets\n`+sendticketpanel #salon` - Envoie le bouton de ticket\n`+welcomeembed #salon` - Salon de bienvenue (embed)\n`+welcomesimple #salon` - Salon de bienvenue (simple)\n`+leavechat #salon` - Salon des départs",
        inline=False
    )

    embed.add_field(
        name="🛡️ Modération (Staff)",
        value="`+ban @membre [raison]`\n`+kick @membre [raison]`\n`+mute @membre [durée en min] [raison]`\n`+unmute @membre`\n`+clear [nombre]` - Supprime des messages\n`+close` - Ferme le ticket actuel\n`+add @membre` - Ajoute un membre au ticket",
        inline=False
    )

    embed.add_field(
        name="🔧 Utilitaires",
        value="`+ping`\n`+avatar [@membre]`\n`+userinfo [@membre]`\n`+serverinfo` - **Infos et stats du serveur 📊**", # ✅ NOUVEAU
        inline=False
    )

    embed.set_footer(text=f"Demandé par {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)


# --- DÉMARRAGE DU BOT ---

# Si vous utilisez un système de "keep-alive" comme Flask
# keep_alive() 

# Remplacez "VOTRE_TOKEN_DISCORD" par la variable d'environnement ou le token de votre bot
if __name__ == "__main__":
    if 'DISCORD_TOKEN' not in os.environ:
        print("❌ ERREUR : La variable d'environnement 'DISCORD_TOKEN' n'est pas définie.")
        print("Veuillez définir votre token Discord pour démarrer le bot.")
    else:
        keep_alive() # Démarre le serveur web
        try:
            bot.run(os.environ['DISCORD_TOKEN'])
        except discord.errors.LoginFailure:
            print("❌ Échec de la connexion : Le token est invalide. Veuillez vérifier la variable DISCORD_TOKEN.")
        except Exception as e:
            print(f"❌ Erreur inattendue au démarrage : {e}")
