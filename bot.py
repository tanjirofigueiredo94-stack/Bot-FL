#!/usr/bin/env python3
"""
Futsal Legends - Discord server builder + bot  (v3)

Cria o servidor (estilo Volleyball Legends) E deixa o bot online com:
  • Verificação real com Roblox (código na descrição do perfil) ou botão simples
  • Cargos por botão (posição, região, pings)
  • Slash commands: /verify /unverify /profile /roblox /bio /leaderboard /help
  • Staff: /record /warn /warnings /timeout /clear /panel
  • XP por mensagem, nível, ranking, vitórias/derrotas

Instalação:
    pip install -U "discord.py>=2.4"      (já traz o aiohttp)

Uso:
    python setup_futsal_legends.py --dry-run     # mostra a estrutura (sem token)
    python setup_futsal_legends.py               # cria tudo e FICA ONLINE
    python setup_futsal_legends.py --serve       # só fica online (já criado antes)
    python setup_futsal_legends.py --setup-only  # cria tudo e fecha (botões ficam parados!)
    python setup_futsal_legends.py --lang en     # textos em inglês
    python setup_futsal_legends.py --wipe        # apaga os canais antes de criar
    python setup_futsal_legends.py --repost verify reaction   # reposta só esses painéis

IMPORTANTE: botões e slash commands só funcionam com o bot ONLINE.
Convide o bot com os escopos "bot" e "applications.commands" (o script imprime o link).
Variáveis de ambiente (opcional): DISCORD_TOKEN, GUILD_ID
"""

import argparse
import asyncio
import math
import os
import random
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

# ======================================================================
#  CONFIG  (edite aqui)
# ======================================================================

GAME_NAME = "Futsal Legends"
GAME_LINK = "https://www.roblox.com/games/SEU_ID_AQUI/Futsal-Legends"
GROUP_LINK = "https://www.roblox.com/share/g/208054507"
ACCENT = 0x2ECC71

LANG = "pt"                    # "pt" ou "en" (ou use --lang)

VERIFY_MODE = "button"         # "button" = só clicar e ganhar o cargo | "roblox" = código no perfil do Roblox
MIN_ROBLOX_ACCOUNT_DAYS = 0    # idade mínima da conta Roblox (anti-alt). 0 = desligado
PREFIX = "."                   # prefixo dos comandos de texto (.setup, .verify ...)
SET_NICKNAME = True            # muda o apelido do Discord pro usuário do Roblox
CODE_MINUTES = 10              # validade do código de verificação
XP_COOLDOWN = 60               # segundos entre ganhos de XP por mensagem
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "futsal_data.db")


def tr(pt, en):
    return pt if LANG == "pt" else en


def L(value):
    return value[LANG] if isinstance(value, dict) else value


# ======================================================================
#  CARGOS
# ======================================================================

OWNER_ROLE = "👑 Owner"
DEV_ROLE = "💻 Developer"
ADMIN_ROLE = "🔒 Admin"
MOD_ROLE = "🛡️ Moderator"
VERIFIED_ROLE = "✅ Verified"
MUTED_ROLE = "🔇 Muted"
STAFF_ROLES = [OWNER_ROLE, ADMIN_ROLE, MOD_ROLE, DEV_ROLE]

POSITION_ROLES = ["🧤 Goalkeeper", "🛡️ Defender", "⚡ Winger", "🎯 Pivot"]
REGION_ROLES = ["🇧🇷 Brazil", "🌎 LATAM", "🇺🇸 North America", "🌍 Europe", "🌏 Asia"]
PING_ROLES = ["📢 Announcements Ping", "👀 Sneak Peek Ping", "🎁 Codes Ping", "🎉 Events Ping"]

ROLES = [
    {"name": OWNER_ROLE, "color": 0xF1C40F, "admin": True, "hoist": True},
    {"name": ADMIN_ROLE, "color": 0xE74C3C, "admin": True, "hoist": True},
    {"name": DEV_ROLE, "color": 0x3498DB, "hoist": True, "perms": dict(
        manage_channels=True, manage_messages=True, manage_threads=True,
        view_audit_log=True)},
    {"name": MOD_ROLE, "color": 0x2ECC71, "hoist": True, "perms": dict(
        kick_members=True, ban_members=True, moderate_members=True,
        manage_messages=True, manage_threads=True, move_members=True,
        mute_members=True, deafen_members=True, view_audit_log=True)},
    {"name": "🎥 Content Creator", "color": 0x9B59B6, "hoist": True},
    {"name": "💎 Booster", "color": 0xF47FFF},
    {"name": VERIFIED_ROLE, "color": 0x95A5A6},
    {"name": MUTED_ROLE, "color": 0x546E7A},
    {"name": "🧤 Goalkeeper", "color": 0xF39C12},
    {"name": "🛡️ Defender", "color": 0x2980B9},
    {"name": "⚡ Winger", "color": 0x1ABC9C},
    {"name": "🎯 Pivot", "color": 0xE67E22},
    {"name": "🇧🇷 Brazil", "color": 0x27AE60},
    {"name": "🌎 LATAM", "color": 0xD35400},
    {"name": "🇺🇸 North America", "color": 0x2C3E50},
    {"name": "🌍 Europe", "color": 0x8E44AD},
    {"name": "🌏 Asia", "color": 0xC0392B},
    {"name": "📢 Announcements Ping", "color": 0x7F8C8D, "mention": True},
    {"name": "👀 Sneak Peek Ping", "color": 0x7F8C8D, "mention": True},
    {"name": "🎁 Codes Ping", "color": 0x7F8C8D, "mention": True},
    {"name": "🎉 Events Ping", "color": 0x7F8C8D, "mention": True},
]

REACTION_GROUPS = [
    ({"pt": "⚽ Posição", "en": "⚽ Position"},
     {"pt": "Escolha sua posição favorita. Clique de novo pra remover.",
      "en": "Pick your favorite position. Click again to remove."},
     POSITION_ROLES),
    ({"pt": "🌎 Região", "en": "🌎 Region"},
     {"pt": "De onde você joga?", "en": "Where do you play from?"},
     REGION_ROLES),
    ({"pt": "🔔 Notificações", "en": "🔔 Pings"},
     {"pt": "Escolha o que você quer ser avisado.",
      "en": "Choose what you want to be notified about."},
     PING_ROLES),
]

# ======================================================================
#  TEXTOS DAS MENSAGENS
# ======================================================================

BUG_TEMPLATE = {
    "pt": ("Formato do report:\n"
           "• Descrição do bug\n• Passos pra reproduzir\n"
           "• Dispositivo (PC / Celular / Console)\n• Print ou vídeo\n\n"
           "Procure antes pra não duplicar. Um bug por post."),
    "en": ("Report format:\n"
           "• Bug description\n• Steps to reproduce\n"
           "• Device (PC / Mobile / Console)\n• Screenshot or video\n\n"
           "Search first to avoid duplicates. One bug per post."),
}

SUGGESTION_TEMPLATE = {
    "pt": "Dê sua sugestão! Uma ideia por post. Explique o que é e por que ajudaria o jogo.",
    "en": "Share your idea! One suggestion per post. Explain what it is and why it helps the game.",
}

RULES = {
    "pt": [
        "**Respeito acima de tudo.** Sem ofensas, assédio, preconceito ou discriminação.",
        "**Sem spam, flood ou divulgação** de outros servidores, canais ou grupos.",
        "**Sem conteúdo NSFW, gore ou ilegal.**",
        "**Use cada canal pro seu propósito.**",
        "**Sem trapaça, exploits ou hacks.** Achou um bug? Reporte em #bug-reports.",
        "**Sem golpes** nem venda de contas/itens por dinheiro real.",
        "**Siga os Termos do Discord e do Roblox.**",
        "**A decisão da staff é final.** Se discordar, fale com um moderador por DM.",
    ],
    "en": [
        "**Respect everyone.** No insults, harassment, bigotry or discrimination.",
        "**No spam, flooding or advertising** other servers, channels or groups.",
        "**No NSFW, gore or illegal content.**",
        "**Use each channel for its purpose.**",
        "**No cheating, exploits or hacks.** Found a bug? Report it in #bug-reports.",
        "**No scams** or selling accounts/items for real money.",
        "**Follow the Discord and Roblox Terms of Service.**",
        "**Staff decisions are final.** If you disagree, DM a moderator.",
    ],
}

FAQ = {
    "pt": [
        ("Como eu pego os códigos?", "Todos os códigos ativos ficam no canal **codes**."),
        ("Como eu reporto um bug?", "Crie um post em **bug-reports** seguindo o formato fixado."),
        ("Como eu dou uma sugestão?", "Crie um post em **suggestions**. A comunidade e a staff avaliam."),
        ("Como eu entro em um scrim?", "Entre em um canal de voz **Scrims**: **HOME** ou **AWAY**, do tamanho que quiser (2v2 até 6v6)."),
        ("Como eu pego cargos?", "Em **reaction-role**, clique nos botões."),
        ("Como vejo meu perfil?", "Use **/profile** em qualquer canal. Pra vincular o Roblox, use **/verify**."),
        ("Não consigo ver os canais.", "Vá em **verify** e faça a verificação."),
    ],
    "en": [
        ("How do I get codes?", "All active codes are posted in **codes**."),
        ("How do I report a bug?", "Create a post in **bug-reports** following the pinned format."),
        ("How do I make a suggestion?", "Create a post in **suggestions**. The community and staff review it."),
        ("How do I join a scrim?", "Join a **Scrims** voice channel: **HOME** or **AWAY**, any size (2v2 to 6v6)."),
        ("How do I get roles?", "In **reaction-role**, click the buttons."),
        ("How do I see my profile?", "Use **/profile** in any channel. To link Roblox, use **/verify**."),
        ("I can't see any channels.", "Go to **verify** and complete the verification."),
    ],
}

INFO = {
    "pt": ("Bem-vindo ao servidor oficial de **{g}**! ⚽\n\n"
           "Aqui você acompanha novidades, pega códigos, vê sneak peeks, "
           "reporta bugs, dá sugestões e marca scrims com a comunidade."),
    "en": ("Welcome to the official **{g}** server! ⚽\n\n"
           "Follow updates, grab codes, see sneak peeks, report bugs, "
           "share suggestions and set up scrims with the community."),
}

CODES = {
    "pt": ("Nenhum código ativo no momento.\n\n"
           "**Como resgatar:** abra o jogo, clique no botão de códigos e cole o código.\n"
           "Pegue o cargo **🎁 Codes Ping** em reaction-role pra ser avisado."),
    "en": ("No active codes right now.\n\n"
           "**How to redeem:** open the game, click the codes button and paste the code.\n"
           "Get the **🎁 Codes Ping** role in reaction-role to be notified."),
}

VERIFY_ROBLOX = {
    "pt": ("Pra liberar o servidor, vincule sua conta do **Roblox**.\n\n"
           "**1.** Clique em **Verificar com Roblox**\n"
           "**2.** Digite seu usuário do Roblox\n"
           "**3.** Cole o código que o bot te enviar na **descrição (About)** do seu perfil do Roblox\n"
           "**4.** Clique em **Já coloquei o código**\n\n"
           "Depois de verificar, você pode apagar o código do perfil.\n"
           "Ao verificar, você aceita as regras. Comandos úteis: `/profile`, `/verify`, `/unverify`."),
    "en": ("To unlock the server, link your **Roblox** account.\n\n"
           "**1.** Click **Verify with Roblox**\n"
           "**2.** Type your Roblox username\n"
           "**3.** Paste the code the bot sends you into your Roblox profile **About** section\n"
           "**4.** Click **I added the code**\n\n"
           "After verifying you can remove the code from your profile.\n"
           "By verifying you agree to the rules. Useful commands: `/profile`, `/verify`, `/unverify`."),
}

VERIFY_BUTTON = {
    "pt": "Clique no botão abaixo pra liberar o acesso ao servidor.\nAo verificar, você aceita as regras.",
    "en": "Click the button below to unlock the server.\nBy verifying you agree to the rules.",
}

CREATOR = {
    "pt": ("Faz conteúdo de **{g}**? Você pode ganhar o cargo **🎥 Content Creator**!\n\n"
           "**Requisitos (edite aqui):**\n• Conteúdo regular do jogo\n"
           "• Canal/perfil público\n• Respeitar as regras\n\n"
           "Pra aplicar, abra um ticket ou fale com um moderador."),
    "en": ("Make **{g}** content? You can earn the **🎥 Content Creator** role!\n\n"
           "**Requirements (edit this):**\n• Regular game content\n"
           "• Public channel/profile\n• Follow the rules\n\n"
           "To apply, open a ticket or message a moderator."),
}

GIVEAWAY = {
    "pt": "Convide amigos pro servidor e concorra a prêmios!\nOs sorteios e regras serão anunciados aqui.",
    "en": "Invite friends to the server and win prizes!\nGiveaways and rules will be announced here.",
}

WELCOME = {
    "pt": "👋 Bem-vindo(a) {m} ao **{g}**! Vá em {v} pra liberar o servidor.",
    "en": "👋 Welcome {m} to **{g}**! Head to {v} to unlock the server.",
}

# ======================================================================
#  TEMPLATE DO SERVIDOR
# ======================================================================
# access: "public" | "verified" | "staff"
# type:   text | news | forum | stage | voice

TEMPLATE = [
    {"category": None, "access": "public", "channels": [
        {"type": "text", "key": "joins", "name": "｢👋｣joins", "readonly": True},
        {"type": "text", "key": "verify", "name": "｢☑️｣verify", "readonly": True},
    ]},
    {"category": "📖〔INFORMATION〕📖", "access": "public", "channels": [
        {"type": "text", "key": "rules", "name": "｢📜｣rules", "readonly": True},
        {"type": "text", "key": "information", "name": "｢📘｣information", "readonly": True},
        {"type": "text", "key": "faq", "name": "｢❓｣faq", "readonly": True},
        {"type": "text", "key": "codes", "name": "｢⚡｣codes", "readonly": True},
        {"type": "text", "key": "giveaway", "name": "｢💸｣invite-giveaway", "readonly": True},
    ]},
    {"category": "📍〔IMPORTANT〕📍", "access": "verified", "channels": [
        {"type": "news", "key": "announcements", "name": "｢📢｣announcements", "readonly": True},
        {"type": "news", "key": "sub-announcements", "name": "｢🔔｣sub-announcements", "readonly": True},
        {"type": "text", "key": "sneak", "name": "｢👀｣sneak-peeks", "readonly": True},
        {"type": "text", "key": "reaction", "name": "｢✅｣reaction-role", "readonly": True},
        {"type": "text", "key": "creator", "name": "｢📷｣content-creator-program", "readonly": True},
    ]},
    {"category": "🏆〔EVENTS〕🏆", "access": "verified", "channels": [
        {"type": "stage", "name": "｢🎭｣stage"},
    ]},
    {"category": "🎯〔COMMUNITY〕🎯", "access": "verified", "channels": [
        {"type": "text", "name": "｢💬｣general", "slowmode": 3},
        {"type": "text", "name": "｢🌎｣international-chat", "slowmode": 3},
        {"type": "text", "name": "｢❓｣questions", "slowmode": 5},
    ]},
    {"category": "📱〔MISCELLANEOUS〕📱", "access": "verified", "channels": [
        {"type": "text", "name": "｢🤖｣bot-commands"},
        {"type": "text", "name": "｢📷｣clips", "slowmode": 10},
    ]},
    {"category": "🔀〔FEEDBACK〕🔀", "access": "verified", "channels": [
        {"type": "forum", "key": "suggestions", "name": "｢💡｣suggestions",
         "topic": SUGGESTION_TEMPLATE, "slowmode": 30,
         "tags": [("Pending", "⏳"), ("Approved", "✅"), ("Denied", "❌"), ("Implemented", "🚀")]},
        {"type": "forum", "key": "bugs", "name": "｢🐛｣bug-reports",
         "topic": BUG_TEMPLATE, "slowmode": 30,
         "tags": [("Open", "🐛"), ("Investigating", "🔎"), ("Fixed", "✅"), ("Not a bug", "🚫")]},
    ]},
    *[
        {"category": f"⚽ Scrims - {n}v{n}", "access": "verified", "channels": [
            {"type": "voice", "name": "⚽ HOME", "limit": n},
            {"type": "voice", "name": "⚽ AWAY", "limit": n},
        ]}
        for n in (2, 3, 4, 5, 6)
    ],
    {"category": "🔒〔STAFF〕🔒", "access": "staff", "channels": [
        {"type": "text", "name": "｢🔒｣chat-admin"},
        {"type": "text", "name": "｢🛡️｣chat-mod"},
        {"type": "text", "name": "｢💻｣chat-devs"},
        {"type": "text", "name": "｢📋｣logs"},
        {"type": "text", "name": "｢🔨｣punishments"},
        {"type": "voice", "name": "🔊 Staff Voice"},
    ]},
]

ICONS = {"text": "#", "news": "📣", "forum": "🗂️", "stage": "🎭", "voice": "🔊"}


def print_structure():
    print(f"\n=== {GAME_NAME} ===\n\nCargos:")
    for r in ROLES:
        print(f"  • {r['name']}")
    print("\nEstrutura:")
    for block in TEMPLATE:
        print(f"\n  ▸ {block['category'] or '(sem categoria)'}   [{block['access']}]")
        for c in block["channels"]:
            extra = f"  (limite {c['limit']})" if "limit" in c else ""
            ro = "  [somente leitura]" if c.get("readonly") else ""
            print(f"      {ICONS[c['type']]} {c['name']}{extra}{ro}")
    print()


# ======================================================================
#  BANCO DE DADOS (SQLite)
# ======================================================================

class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                discord_id INTEGER PRIMARY KEY,
                roblox_id INTEGER UNIQUE,
                roblox_name TEXT,
                verified_at TEXT,
                bio TEXT DEFAULT '',
                xp INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_xp REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS warns(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER, user_id INTEGER, mod_id INTEGER,
                reason TEXT, ts TEXT
            );
        """)
        self.c.commit()

    def user(self, uid):
        return self.c.execute("SELECT * FROM users WHERE discord_id=?", (uid,)).fetchone()

    def ensure(self, uid):
        self.c.execute("INSERT OR IGNORE INTO users(discord_id) VALUES(?)", (uid,))
        self.c.commit()

    def by_roblox(self, rid):
        return self.c.execute("SELECT * FROM users WHERE roblox_id=?", (rid,)).fetchone()

    def link(self, uid, rid, rname):
        self.ensure(uid)
        self.c.execute(
            "UPDATE users SET roblox_id=?, roblox_name=?, verified_at=? WHERE discord_id=?",
            (rid, rname, datetime.now(timezone.utc).isoformat(), uid))
        self.c.commit()

    def unlink(self, uid):
        self.c.execute(
            "UPDATE users SET roblox_id=NULL, roblox_name=NULL, verified_at=NULL WHERE discord_id=?",
            (uid,))
        self.c.commit()

    def set_bio(self, uid, bio):
        self.ensure(uid)
        self.c.execute("UPDATE users SET bio=? WHERE discord_id=?", (bio, uid))
        self.c.commit()

    def add_xp(self, uid, amount, now, cooldown):
        self.ensure(uid)
        row = self.user(uid)
        if now - (row["last_xp"] or 0) < cooldown:
            return False
        self.c.execute("UPDATE users SET xp=xp+?, last_xp=? WHERE discord_id=?", (amount, now, uid))
        self.c.commit()
        return True

    def add_result(self, uid, win):
        self.ensure(uid)
        col = "wins" if win else "losses"
        bonus = 50 if win else 15
        self.c.execute(f"UPDATE users SET {col}={col}+1, xp=xp+? WHERE discord_id=?", (bonus, uid))
        self.c.commit()

    def rank(self, uid):
        row = self.c.execute(
            "SELECT COUNT(*)+1 AS r FROM users WHERE xp > (SELECT xp FROM users WHERE discord_id=?)",
            (uid,)).fetchone()
        return row["r"]

    def top(self, column, limit=10):
        assert column in ("xp", "wins")
        return self.c.execute(
            f"SELECT * FROM users WHERE {column}>0 ORDER BY {column} DESC LIMIT ?", (limit,)).fetchall()

    def add_warn(self, gid, uid, mod, reason):
        self.c.execute("INSERT INTO warns(guild_id,user_id,mod_id,reason,ts) VALUES(?,?,?,?,?)",
                       (gid, uid, mod, reason, datetime.now(timezone.utc).isoformat()))
        self.c.commit()

    def warns(self, gid, uid):
        return self.c.execute(
            "SELECT * FROM warns WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10",
            (gid, uid)).fetchall()


def level_for(xp):
    return int(math.sqrt(max(xp, 0) / 100))


def xp_for(level):
    return level * level * 100


def progress_bar(cur, total, size=10):
    filled = 0 if total <= 0 else min(size, int(size * cur / total))
    return "█" * filled + "░" * (size - filled)


# ======================================================================
#  API DO ROBLOX
# ======================================================================

class RobloxError(Exception):
    pass


async def _rbx(session, method, url, **kw):
    import aiohttp
    try:
        async with session.request(method, url, timeout=aiohttp.ClientTimeout(total=10), **kw) as r:
            if r.status != 200:
                raise RobloxError(f"HTTP {r.status}")
            return await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        raise RobloxError(str(e))


async def rbx_find(session, username):
    data = await _rbx(session, "POST", "https://users.roblox.com/v1/usernames/users",
                      json={"usernames": [username], "excludeBannedUsers": True})
    items = data.get("data", [])
    return items[0] if items else None


async def rbx_info(session, uid):
    return await _rbx(session, "GET", f"https://users.roblox.com/v1/users/{uid}")


async def rbx_avatar(session, uid):
    try:
        data = await _rbx(session, "GET",
                          "https://thumbnails.roblox.com/v1/users/avatar-headshot"
                          f"?userIds={uid}&size=420x420&format=Png&isCircular=false")
        return data["data"][0].get("imageUrl")
    except (RobloxError, KeyError, IndexError):
        return None


async def rbx_count(session, uid, kind):
    try:
        data = await _rbx(session, "GET", f"https://friends.roblox.com/v1/users/{uid}/{kind}/count")
        return data.get("count")
    except RobloxError:
        return None


def parse_rbx_date(s):
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def make_code():
    return "FL-" + "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))


# ======================================================================
#  BOT
# ======================================================================

def parse_args():
    p = argparse.ArgumentParser(description=f"Cria o servidor {GAME_NAME} e roda o bot")
    p.add_argument("--token", default=os.getenv("DISCORD_TOKEN"))
    p.add_argument("--guild", default=os.getenv("GUILD_ID"), help="ID do servidor")
    p.add_argument("--lang", choices=["pt", "en"], default=LANG)
    p.add_argument("--wipe", action="store_true", help="apaga todos os canais antes")
    p.add_argument("--yes", action="store_true", help="não pedir confirmação do --wipe")
    p.add_argument("--no-messages", action="store_true", help="não postar mensagens")
    p.add_argument("--repost", nargs="*", default=None, metavar="CANAL",
                   help="repostar mensagens (sem argumentos = todas; ou: verify reaction rules faq codes ...)")
    p.add_argument("--serve", action="store_true", help="só deixa o bot online (sem criar)")
    p.add_argument("--setup-only", action="store_true", help="cria e fecha (botões ficam parados)")
    p.add_argument("--welcome", action="store_true",
                   help="boas-vindas em joins (ativa Server Members Intent no portal)")
    p.add_argument("--no-prefix", action="store_true",
                   help="desliga comandos de texto (.setup/.verify) e não exige Message Content Intent")
    p.add_argument("--dry-run", action="store_true", help="mostra a estrutura e sai")
    return p.parse_args()


def main():
    global LANG
    args = parse_args()
    LANG = args.lang

    if args.dry_run:
        print_structure()
        return

    try:
        import discord  # noqa: F401
    except ImportError:
        sys.exit('discord.py não instalado. Rode: pip install -U "discord.py>=2.4"')

    token = args.token or input("Token do bot: ").strip()
    gid = args.guild or input("ID do servidor (Enter = detectar): ").strip()

    if args.wipe and not args.yes and not args.serve:
        print("\n⚠ --wipe vai APAGAR todos os canais do servidor.")
        if input('Digite "APAGAR" pra confirmar: ').strip() != "APAGAR":
            sys.exit("Cancelado.")

    import discord
    bot = make_bot(args, int(gid) if gid else None)
    try:
        bot.run(token)
    except discord.PrivilegedIntentsRequired:
        sys.exit("\nERRO: ative o MESSAGE CONTENT INTENT no portal do bot:\n"
                 "  discord.com/developers/applications > seu bot > Bot > Privileged Gateway Intents\n"
                 "  > Message Content Intent (ON) > Save.\n"
                 "Ou rode com --no-prefix pra usar só os slash commands (/setup, /panel).")


def make_bot(args, guild_id):
    import aiohttp
    import discord
    from discord import app_commands, ui

    PO = discord.PermissionOverwrite
    db = DB(DB_FILE)
    pending = {}  # discord_id -> {rid, rname, code, exp}

    # ---------------- utilidades ----------------

    async def reply(interaction, content=None, **kw):
        kw.setdefault("ephemeral", True)
        if interaction.response.is_done():
            await interaction.followup.send(content, **kw)
        else:
            await interaction.response.send_message(content, **kw)

    def is_staff(member):
        return member.guild_permissions.administrator or any(
            r.name in STAFF_ROLES for r in member.roles)

    def emb(title, desc, color=ACCENT):
        return discord.Embed(title=title, description=desc, colour=color)

    async def mod_log(guild, title, text):
        ch = next((c for c in guild.text_channels if c.name.endswith("logs")), None)
        if ch:
            try:
                await ch.send(embed=emb(title, text, 0xE67E22))
            except discord.HTTPException:
                pass

    API_ERRORS = (RobloxError, aiohttp.ClientError, asyncio.TimeoutError)

    class SafeView(ui.View):
        async def on_error(self, interaction, error, item):
            traceback.print_exception(type(error), error, error.__traceback__)
            await reply(interaction, tr("Algo deu errado. Tente de novo.",
                                        "Something went wrong. Try again."))

    class SafeModal(ui.Modal):
        async def on_error(self, interaction, error):
            traceback.print_exception(type(error), error, error.__traceback__)
            await reply(interaction, tr("Algo deu errado. Tente de novo.",
                                        "Something went wrong. Try again."))

    # ---------------- cargos por botão ----------------

    async def toggle_role(interaction, role_name, only_add=False):
        await interaction.response.defer(ephemeral=True)
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role is None:
            return await interaction.followup.send(
                tr("Cargo não encontrado. Rode o setup de novo.",
                   "Role not found. Run the setup again."), ephemeral=True)
        member = interaction.user
        try:
            if role in member.roles and not only_add:
                await member.remove_roles(role, reason="Botão de cargo")
                msg = f"➖ {role.name}"
            elif role in member.roles:
                msg = tr("✅ Você já está verificado.", "✅ You're already verified.")
            else:
                await member.add_roles(role, reason="Botão de cargo")
                msg = f"➕ {role.name}"
        except discord.Forbidden:
            msg = tr("Não consigo dar esse cargo: o cargo do BOT precisa estar ACIMA dele "
                     "na lista de cargos do servidor.",
                     "I can't give that role: the BOT's role must be ABOVE it in the server's role list.")
        await interaction.followup.send(msg, ephemeral=True)

    class RoleButton(ui.Button):
        def __init__(self, role_name):
            emoji, label = role_name.split(" ", 1)
            super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
                             custom_id=f"fl:role:{role_name}")
            self.role_name = role_name

        async def callback(self, interaction):
            await toggle_role(interaction, self.role_name)

    def role_view(role_names):
        v = SafeView(timeout=None)
        for r in role_names:
            v.add_item(RoleButton(r))
        return v

    # ---------------- verificação ----------------

    async def finish_verification(interaction, member, rid, rname, returning=False):
        """Assume que a interação já recebeu defer(ephemeral=True)."""
        role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE)
        if role is None:
            return await interaction.followup.send(
                tr("Cargo Verified não existe. Rode o setup de novo.",
                   "Verified role doesn't exist. Run the setup again."), ephemeral=True)
        try:
            await member.add_roles(role, reason="Verificação Roblox")
        except discord.Forbidden:
            return await interaction.followup.send(
                tr("Não consigo te dar o cargo: o cargo do BOT precisa estar ACIMA de "
                   "✅ Verified na lista de cargos. Avise um admin.",
                   "I can't give you the role: the BOT's role must be ABOVE ✅ Verified in the role list. "
                   "Tell an admin."), ephemeral=True)
        db.link(member.id, rid, rname)
        if SET_NICKNAME:
            try:
                await member.edit(nick=rname[:32], reason="Verificação Roblox")
            except discord.HTTPException:
                pass
        title = tr("Bem-vindo de volta!", "Welcome back!") if returning else tr("Verificado!", "Verified!")
        e = emb(f"✅ {title}",
                tr(f"Conta vinculada: **[{rname}](https://www.roblox.com/users/{rid}/profile)**\n"
                   "Você já pode ver o servidor. Use `/profile` pra ver seu perfil.",
                   f"Linked account: **[{rname}](https://www.roblox.com/users/{rid}/profile)**\n"
                   "You can now see the server. Use `/profile` to see your profile."))
        await interaction.followup.send(embed=e, ephemeral=True)
        await mod_log(interaction.guild, "✅ Verify",
                      f"{member.mention} → **{rname}** (`{rid}`)")

    class ConfirmView(SafeView):
        def __init__(self):
            super().__init__(timeout=CODE_MINUTES * 60)

        @ui.button(label=tr("Já coloquei o código", "I added the code"),
                   emoji="✅", style=discord.ButtonStyle.success)
        async def done(self, interaction, button):
            await interaction.response.defer(ephemeral=True)
            p = pending.get(interaction.user.id)
            if not p or p["exp"] < time.time():
                return await interaction.followup.send(
                    tr("Código expirado. Use /verify pra gerar outro.",
                       "Code expired. Use /verify to get a new one."), ephemeral=True)
            try:
                info = await rbx_info(bot.session, p["rid"])
            except API_ERRORS:
                return await interaction.followup.send(
                    tr("Não consegui falar com o Roblox agora. Tente em instantes.",
                       "Couldn't reach Roblox right now. Try again shortly."), ephemeral=True)
            if p["code"] not in (info.get("description") or ""):
                return await interaction.followup.send(
                    tr(f"Não achei o código `{p['code']}` na descrição do perfil de **{p['rname']}**.\n"
                       "Cole o código na seção **About**, salve, e clique de novo.",
                       f"I couldn't find the code `{p['code']}` in **{p['rname']}**'s profile.\n"
                       "Paste it in the **About** section, save, and click again."), ephemeral=True)
            pending.pop(interaction.user.id, None)
            await finish_verification(interaction, interaction.user, p["rid"], info.get("name", p["rname"]))

    class RobloxModal(SafeModal, title=tr("Verificação Roblox", "Roblox verification")):
        username = ui.TextInput(label=tr("Seu usuário do Roblox", "Your Roblox username"),
                                placeholder="Builderman", min_length=3, max_length=20)

        async def on_submit(self, interaction):
            await interaction.response.defer(ephemeral=True)
            name = self.username.value.strip().lstrip("@")
            try:
                found = await rbx_find(bot.session, name)
                if not found:
                    return await interaction.followup.send(
                        tr(f"Não encontrei o usuário **{name}** no Roblox. Confira a escrita.",
                           f"I couldn't find **{name}** on Roblox. Check the spelling."), ephemeral=True)
                info = await rbx_info(bot.session, found["id"])
            except API_ERRORS:
                return await interaction.followup.send(
                    tr("Não consegui falar com o Roblox agora. Tente em instantes.",
                       "Couldn't reach Roblox right now. Try again shortly."), ephemeral=True)

            rid, rname = found["id"], found["name"]
            other = db.by_roblox(rid)
            if other and other["discord_id"] != interaction.user.id:
                return await interaction.followup.send(
                    tr("Essa conta do Roblox já está vinculada a outro usuário do Discord. "
                       "Fale com a staff se for sua.",
                       "That Roblox account is already linked to another Discord user. "
                       "Contact staff if it's yours."), ephemeral=True)

            created = parse_rbx_date(info.get("created"))
            if MIN_ROBLOX_ACCOUNT_DAYS and created:
                age = (datetime.now(timezone.utc) - created).days
                if age < MIN_ROBLOX_ACCOUNT_DAYS:
                    return await interaction.followup.send(
                        tr(f"Sua conta do Roblox precisa ter pelo menos {MIN_ROBLOX_ACCOUNT_DAYS} dias.",
                           f"Your Roblox account must be at least {MIN_ROBLOX_ACCOUNT_DAYS} days old."),
                        ephemeral=True)

            if other and other["discord_id"] == interaction.user.id:
                return await finish_verification(interaction, interaction.user, rid, rname, returning=True)

            code = make_code()
            pending[interaction.user.id] = {"rid": rid, "rname": rname, "code": code,
                                            "exp": time.time() + CODE_MINUTES * 60}
            e = emb(tr("🔐 Quase lá!", "🔐 Almost there!"),
                    tr(f"Conta: **{rname}**\n\n"
                       f"**1.** Copie este código:\n```{code}```\n"
                       "**2.** Abra seu perfil do Roblox, clique em editar e cole na **descrição (About)**. Salve.\n"
                       f"**3.** Clique em **Já coloquei o código** abaixo.\n\n"
                       f"O código vale por {CODE_MINUTES} minutos.",
                       f"Account: **{rname}**\n\n"
                       f"**1.** Copy this code:\n```{code}```\n"
                       "**2.** Open your Roblox profile, edit it and paste the code into the **About** section. Save.\n"
                       f"**3.** Click **I added the code** below.\n\n"
                       f"The code is valid for {CODE_MINUTES} minutes."))
            await interaction.followup.send(embed=e, view=ConfirmView(), ephemeral=True)

    async def start_verification(interaction):
        member = interaction.user
        if VERIFY_MODE != "roblox":
            return await toggle_role(interaction, VERIFIED_ROLE, only_add=True)
        row = db.user(member.id)
        if row and row["roblox_id"]:
            await interaction.response.defer(ephemeral=True)
            return await finish_verification(interaction, member, row["roblox_id"],
                                             row["roblox_name"], returning=True)
        await interaction.response.send_modal(RobloxModal())

    class VerifyButton(ui.Button):
        def __init__(self):
            label = tr("Verificar com Roblox", "Verify with Roblox") if VERIFY_MODE == "roblox" else tr("Verificar", "Verify")
            super().__init__(label=label, emoji="✅", style=discord.ButtonStyle.success,
                             custom_id="fl:verify")

        async def callback(self, interaction):
            await start_verification(interaction)

    class VerifyView(SafeView):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(VerifyButton())

    # ---------------- estrutura do servidor ----------------

    def make_overwrites(guild, roles, access, readonly, ctype):
        ow = {}
        everyone = guild.default_role
        verified = roles[VERIFIED_ROLE]

        if access == "public":
            ow[everyone] = PO(view_channel=True, read_message_history=True,
                              add_reactions=True, send_messages=not readonly,
                              create_public_threads=not readonly,
                              send_messages_in_threads=not readonly)
        elif access == "verified":
            ow[everyone] = PO(view_channel=False)
            ow[verified] = PO(view_channel=True, read_message_history=True,
                              add_reactions=True, connect=True,
                              speak=(ctype != "stage"),
                              request_to_speak=(ctype == "stage"),
                              send_messages=not readonly,
                              create_public_threads=not readonly,
                              send_messages_in_threads=not readonly)
        else:
            ow[everyone] = PO(view_channel=False)

        for name in STAFF_ROLES:
            ow[roles[name]] = PO(view_channel=True, send_messages=True,
                                 manage_messages=True, manage_threads=True,
                                 connect=True, speak=True, mute_members=True,
                                 move_members=True, read_message_history=True)

        ow[roles[MUTED_ROLE]] = PO(send_messages=False, add_reactions=False,
                                   speak=False, create_public_threads=False,
                                   send_messages_in_threads=False)
        return ow

    async def create_roles(guild):
        print("\n[1/4] Cargos")
        roles = {}
        for spec in ROLES:
            name = spec["name"]
            existing = discord.utils.get(guild.roles, name=name)
            if existing:
                roles[name] = existing
                print(f"  = {name}")
                continue
            if spec.get("admin"):
                perms = discord.Permissions(administrator=True)
            else:
                perms = discord.Permissions(**spec.get("perms", {}))
            roles[name] = await guild.create_role(
                name=name, colour=discord.Colour(spec["color"]), permissions=perms,
                hoist=spec.get("hoist", False), mentionable=spec.get("mention", False),
                reason=f"Setup {GAME_NAME}")
            print(f"  + {name}")
        return roles

    def find_existing(guild, category, name):
        cid = category.id if category else None
        for c in guild.channels:
            if c.category_id == cid and not isinstance(c, discord.CategoryChannel) \
                    and c.name.lower() == name.lower():
                return c
        return None

    async def ensure_channel(guild, category, spec, ow, community):
        ctype, name = spec["type"], spec["name"]
        topic = L(spec["topic"]) if "topic" in spec else None
        slow = spec.get("slowmode", 0)

        if not community:
            ctype = {"news": "text", "forum": "text", "stage": "voice"}.get(ctype, ctype)

        existing = find_existing(guild, category, name)
        if existing:
            try:
                kw = {"overwrites": ow}
                if isinstance(existing, (discord.TextChannel, discord.ForumChannel)):
                    kw["topic"] = topic
                    kw["slowmode_delay"] = slow
                elif isinstance(existing, discord.VoiceChannel):
                    kw["user_limit"] = spec.get("limit", 0)
                await existing.edit(**kw)
            except discord.HTTPException:
                pass
            return existing, True

        try:
            if ctype == "text":
                ch = await guild.create_text_channel(
                    name, category=category, topic=topic, overwrites=ow, slowmode_delay=slow)
            elif ctype == "news":
                ch = await guild.create_text_channel(
                    name, category=category, topic=topic, overwrites=ow, news=True)
            elif ctype == "voice":
                ch = await guild.create_voice_channel(
                    name, category=category, overwrites=ow, user_limit=spec.get("limit", 0))
            elif ctype == "stage":
                ch = await guild.create_stage_channel(name, category=category, overwrites=ow)
            else:
                tags = [discord.ForumTag(name=t, emoji=e) for t, e in spec.get("tags", [])]
                ch = await guild.create_forum(
                    name, category=category, topic=topic, overwrites=ow,
                    slowmode_delay=slow, available_tags=tags)
        except discord.HTTPException as e:
            print(f"    ! {name} falhou como {ctype} ({e.status}); criando simples.")
            if ctype in ("voice", "stage"):
                ch = await guild.create_voice_channel(name, category=category, overwrites=ow)
            else:
                ch = await guild.create_text_channel(
                    name, category=category, topic=topic, overwrites=ow)
        return ch, False

    async def build_structure(guild, roles, community):
        print("\n[2/4] Categorias e canais")
        chans = {}
        for block in TEMPLATE:
            access = block["access"]
            category = None
            if block["category"]:
                cat_ow = make_overwrites(guild, roles, access, False, "category")
                category = discord.utils.get(guild.categories, name=block["category"])
                if category:
                    await category.edit(overwrites=cat_ow)
                else:
                    category = await guild.create_category(
                        block["category"], overwrites=cat_ow, reason=f"Setup {GAME_NAME}")
                print(f"\n  ▸ {block['category']}")
            for spec in block["channels"]:
                ow = make_overwrites(guild, roles, access, spec.get("readonly", False), spec["type"])
                ch, existed = await ensure_channel(guild, category, spec, ow, community)
                print(f"    {'=' if existed else '+'} {spec['name']}  ({spec['type']})")
                if "key" in spec:
                    chans[spec["key"]] = ch
        return chans

    async def tune_guild(guild, chans, community):
        print("\n[3/4] Configurações do servidor")
        try:
            kw = {"verification_level": discord.VerificationLevel.medium,
                  "default_notifications": discord.NotificationLevel.only_mentions}
            if "joins" in chans:
                kw["system_channel"] = chans["joins"]
            await guild.edit(**kw, reason=f"Setup {GAME_NAME}")
            print("  ✓ verificação, notificações e canal de sistema")
        except discord.HTTPException as e:
            print(f"  ! não consegui ajustar o servidor: {e}")
        if community and "rules" in chans:
            try:
                kw = {"rules_channel": chans["rules"]}
                if "sub-announcements" in chans:
                    kw["public_updates_channel"] = chans["sub-announcements"]
                await guild.edit(**kw, reason=f"Setup {GAME_NAME}")
                print("  ✓ canal de regras e de atualizações da Comunidade")
            except discord.HTTPException as e:
                print(f"  ! defina rules/updates manualmente em Configurações > Comunidade ({e.status})")

    # ---------------- mensagens ----------------

    async def already_posted(ch, me):
        async for m in ch.history(limit=15):
            if m.author == me:
                return True
        return False

    def verify_embed():
        text = L(VERIFY_ROBLOX) if VERIFY_MODE == "roblox" else L(VERIFY_BUTTON)
        return emb("☑️ Verify", text)

    async def post_messages(guild, chans, repost):
        print("\n[4/4] Mensagens")
        me = guild.me
        repost_all = repost is not None and len(repost) == 0
        repost_keys = set(repost or [])

        def force(key):
            return repost_all or key in repost_keys

        async def send(key, embeds, view=None):
            ch = chans.get(key)
            if not isinstance(ch, discord.TextChannel):
                return
            if not force(key) and await already_posted(ch, me):
                print(f"  = {key} (já tem mensagem)")
                return
            kw = {"embeds": embeds}
            if view:
                kw["view"] = view
            await ch.send(**kw)
            print(f"  + {key}")

        rules = "\n".join(f"**{i}.** {r}" for i, r in enumerate(L(RULES), 1))
        await send("rules", [emb(f"📜 {tr('Regras', 'Rules')}", rules)])

        info = emb(f"📘 {GAME_NAME}", L(INFO).format(g=GAME_NAME))
        info.add_field(name="🎮 Play", value=GAME_LINK, inline=False)
        info.add_field(name="👥 Group", value=GROUP_LINK, inline=False)
        info.add_field(name="📋 Trello", value=TRELLO_LINK, inline=False)
        await send("information", [info])

        faq = emb("❓ FAQ", "")
        for q, a in L(FAQ):
            faq.add_field(name=q, value=a, inline=False)
        await send("faq", [faq])

        await send("codes", [emb("⚡ Codes", L(CODES), 0xF1C40F)])
        await send("giveaway", [emb("💸 Invite Giveaway", L(GIVEAWAY), 0xE91E63)])
        await send("creator", [emb("📷 Content Creator Program",
                                   L(CREATOR).format(g=GAME_NAME), 0x9B59B6)])
        await send("verify", [verify_embed()], VerifyView())

        reaction = chans.get("reaction")
        if isinstance(reaction, discord.TextChannel):
            if force("reaction") or not await already_posted(reaction, me):
                for title, desc, names in REACTION_GROUPS:
                    await reaction.send(embed=emb(L(title), L(desc)), view=role_view(names))
                print("  + reaction-role")
            else:
                print("  = reaction-role (já tem mensagem)")

        for key, body in (("bugs", BUG_TEMPLATE), ("suggestions", SUGGESTION_TEMPLATE)):
            forum = chans.get(key)
            if isinstance(forum, discord.ForumChannel):
                if not force(key) and any(t.owner_id == me.id for t in forum.threads):
                    print(f"  = {key} (guidelines já existe)")
                    continue
                try:
                    created = await forum.create_thread(
                        name="📌 Guidelines", embed=emb("📌 Guidelines", L(body)))
                    await created.thread.edit(pinned=True)
                    print(f"  + {key} guidelines")
                except discord.HTTPException as e:
                    print(f"  ! guidelines de {key}: {e}")

    # ---------------- slash commands ----------------

    def register_commands(tree):
        guild_only = app_commands.guild_only

        @tree.error
        async def on_tree_error(interaction, error):
            if isinstance(error, app_commands.CheckFailure):
                msg = tr("Você não tem permissão pra isso.", "You don't have permission for that.")
            else:
                traceback.print_exception(type(error), error, error.__traceback__)
                msg = tr("Algo deu errado. Tente de novo.", "Something went wrong. Try again.")
            try:
                await reply(interaction, msg)
            except discord.HTTPException:
                pass

        @tree.command(name="verify", description=tr("Verifique sua conta e libere o servidor",
                                                    "Verify your account and unlock the server"))
        @guild_only()
        async def verify_cmd(interaction: discord.Interaction):
            await start_verification(interaction)

        @tree.command(name="unverify", description=tr("Desvincule sua conta do Roblox",
                                                      "Unlink your Roblox account"))
        @guild_only()
        async def unverify_cmd(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            member = interaction.user
            db.unlink(member.id)
            role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE)
            try:
                if role and role in member.roles:
                    await member.remove_roles(role, reason="Unverify")
                if SET_NICKNAME:
                    await member.edit(nick=None, reason="Unverify")
            except discord.HTTPException:
                pass
            await interaction.followup.send(
                tr("Conta desvinculada. Use /verify pra vincular de novo.",
                   "Account unlinked. Use /verify to link again."), ephemeral=True)

        @tree.command(name="profile", description=tr("Veja o perfil de um jogador",
                                                     "See a player's profile"))
        @app_commands.describe(member=tr("Jogador (padrão: você)", "Player (default: you)"))
        @guild_only()
        async def profile_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
            await interaction.response.defer()
            member = member or interaction.user
            row = db.user(member.id)
            linked = bool(row and row["roblox_id"])

            avatar = None
            if linked:
                avatar = await rbx_avatar(bot.session, row["roblox_id"])

            xp = row["xp"] if row else 0
            lvl = level_for(xp)
            base, nxt = xp_for(lvl), xp_for(lvl + 1)
            wins = row["wins"] if row else 0
            losses = row["losses"] if row else 0
            total = wins + losses
            wr = f"{round(100 * wins / total)}%" if total else "—"

            e = discord.Embed(colour=member.colour if member.colour.value else ACCENT)
            e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            e.set_thumbnail(url=avatar or member.display_avatar.url)

            if linked:
                e.add_field(name="🎮 Roblox",
                            value=f"[{row['roblox_name']}](https://www.roblox.com/users/{row['roblox_id']}/profile)",
                            inline=True)
            else:
                e.add_field(name="🎮 Roblox",
                            value=tr("Não vinculado (`/verify`)", "Not linked (`/verify`)"), inline=True)

            staff = next((r.name for r in member.roles if r.name in STAFF_ROLES), None)
            if staff:
                e.add_field(name="🏅 Staff", value=staff, inline=True)

            rank = f"#{db.rank(member.id)}" if row and xp > 0 else "—"
            e.add_field(name=tr("📈 Nível", "📈 Level"),
                        value=f"**{lvl}** • {xp} XP • {tr('Rank', 'Rank')} {rank}\n"
                              f"`{progress_bar(xp - base, nxt - base)}` {xp - base}/{nxt - base}",
                        inline=False)
            e.add_field(name=tr("⚽ Partidas", "⚽ Matches"),
                        value=f"🏆 {wins}  ❌ {losses}  📊 {wr}", inline=True)

            positions = [r.name for r in member.roles if r.name in POSITION_ROLES]
            regions = [r.name for r in member.roles if r.name in REGION_ROLES]
            e.add_field(name=tr("🎯 Posição", "🎯 Position"),
                        value=", ".join(positions) or "—", inline=True)
            e.add_field(name=tr("🌍 Região", "🌍 Region"),
                        value=", ".join(regions) or "—", inline=True)

            bio = row["bio"] if row and row["bio"] else None
            if bio:
                e.add_field(name="📝 Bio", value=bio, inline=False)

            joined = discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "—"
            created = discord.utils.format_dt(member.created_at, "D")
            e.add_field(name=tr("📅 No servidor desde", "📅 In server since"), value=joined, inline=True)
            e.add_field(name=tr("🆔 Conta Discord", "🆔 Discord account"), value=created, inline=True)
            e.set_footer(text=GAME_NAME)
            await interaction.followup.send(embed=e)

        @tree.command(name="roblox", description=tr("Consulta um usuário do Roblox",
                                                    "Look up a Roblox user"))
        @app_commands.describe(username=tr("Usuário do Roblox", "Roblox username"))
        @guild_only()
        async def roblox_cmd(interaction: discord.Interaction, username: str):
            await interaction.response.defer()
            try:
                found = await rbx_find(bot.session, username.strip().lstrip("@"))
                if not found:
                    return await interaction.followup.send(
                        tr("Usuário não encontrado.", "User not found."), ephemeral=True)
                uid = found["id"]
                info = await rbx_info(bot.session, uid)
                avatar = await rbx_avatar(bot.session, uid)
                friends = await rbx_count(bot.session, uid, "friends")
                followers = await rbx_count(bot.session, uid, "followers")
            except API_ERRORS:
                return await interaction.followup.send(
                    tr("Não consegui falar com o Roblox agora.", "Couldn't reach Roblox right now."),
                    ephemeral=True)
            created = parse_rbx_date(info.get("created"))
            e = discord.Embed(
                title=f"{info.get('displayName', found['name'])} (@{info.get('name', found['name'])})",
                url=f"https://www.roblox.com/users/{uid}/profile",
                description=(info.get("description") or "")[:300] or None, colour=ACCENT)
            if avatar:
                e.set_thumbnail(url=avatar)
            e.add_field(name="ID", value=str(uid), inline=True)
            e.add_field(name=tr("Amigos", "Friends"), value=str(friends if friends is not None else "—"), inline=True)
            e.add_field(name=tr("Seguidores", "Followers"), value=str(followers if followers is not None else "—"), inline=True)
            if created:
                e.add_field(name=tr("Conta criada", "Account created"),
                            value=discord.utils.format_dt(created, "D"), inline=True)
            row = db.by_roblox(uid)
            if row:
                e.add_field(name="Discord", value=f"<@{row['discord_id']}>", inline=True)
            await interaction.followup.send(embed=e)

        @tree.command(name="bio", description=tr("Defina a bio do seu perfil", "Set your profile bio"))
        @app_commands.describe(text=tr("Até 150 caracteres (vazio apaga)", "Up to 150 characters (empty clears)"))
        @guild_only()
        async def bio_cmd(interaction: discord.Interaction, text: app_commands.Range[str, 0, 150] = ""):
            db.set_bio(interaction.user.id, text)
            await reply(interaction, tr("Bio atualizada! Veja em /profile.", "Bio updated! See it in /profile."))

        @tree.command(name="leaderboard", description=tr("Ranking do servidor", "Server leaderboard"))
        @app_commands.describe(sort=tr("Ordenar por", "Sort by"))
        @app_commands.choices(sort=[app_commands.Choice(name="XP", value="xp"),
                                    app_commands.Choice(name=tr("Vitórias", "Wins"), value="wins")])
        @guild_only()
        async def leaderboard_cmd(interaction: discord.Interaction,
                                  sort: Optional[app_commands.Choice[str]] = None):
            col = sort.value if sort else "xp"
            rows = db.top(col)
            if not rows:
                return await reply(interaction, tr("Ainda não há dados.", "No data yet."))
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, r in enumerate(rows):
                mark = medals[i] if i < 3 else f"**{i + 1}.**"
                if col == "xp":
                    lines.append(f"{mark} <@{r['discord_id']}> — Lv {level_for(r['xp'])} • {r['xp']} XP")
                else:
                    lines.append(f"{mark} <@{r['discord_id']}> — 🏆 {r['wins']}")
            await interaction.response.send_message(
                embed=emb(f"🏆 Leaderboard — {'XP' if col == 'xp' else tr('Vitórias', 'Wins')}",
                          "\n".join(lines)))

        @tree.command(name="help", description=tr("Lista os comandos", "List commands"))
        @guild_only()
        async def help_cmd(interaction: discord.Interaction):
            lines = [
                tr("`/verify` — verificar e vincular o Roblox", "`/verify` — verify and link Roblox"),
                tr("`/unverify` — desvincular o Roblox", "`/unverify` — unlink Roblox"),
                tr("`/profile [jogador]` — ver perfil", "`/profile [player]` — see a profile"),
                tr("`/bio` — definir sua bio", "`/bio` — set your bio"),
                tr("`/roblox` — consultar um usuário do Roblox", "`/roblox` — look up a Roblox user"),
                tr("`/leaderboard` — ranking", "`/leaderboard` — rankings"),
            ]
            if is_staff(interaction.user):
                lines += [
                    "",
                    "**Staff**",
                    tr("`/record` — registrar vitória/derrota", "`/record` — log a win/loss"),
                    tr("`/warn` `/warnings` — avisos", "`/warn` `/warnings` — warnings"),
                    tr("`/timeout` — silenciar temporariamente", "`/timeout` — temporary mute"),
                    tr("`/clear` — apagar mensagens", "`/clear` — delete messages"),
                    tr("`/panel` — postar painel de verify/cargos", "`/panel` — post verify/roles panel"),
                ]
            await reply(interaction, embed=emb("📖 " + tr("Comandos", "Commands"), "\n".join(lines)))

        @tree.command(name="setup", description=tr("(Admin) Cria cargos, canais e mensagens do servidor",
                                                   "(Admin) Create the server's roles, channels and messages"))
        @app_commands.default_permissions(administrator=True)
        @guild_only()
        async def setup_cmd(interaction: discord.Interaction):
            if not interaction.user.guild_permissions.administrator:
                raise app_commands.CheckFailure()
            await interaction.response.defer(ephemeral=True)

            async def announce(text):
                await interaction.followup.send(text, ephemeral=True)

            await setup_from_discord(interaction.guild, announce)

        # ----- staff -----

        @tree.command(name="record", description=tr("(Staff) Registrar vitória/derrota de um jogador",
                                                    "(Staff) Log a player's win/loss"))
        @app_commands.describe(member=tr("Jogador", "Player"), result=tr("Resultado", "Result"))
        @app_commands.choices(result=[app_commands.Choice(name=tr("Vitória", "Win"), value="win"),
                                      app_commands.Choice(name=tr("Derrota", "Loss"), value="loss")])
        @app_commands.default_permissions(moderate_members=True)
        @guild_only()
        async def record_cmd(interaction: discord.Interaction, member: discord.Member,
                             result: app_commands.Choice[str]):
            if not is_staff(interaction.user):
                raise app_commands.CheckFailure()
            db.add_result(member.id, result.value == "win")
            await reply(interaction, f"✅ {member.mention}: {result.name}", ephemeral=False,
                        allowed_mentions=discord.AllowedMentions.none())

        @tree.command(name="warn", description=tr("(Staff) Avisar um membro", "(Staff) Warn a member"))
        @app_commands.describe(member=tr("Membro", "Member"), reason=tr("Motivo", "Reason"))
        @app_commands.default_permissions(moderate_members=True)
        @guild_only()
        async def warn_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
            if not is_staff(interaction.user):
                raise app_commands.CheckFailure()
            db.add_warn(interaction.guild.id, member.id, interaction.user.id, reason)
            n = len(db.warns(interaction.guild.id, member.id))
            await reply(interaction, f"⚠️ {member.mention} — {reason} ({n})",
                        ephemeral=False, allowed_mentions=discord.AllowedMentions.none())
            await mod_log(interaction.guild, "⚠️ Warn",
                          f"{member.mention} por {interaction.user.mention}\n{reason}")
            try:
                await member.send(tr(f"Você recebeu um aviso em **{interaction.guild.name}**: {reason}",
                                     f"You received a warning in **{interaction.guild.name}**: {reason}"))
            except discord.HTTPException:
                pass

        @tree.command(name="warnings", description=tr("(Staff) Ver avisos de um membro",
                                                      "(Staff) See a member's warnings"))
        @app_commands.describe(member=tr("Membro", "Member"))
        @app_commands.default_permissions(moderate_members=True)
        @guild_only()
        async def warnings_cmd(interaction: discord.Interaction, member: discord.Member):
            if not is_staff(interaction.user):
                raise app_commands.CheckFailure()
            rows = db.warns(interaction.guild.id, member.id)
            if not rows:
                return await reply(interaction, tr("Nenhum aviso.", "No warnings."))
            lines = [f"**#{r['id']}** <@{r['mod_id']}> — {r['reason']} ({r['ts'][:10]})" for r in rows]
            await reply(interaction, embed=emb(f"⚠️ {member.display_name}", "\n".join(lines), 0xE67E22))

        @tree.command(name="timeout", description=tr("(Staff) Silenciar um membro por um tempo",
                                                     "(Staff) Temporarily mute a member"))
        @app_commands.describe(member=tr("Membro", "Member"), minutes=tr("Minutos", "Minutes"),
                               reason=tr("Motivo", "Reason"))
        @app_commands.default_permissions(moderate_members=True)
        @guild_only()
        async def timeout_cmd(interaction: discord.Interaction, member: discord.Member,
                              minutes: app_commands.Range[int, 1, 40320], reason: str = "—"):
            if not is_staff(interaction.user):
                raise app_commands.CheckFailure()
            try:
                await member.timeout(timedelta(minutes=minutes), reason=reason)
            except discord.Forbidden:
                return await reply(interaction, tr("Não consigo silenciar esse membro.",
                                                   "I can't time out that member."))
            await reply(interaction, f"🔇 {member.mention} — {minutes} min", ephemeral=False,
                        allowed_mentions=discord.AllowedMentions.none())
            await mod_log(interaction.guild, "🔇 Timeout",
                          f"{member.mention} por {interaction.user.mention} ({minutes} min)\n{reason}")

        @tree.command(name="clear", description=tr("(Staff) Apagar mensagens do canal",
                                                   "(Staff) Delete messages in this channel"))
        @app_commands.describe(amount=tr("Quantidade (1-100)", "Amount (1-100)"))
        @app_commands.default_permissions(manage_messages=True)
        @guild_only()
        async def clear_cmd(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
            if not is_staff(interaction.user):
                raise app_commands.CheckFailure()
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f"🧹 {len(deleted)}", ephemeral=True)

        @tree.command(name="panel", description=tr("(Admin) Postar um painel neste canal",
                                                   "(Admin) Post a panel in this channel"))
        @app_commands.describe(kind=tr("Qual painel", "Which panel"))
        @app_commands.choices(kind=[app_commands.Choice(name="Verify", value="verify"),
                                    app_commands.Choice(name=tr("Cargos", "Roles"), value="roles")])
        @app_commands.default_permissions(administrator=True)
        @guild_only()
        async def panel_cmd(interaction: discord.Interaction, kind: app_commands.Choice[str]):
            if not interaction.user.guild_permissions.administrator:
                raise app_commands.CheckFailure()
            await interaction.response.defer(ephemeral=True)
            if kind.value == "verify":
                await interaction.channel.send(embed=verify_embed(), view=VerifyView())
            else:
                for title, desc, names in REACTION_GROUPS:
                    await interaction.channel.send(embed=emb(L(title), L(desc)), view=role_view(names))
            await interaction.followup.send("✅", ephemeral=True)

    # ---------------- setup completo (usado pelo CLI, .setup e /setup) ----------------

    busy = set()

    async def run_setup(guild, wipe=False, repost=None, no_messages=False):
        """Cria cargos, canais, configurações e mensagens. Retorna avisos."""
        warnings = []
        community = "COMMUNITY" in guild.features
        if not community:
            warnings.append(tr("Modo Comunidade está desativado: anúncios, fóruns e palco foram "
                               "criados como canais simples. Ative em Configurações > Comunidade e "
                               "rode `.setup` de novo.",
                               "Community mode is off: announcements, forums and stage were created as "
                               "plain channels. Enable it in Settings > Community and run `.setup` again."))
            print("\n⚠ Modo Comunidade desativado: anúncios/fórum/palco serão criados como canais simples.")
        if wipe:
            print("\nApagando canais...")
            for ch in list(guild.channels):
                try:
                    await ch.delete(reason=f"Setup {GAME_NAME}")
                except discord.HTTPException as e:
                    print(f"  ! {ch.name}: {e}")

        roles = await create_roles(guild)
        if guild.me.top_role <= roles[VERIFIED_ROLE]:
            warnings.append(tr("O cargo do bot está ABAIXO de ✅ Verified. Suba o cargo do bot pro topo "
                               "da lista de cargos, senão o verify e os botões de cargo dão erro.",
                               "The bot's role is BELOW ✅ Verified. Move the bot's role to the top of the "
                               "role list, otherwise verify and role buttons will error."))
            print("\n⚠ O cargo do bot está ABAIXO de ✅ Verified. Suba o cargo do bot no topo.")
        chans = await build_structure(guild, roles, community)
        await tune_guild(guild, chans, community)
        if not no_messages:
            await post_messages(guild, chans, repost)
        return warnings

    async def setup_from_discord(guild, announce):
        """Roda o setup a partir de um comando do Discord. announce(texto) responde no canal."""
        if guild.id in busy:
            return await announce(tr("⏳ Já tem um setup rodando. Aguarde.",
                                     "⏳ A setup is already running. Please wait."))
        busy.add(guild.id)
        try:
            warnings = await run_setup(guild)
        except discord.Forbidden:
            return await announce(tr("❌ Sem permissão. Dê **Administrador** ao bot e coloque o cargo "
                                     "dele no topo da lista de cargos.",
                                     "❌ Missing permissions. Give the bot **Administrator** and move its "
                                     "role to the top of the role list."))
        except Exception as e:  # noqa: BLE001
            traceback.print_exception(type(e), e, e.__traceback__)
            return await announce(f"❌ {type(e).__name__}: {e}")
        finally:
            busy.discard(guild.id)
        text = tr("✅ **Setup concluído!** Cargos, canais, permissões e mensagens criados.\n"
                  "Se algo já existia, foi mantido e só as permissões foram atualizadas.",
                  "✅ **Setup complete!** Roles, channels, permissions and messages created.\n"
                  "Anything that already existed was kept; only permissions were updated.")
        if warnings:
            text += "\n\n" + "\n".join(f"⚠️ {w}" for w in warnings)
        await announce(text)

    # ---------------- cliente ----------------

    class Bot(discord.Client):
        def __init__(self):
            intents = discord.Intents.default()
            if args.welcome:
                intents.members = True
            if not args.no_prefix:
                intents.message_content = True
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)
            register_commands(self.tree)
            self.session = None
            self.started = False

        async def setup_hook(self):
            self.session = aiohttp.ClientSession(headers={"User-Agent": "FutsalLegendsBot/3.0"})
            # botões persistentes: continuam funcionando depois de reiniciar o bot
            self.add_view(VerifyView())
            for _, _, names in REACTION_GROUPS:
                self.add_view(role_view(names))

        async def close(self):
            if self.session:
                await self.session.close()
            await super().close()

        def pick_guild(self):
            if guild_id:
                return self.get_guild(guild_id)
            return self.guilds[0] if len(self.guilds) == 1 else None

        async def sync_commands(self):
            for g in self.guilds:
                try:
                    self.tree.copy_global_to(guild=g)
                    synced = await self.tree.sync(guild=g)
                    print(f"  ✓ {len(synced)} slash commands em {g.name}")
                except discord.HTTPException as e:
                    print(f"  ! falha ao sincronizar comandos em {g.name}: {e}")

        async def on_ready(self):
            if self.started:
                return
            self.started = True
            print(f"Logado como {self.user}")
            invite = discord.utils.oauth_url(
                self.user.id, permissions=discord.Permissions(administrator=True),
                scopes=("bot", "applications.commands"))
            print(f"Link de convite (bot + slash commands):\n  {invite}")

            await self.sync_commands()

            if args.serve:
                print("\nModo --serve: bot online, botões e comandos ativos. Ctrl+C pra parar.")
                return

            guild = self.pick_guild()
            if guild is None:
                print("Servidor não encontrado. O bot está nele? Passe --guild ID.")
                return await self.close()

            try:
                await run_setup(guild, args.wipe, args.repost, args.no_messages)
                print("\n✅ Setup concluído!")
            except discord.Forbidden:
                print("\nERRO: permissão negada. Dê ADMINISTRATOR ao bot e coloque "
                      "o cargo dele no topo da lista de cargos.")
            finally:
                if args.setup_only:
                    print("--setup-only: fechando. Os botões NÃO vão funcionar até rodar com --serve.")
                    await self.close()
                else:
                    print("\nBot online. Botões e slash commands ativos. Ctrl+C pra parar.")

        async def on_message(self, message):
            if message.author.bot or message.guild is None:
                return
            db.add_xp(message.author.id, random.randint(15, 25), time.time(), XP_COOLDOWN)
            if not args.no_prefix and message.content.startswith(PREFIX):
                try:
                    await self.handle_prefix(message)
                except discord.HTTPException as e:
                    print(f"Erro no comando de texto: {e}")

        async def handle_prefix(self, message):
            parts = message.content[len(PREFIX):].strip().split()
            if not parts:
                return
            cmd = parts[0].lower()
            known = {"setup", "verify", "painel", "panel", "roles", "cargos", "help", "ajuda"}
            if cmd not in known:
                return
            if not message.author.guild_permissions.administrator:
                return await message.reply(tr("Só administradores podem usar esse comando.",
                                              "Only administrators can use this command."),
                                           mention_author=False)

            if cmd == "setup":
                await message.reply(tr("⚙️ Configurando o servidor... isso pode levar alguns minutos.",
                                       "⚙️ Setting up the server... this may take a few minutes."),
                                    mention_author=False)

                async def announce(text):
                    await message.channel.send(text)

                await setup_from_discord(message.guild, announce)

            elif cmd in ("verify", "painel", "panel"):
                await message.channel.send(embed=verify_embed(), view=VerifyView())
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

            elif cmd in ("roles", "cargos"):
                for title, desc, names in REACTION_GROUPS:
                    await message.channel.send(embed=emb(L(title), L(desc)), view=role_view(names))
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

            else:  # help / ajuda
                await message.reply(embed=emb("🛠️ " + tr("Comandos de admin", "Admin commands"), "\n".join([
                    tr(f"`{PREFIX}setup` — cria cargos, canais, permissões e mensagens (pode rodar de novo sem duplicar)",
                       f"`{PREFIX}setup` — creates roles, channels, permissions and messages (safe to re-run)"),
                    tr(f"`{PREFIX}verify` — envia o painel com o botão de verify neste canal",
                       f"`{PREFIX}verify` — sends the verify button panel in this channel"),
                    tr(f"`{PREFIX}roles` — envia os painéis de cargos por botão neste canal",
                       f"`{PREFIX}roles` — sends the role button panels in this channel"),
                ])), mention_author=False)

        async def on_member_join(self, member):
            joins = next((c for c in member.guild.text_channels if c.name.endswith("joins")), None)
            verify = next((c for c in member.guild.text_channels if c.name.endswith("verify")), None)
            if joins:
                text = L(WELCOME).format(
                    m=member.mention, g=GAME_NAME, v=verify.mention if verify else "#verify")
                await joins.send(text, allowed_mentions=discord.AllowedMentions(users=True))

    bot = Bot()
    return bot


if __name__ == "__main__":
    main()