#!/usr/bin/env python3
# 💎 Hoshikuzu_games_plus.py — version finale complète
# Jeux, Économie, XP, Rôles de niveaux, Leaderboards, Fun & Giveaway
# Requiert discord.py==2.3.2
# Configure ton token via la variable d'environnement DISCORD_BOT_TOKEN

import os, json, random, asyncio, datetime, threading, http.server, socketserver
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands

# -------------------- Keep-alive (Render) --------------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------- Data Manager --------------------
class DataManager:
    def __init__(self, filename: str = "games_data.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print("Data load error:", e)
        return {
            "economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {},
            "config": {}, "xp_cooldowns": {}, "level_roles": {}
        }

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # config helpers
    def get_levelup_channel(self, guild_id: int) -> Optional[int]:
        return self.data.get("config", {}).get(str(guild_id), {}).get("levelup_channel")

    def set_levelup_channel(self, guild_id: int, channel_id: int):
        self.data.setdefault("config", {}).setdefault(str(guild_id), {})["levelup_channel"] = channel_id

    # level roles
    def add_level_role(self, guild_id: int, level: int, role_id: int):
        gid = str(guild_id)
        self.data.setdefault("level_roles", {}).setdefault(gid, {})[str(level)] = role_id

    def remove_level_role(self, guild_id: int, level: int):
        gid = str(guild_id)
        roles = self.data.setdefault("level_roles", {}).setdefault(gid, {})
        roles.pop(str(level), None)

    def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        gid = str(guild_id)
        roles = self.data.get("level_roles", {}).get(gid, {})
        return {int(lvl): int(role_id) for lvl, role_id in roles.items()}

    def get_role_for_level(self, guild_id: int, level: int) -> Optional[int]:
        return self.data.get("level_roles", {}).get(str(guild_id), {}).get(str(level))

    # economy helpers
    def get_balance(self, gid: int, uid: int) -> int:
        return int(self.data.setdefault("economy", {}).setdefault(str(gid), {}).setdefault(str(uid), 0))

    async def set_balance(self, gid: int, uid: int, amount: int):
        self.data.setdefault("economy", {}).setdefault(str(gid), {})[str(uid)] = int(amount)
        await self.save()

    # XP management
    def add_xp(self, gid: int, uid: int, amount: int) -> Dict[str, Any]:
        guild_xp = self.data.setdefault("xp", {}).setdefault(str(gid), {})
        user = guild_xp.setdefault(str(uid), {"xp": 0, "level": 1, "messages": 0})
        user["xp"] += int(amount)
        user["messages"] += 1
        leveled = False
        while user["xp"] >= user["level"] * 100:
            user["xp"] -= user["level"] * 100
            user["level"] += 1
            leveled = True
        return {"xp": user["xp"], "level": user["level"], "leveled": leveled}

    def get_rank(self, gid: int, uid: int):
        return self.data.setdefault("xp", {}).setdefault(str(gid), {}).get(str(uid), {"xp": 0, "level": 1, "messages": 0})

    def can_gain_xp(self, gid: int, uid: int) -> bool:
        last = self.data.get("xp_cooldowns", {}).get(str(gid), {}).get(str(uid), 0)
        now = int(datetime.datetime.now().timestamp())
        return (now - last) >= 60

    def set_xp_cooldown(self, gid: int, uid: int):
        now = int(datetime.datetime.now().timestamp())
        self.data.setdefault("xp_cooldowns", {}).setdefault(str(gid), {})[str(uid)] = now

data_manager = DataManager()

# -------------------- Bot Setup --------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# -------------------- Utilities --------------------
def _now_ts(): return int(datetime.datetime.now().timestamp())

def parse_time(t: str):
    for s, mult in {"s": 1, "m": 60, "h": 3600, "d": 86400}.items():
        if t.endswith(s): return int(t[:-1]) * mult
    return None

# -------------------- HELP --------------------
@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="💎 Hoshikuzu — Jeux, Économie & Fun", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance [@user]`, `+work`, `+daily`, `+give @user <amount>`", inline=False)
    e.add_field(name="📈 XP & Niveau", value="`+rank [@user]`, `+level [@user]`, `+profile [@user]`\n`+setlevelup #channel`\n`+addrole <niveau> @role`\n`+removerole <niveau>`\n`+listroles`", inline=False)
    e.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    e.add_field(name="🏆 Leaderboard", value="`+lb money`, `+lb xp`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`\nEx: `+gstart 1h 2 Nitro`", inline=False)
    e.set_footer(text="Bot Hoshikuzu — utilise + pour les commandes.")
    await ctx.send(embed=e)

# -------------------- ECONOMY --------------------
COOLDOWNS = {"work": 2*60*60, "daily": 24*60*60}

@bot.command()
async def balance(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    await ctx.send(f"💰 {member.mention} a **{bal}** coins.")

@bot.command()
async def work(ctx):
    uid, gid = ctx.author.id, ctx.guild.id
    last = data_manager.get_rank(gid, uid).get("work_cd", 0)
    now = _now_ts()
    if now - last < COOLDOWNS["work"]:
        await ctx.send("⏳ Tu dois attendre avant de retravailler.")
        return
    gain = random.randint(50, 150)
    bal = data_manager.get_balance(gid, uid)
    await data_manager.set_balance(gid, uid, bal + gain)
    await ctx.send(f"💼 Tu gagnes **{gain}** coins ! Nouveau solde : **{bal + gain}**")

@bot.command()
async def daily(ctx):
    uid, gid = ctx.author.id, ctx.guild.id
    last = data_manager.get_rank(gid, uid).get("daily_cd", 0)
    now = _now_ts()
    if now - last < COOLDOWNS["daily"]:
        await ctx.send("⏳ Tu as déjà récupéré ton daily.")
        return
    gain = 250
    bal = data_manager.get_balance(gid, uid)
    await data_manager.set_balance(gid, uid, bal + gain)
    await ctx.send(f"🎁 Tu gagnes **{gain}** coins ! Nouveau solde : **{bal + gain}**")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0: return await ctx.send("Montant invalide.")
    gid, uid = ctx.guild.id, ctx.author.id
    bal = data_manager.get_balance(gid, uid)
    if bal < amount: return await ctx.send("❌ Solde insuffisant.")
    await data_manager.set_balance(gid, uid, bal - amount)
    await data_manager.set_balance(gid, member.id, data_manager.get_balance(gid, member.id) + amount)
    await ctx.send(f"✅ {ctx.author.mention} a donné **{amount}** coins à {member.mention}.")

# -------------------- FUN --------------------
@bot.command()
async def eightball(ctx, *, question: str):
    rep = random.choice(["Oui.", "Non.", "Peut-être.", "Certainement.", "Je ne pense pas."])
    await ctx.send(f"🎱 **Question:** {question}\n**Réponse:** {rep}")

@bot.command()
async def hug(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    if member == ctx.author:
        await ctx.send(f"{ctx.author.mention} se fait un câlin 🤗")
    else:
        await ctx.send(f"{ctx.author.mention} fait un câlin à {member.mention} 🤗")

@bot.command()
async def ship(ctx, a: discord.Member, b: discord.Member):
    score = random.randint(0, 100)
    heart = "💖" if score > 70 else "💔" if score < 30 else "💛"
    await ctx.send(f"💞 Compatibilité entre **{a.display_name}** et **{b.display_name}** : **{score}%** {heart}")

@bot.command()
async def meme(ctx):
    try:
        import requests
        r = requests.get("https://meme-api.com/gimme", timeout=5)
        if r.status_code == 200:
            j = r.json()
            e = discord.Embed(title=j["title"], color=discord.Color.random())
            e.set_image(url=j["url"])
            await ctx.send(embed=e)
            return
    except: pass
    await ctx.send("😅 Impossible de récupérer un meme, réessaie plus tard.")

# -------------------- RANK / XP --------------------
@bot.command()
async def rank(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    r = data_manager.get_rank(ctx.guild.id, member.id)
    await ctx.send(f"📊 {member.mention} — Niveau **{r['level']}** • XP **{r['xp']}**")

@bot.command()
async def level(ctx, member: Optional[discord.Member] = None):
    await rank(ctx, member)

@bot.command()
async def profile(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    r = data_manager.get_rank(ctx.guild.id, member.id)
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    e = discord.Embed(title=f"👤 Profil — {member.display_name}", color=discord.Color.blurple())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Niveau", value=r['level'])
    e.add_field(name="XP", value=r['xp'])
    e.add_field(name="Coins", value=bal)
    await ctx.send(embed=e)

# -------------------- CONFIG --------------------
@bot.command()
@commands.has_permissions(manage_guild=True)
async def setlevelup(ctx, channel: discord.TextChannel):
    data_manager.set_levelup_channel(ctx.guild.id, channel.id)
    await data_manager.save()
    await ctx.send(f"✅ Salon de level-up défini sur {channel.mention}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, level: int, role: discord.Role):
    data_manager.add_level_role(ctx.guild.id, level, role.id)
    await data_manager.save()
    await ctx.send(f"✅ Le rôle {role.mention} sera donné au niveau **{level}**")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, level: int):
    data_manager.remove_level_role(ctx.guild.id, level)
    await data_manager.save()
    await ctx.send(f"✅ Le rôle du niveau **{level}** a été retiré")

@bot.command()
async def listroles(ctx):
    roles = data_manager.get_level_roles(ctx.guild.id)
    if not roles:
        return await ctx.send("📋 Aucun rôle configuré.")
    desc = "\n".join([f"**Niveau {lvl}** → <@&{rid}>" for lvl, rid in roles.items()])
    e = discord.Embed(title="🎭 Rôles de niveaux", description=desc, color=discord.Color.blue())
    await ctx.send(embed=e)

# -------------------- EVENTS --------------------
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Hoshikuzu | +help"))
    print(f"[Hoshikuzu] Connecté en tant que {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    await bot.process_commands(msg)
    if data_manager.can_gain_xp(msg.guild.id, msg.author.id):
        xp = random.randint(5, 15)
        res = data_manager.add_xp(msg.guild.id, msg.author.id, xp)
        data_manager.set_xp_cooldown(msg.guild.id, msg.author.id)
        await data_manager.save()
        if res["leveled"]:
            lvlch = data_manager.get_levelup_channel(msg.guild.id)
            if lvlch:
                ch = bot.get_channel(lvlch)
                if ch:
                    e = discord.Embed(title="🎉 LEVEL UP 🎉", description=f"{msg.author.mention} est maintenant **niveau {res['level']}** !", color=discord.Color.gold())
                    await ch.send(embed=e)

# -------------------- RUN --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN manquant.")
else:
    bot.run(TOKEN)
