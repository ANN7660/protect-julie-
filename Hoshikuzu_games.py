#!/usr/bin/env python3
# 💫 Hoshikuzu — Jeux & Fun Bot complet

import os, json, random, asyncio, datetime, threading, http.server, socketserver
from typing import Optional, Dict, Any, List
import discord
from discord.ext import commands

# === Keep Alive (Render) ===
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except:
        port = 8080
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP server running on port {port}")
        httpd.serve_forever()
threading.Thread(target=keep_alive, daemon=True).start()

# === Data Manager ===
class DataManager:
    def __init__(self, filename="hoshikuzu_data.json"):
        self.filename = filename
        self.data = self._load()
        self.lock = asyncio.Lock()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print("load error:", e)
        return {"economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {}, "config": {}, "level_roles": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # ==== Économie ====
    def get_balance(self, gid, uid): return int(self.data.setdefault("economy", {}).setdefault(str(gid), {}).setdefault(str(uid), 0))
    async def set_balance(self, gid, uid, amt):
        self.data.setdefault("economy", {}).setdefault(str(gid), {})[str(uid)] = int(amt)
        await self.save()

    # ==== XP & Levels ====
    def add_xp(self, gid, uid, amount):
        g = str(gid); u = str(uid)
        xp = self.data.setdefault("xp", {}).setdefault(g, {}).setdefault(u, {"xp": 0, "level": 1, "messages": 0})
        xp["xp"] += amount; xp["messages"] += 1
        leveled = False
        while xp["xp"] >= xp["level"] * 100:
            xp["xp"] -= xp["level"] * 100
            xp["level"] += 1
            leveled = True
        return {"leveled": leveled, "level": xp["level"], "xp": xp["xp"]}

    def get_rank(self, gid, uid): 
        return self.data.setdefault("xp", {}).setdefault(str(gid), {}).get(str(uid), {"xp": 0, "level": 1, "messages": 0})

    def get_levelup_channel(self, gid): return self.data.get("config", {}).get(str(gid), {}).get("levelup_channel")
    def set_levelup_channel(self, gid, cid): self.data.setdefault("config", {}).setdefault(str(gid), {})["levelup_channel"] = cid

    # ==== Level Roles ====
    def add_level_role(self, gid, lvl, rid): self.data.setdefault("level_roles", {}).setdefault(str(gid), {})[str(lvl)] = rid
    def remove_level_role(self, gid, lvl): self.data.setdefault("level_roles", {}).setdefault(str(gid), {}).pop(str(lvl), None)
    def get_level_roles(self, gid): return {int(l): int(r) for l, r in self.data.get("level_roles", {}).get(str(gid), {}).items()}

    # ==== Giveaways ====
    def create_giveaway(self, gid, mid, prize, end, winners):
        self.data.setdefault("giveaways", {})[str(mid)] = {"guild": gid, "prize": prize, "end": end, "winners": winners, "users": []}
    def get_giveaway(self, mid): return self.data.get("giveaways", {}).get(str(mid))
    def add_user(self, mid, uid):
        g = self.get_giveaway(mid)
        if g and str(uid) not in g["users"]: g["users"].append(str(uid))

data = DataManager()

# === Bot Init ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# === Help ===
@bot.command()
async def help(ctx):
    e = discord.Embed(title="💎 Hoshikuzu — Jeux & Fun", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance`, `+work`, `+daily`, `+give @user <amount>`", inline=False)
    e.add_field(name="📈 XP & Niveau", value="`+rank`, `+level`, `+profile`\n`+setlevelup #salon`\n`+addrole <niveau> @role`\n`+removerole <niveau>`\n`+listroles`", inline=False)
    e.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    e.add_field(name="🏆 Leaderboard", value="`+lb money`, `+lb xp`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`\nEx: `+gstart 1h 2 Nitro`", inline=False)
    e.set_footer(text="hoshikuzu | +help 🌙")
    await ctx.send(embed=e)

# === Économie ===
@bot.command()
async def balance(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    await ctx.send(f"💰 {member.mention} a **{data.get_balance(ctx.guild.id, member.id)}** coins")

@bot.command()
async def work(ctx):
    earn = random.randint(50, 150)
    bal = data.get_balance(ctx.guild.id, ctx.author.id) + earn
    await data.set_balance(ctx.guild.id, ctx.author.id, bal)
    await ctx.send(f"💼 Tu as gagné **{earn}** coins ! Total: {bal}")

@bot.command()
async def daily(ctx):
    bonus = 250
    bal = data.get_balance(ctx.guild.id, ctx.author.id) + bonus
    await data.set_balance(ctx.guild.id, ctx.author.id, bal)
    await ctx.send(f"🎁 Daily collecté : **{bonus}** coins ! Total: {bal}")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0: return await ctx.send("Montant invalide.")
    bal_from = data.get_balance(ctx.guild.id, ctx.author.id)
    if bal_from < amount: return await ctx.send("Tu n’as pas assez d’argent.")
    await data.set_balance(ctx.guild.id, ctx.author.id, bal_from - amount)
    await data.set_balance(ctx.guild.id, member.id, data.get_balance(ctx.guild.id, member.id) + amount)
    await ctx.send(f"✅ {ctx.author.mention} a donné **{amount}** coins à {member.mention}.")

# === Jeux ===
@bot.command()
async def coinflip(ctx, bet: int, choice: Optional[str] = None):
    if bet <= 0: return await ctx.send("❌ Pari invalide.")
    bal = data.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("❌ Pas assez d’argent.")
    res = random.choice(["pile", "face"])
    if choice and choice.lower() == res:
        await data.set_balance(ctx.guild.id, ctx.author.id, bal + bet)
        await ctx.send(f"🎉 C’était **{res}** ! Tu gagnes {bet} coins !")
    else:
        await data.set_balance(ctx.guild.id, ctx.author.id, bal - bet)
        await ctx.send(f"😢 C’était **{res}**. Tu perds {bet} coins.")

@bot.command()
async def slots(ctx, bet: int):
    if bet <= 0: return await ctx.send("Pari invalide.")
    bal = data.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("Pas assez d’argent.")
    s = ["🍒","🍋","🔔","⭐","7️⃣"]
    r = [random.choice(s) for _ in range(3)]
    if len(set(r)) == 1:
        win = bet * 5
        msg = f"🎰 {' '.join(r)} — JACKPOT ! Tu gagnes {win} coins !"
        await data.set_balance(ctx.guild.id, ctx.author.id, bal + win)
    elif len(set(r)) == 2:
        win = int(bet * 1.5)
        msg = f"🎰 {' '.join(r)} — Tu gagnes {win} coins !"
        await data.set_balance(ctx.guild.id, ctx.author.id, bal + win)
    else:
        msg = f"🎰 {' '.join(r)} — Tu perds {bet} coins."
        await data.set_balance(ctx.guild.id, ctx.author.id, bal - bet)
    await ctx.send(msg)

# === XP & Level Roles ===
@bot.command()
async def setlevelup(ctx, channel: discord.TextChannel):
    data.set_levelup_channel(ctx.guild.id, channel.id)
    await data.save()
    await ctx.send(f"✅ Messages de level-up envoyés dans {channel.mention}")

@bot.command()
async def rank(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    r = data.get_rank(ctx.guild.id, member.id)
    await ctx.send(f"📊 {member.mention} — Niveau {r['level']} ({r['xp']} XP)")

@bot.command()
async def addrole(ctx, level: int, role: discord.Role):
    data.add_level_role(ctx.guild.id, level, role.id)
    await data.save()
    await ctx.send(f"🎭 Rôle {role.mention} ajouté pour le niveau {level}")

@bot.command()
async def removerole(ctx, level: int):
    data.remove_level_role(ctx.guild.id, level)
    await data.save()
    await ctx.send(f"🗑️ Rôle supprimé pour le niveau {level}")

@bot.command()
async def listroles(ctx):
    roles = data.get_level_roles(ctx.guild.id)
    if not roles: return await ctx.send("Aucun rôle configuré.")
    msg = "\n".join([f"Niveau {lvl} → <@&{rid}>" for lvl, rid in roles.items()])
    await ctx.send(f"🎭 Rôles configurés :\n{msg}")

# === Fun ===
@bot.command()
async def eightball(ctx, *, question):
    rep = random.choice(["Oui.", "Non.", "Peut-être.", "Absolument.", "Jamais."])
    await ctx.send(f"🎱 Question: {question}\nRéponse: {rep}")

@bot.command()
async def hug(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    if member == ctx.author: await ctx.send(f"{ctx.author.mention} se câline lui-même 🤗")
    else: await ctx.send(f"{ctx.author.mention} fait un câlin à {member.mention} 🤗")

@bot.command()
async def ship(ctx, a: discord.Member, b: discord.Member):
    score = random.randint(0, 100)
    emoji = "💖" if score > 70 else "💔" if score < 30 else "💛"
    await ctx.send(f"💞 Compatibilité {a.display_name} & {b.display_name} : {score}% {emoji}")

@bot.command()
async def meme(ctx):
    try:
        import requests
        r = requests.get("https://meme-api.com/gimme", timeout=5).json()
        e = discord.Embed(title=r['title'], color=discord.Color.random())
        e.set_image(url=r['url'])
        await ctx.send(embed=e)
    except: await ctx.send("Erreur de meme API 😅")

# === Leaderboard ===
@bot.command()
async def lb(ctx, typ: Optional[str] = "money"):
    if typ == "money":
        top = sorted(data.data["economy"].get(str(ctx.guild.id), {}).items(), key=lambda x: int(x[1]), reverse=True)[:10]
        desc = "\n".join([f"{i+1}. <@{uid}> — {amt} coins" for i, (uid, amt) in enumerate(top)])
        await ctx.send(embed=discord.Embed(title="🏆 Top Riches", description=desc, color=discord.Color.gold()))
    else:
        top = sorted(data.data["xp"].get(str(ctx.guild.id), {}).items(), key=lambda x: x[1]["level"], reverse=True)[:10]
        desc = "\n".join([f"{i+1}. <@{uid}> — niveau {x['level']}" for i,(uid,x) in enumerate(top)])
        await ctx.send(embed=discord.Embed(title="📈 Top XP", description=desc, color=discord.Color.green()))

# === Giveaway ===
@bot.command()
async def gstart(ctx, duration: str, winners: int, *, prize: str):
    units = {'s':1,'m':60,'h':3600,'d':86400}
    t = int(duration[:-1]) * units.get(duration[-1],1)
    end = int(datetime.datetime.now().timestamp()) + t
    e = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**{prize}**\nDurée: {duration}\nRéagis 🎁 pour participer !", color=discord.Color.green())
    m = await ctx.send(embed=e); await m.add_reaction("🎁")
    data.create_giveaway(ctx.guild.id, m.id, prize, end, winners)
    await data.save()
    await asyncio.sleep(t)
    msg = await ctx.channel.fetch_message(m.id)
    users = [u async for u in msg.reactions[0].users() if not u.bot]
    if users:
        win = random.sample(users, min(len(users), winners))
        await ctx.send(f"🎊 Gagnant(s): {' '.join(u.mention for u in win)} — {prize}")
    else:
        await ctx.send("❌ Aucun participant.")
        
# === Events ===
@bot.event
async def on_message(msg):
    if msg.author.bot: return
    await bot.process_commands(msg)
    res = data.add_xp(msg.guild.id, msg.author.id, random.randint(5,15))
    if res["leveled"]:
        ch = data.get_levelup_channel(msg.guild.id)
        if ch:
            chan = bot.get_channel(ch)
            await chan.send(f"🌟 {msg.author.mention} est passé niveau **{res['level']}** !")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("hoshikuzu | +help"))
    print(f"[Hoshikuzu] Connecté comme {bot.user}")

# === Run ===
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN: print("❌ Token non défini")
else: bot.run(TOKEN)
