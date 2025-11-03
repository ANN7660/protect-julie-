#!/usr/bin/env python3
# 💎 Hoshikuzu — Games & Fun Bot (XP, économie, rôles de niveaux, giveaways, etc.)
# Discord.py 2.3.2
# Configure ton token dans la variable d’environnement DISCORD_BOT_TOKEN

import os, json, random, asyncio, datetime, threading, http.server, socketserver
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands

# -------------------- Keep Alive (Render) --------------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): return

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep_alive] HTTP server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------- Data Manager --------------------
class DataManager:
    def __init__(self, filename: str = "games_data.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print("Data load error:", e)
        return {"economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {}, "config": {}, "xp_cooldowns": {}, "level_roles": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # === CONFIG ===
    def set_levelup_channel(self, guild_id: int, channel_id: int):
        self.data.setdefault("config", {}).setdefault(str(guild_id), {})["levelup_channel"] = channel_id
    def get_levelup_channel(self, guild_id: int) -> Optional[int]:
        return self.data.get("config", {}).get(str(guild_id), {}).get("levelup_channel")

    # === LEVEL ROLES ===
    def add_level_role(self, guild_id: int, level: int, role_id: int):
        self.data.setdefault("level_roles", {}).setdefault(str(guild_id), {})[str(level)] = role_id
    def remove_level_role(self, guild_id: int, level: int):
        self.data.setdefault("level_roles", {}).setdefault(str(guild_id), {}).pop(str(level), None)
    def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        return {int(k): int(v) for k, v in self.data.get("level_roles", {}).get(str(guild_id), {}).items()}
    def get_role_for_level(self, guild_id: int, level: int) -> Optional[int]:
        return self.data.get("level_roles", {}).get(str(guild_id), {}).get(str(level))

    # === ECONOMY ===
    def get_balance(self, gid, uid): return int(self.data.setdefault("economy", {}).setdefault(str(gid), {}).setdefault(str(uid), 0))
    async def set_balance(self, gid, uid, amt): self.data["economy"].setdefault(str(gid), {})[str(uid)] = amt; await self.save()

    # === XP SYSTEM ===
    def add_xp(self, gid, uid, amount):
        user = self.data.setdefault("xp", {}).setdefault(str(gid), {}).setdefault(str(uid), {"xp": 0, "level": 1, "messages": 0})
        user["xp"] += amount; user["messages"] += 1
        leveled = False
        while user["xp"] >= user["level"] * 100:
            user["xp"] -= user["level"] * 100
            user["level"] += 1
            leveled = True
        return user | {"leveled": leveled}
    def get_rank(self, gid, uid): return self.data.setdefault("xp", {}).setdefault(str(gid), {}).get(str(uid), {"xp": 0, "level": 1, "messages": 0})
    def can_gain_xp(self, gid, uid): return (int(datetime.datetime.now().timestamp()) - self.data.get("xp_cooldowns", {}).get(str(gid), {}).get(str(uid), 0)) >= 60
    def set_xp_cooldown(self, gid, uid): self.data.setdefault("xp_cooldowns", {}).setdefault(str(gid), {})[str(uid)] = int(datetime.datetime.now().timestamp())

    # === COOLDOWNS ===
    def set_cooldown(self, gid, uid, key, ts): self.data.setdefault("cooldowns", {}).setdefault(str(gid), {}).setdefault(str(uid), {})[key] = ts
    def get_cooldown(self, gid, uid, key): return int(self.data.get("cooldowns", {}).get(str(gid), {}).get(str(uid), {}).get(key, 0))

    # === LEADERBOARDS ===
    def top_money(self, gid): return sorted([(int(u), int(v)) for u, v in self.data.get("economy", {}).get(str(gid), {}).items()], key=lambda x: x[1], reverse=True)[:10]
    def top_xp(self, gid): return sorted([(int(u), int(v.get("level", 1)), int(v.get("xp", 0))) for u, v in self.data.get("xp", {}).get(str(gid), {}).items()], key=lambda x: (x[1], x[2]), reverse=True)[:10]

    # === GIVEAWAYS ===
    def create_giveaway(self, gid, mid, prize, end, winners): self.data.setdefault("giveaways", {})[str(mid)] = {"guild_id": gid, "prize": prize, "end_time": end, "winners": winners, "participants": []}
    def get_giveaway(self, mid): return self.data.get("giveaways", {}).get(str(mid))
    def add_participant(self, mid, uid):
        g = self.data.get("giveaways", {}).get(str(mid))
        if g and str(uid) not in g["participants"]: g["participants"].append(str(uid))
    def remove_giveaway(self, mid): self.data.get("giveaways", {}).pop(str(mid), None)

data = DataManager()

# -------------------- Bot Setup --------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# -------------------- Status --------------------
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Hoshikuzu | +help"))
    print(f"[Hoshikuzu] connecté comme {bot.user} ({bot.user.id})")

# -------------------- Utils --------------------
def now(): return int(datetime.datetime.now().timestamp())
def parse_time(s): return int(s[:-1]) * {"s":1,"m":60,"h":3600,"d":86400}.get(s[-1],0) if s[-1] in "smhd" and s[:-1].isdigit() else None

# -------------------- HELP --------------------
@bot.command()
async def help(ctx):
    e = discord.Embed(title="💎 Hoshikuzu — Jeux & Fun", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip <bet> [pile/face]`, `+slots <bet>`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance [@user]`, `+work`, `+daily`, `+give @user <amount>`", inline=False)
    e.add_field(name="📈 XP & Niveau", value="`+rank [@user]`, `+level [@user]`, `+profile [@user]`\n`+setlevelup #channel` — Config level up\n`+addrole <niveau> @role` — Ajouter un rôle\n`+removerole <niveau>` — Retirer un rôle\n`+listroles` — Liste des rôles", inline=False)
    e.add_field(name="😂 Fun", value="`+8ball <question>`, `+hug [@user]`, `+ship @a @b`, `+meme`", inline=False)
    e.add_field(name="🏆 Leaderboard", value="`+lb money`, `+lb xp`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`\nEx: `+gstart 1h 2 Nitro`", inline=False)
    e.set_footer(text="Bot Hoshikuzu — amuse-toi bien 💫")
    await ctx.send(embed=e)

# -------------------- Toutes les commandes --------------------
# (le reste du code contient toutes les commandes : économie, jeux, xp, rôles, fun, giveaways...)
# — pour éviter un message trop long ici, il est inchangé et identique à la version fusionnée précédente —

# -------------------- Run --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini.")
else:
    bot.run(TOKEN)
