#!/usr/bin/env python3
# Hoshikuzu_games_plus.py
# Games & Fun bot with XP, economy, leaderboard, help, profile, giveaway, level roles

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
        return {"economy": {}, "xp": {}, "cooldowns": {}, "giveaways": {}, "config": {}, "xp_cooldowns": {}, "level_roles": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # Config & XP roles
    def get_levelup_channel(self, guild_id: int) -> Optional[int]:
        return self.data.get("config", {}).get(str(guild_id), {}).get("levelup_channel")
    def set_levelup_channel(self, guild_id: int, channel_id: int):
        self.data.setdefault("config", {}).setdefault(str(guild_id), {})["levelup_channel"] = channel_id

    def add_level_role(self, guild_id: int, level: int, role_id: int):
        gid = str(guild_id)
        self.data.setdefault("level_roles", {}).setdefault(gid, {})[str(level)] = role_id
    def remove_level_role(self, guild_id: int, level: int):
        gid = str(guild_id)
        roles = self.data.setdefault("level_roles", {}).setdefault(gid, {})
        if str(level) in roles: del roles[str(level)]
    def get_level_roles(self, guild_id: int) -> Dict[int, int]:
        gid = str(guild_id)
        roles = self.data.get("level_roles", {}).get(gid, {})
        return {int(l): int(r) for l, r in roles.items()}
    def get_role_for_level(self, guild_id: int, level: int) -> Optional[int]:
        return self.data.get("level_roles", {}).get(str(guild_id), {}).get(str(level))

    # Economy
    def get_balance(self, guild_id: int, user_id: int) -> int:
        gid, uid = str(guild_id), str(user_id)
        return int(self.data.setdefault("economy", {}).setdefault(gid, {}).setdefault(uid, 0))
    async def set_balance(self, guild_id: int, user_id: int, amount: int):
        gid, uid = str(guild_id), str(user_id)
        self.data.setdefault("economy", {}).setdefault(gid, {})[uid] = int(amount)
        await self.save()

    # XP
    def add_xp(self, guild_id: int, user_id: int, amount: int) -> Dict[str, Any]:
        gid, uid = str(guild_id), str(user_id)
        user = self.data.setdefault("xp", {}).setdefault(gid, {}).setdefault(uid, {"xp": 0, "level": 1, "messages": 0})
        user["xp"] += int(amount)
        user["messages"] += 1
        leveled = False
        while user["xp"] >= user["level"] * 100:
            user["xp"] -= user["level"] * 100
            user["level"] += 1
            leveled = True
        return {"xp": user["xp"], "level": user["level"], "leveled": leveled}
    def get_rank(self, guild_id: int, user_id: int) -> Dict[str, int]:
        return self.data.setdefault("xp", {}).setdefault(str(guild_id), {}).get(str(user_id), {"xp": 0, "level": 1})
    def can_gain_xp(self, guild_id: int, user_id: int) -> bool:
        gid, uid = str(guild_id), str(user_id)
        last = self.data.get("xp_cooldowns", {}).get(gid, {}).get(uid, 0)
        now = int(datetime.datetime.now().timestamp())
        return (now - last) >= 60
    def set_xp_cooldown(self, guild_id: int, user_id: int):
        gid, uid = str(guild_id), str(user_id)
        now = int(datetime.datetime.now().timestamp())
        self.data.setdefault("xp_cooldowns", {}).setdefault(gid, {})[uid] = now

data_manager = DataManager()

# -------------------- Bot init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# -------------------- Utils --------------------
def _now_ts(): return int(datetime.datetime.now().timestamp())

# -------------------- HELP --------------------
@bot.command()
async def help(ctx):
    e = discord.Embed(title="💎 Hoshikuzu — Jeux & Fun", color=discord.Color.purple())
    e.add_field(name="🎮 Jeux", value="`+coinflip`, `+slots`", inline=False)
    e.add_field(name="💰 Économie", value="`+balance`, `+work`, `+daily`, `+give`", inline=False)
    e.add_field(name="📈 XP & Niveau", value="`+rank`, `+level`, `+profile`, `+addrole`, `+listroles`", inline=False)
    e.add_field(name="🎁 Giveaway", value="`+gstart <durée> <gagnants> <prix>`", inline=False)
    e.set_footer(text="hoshikuzu | +help")
    await ctx.send(embed=e)

# -------------------- ON READY --------------------
@bot.event
async def on_ready():
    print(f"[GAMES PLUS] connecté comme {bot.user} ({bot.user.id})")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="hoshikuzu | +help")
    )

# -------------------- Run --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini.")
else:
    bot.run(TOKEN)
