import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import os

# ✅ Ajout pour Render : mini serveur web pour éviter la coupure
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "✅ Le bot Hoshikuzu est en ligne et prêt à servir !"

def run():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    thread = Thread(target=run)
    thread.start()

# ===== CONFIGURATION =====

WELCOME_CHANNEL_ID = 1433096078311293032
LEAVE_CHANNEL_ID = 1433096160800804894
WELCOME_EMBED_CHANNEL_ID = None
WELCOME_SIMPLE_CHANNEL_ID = 1433120551865417738

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='+', intents=intents, help_command=None)

# ===== ÉVÉNEMENTS =====

@bot.event
async def on_ready():
    print('=' * 60)
    print(f"🤖 Bot connecté: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Serveurs: {len(bot.guilds)}")
    print(f"👥 Utilisateurs: {len(set(bot.get_all_members()))}")
    print('=' * 60)

    await bot.change_presence(
        activity=discord.Game(name="Hoshikuzu"),
        status=discord.Status.dnd
    )

@bot.event
async def on_member_join(member):
    """Message de bienvenue avec embed et MP"""
    if WELCOME_SIMPLE_CHANNEL_ID:
        simple_channel = bot.get_channel(WELCOME_SIMPLE_CHANNEL_ID)
        if simple_channel:
            await simple_channel.send(f"Bienvenue {member.mention} sur Hoshikuzu ! 💫")

    try:
        dm_embed = discord.Embed(
            title="🎉 Bienvenue sur Hoshikuzu !",
            description=f"Salut **{member.display_name}** ! 👋\n\nNous sommes ravis de t'accueillir dans notre communauté ! 🔥",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        dm_embed.add_field(
            name="📝 Pour bien commencer",
            value="• Présente-toi dans le salon approprié\n• Explore les différents salons\n• Respecte les règles et les membres\n• Amuse-toi bien !",
            inline=False
        )
        dm_embed.set_footer(text="Équipe Hoshikuzu")
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        pass

@bot.event
async def on_member_remove(member):
    """Message d'au revoir élégant avec embed"""
    leave_channel = bot.get_channel(LEAVE_CHANNEL_ID)
    if leave_channel:
        member_count = len(member.guild.members)
        leave_embed = discord.Embed(
            title="👋 Au revoir...",
            description=f"**{member.display_name}** vient de quitter **Hoshikuzu**.\nNous sommes maintenant **{member_count}** membres.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        leave_embed.set_thumbnail(url=member.display_avatar.url)
        leave_embed.set_footer(
            text=f"Membre depuis le {member.joined_at.strftime('%d/%m/%Y')}" if member.joined_at else "Départ d'un membre",
        )
        await leave_channel.send(embed=leave_embed)

# ===== COMMANDES DE CONFIGURATION =====

@bot.command(name='welcomechat')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    global WELCOME_CHANNEL_ID
    WELCOME_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Les messages de bienvenue seront envoyés dans {channel.mention}")

@bot.command(name='welcomesimple')
@commands.has_permissions(administrator=True)
async def set_welcome_simple_channel(ctx, channel: discord.TextChannel):
    global WELCOME_SIMPLE_CHANNEL_ID
    WELCOME_SIMPLE_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Le message de bienvenue simple sera envoyé dans {channel.mention}")

@bot.command(name='leavechat')
@commands.has_permissions(administrator=True)
async def set_leave_channel(ctx, channel: discord.TextChannel):
    global LEAVE_CHANNEL_ID
    LEAVE_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Les messages de départ seront envoyés dans {channel.mention}")

# ===== MODÉRATION =====

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_member(ctx, member: discord.Member, *, raison="Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas te bannir toi-même !")
    try:
        await member.ban(reason=f"{raison} (par {ctx.author})")
        await ctx.send(f"🔨 {member.display_name} a été banni ! Raison : {raison}")
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, raison="Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même !")
    try:
        await member.kick(reason=f"{raison} (par {ctx.author})")
        await ctx.send(f"👢 {member.display_name} a été expulsé ! Raison : {raison}")
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")

@bot.command(name='clear', aliases=['purge'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 {len(deleted) - 1} messages supprimés.", delete_after=3)

# ===== COMMANDES UTILES =====

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong ! Latence : {latency}ms")

@bot.command(name='avatar')
async def avatar(ctx, membre: discord.Member = None):
    membre = membre or ctx.author
    embed = discord.Embed(title=f"📸 Avatar de {membre.display_name}", color=discord.Color.blurple())
    embed.set_image(url=membre.display_avatar.url)
    await ctx.send(embed=embed)

# ===== DÉMARRAGE DU BOT =====

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')

    if not TOKEN:
        print("❌ ERREUR : Token Discord non trouvé !")
        print("📝 Ajoute DISCORD_TOKEN dans les variables d'environnement Render")
        exit(1)

    keep_alive()  # ✅ Pour Render (évite l’arrêt automatique)

    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Erreur de démarrage : {e}")
