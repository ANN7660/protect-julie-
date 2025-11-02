#!/usr/bin/env python3
# Hoshikuzu_games_plus.py
# Games & Fun bot with XP, economy, leaderboard, help, profile, giveaway
# Requires: discord.py==2.3.2, requests (optional, used for +meme)
# Configure DISCORD_BOT_TOKEN in environment variables before running.

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
            return

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
        # default structure
        return {"economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # economy helpers
    def get_balance(self, guild_id: int, user_id: int) -> int:
        gid = str(guild_id); uid = str(user_id)
        return int(self.data.setdefault("economy", {}).setdefault(gid, {}).setdefault(uid, 0))

    async def set_balance(self, guild_id: int, user_id: int, amount: int):
        gid = str(guild_id); uid = str(user_id)
        self.data.setdefault("economy", {}).setdefault(gid, {})[uid] = int(amount)
        await self.save()

    # xp helpers
    def add_xp(self, guild_id: int, user_id: int, amount: int) -> Dict[str, Any]:
        gid = str(guild_id); uid = str(user_id)
        guild_xp = self.data.setdefault("xp", {}).setdefault(gid, {})
        user = guild_xp.setdefault(uid, {"xp": 0, "level": 1, "messages": 0})
        user["xp"] += int(amount)
        user["messages"] += 1
        leveled = False
        while user["xp"] >= user["level"] * 100:
            user["xp"] -= user["level"] * 100
            user["level"] += 1
            leveled = True
        return {"xp": user["xp"], "level": user["level"], "leveled": leveled, "messages": user["messages"]}

    def get_rank(self, guild_id: int, user_id: int) -> Dict[str, int]:
        gid = str(guild_id); uid = str(user_id)
        user = self.data.setdefault("xp", {}).setdefault(gid, {}).get(uid, {"xp": 0, "level": 1, "messages": 0})
        return {"xp": user.get("xp", 0), "level": user.get("level", 1), "messages": user.get("messages", 0)}

    # cooldowns persisted
    def set_cooldown(self, guild_id: int, user_id: int, key: str, ts: int):
        cfg = self.data.setdefault("cooldowns", {}).setdefault(str(guild_id), {})
        cfg.setdefault(str(user_id), {})[key] = ts

    def get_cooldown(self, guild_id: int, user_id: int, key: str) -> int:
        return int(self.data.get("cooldowns", {}).get(str(guild_id), {}).get(str(user_id), {}).get(key, 0))

    # leaderboards helpers
    def top_money(self, guild_id: int, limit: int = 10) -> List[tuple]:
        gid = str(guild_id)
        guild_econ = self.data.get("economy", {}).get(gid, {})
        sorted_ = sorted(guild_econ.items(), key=lambda kv: int(kv[1]), reverse=True)
        return [(int(uid), int(amount)) for uid, amount in sorted_[:limit]]

    def top_xp(self, guild_id: int, limit: int = 10) -> List[tuple]:
        gid = str(guild_id)
        guild_xp = self.data.get("xp", {}).get(gid, {})
        sorted_ = sorted(guild_xp.items(), key=lambda kv: (int(kv[1].get("level", 1)), int(kv[1].get("xp", 0))), reverse=True)
        return [(int(uid), int(info.get("level", 1)), int(info.get("xp", 0))) for uid, info in sorted_[:limit]]

    # giveaway helpers
    def create_giveaway(self, guild_id: int, message_id: int, prize: str, end_time: int, winners: int):
        gid = str(guild_id); mid = str(message_id)
        self.data.setdefault("giveaways", {})[mid] = {
            "guild_id": gid,
            "prize": prize,
            "end_time": end_time,
            "winners": winners,
            "participants": []
        }

    def get_giveaway(self, message_id: int) -> Optional[Dict]:
        return self.data.get("giveaways", {}).get(str(message_id))

    def add_participant(self, message_id: int, user_id: int):
        mid = str(message_id); uid = str(user_id)
        giveaway = self.data.get("giveaways", {}).get(mid)
        if giveaway and uid not in giveaway["participants"]:
            giveaway["participants"].append(uid)

    def remove_giveaway(self, message_id: int):
        mid = str(message_id)
        if mid in self.data.get("giveaways", {}):
            del self.data["giveaways"][mid]

data_manager = DataManager()

# -------------------- Bot init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)
bot.data_manager = data_manager

# -------------------- Utilities --------------------
def _now_ts() -> int:
    return int(datetime.datetime.now().timestamp())

def parse_time(time_str: str) -> Optional[int]:
    """Parse time like 1h, 30m, 2d into seconds"""
    try:
        if time_str.endswith('s'):
            return int(time_str[:-1])
        elif time_str.endswith('m'):
            return int(time_str[:-1]) * 60
        elif time_str.endswith('h'):
            return int(time_str[:-1]) * 3600
        elif time_str.endswith('d'):
            return int(time_str[:-1]) * 86400
    except:
        pass
    return None

# -------------------- Help (single colored embed) --------------------
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="💎 Hoshikuzu — Jeux & Fun", color=discord.Color.purple())
    embed.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    embed.add_field(name="💰 Économie", value="`+balance [@user]`, `+work`, `+daily`, `+give @user <amount>`", inline=False)
    embed.add_field(name="📈 XP & Niveau", value="`+rank [@user]`, `+level [@user]`, `+profile [@user]`", inline=False)
    embed.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    embed.add_field(name="🏆 Leaderboard", value="`+lb money`, `+lb xp`", inline=False)
    embed.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`\nEx: `+gstart 1h 2 Nitro`", inline=False)
    embed.set_footer(text="Bot games léger — commandes avec +. Toutes les données sont sauvegardées.")
    await ctx.send(embed=embed)

# -------------------- Fun Commands --------------------
@bot.command(name="8ball")
async def eightball_cmd(ctx: commands.Context, *, question: str):
    answers = ["Oui.", "Non.", "Peut-être.", "Très probable.", "Je ne pense pas.", "Demande plus tard.", "Certainement!", "Impossible."]
    await ctx.send(f"🎱 **Question:** {question}\n**Réponse:** {random.choice(answers)}")

@bot.command(name="hug")
async def hug_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    if member == ctx.author:
        await ctx.send(f"{ctx.author.mention} se donne un câlin 🤗")
    else:
        await ctx.send(f"{ctx.author.mention} fait un câlin à {member.mention} 🤗")

@bot.command(name="ship")
async def ship_cmd(ctx: commands.Context, a: discord.Member, b: discord.Member):
    score = random.randint(0, 100)
    heart = "💖" if score > 70 else "💔" if score < 30 else "💛"
    await ctx.send(f"💞 Compatibilité entre **{a.display_name}** et **{b.display_name}**: **{score}%** {heart}")

@bot.command(name="meme")
async def meme_cmd(ctx: commands.Context):
    # try to fetch from meme-api, fallback to static images
    fallback = [
        "https://i.imgur.com/1J9Z6.jpg", "https://i.imgur.com/8pQ0Z.jpg", "https://i.imgur.com/2c3KX.jpg"
    ]
    try:
        import requests
        r = requests.get("https://meme-api.com/gimme", timeout=6)
        if r.status_code == 200:
            d = r.json()
            title = d.get("title", "Meme")
            url = d.get("url")
            sub = d.get("subreddit", "unknown")
            embed = discord.Embed(title=title, description=f"From r/{sub}", color=discord.Color.random())
            if url and (url.endswith(".jpg") or url.endswith(".png") or url.endswith(".gif") or "imgur" in url):
                embed.set_image(url=url)
                await ctx.send(embed=embed)
                return
            else:
                await ctx.send(f"{title} — {url}")
                return
    except Exception as e:
        # print for debug but don't spam channel
        print("meme error:", e)
    await ctx.send(random.choice(fallback))

# -------------------- Economy --------------------
COOLDOWNS = {"work": 2*60*60, "daily": 24*60*60}

@bot.command(name="balance", aliases=["bal"])
async def balance_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    await ctx.send(f"💰 {member.mention} a **{bal}** coins.")

@bot.command(name="work")
async def work_cmd(ctx: commands.Context):
    uid = ctx.author.id; gid = ctx.guild.id
    now = _now_ts()
    last = data_manager.get_cooldown(gid, uid, "work")
    if now - last < COOLDOWNS["work"]:
        remain = COOLDOWNS["work"] - (now - last)
        return await ctx.send(f"⏳ Attends encore **{remain//60}** minutes avant de travailler.")
    earn = random.randint(40, 120)
    bal = data_manager.get_balance(gid, uid)
    await data_manager.set_balance(gid, uid, bal + earn)
    data_manager.set_cooldown(gid, uid, "work", now)
    await data_manager.save()
    await ctx.send(f"💼 Tu as travaillé et gagné **{earn}** coins ! Balance: {bal+earn}")

@bot.command(name="daily")
async def daily_cmd(ctx: commands.Context):
    uid = ctx.author.id; gid = ctx.guild.id
    now = _now_ts()
    last = data_manager.get_cooldown(gid, uid, "daily")
    if now - last < COOLDOWNS["daily"]:
        remain = COOLDOWNS["daily"] - (now - last)
        return await ctx.send(f"⏳ Tu as déjà pris ton daily. Attends **{remain//3600}** heures.")
    bonus = 250
    bal = data_manager.get_balance(gid, uid)
    await data_manager.set_balance(gid, uid, bal + bonus)
    data_manager.set_cooldown(gid, uid, "daily", now)
    await data_manager.save()
    await ctx.send(f"🎁 Tu as récupéré ton daily : **{bonus}** coins. Balance: {bal+bonus}")

@bot.command(name="give")
async def give_cmd(ctx: commands.Context, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Montant invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal_from = data_manager.get_balance(gid, uid)
    if bal_from < amount:
        return await ctx.send("Tu n'as pas assez d'argent.")
    await data_manager.set_balance(gid, uid, bal_from - amount)
    bal_to = data_manager.get_balance(gid, member.id)
    await data_manager.set_balance(gid, member.id, bal_to + amount)
    await data_manager.save()
    await ctx.send(f"✅ {ctx.author.mention} a donné **{amount}** coins à {member.mention}.")

@bot.command(name="coinflip")
async def coinflip_cmd(ctx: commands.Context, bet: int, guess: Optional[str] = None):
    if bet <= 0:
        return await ctx.send("Pari invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal = data_manager.get_balance(gid, uid)
    if bal < bet:
        return await ctx.send("Tu n'as pas assez d'argent.")
    outcome = random.choice(["pile", "face"])
    if guess and guess.lower() == outcome:
        await data_manager.set_balance(gid, uid, bal + bet)
        await data_manager.save()
        await ctx.send(f"🎉 C'est **{outcome}** — tu as gagné **{bet}** ! Balance: {bal+bet}")
    else:
        await data_manager.set_balance(gid, uid, bal - bet)
        await data_manager.save()
        await ctx.send(f"😞 C'est **{outcome}** — tu as perdu **{bet}**. Balance: {bal-bet}")

@bot.command(name="slots")
async def slots_cmd(ctx: commands.Context, bet: int):
    if bet <= 0:
        return await ctx.send("Pari invalide.")
    gid = ctx.guild.id; uid = ctx.author.id
    bal = data_manager.get_balance(gid, uid)
    if bal < bet:
        return await ctx.send("Tu n'as pas assez d'argent.")
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    if len(set(res)) == 1:
        win = bet * 5
        await data_manager.set_balance(gid, uid, bal + win)
        await data_manager.save()
        return await ctx.send(f"🎰 {' '.join(res)} — JACKPOT! Tu gagnes **{win}**.")
    elif len(set(res)) == 2:
        win = int(bet * 1.5)
        await data_manager.set_balance(gid, uid, bal + win)
        await data_manager.save()
        return await ctx.send(f"🎰 {' '.join(res)} — Tu gagnes **{win}**.")
    else:
        await data_manager.set_balance(gid, uid, bal - bet)
        await data_manager.save()
        return await ctx.send(f"🎰 {' '.join(res)} — Tu perds **{bet}**.")

# -------------------- Rank / XP commands --------------------
@bot.command(name="rank")
async def rank_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    r = data_manager.get_rank(ctx.guild.id, member.id)
    await ctx.send(f"📊 {member.mention} — Niveau **{r['level']}** • XP **{r['xp']}** / {r['level']*100} • Messages: {r.get('messages',0)}")

@bot.command(name="level")
async def level_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    await rank_cmd(ctx, member)

# -------------------- Leaderboards --------------------
@bot.command(name="lb")
async def lb_cmd(ctx: commands.Context, kind: Optional[str] = "money"):
    kind = (kind or "money").lower()
    if kind == "money":
        top = data_manager.top_money(ctx.guild.id, limit=10)
        if not top: return await ctx.send("Aucune donnée disponible.")
        desc = ""
        for i, (uid, amount) in enumerate(top, start=1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            desc += f"**{i}.** {name} — {amount} coins\n"
        embed = discord.Embed(title="🏆 Top Riches", description=desc, color=discord.Color.gold())
        await ctx.send(embed=embed)
    elif kind == "xp":
        top = data_manager.top_xp(ctx.guild.id, limit=10)
        if not top: return await ctx.send("Aucune donnée disponible.")
        desc = ""
        for i, (uid, level, xp) in enumerate(top, start=1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            desc += f"**{i}.** {name} — Niveau {level} ({xp} XP)\n"
        embed = discord.Embed(title="📈 Top XP", description=desc, color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("Usage: `+lb money` ou `+lb xp`")

# -------------------- Profile --------------------
@bot.command(name="profile")
async def profile_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    r = data_manager.get_rank(ctx.guild.id, member.id)
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    embed = discord.Embed(title=f"👤 Profil — {member.display_name}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url if hasattr(member, "display_avatar") else None)
    embed.add_field(name="Niveau", value=str(r["level"]), inline=True)
    embed.add_field(name="XP", value=str(r["xp"]), inline=True)
    embed.add_field(name="Coins", value=str(bal), inline=True)
    embed.add_field(name="Messages", value=str(r.get("messages", 0)), inline=True)
    await ctx.send(embed=embed)

# -------------------- Giveaway --------------------
@bot.command(name="gstart")
@commands.has_permissions(manage_guild=True)
async def giveaway_start(ctx: commands.Context, duration: str, winners: int, *, prize: str):
    """Lance un giveaway. Ex: +gstart 1h 2 Discord Nitro"""
    seconds = parse_time(duration)
    if not seconds:
        return await ctx.send("❌ Durée invalide ! Utilise: 30s, 5m, 1h, 2d")
    
    if winners < 1:
        return await ctx.send("❌ Il faut au moins 1 gagnant !")
    
    end_time = _now_ts() + seconds
    
    # Créer l'embed du giveaway
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prix:** {prize}\n**Gagnants:** {winners}\n**Temps restant:** {duration}\n\nRéagis avec 🎁 pour participer !",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Se termine dans {duration}")
    embed.timestamp = datetime.datetime.fromtimestamp(end_time)
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎁")
    
    # Sauvegarder le giveaway
    data_manager.create_giveaway(ctx.guild.id, msg.id, prize, end_time, winners)
    await data_manager.save()
    
    # Attendre la fin
    await asyncio.sleep(seconds)
    
    # Récupérer les participants
    giveaway = data_manager.get_giveaway(msg.id)
    if not giveaway:
        return
    
    try:
        msg = await ctx.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎁")
        
        if reaction:
            users = []
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)
            
            if len(users) == 0:
                await ctx.send("❌ Aucun participant au giveaway !")
            elif len(users) < winners:
                winners_list = users
                mentions = " ".join([u.mention for u in winners_list])
                await ctx.send(f"🎉 Pas assez de participants ! Gagnant(s): {mentions}\n**Prix:** {prize}")
            else:
                winners_list = random.sample(users, winners)
                mentions = " ".join([u.mention for u in winners_list])
                await ctx.send(f"🎉 Félicitations ! Gagnant(s): {mentions}\n**Prix:** {prize}")
            
            # Update embed
            embed = msg.embeds[0]
            embed.description = f"**Prix:** {prize}\n**Gagnants:** {', '.join([u.mention for u in winners_list]) if users else 'Aucun'}\n\n✅ Giveaway terminé !"
            embed.color = discord.Color.red()
            await msg.edit(embed=embed)
    
    except Exception as e:
        print(f"Erreur giveaway: {e}")
    
    finally:
        data_manager.remove_giveaway(msg.id)
        await data_manager.save()

# -------------------- Events --------------------
@bot.event
async def on_ready():
    print(f"[GAMES PLUS] connecté comme {bot.user} ({bot.user.id})")

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return
    
    # Vérifier si c'est un giveaway
    giveaway = data_manager.get_giveaway(reaction.message.id)
    if giveaway and str(reaction.emoji) == "🎁":
        data_manager.add_participant(reaction.message.id, user.id)
        await data_manager.save()

# -------------------- Run --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini. Défini la variable d'environnement et relance.")
else:
    bot.run(TOKEN)
