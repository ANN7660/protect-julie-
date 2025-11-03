#!/usr/bin/env python3
# Hoshikuzu_games_plus.py — version complète avec statut et help mis à jour

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
        def log_message(self, format, *args):
            pass

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
        return {"economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {}, "xp_cooldowns": {}, "level_roles": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_balance(self, gid: int, uid: int) -> int:
        return int(self.data.setdefault("economy", {}).setdefault(str(gid), {}).setdefault(str(uid), 0))

    async def set_balance(self, gid: int, uid: int, amount: int):
        self.data.setdefault("economy", {}).setdefault(str(gid), {})[str(uid)] = amount
        await self.save()

    def add_xp(self, gid: int, uid: int, amount: int):
        guild_xp = self.data.setdefault("xp", {}).setdefault(str(gid), {})
        user = guild_xp.setdefault(str(uid), {"xp": 0, "level": 1, "messages": 0})
        user["xp"] += amount
        user["messages"] += 1
        leveled = False
        while user["xp"] >= user["level"] * 100:
            user["xp"] -= user["level"] * 100
            user["level"] += 1
            leveled = True
        return {"xp": user["xp"], "level": user["level"], "leveled": leveled}

    def get_rank(self, gid: int, uid: int):
        return self.data.get("xp", {}).get(str(gid), {}).get(str(uid), {"xp": 0, "level": 1, "messages": 0})

    def can_gain_xp(self, gid: int, uid: int) -> bool:
        now = int(datetime.datetime.now().timestamp())
        last = self.data.get("xp_cooldowns", {}).get(str(gid), {}).get(str(uid), 0)
        return now - last >= 60

    def set_xp_cooldown(self, gid: int, uid: int):
        now = int(datetime.datetime.now().timestamp())
        self.data.setdefault("xp_cooldowns", {}).setdefault(str(gid), {})[str(uid)] = now

    def set_cooldown(self, gid: int, uid: int, key: str, ts: int):
        self.data.setdefault("cooldowns", {}).setdefault(str(gid), {}).setdefault(str(uid), {})[key] = ts

    def get_cooldown(self, gid: int, uid: int, key: str) -> int:
        return self.data.get("cooldowns", {}).get(str(gid), {}).get(str(uid), {}).get(key, 0)

    def create_giveaway(self, gid: int, mid: int, prize: str, end_time: int, winners: int):
        self.data.setdefault("giveaways", {})[str(mid)] = {
            "guild_id": str(gid),
            "prize": prize,
            "end_time": end_time,
            "winners": winners,
            "participants": []
        }

    def get_giveaway(self, mid: int):
        return self.data.get("giveaways", {}).get(str(mid))

    def add_participant(self, mid: int, uid: int):
        g = self.get_giveaway(mid)
        if g and str(uid) not in g["participants"]:
            g["participants"].append(str(uid))

    def remove_giveaway(self, mid: int):
        if str(mid) in self.data.get("giveaways", {}):
            del self.data["giveaways"][str(mid)]

data_manager = DataManager()

# -------------------- Bot Init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# -------------------- Help --------------------
@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="💎 Hoshikuzu — Jeux & Fun", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance [@user]`, `+work`, `+daily`, `+give @user <montant>`", inline=False)
    e.add_field(name="📈 XP & Niveaux", value="`+rank [@user]`, `+level [@user]`, `+profile [@user]`\n`+addrole <niveau> @role`, `+removerole <niveau>`, `+listroles`", inline=False)
    e.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    e.add_field(name="🏆 Classements", value="`+lb money`, `+lb xp`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>` (ex: `+gstart 1h 2 Nitro`)", inline=False)
    e.set_footer(text="Utilise + devant les commandes • Hoshikuzu | +help")
    await ctx.send(embed=e)

# -------------------- Fun --------------------
@bot.command(name="8ball")
async def eightball(ctx, *, question: str):
    responses = ["Oui.", "Non.", "Peut-être.", "Très probable.", "Je ne pense pas.", "Certainement!", "Impossible."]
    await ctx.send(f"🎱 **Question:** {question}\n**Réponse:** {random.choice(responses)}")

@bot.command(name="hug")
async def hug(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    if member == ctx.author:
        await ctx.send(f"{ctx.author.mention} se donne un câlin 🤗")
    else:
        await ctx.send(f"{ctx.author.mention} fait un câlin à {member.mention} 🤗")

@bot.command(name="ship")
async def ship(ctx, a: discord.Member, b: discord.Member):
    score = random.randint(0, 100)
    heart = "💖" if score > 70 else "💔" if score < 30 else "💛"
    await ctx.send(f"💞 Compatibilité entre **{a.display_name}** et **{b.display_name}**: **{score}%** {heart}")

@bot.command(name="meme")
async def meme(ctx):
    try:
        import requests
        r = requests.get("https://meme-api.com/gimme", timeout=6)
        if r.status_code == 200:
            d = r.json()
            embed = discord.Embed(title=d["title"], description=f"r/{d['subreddit']}", color=discord.Color.random())
            embed.set_image(url=d["url"])
            return await ctx.send(embed=embed)
    except:
        pass
    await ctx.send("Erreur lors du chargement du meme 😢")

# -------------------- Economy --------------------
COOLDOWNS = {"work": 2*60*60, "daily": 24*60*60}

@bot.command(name="balance", aliases=["bal"])
async def balance(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    await ctx.send(f"💰 {member.mention} a **{bal}** coins.")

@bot.command(name="work")
async def work(ctx):
    now = int(datetime.datetime.now().timestamp())
    last = data_manager.get_cooldown(ctx.guild.id, ctx.author.id, "work")
    if now - last < COOLDOWNS["work"]:
        return await ctx.send("⏳ Tu dois attendre avant de retravailler.")
    gain = random.randint(40, 120)
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + gain)
    data_manager.set_cooldown(ctx.guild.id, ctx.author.id, "work", now)
    await data_manager.save()
    await ctx.send(f"💼 Tu as gagné **{gain}** coins ! Balance : {bal+gain}")

@bot.command(name="daily")
async def daily(ctx):
    now = int(datetime.datetime.now().timestamp())
    last = data_manager.get_cooldown(ctx.guild.id, ctx.author.id, "daily")
    if now - last < COOLDOWNS["daily"]:
        return await ctx.send("⏳ Reviens demain pour ton daily !")
    bonus = 250
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + bonus)
    data_manager.set_cooldown(ctx.guild.id, ctx.author.id, "daily", now)
    await data_manager.save()
    await ctx.send(f"🎁 Tu as gagné ton daily de **{bonus}** coins ! Balance : {bal+bonus}")

@bot.command(name="give")
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Montant invalide.")
    if data_manager.get_balance(ctx.guild.id, ctx.author.id) < amount:
        return await ctx.send("Tu n’as pas assez d’argent.")
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, data_manager.get_balance(ctx.guild.id, ctx.author.id) - amount)
    await data_manager.set_balance(ctx.guild.id, member.id, data_manager.get_balance(ctx.guild.id, member.id) + amount)
    await data_manager.save()
    await ctx.send(f"✅ {ctx.author.mention} a donné **{amount}** coins à {member.mention}.")

# -------------------- Games --------------------
@bot.command(name="coinflip")
async def coinflip(ctx, bet: int, guess: Optional[str] = None):
    if bet <= 0: return await ctx.send("Montant invalide.")
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("Pas assez de coins.")
    side = random.choice(["pile", "face"])
    if guess and guess.lower() == side:
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + bet)
        msg = f"🎉 C’est **{side}** ! Tu gagnes **{bet}** coins."
    else:
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal - bet)
        msg = f"😞 C’est **{side}**. Tu perds **{bet}** coins."
    await data_manager.save()
    await ctx.send(msg)

@bot.command(name="slots")
async def slots(ctx, bet: int):
    if bet <= 0: return await ctx.send("Montant invalide.")
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("Pas assez de coins.")
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    if len(set(res)) == 1:
        win = bet * 5
        result = f"🎰 {' '.join(res)} — JACKPOT ! +{win}"
    elif len(set(res)) == 2:
        win = bet * 2
        result = f"🎰 {' '.join(res)} — Gagné ! +{win}"
    else:
        win = -bet
        result = f"🎰 {' '.join(res)} — Perdu ! -{bet}"
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + win)
    await data_manager.save()
    await ctx.send(result)

# -------------------- XP System --------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    await bot.process_commands(message)
    if data_manager.can_gain_xp(message.guild.id, message.author.id):
        gain = random.randint(5, 15)
        res = data_manager.add_xp(message.guild.id, message.author.id, gain)
        data_manager.set_xp_cooldown(message.guild.id, message.author.id)
        await data_manager.save()
        if res["leveled"]:
            await message.channel.send(f"🏆 {message.author.mention} est passé niveau **{res['level']}** !")

# -------------------- Leaderboards --------------------
@bot.command(name="lb")
async def leaderboard(ctx, kind: Optional[str] = "money"):
    if kind.lower() == "money":
        lb = sorted(data_manager.data["economy"].get(str(ctx.guild.id), {}).items(), key=lambda x: int(x[1]), reverse=True)[:10]
        desc = "\n".join([f"{i+1}. <@{uid}> — {bal} coins" for i, (uid, bal) in enumerate(lb)])
        await ctx.send(embed=discord.Embed(title="🏆 Top Riches", description=desc, color=discord.Color.gold()))
    else:
        xpdata = data_manager.data["xp"].get(str(ctx.guild.id), {})
        lb = sorted(xpdata.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
        desc = "\n".join([f"{i+1}. <@{uid}> — Niveau {v['level']} ({v['xp']} XP)" for i, (uid, v) in enumerate(lb)])
        await ctx.send(embed=discord.Embed(title="📈 Top XP", description=desc, color=discord.Color.green()))

# -------------------- Profile --------------------
@bot.command(name="profile")
async def profile(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    rank = data_manager.get_rank(ctx.guild.id, member.id)
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    e = discord.Embed(title=f"👤 Profil — {member.display_name}", color=discord.Color.blurple())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Niveau", value=rank["level"])
    e.add_field(name="XP", value=f"{rank['xp']} / {rank['level']*100}")
    e.add_field(name="Coins", value=str(bal))
    e.add_field(name="Messages", value=str(rank.get("messages", 0)))
    await ctx.send(embed=e)

# -------------------- Giveaway --------------------
def parse_time(t: str):
    t = t.lower()
    if t.endswith("s"): return int(t[:-1])
    if t.endswith("m"): return int(t[:-1])*60
    if t.endswith("h"): return int(t[:-1])*3600
    if t.endswith("d"): return int(t[:-1])*86400
    return None

@bot.command(name="gstart")
@commands.has_permissions(manage_guild=True)
async def gstart(ctx, duration: str, winners: int, *, prize: str):
    seconds = parse_time(duration)
    if not seconds: return await ctx.send("❌ Durée invalide. Ex: `10m`, `2h`, `1d`.")
    end = int(datetime.datetime.now().timestamp()) + seconds
    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prix:** {prize}\n**Gagnants:** {winners}\nTemps: {duration}\nRéagis avec 🎁 pour participer !", color=discord.Color.green())
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎁")
    data_manager.create_giveaway(ctx.guild.id, msg.id, prize, end, winners)
    await data_manager.save()
    await asyncio.sleep(seconds)
    g = data_manager.get_giveaway(msg.id)
    if not g: return
    msg = await ctx.channel.fetch_message(msg.id)
    users = [u async for u in msg.reactions[0].users() if not u.bot]
    if not users: return await ctx.send("Aucun participant 😢")
    winners_list = random.sample(users, min(winners, len(users)))
    await ctx.send(f"🎉 Gagnant(s): {' '.join(u.mention for u in winners_list)} — **{prize}** !")
    data_manager.remove_giveaway(msg.id)
    await data_manager.save()

# -------------------- Status & Ready --------------------
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Hoshikuzu | +help"))
    print(f"[Hoshikuzu] connecté comme {bot.user} ({bot.user.id})")

# -------------------- Run --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini.")
else:
    bot.run(TOKEN)
