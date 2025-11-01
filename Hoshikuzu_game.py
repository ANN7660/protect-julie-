#!/usr/bin/env python3
# Hoshikuzu_games.py
# Lightweight "games & fun" version of Hoshikuzu
# - XP/Level on message
# - Economy: balance, work, daily, give, coinflip, slots
# - Fun: 8ball, hug, ship, meme (static fallback)
# - Simple +help
# - Persistency to games_data.json
# Requires: discord.py==2.3.2

import os, json, random, asyncio, threading, http.server, socketserver, datetime
from typing import Optional, Dict, Any
import discord
from discord.ext import commands

# ---------------- keep-alive (Render) ----------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): pass
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ---------------- Data Manager ----------------
class DataManager:
    def __init__(self, path="games_data.json"):
        self.path = path
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print("DataManager load error:", e)
        return {"economy": {}, "xp": {}, "cooldowns": {}}

    async def save(self):
        async with self.lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # economy helpers
    def get_balance(self, guild_id:int, user_id:int) -> int:
        gid=str(guild_id); uid=str(user_id)
        return int(self.data.setdefault("economy", {}).setdefault(gid, {}).setdefault(uid, 0))

    async def set_balance(self, guild_id:int, user_id:int, amount:int):
        gid=str(guild_id); uid=str(user_id)
        self.data.setdefault("economy", {}).setdefault(gid, {})[uid] = int(amount)
        await self.save()

    # xp helpers
    def add_xp(self, guild_id:int, user_id:int, xp:int):
        gid=str(guild_id); uid=str(user_id)
        g = self.data.setdefault("xp", {}).setdefault(gid, {})
        stats = g.setdefault(uid, {"xp":0, "messages":0})
        stats["xp"] += int(xp)
        stats["messages"] += 1
        return stats["xp"]

    def get_xp(self, guild_id:int, user_id:int) -> int:
        gid=str(guild_id); uid=str(user_id)
        return int(self.data.setdefault("xp", {}).setdefault(gid, {}).setdefault(uid, {}).get("xp", 0))

    def get_messages(self, guild_id:int, user_id:int) -> int:
        gid=str(guild_id); uid=str(user_id)
        return int(self.data.setdefault("xp", {}).setdefault(gid, {}).setdefault(uid, {}).get("messages", 0))

    # cooldown storage (simple, persisted for safety)
    def get_cd(self, guild_id:int, user_id:int, key:str) -> int:
        gid=str(guild_id); uid=str(user_id)
        return int(self.data.setdefault("cooldowns", {}).setdefault(gid, {}).setdefault(uid, {}).get(key, 0))

    async def set_cd(self, guild_id:int, user_id:int, key:str, ts:int):
        gid=str(guild_id); uid=str(user_id)
        self.data.setdefault("cooldowns", {}).setdefault(gid, {}).setdefault(uid, {})[key] = int(ts)
        await self.save()

data = DataManager()

# ---------------- Bot init ----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = False  # no heavy member intents needed
intents.guilds = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# ---------------- Utilities ----------------
def xp_to_level(xp:int) -> int:
    # level ≈ floor(sqrt(xp/50))
    return int((xp / 50) ** 0.5)

def next_level_xp(level:int) -> int:
    return int(((level + 1) ** 2) * 50)

# ---------------- Commands: help & fun ----------------
@bot.command(name="help")
async def help_cmd(ctx:commands.Context):
    embed = discord.Embed(title="Hoshikuzu — Jeux & Fun", color=discord.Color.blue())
    embed.add_field(name="Jeux & économie", value="`+balance`, `+work`, `+daily`, `+give`, `+coinflip`, `+slots`, `+rank`", inline=False)
    embed.add_field(name="Fun", value="`+8ball`, `+hug @user`, `+ship @a @b`, `+meme`", inline=False)
    await ctx.send(embed=embed)

# 8ball
EIGHT_BALL = [
    "Oui.", "Non.", "Peut-être.", "Sans doute.", "Demande plus tard.", "Je n'en suis pas sûr.",
    "Très probable.", "Impossible."
]
@bot.command(name="8ball")
async def eightball_cmd(ctx:commands.Context, *, question: str):
    await ctx.send(f"🎱 Question : {question}\nRéponse : **{random.choice(EIGHT_BALL)}**")

# hug
@bot.command(name="hug")
async def hug_cmd(ctx:commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    if member == ctx.author:
        return await ctx.send(f"{ctx.author.mention} reçoit un câlin 🤗")
    await ctx.send(f"{ctx.author.mention} envoie un câlin à {member.mention} 🤗")

# ship
@bot.command(name="ship")
async def ship_cmd(ctx:commands.Context, a: discord.Member, b: discord.Member):
    score = random.randint(0,100)
    hearts = "❤️" * (score//20)
    await ctx.send(f"💞 Compatibilité entre {a.mention} et {b.mention} : **{score}%** {hearts}")

# meme - static fallback images (no external fetch required)
FALLBACK_MEMES = [
    "https://i.imgur.com/1J9Z6.jpg", "https://i.imgur.com/8pQ0Z.jpg", "https://i.imgur.com/2c3KX.jpg"
]
@bot.command(name="meme")
async def meme_cmd(ctx:commands.Context):
    url = random.choice(FALLBACK_MEMES)
    embed = discord.Embed(title="Meme aléatoire", color=discord.Color.random())
    embed.set_image(url=url)
    await ctx.send(embed=embed)

# ---------------- Economy ----------------
COOLDOWNS = {"work": 2*60*60, "daily": 24*60*60}  # seconds - same guild/user mapping
@bot.command(name="balance", aliases=["bal"])
async def balance_cmd(ctx:commands.Context, member: Optional[discord.Member]=None):
    member = member or ctx.author
    bal = data.get_balance(ctx.guild.id, member.id)
    await ctx.send(f"💰 {member.mention} a {bal} coins.")

@bot.command(name="work")
async def work_cmd(ctx:commands.Context):
    uid = ctx.author.id; gid = ctx.guild.id
    now = int(datetime.datetime.now().timestamp())
    last = data.get_cd(gid, uid, "work") or 0
    if now - last < COOLDOWNS["work"]:
        remaining = COOLDOWNS["work"] - (now - last)
        return await ctx.send(f"⏳ Attends {remaining//60} minutes avant de retravailler.")
    gain = random.randint(40, 130)
    bal = data.get_balance(gid, uid)
    await data.set_balance(gid, uid, bal + gain)
    await data.set_cd(gid, uid, "work", now)
    await ctx.send(f"💼 Tu as travaillé et gagné **{gain} coins**. Balance: {bal+gain}")

@bot.command(name="daily")
async def daily_cmd(ctx:commands.Context):
    uid = ctx.author.id; gid = ctx.guild.id
    now = int(datetime.datetime.now().timestamp())
    last = data.get_cd(gid, uid, "daily") or 0
    if now - last < COOLDOWNS["daily"]:
        remaining = COOLDOWNS["daily"] - (now - last)
        return await ctx.send(f"⏳ Tu as déjà pris ton daily. Attends {remaining//3600} heures.")
    bonus = 250
    bal = data.get_balance(gid, uid)
    await data.set_balance(gid, uid, bal + bonus)
    await data.set_cd(gid, uid, "daily", now)
    await ctx.send(f"🎁 Tu as reçu ton daily : **{bonus} coins**. Balance: {bal+bonus}")

@bot.command(name="give")
async def give_cmd(ctx:commands.Context, member:discord.Member, amount:int):
    if amount <= 0: return await ctx.send("Montant invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal_from = data.get_balance(gid, uid)
    if bal_from < amount: return await ctx.send("Tu n'as pas assez d'argent.")
    await data.set_balance(gid, uid, bal_from - amount)
    bal_to = data.get_balance(gid, member.id)
    await data.set_balance(gid, member.id, bal_to + amount)
    await ctx.send(f"✅ {ctx.author.mention} a donné {amount} coins à {member.mention}.")

@bot.command(name="coinflip")
async def coinflip_cmd(ctx:commands.Context, bet:int, guess:Optional[str]=None):
    if bet <= 0: return await ctx.send("Pari invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal = data.get_balance(gid, uid)
    if bal < bet: return await ctx.send("Tu n'as pas assez d'argent.")
    outcome = random.choice(["pile","face"])
    if guess and guess.lower() == outcome:
        await data.set_balance(gid, uid, bal + bet)
        await ctx.send(f"🎉 {outcome} — tu gagnes {bet}! Balance: {bal+bet}")
    else:
        await data.set_balance(gid, uid, bal - bet)
        await ctx.send(f"😞 {outcome} — tu perds {bet}. Balance: {bal-bet}")

@bot.command(name="slots")
async def slots_cmd(ctx:commands.Context, bet:int):
    if bet <= 0: return await ctx.send("Pari invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal = data.get_balance(gid, uid)
    if bal < bet: return await ctx.send("Tu n'as pas assez d'argent.")
    symbols = ["🍒","🍋","🔔","⭐","7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    if len(set(res)) == 1:
        win = bet * 5; await data.set_balance(gid, uid, bal + win); await ctx.send(f"🎰 {' '.join(res)} — JACKPOT! Tu gagnes {win}.")
    elif len(set(res)) == 2:
        win = int(bet * 1.5); await data.set_balance(gid, uid, bal + win); await ctx.send(f"🎰 {' '.join(res)} — Tu gagnes {win}.")
    else:
        await data.set_balance(gid, uid, bal - bet); await ctx.send(f"🎰 {' '.join(res)} — Tu perds {bet}.")

# ---------------- XP / Level system ----------------
MSG_XP = (5, 12)  # random XP per message
MSG_CD = 15  # seconds between xp gains per user per guild

async def try_award_xp(message:discord.Message):
    if not message.guild: return
    if message.author.bot: return
    gid = message.guild.id; uid = message.author.id
    now = int(datetime.datetime.now().timestamp())
    last = data.get_cd(gid, uid, "msg_xp") or 0
    if now - last < MSG_CD: return
    xp_gain = random.randint(MSG_XP[0], MSG_XP[1])
    new_xp = data.add_xp(gid, uid, xp_gain)
    await data.set_cd(gid, uid, "msg_xp", now)
    old_level = xp_to_level(new_xp - xp_gain)
    new_level = xp_to_level(new_xp)
    if new_level > old_level:
        try:
            await message.channel.send(f"🎉 {message.author.mention} vient d'atteindre le niveau **{new_level}** !")
        except:
            pass

@bot.event
async def on_message(message:discord.Message):
    await try_award_xp(message)
    await bot.process_commands(message)

@bot.command(name="rank")
async def rank_cmd(ctx:commands.Context, member:Optional[discord.Member]=None):
    member = member or ctx.author
    xp = data.get_xp(ctx.guild.id, member.id)
    level = xp_to_level(xp)
    needed = next_level_xp(level) - xp
    msgs = data.get_messages(ctx.guild.id, member.id)
    embed = discord.Embed(title=f"📊 Rang de {member.display_name}", color=discord.Color.gold())
    embed.add_field(name="Niveau", value=str(level), inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="Messages", value=str(msgs), inline=True)
    embed.set_footer(text=f"XP nécessaire pour niveau suivant: {needed}")
    await ctx.send(embed=embed)

# ---------------- Run ----------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini. Ajoute la variable d'environnement et relance.")
else:
    bot.run(TOKEN)
