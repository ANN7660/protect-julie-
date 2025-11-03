#!/usr/bin/env python3
# 🌸 Hoshikuzu — Bot Jeux, Économie, XP, Giveaways & Fun 🌸
# Compatible Python 3.11+ et discord.py==2.3.2

import os, json, random, asyncio, datetime, threading, http.server, socketserver
from typing import Optional, Dict, Any, List
import discord
from discord.ext import commands

# --- Keep Alive (Render / Replit)
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP running on port {port}")
        httpd.serve_forever()
threading.Thread(target=keep_alive, daemon=True).start()

# --- Data Manager
class DataManager:
    def __init__(self, filename="hoshikuzu_data.json"):
        self.filename = filename
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"economy": {}, "xp": {}, "cooldowns": {}, "xp_cooldowns": {}, "level_roles": {}, "config": {}, "giveaways": {}}

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # --- Economy
    def get_balance(self, gid, uid): return int(self.data.setdefault("economy", {}).setdefault(str(gid), {}).get(str(uid), 0))
    def set_balance(self, gid, uid, amount):
        self.data.setdefault("economy", {}).setdefault(str(gid), {})[str(uid)] = amount
        self.save()

    # --- XP
    def add_xp(self, gid, uid, amount):
        u = self.data.setdefault("xp", {}).setdefault(str(gid), {}).setdefault(str(uid), {"xp":0,"level":1,"messages":0})
        u["xp"] += amount; u["messages"] += 1
        leveled = False
        while u["xp"] >= u["level"] * 100:
            u["xp"] -= u["level"] * 100
            u["level"] += 1; leveled = True
        self.save(); return u, leveled

    def get_rank(self, gid, uid): return self.data.get("xp", {}).get(str(gid), {}).get(str(uid), {"xp":0,"level":1,"messages":0})

    # --- Level roles
    def add_level_role(self, gid, level, rid):
        self.data.setdefault("level_roles", {}).setdefault(str(gid), {})[str(level)] = rid; self.save()
    def remove_level_role(self, gid, level):
        self.data.setdefault("level_roles", {}).setdefault(str(gid), {}).pop(str(level), None); self.save()
    def get_level_roles(self, gid):
        return {int(lvl): rid for lvl, rid in self.data.get("level_roles", {}).get(str(gid), {}).items()}

    # --- Giveaways
    def create_giveaway(self, gid, mid, prize, end, winners):
        self.data.setdefault("giveaways", {})[str(mid)] = {"gid":gid,"prize":prize,"end":end,"winners":winners,"participants":[]}; self.save()
    def get_giveaway(self, mid): return self.data.get("giveaways", {}).get(str(mid))
    def add_participant(self, mid, uid):
        g = self.get_giveaway(mid)
        if g and str(uid) not in g["participants"]:
            g["participants"].append(str(uid)); self.save()
    def remove_giveaway(self, mid): self.data.get("giveaways", {}).pop(str(mid), None); self.save()

data = DataManager()

# --- Bot init
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# --- Utils
def now(): return int(datetime.datetime.now().timestamp())
def parse_time(t):
    m = {"s":1,"m":60,"h":3600,"d":86400}
    try: return int(t[:-1])*m.get(t[-1],0)
    except: return None

# --- Presence
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Hoshikuzu | +help"))
    print(f"[Hoshikuzu] Connecté en tant que {bot.user}")

# --- HELP
@bot.command()
async def help(ctx):
    e = discord.Embed(title="🌸 Commandes Hoshikuzu", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance [@user]`, `+work`, `+daily`, `+give @user <montant>`", inline=False)
    e.add_field(name="📈 XP & Niveau", value="`+rank [@user]`, `+level [@user]`, `+profile [@user]`\n`+setlevelup #salon` — définir le salon level up\n`+addrole <niveau> @rôle`, `+removerole <niveau>`, `+listroles`", inline=False)
    e.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    e.add_field(name="🏆 Classements", value="`+lb money`, `+lb xp`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`\nEx: `+gstart 1h 2 Nitro`", inline=False)
    e.set_footer(text="Bot Hoshikuzu — amuse-toi bien 💫")
    await ctx.send(embed=e)

# --- ÉCONOMIE
COOLDOWNS = {"work":7200,"daily":86400}

@bot.command()
async def balance(ctx, member: discord.Member=None):
    m = member or ctx.author
    await ctx.send(f"💰 {m.mention} a **{data.get_balance(ctx.guild.id, m.id)}** coins.")

@bot.command()
async def work(ctx):
    uid, gid = ctx.author.id, ctx.guild.id
    earn = random.randint(50,150)
    bal = data.get_balance(gid, uid)
    data.set_balance(gid, uid, bal+earn)
    await ctx.send(f"💼 Tu as travaillé et gagné **{earn}** coins !")

@bot.command()
async def daily(ctx):
    uid, gid = ctx.author.id, ctx.guild.id
    bonus = 250
    bal = data.get_balance(gid, uid)
    data.set_balance(gid, uid, bal+bonus)
    await ctx.send(f"🎁 Tu as récupéré ton daily : **{bonus}** coins !")

@bot.command()
async def give(ctx, member: discord.Member, amount:int):
    if amount<=0: return await ctx.send("Montant invalide.")
    gid=ctx.guild.id
    b1=data.get_balance(gid, ctx.author.id)
    if b1<amount: return await ctx.send("Tu n'as pas assez de coins.")
    b2=data.get_balance(gid, member.id)
    data.set_balance(gid, ctx.author.id, b1-amount)
    data.set_balance(gid, member.id, b2+amount)
    await ctx.send(f"✅ {ctx.author.mention} a donné **{amount}** coins à {member.mention} !")

# --- JEUX
@bot.command()
async def coinflip(ctx, bet:int, guess:str=None):
    if bet<=0: return await ctx.send("Montant invalide.")
    bal=data.get_balance(ctx.guild.id, ctx.author.id)
    if bal<bet: return await ctx.send("Pas assez de coins.")
    result=random.choice(["pile","face"])
    if guess and guess.lower()==result:
        data.set_balance(ctx.guild.id, ctx.author.id, bal+bet)
        await ctx.send(f"🎉 C'est **{result}** ! Tu gagnes **{bet}** !")
    else:
        data.set_balance(ctx.guild.id, ctx.author.id, bal-bet)
        await ctx.send(f"😞 C'est **{result}** ! Tu perds **{bet}**.")

@bot.command()
async def slots(ctx, bet:int):
    if bet<=0: return await ctx.send("Montant invalide.")
    bal=data.get_balance(ctx.guild.id, ctx.author.id)
    if bal<bet: return await ctx.send("Pas assez de coins.")
    symbols=["🍒","🍋","🔔","⭐","7️⃣"]
    res=[random.choice(symbols) for _ in range(3)]
    if len(set(res))==1:
        win=bet*5; data.set_balance(ctx.guild.id, ctx.author.id, bal+win)
        await ctx.send(f"🎰 {' '.join(res)} — JACKPOT ! +{win} coins")
    elif len(set(res))==2:
        win=int(bet*1.5); data.set_balance(ctx.guild.id, ctx.author.id, bal+win)
        await ctx.send(f"🎰 {' '.join(res)} — Gagné {win} coins !")
    else:
        data.set_balance(ctx.guild.id, ctx.author.id, bal-bet)
        await ctx.send(f"🎰 {' '.join(res)} — Perdu {bet} coins.")

# --- FUN
@bot.command()
async def eightball(ctx, *, question:str):
    resp=["Oui.","Non.","Peut-être.","Certainement !","Peu probable.","Absolument pas."]
    await ctx.send(f"🎱 **Question :** {question}\n**Réponse :** {random.choice(resp)}")

@bot.command()
async def hug(ctx, member: discord.Member=None):
    m=member or ctx.author
    if m==ctx.author: await ctx.send(f"{ctx.author.mention} se donne un câlin 🤗")
    else: await ctx.send(f"{ctx.author.mention} fait un câlin à {m.mention} 🤗")

@bot.command()
async def ship(ctx, a:discord.Member,b:discord.Member):
    score=random.randint(0,100)
    heart="💖" if score>70 else "💛" if score>40 else "💔"
    await ctx.send(f"💞 Compatibilité entre {a.display_name} et {b.display_name} : **{score}%** {heart}")

@bot.command()
async def meme(ctx):
    fallback=["https://i.imgur.com/1J9Z6.jpg","https://i.imgur.com/8pQ0Z.jpg","https://i.imgur.com/2c3KX.jpg"]
    try:
        import requests
        r=requests.get("https://meme-api.com/gimme",timeout=5)
        d=r.json()
        e=discord.Embed(title=d["title"], description=f"r/{d['subreddit']}", color=discord.Color.random())
        e.set_image(url=d["url"]); await ctx.send(embed=e)
    except: await ctx.send(random.choice(fallback))

# --- XP / RANK
@bot.command()
async def rank(ctx, member:discord.Member=None):
    m=member or ctx.author; r=data.get_rank(ctx.guild.id,m.id)
    await ctx.send(f"📊 {m.display_name} — Niveau **{r['level']}** • XP {r['xp']}/{r['level']*100} • Msg {r['messages']}")

@bot.command()
async def level(ctx, member:discord.Member=None): await rank(ctx, member)

@bot.command()
async def profile(ctx, member:discord.Member=None):
    m=member or ctx.author; r=data.get_rank(ctx.guild.id,m.id); bal=data.get_balance(ctx.guild.id,m.id)
    e=discord.Embed(title=f"👤 Profil de {m.display_name}", color=discord.Color.blurple())
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Niveau", value=r['level']); e.add_field(name="XP", value=r['xp'])
    e.add_field(name="Coins", value=bal); e.add_field(name="Messages", value=r['messages'])
    await ctx.send(embed=e)

# --- LEVEL ROLES
@bot.command()
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, level:int, role:discord.Role):
    data.add_level_role(ctx.guild.id, level, role.id)
    await ctx.send(f"✅ Le rôle {role.mention} sera donné au niveau **{level}**.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, level:int):
    data.remove_level_role(ctx.guild.id, level)
    await ctx.send(f"✅ Le rôle du niveau {level} a été retiré.")

@bot.command()
async def listroles(ctx):
    roles=data.get_level_roles(ctx.guild.id)
    if not roles: return await ctx.send("📋 Aucun rôle configuré.")
    txt="\n".join([f"Niveau {lvl} → <@&{rid}>" for lvl,rid in roles.items()])
    await ctx.send(f"🎭 **Rôles par niveau :**\n{txt}")

# --- GIVEAWAY
@bot.command()
@commands.has_permissions(manage_guild=True)
async def gstart(ctx, duration:str, winners:int, *, prize:str):
    sec=parse_time(duration)
    if not sec: return await ctx.send("❌ Durée invalide. Ex: 1h, 30m")
    end=now()+sec
    e=discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prix:** {prize}\n**Gagnants:** {winners}\nRéagis 🎁 pour participer !", color=discord.Color.green())
    msg=await ctx.send(embed=e); await msg.add_reaction("🎁")
    data.create_giveaway(ctx.guild.id, msg.id, prize, end, winners)
    await asyncio.sleep(sec)
    g=data.get_giveaway(msg.id)
    if not g: return
    msg=await ctx.channel.fetch_message(msg.id)
    users=[u async for u in msg.reactions[0].users() if not u.bot]
    if not users: await ctx.send("❌ Aucun participant !"); return
    winners_list=random.sample(users, min(winners,len(users)))
    await ctx.send("🎊 Gagnant(s) : " + ", ".join([u.mention for u in winners_list]))
    data.remove_giveaway(msg.id)

# --- Leaderboards
@bot.command()
async def lb(ctx, kind:str="money"):
    if kind=="money":
        e=sorted(data.data.get("economy",{}).get(str(ctx.guild.id),{}).items(), key=lambda x:int(x[1]), reverse=True)[:10]
        txt="\n".join([f"{i+1}. <@{uid}> — {v} coins" for i,(uid,v) in enumerate(e)])
        await ctx.send(embed=discord.Embed(title="🏆 Top Riches", description=txt, color=discord.Color.gold()))
    elif kind=="xp":
        e=data.data.get("xp",{}).get(str(ctx.guild.id),{})
        sort=sorted(e.items(), key=lambda kv:(kv[1]['level'],kv[1]['xp']), reverse=True)[:10]
        txt="\n".join([f"{i+1}. <@{uid}> — Niveau {v['level']} ({v['xp']} XP)" for i,(uid,v) in enumerate(sort)])
        await ctx.send(embed=discord.Embed(title="📈 Top XP", description=txt, color=discord.Color.green()))

# --- XP gain
@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    if random.random()<0.6: # gain aléatoire
        res, up=data.add_xp(msg.guild.id, msg.author.id, random.randint(5,15))
        if up:
            roles=data.get_level_roles(msg.guild.id)
            if res['level'] in roles:
                role=msg.guild.get_role(roles[res['level']])
                if role: await msg.author.add_roles(role)
            await msg.channel.send(f"🎉 {msg.author.mention} est passé niveau **{res['level']}** !")
    await bot.process_commands(msg)

# --- Run
TOKEN=os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN: print("❌ Token non défini.")
else: bot.run(TOKEN)
