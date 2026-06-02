#!/usr/bin/env python3
"""
FREE FIRE TOURNAMENT BOT v1.0
Telegram Bot for FF Tournament Management
"""

import os, json, logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

# ============================================================
# CONFIGURATION — EDIT THESE
# ============================================================
BOT_TOKEN = "8810753904:AAETt7b9qYppWvE6btcECn3ONJpWL9WQemU"
ADMIN_IDS = [7691071175]
MAX_TEAMS = 12
MAX_PLAYERS_PER_TEAM = 6
DATA_FILE = "ff_tournament_data.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# DATA STORAGE
# ============================================================
class DataStore:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = self._load()
    def _load(self) -> dict:
        if os.path.exists(self.filepath):
            try: return json.load(open(self.filepath,'r',encoding='utf-8'))
            except: pass
        return {"teams":{},"pending_teams":[],"reviews":[],"channels":[],"admins":[],"history":[],"temp_data":{}}
    def _save(self):
        json.dump(self.data, open(self.filepath,'w',encoding='utf-8'), indent=2, ensure_ascii=False)
    def get_admins(self) -> list:
        return list(set(self.data.get("admins",[]) + ADMIN_IDS))
    def add_admin(self, user_id: int):
        if user_id not in self.data["admins"]: self.data["admins"].append(user_id); self._save()
    def remove_admin(self, user_id: int):
        if user_id in self.data["admins"]: self.data["admins"].remove(user_id); self._save()
    def is_admin(self, user_id: int) -> bool:
        return user_id in self.get_admins()
    def get_channels(self) -> list:
        return self.data.get("channels",[])
    def add_channel(self, channel_id: str):
        channels = self.data.setdefault("channels",[])
        if channel_id not in channels: channels.append(channel_id); self._save()
    def remove_channel(self, channel_id: str):
        channels = self.data.get("channels",[])
        if channel_id in channels: channels.remove(channel_id); self._save()
    def add_review(self, user_id: int, user_name: str, review_text: str):
        self.data["reviews"].append({"user_id":user_id,"user_name":user_name,"review_text":review_text,"date":datetime.now().isoformat()})
        self._save()
    def get_reviews(self) -> list:
        return self.data.get("reviews",[])
    def team_exists(self, team_name: str) -> bool:
        return team_name.lower() in [t.lower() for t in self.data["teams"]]
    def create_team(self, team_name: str, leader_id: int, leader_name: str, ff_id: str):
        self.data["teams"][team_name] = {"leader_id":leader_id,"leader_name":leader_name,"ff_id":ff_id,"players":[],"approved":False,"status":"pending","created_at":datetime.now().isoformat()}
        if team_name not in self.data["pending_teams"]: self.data["pending_teams"].append(team_name)
        self._save()
    def add_player_to_team(self, team_name: str, user_id: int, user_name: str, user_ff_id: str) -> bool:
        team = self.data["teams"].get(team_name)
        if not team or len(team["players"])>=MAX_PLAYERS_PER_TEAM: return False
        if any(p["user_id"]==user_id for p in team["players"]): return False
        team["players"].append({"user_id":user_id,"user_name":user_name,"user_ff_id":user_ff_id})
        self._save(); return True
    def get_team(self, team_name: str) -> Optional[dict]:
        return self.data["teams"].get(team_name)
    def get_team_by_leader(self, leader_id: int) -> Optional[Tuple[str, dict]]:
        for n,t in self.data["teams"].items():
            if t["leader_id"]==leader_id: return n,t
        return None,None
    def get_team_by_player(self, user_id: int) -> Optional[Tuple[str, dict]]:
        for n,t in self.data["teams"].items():
            for p in t["players"]:
                if p["user_id"]==user_id: return n,t
        return None,None
    def approve_team(self, team_name: str):
        team = self.data["teams"].get(team_name)
        if team:
            team["approved"]=True; team["status"]="approved"
            if team_name in self.data["pending_teams"]: self.data["pending_teams"].remove(team_name)
            self.data["history"].append({"team_name":team_name,"leader_name":team["leader_name"],"players_count":len(team["players"]),"date":datetime.now().isoformat()})
            self._save()
    def reject_team(self, team_name: str, reason: str):
        team = self.data["teams"].get(team_name)
        if team: team["status"]="rejected"; team["reject_reason"]=reason
        if team_name in self.data["pending_teams"]: self.data["pending_teams"].remove(team_name)
        self._save()
    def get_pending_teams(self) -> list:
        return [t for t in self.data["pending_teams"] if t in self.data["teams"]]
    def get_approved_teams(self) -> list:
        return [n for n,t in self.data["teams"].items() if t.get("approved")]
    def get_all_teams(self) -> dict:
        return self.data.get("teams",{})
    def get_player_team_list(self) -> list:
        return [n for n,t in self.data["teams"].items() if t.get("approved")]
    def player_count_in_team(self, team_name: str) -> int:
        team = self.data["teams"].get(team_name)
        return len(team["players"]) if team else 0
    def set_temp(self, key: str, value):
        self.data["temp_data"][key]=value; self._save()
    def get_temp(self, key: str, default=None):
        return self.data["temp_data"].get(key,default)
    def del_temp(self, key: str):
        if key in self.data["temp_data"]: del self.data["temp_data"][key]; self._save()
    def get_history(self) -> list:
        return self.data.get("history",[])
    def get_all_user_ids(self) -> set:
        """Get all registered user IDs for broadcasting"""
        uids = set()
        for n,t in self.data["teams"].items():
            uids.add(t["leader_id"])
            for p in t["players"]:
                if p["user_id"]: uids.add(p["user_id"])
        return uids

store = DataStore(DATA_FILE)

# Conversation states
(SELECT_ACTION, WAITING_FF_ID, WAITING_TEAM_NAME, WAITING_PLAYER_LIST,
 WAITING_PLAYER_FF_ID, WAITING_PLAYER_NAME, ADMIN_APPROVAL_REASON,
 ADMIN_ADD_ADMIN, ADMIN_REMOVE_ADMIN, ADMIN_ADD_CHANNEL, ADMIN_REMOVE_CHANNEL,
 ADMIN_MSG_LEADER, WAITING_REVIEW, PLAYER_SELECT_TEAM) = range(14)
 # ============================================================
# FORCE JOIN CHECK
# ============================================================
async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    channels = store.get_channels()
    if not channels: return True
    for ch in channels:
        try:
            ch_clean = ch.strip()
            if ch_clean.startswith("@"):
                chat = await context.bot.get_chat(ch_clean)
                member = await chat.get_member(user_id)
                if member.status in ("left","kicked"): return False
            elif ch_clean.startswith("-100"):
                chat = await context.bot.get_chat(int(ch_clean))
                member = await chat.get_member(user_id)
                if member.status in ("left","kicked"): return False
            else:
                try:
                    chat = await context.bot.get_chat(int(ch_clean))
                    member = await chat.get_member(user_id)
                    if member.status in ("left","kicked"): return False
                except: pass
        except Exception as e:
            logger.warning(f"Force join check error for {ch}: {e}")
            continue
    return True

async def force_join_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = store.get_channels()
    btns = []
    for ch in channels:
        ch_clean = ch.strip()
        if ch_clean.startswith("@"):
            btns.append([InlineKeyboardButton(f"📢 Join {ch_clean}", url=f"https://t.me/{ch_clean[1:]}")])
        else:
            btns.append([InlineKeyboardButton(f"📢 Join Channel", url=f"https://t.me/c/{ch_clean}")])
    btns.append([InlineKeyboardButton("✅ I've Joined ✅", callback_data="check_join")])
    markup = InlineKeyboardMarkup(btns)
    await update.message.reply_text("⚠️ *You must join our channels first!* ⚠️\n\nPlease join all required channels below, then click the button:\n", reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

# ============================================================
# START COMMAND
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_force_join(update, context):
        await force_join_prompt(update, context); return

    # Only send photo if user has profile photo - skip if not
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos and photos.photos:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photos.photos[0][-1].file_id,
                caption=f"🔥 *WELCOME TO FREE FIRE TOURNAMENT BOT!* 🔥\n\n👤 Player: *{user.first_name}*\n🆔 ID: `{user.id}`\n\n━━━━━━━━━━━━━━━━━━━━\n⚡ *TOURNAMENT MODE ACTIVE* ⚡\n━━━━━━━━━━━━━━━━━━━━\n\n📌 *Total Teams Allowed:* `{MAX_TEAMS}`\n📌 *Players Per Team:* `{MAX_PLAYERS_PER_TEAM}`\n\n👇 *Choose Your Option Below* 👇",
                parse_mode=ParseMode.MARKDOWN)
    except:
        pass

    # Check if user is already an approved leader
    tn, tm = store.get_team_by_leader(user.id)
    btns = []
    if tn and tm.get("approved"):
        btns.append([InlineKeyboardButton("👑 LEADER PANEL", callback_data="leader_panel")])
    else:
        btns.append([InlineKeyboardButton("👑 LEADER (Create Team)", callback_data="leader_reg")])
    btns.append([InlineKeyboardButton("🎮 PLAYER (Join Team)", callback_data="player_reg")])
    btns.append([InlineKeyboardButton("⭐ GIVE REVIEW", callback_data="give_review")])
    if store.is_admin(user.id):
        btns.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin_panel")])

    markup = InlineKeyboardMarkup(btns)
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 *FREE FIRE TOURNAMENT* 🔥\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ *Welcome {user.first_name}!*\n\n"
        "👑 *Leader* → Register your team & manage players\n"
        "🎮 *Player* → Join an existing team\n"
        "⭐ *Review* → Share your experience\n\n"
        "👇 *Select an option below:* 👇",
        reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await check_force_join(update, context):
        await query.edit_message_text("✅ *Thank you for your support!* Use /start again.", parse_mode=ParseMode.MARKDOWN)
    else:
        await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        # ============================================================
# LEADER REGISTRATION
# ============================================================
async def leader_reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    tn, tm = store.get_team_by_leader(uid)
    if tn:
        if tm.get("approved"):
            await show_leader_panel(update, context, tn, tm); return
        await query.edit_message_text(f"⚠️ *You are already a Leader!*\n\nTeam: *{tn}*\nStatus: *{tm['status'].upper()}*\n\nUse /start to go back.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    approved_count = len(store.get_approved_teams())
    pending_count = len(store.get_pending_teams())
    total = approved_count + pending_count
    if total >= MAX_TEAMS:
        await query.edit_message_text(f"❌ *Maximum team limit reached!*\n\nTotal teams allowed: `{MAX_TEAMS}`\nTry again later when slots open up.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    store.set_temp(f"step_{uid}","ff_id")
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 *LEADER REGISTRATION* 👑\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 *Step 1/3: Free Fire ID*\n\n"
        "Please enter your *Free Fire ID*:\n"
        "(Example: `2345678901`)\n\n"
        "└ Send the number below 👇",
        parse_mode=ParseMode.MARKDOWN)
    return WAITING_FF_ID

async def receive_ff_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = store.get_temp(f"step_{user_id}")
    if step != "ff_id": return
    ff_id = update.message.text.strip()
    store.set_temp(f"ff_id_{user_id}",ff_id); store.set_temp(f"step_{user_id}","team_name")
    await update.message.reply_text(
        "✅ *FF ID Saved!* ✅\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📝 *Step 2/3: Team Name*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Enter your *Team Name*:\n"
        "(Be creative! Example: `DRAGON SLAYERS`)\n\n"
        "└ Send the name below 👇",
        parse_mode=ParseMode.MARKDOWN)
    return WAITING_TEAM_NAME

async def receive_team_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = store.get_temp(f"step_{user_id}")
    if step != "team_name": return
    team_name = update.message.text.strip()
    if store.team_exists(team_name):
        await update.message.reply_text("❌ *Team name already exists!*\n\nPlease choose a *different name* and try again:\n└ Send the name below 👇", parse_mode=ParseMode.MARKDOWN)
        return WAITING_TEAM_NAME
    store.set_temp(f"team_name_{user_id}",team_name); store.set_temp(f"step_{user_id}","players"); store.set_temp(f"players_{user_id}",[])
    await update.message.reply_text(
        f"✅ *Team Name Saved!* ✅\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 *Step 3/3: Add Players*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Team: *{team_name}*\n"
        f"Players needed: `{MAX_PLAYERS_PER_TEAM}`\n\n"
        "Send your *6 players* one by one in this format:\n"
        "`Name - FF_ID`\n\n"
        "Example:\n"
        "`GamerX - 1234567890`\n"
        "`ProSniper - 9876543210`\n\n"
        "📌 Send one player per message!\n"
        "📌 When done type: `done`\n"
        "📌 To cancel type: `cancel`\n\n"
        f"*Player 1/{MAX_PLAYERS_PER_TEAM}:* 👇",
        parse_mode=ParseMode.MARKDOWN)
    return WAITING_PLAYER_LIST

async def receive_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = store.get_temp(f"step_{user_id}")
    if step != "players": return
    text = update.message.text.strip()
    if text.lower() == "cancel":
        for k in [f"step_{user_id}",f"ff_id_{user_id}",f"team_name_{user_id}",f"players_{user_id}"]: store.del_temp(k)
        await update.message.reply_text("❌ *Registration Cancelled.* Use /start to try again.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    ff_id = store.get_temp(f"ff_id_{user_id}")
    team_name = store.get_temp(f"team_name_{user_id}")
    players = store.get_temp(f"players_{user_id}",[])
    if text.lower() == "done":
        if len(players) < 2:
            await update.message.reply_text(f"⚠️ *You need at least 2 players!*\nCurrent: `{len(players)}` | Need: `2-{MAX_PLAYERS_PER_TEAM}`\n\nSend more players or type `done` when ready.", parse_mode=ParseMode.MARKDOWN)
            return WAITING_PLAYER_LIST
        store.create_team(team_name,user_id,update.effective_user.first_name,ff_id)
        for p in players: name, pid = p; store.add_player_to_team(team_name,0,name,pid)
        for k in [f"step_{user_id}",f"ff_id_{user_id}",f"team_name_{user_id}",f"players_{user_id}"]: store.del_temp(k)
        
        # Notify admins
        plist = "\n".join([f"  👤 *{p[0]}* - `{p[1]}`" for i,p in enumerate(players)])
        for aid in store.get_admins():
            try:
                await context.bot.send_message(aid,
                    f"🔥 *NEW TEAM REGISTRATION* 🔥\n\n👑 Leader: *{update.effective_user.first_name}*\n🆔 ID: `{user_id}`\n🏷️ Team: *{team_name}*\n🔫 FF ID: `{ff_id}`\n👥 Players: `{len(players)}`\n\n📋 *Player List:*\n{plist}\n\n👇 *Actions:*",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ APPROVE",callback_data=f"approve_{team_name}"),InlineKeyboardButton("❌ REJECT",callback_data=f"reject_{team_name}")]]),
                    parse_mode=ParseMode.MARKDOWN)
            except: pass
            
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 *REGISTRATION COMPLETE!* 🔥\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ *Team Created Successfully!*\n\n"
            f"👑 Leader: *{update.effective_user.first_name}*\n"
            f"🏷️ Team: *{team_name}*\n"
            f"🔫 FF ID: `{ff_id}`\n"
            f"👥 Players: `{len(players)}/{MAX_PLAYERS_PER_TEAM}`\n\n"
            f"📋 *Player List:*\n{plist}\n\n"
            "⏳ *Waiting for Admin Approval...*\n"
            "You will be notified once approved!\n\n"
            "Use /start to go back.",
            parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    if "-" in text:
        parts = text.split("-",1)
        pname = parts[0].strip(); pffid = parts[1].strip()
        players.append((pname,pffid))
        store.set_temp(f"players_{user_id}",players)
        remaining = MAX_PLAYERS_PER_TEAM - len(players)
        if remaining <= 0:
            await update.message.reply_text("✅ *All players added!* Type `done` to finish.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"✅ *Player {len(players)} Added!*\n👤 `{pname}` - `{pffid}`\n\n📌 Send *Player {len(players)+1}/{MAX_PLAYERS_PER_TEAM}*\n📌 Or type `done` to finish", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ *Invalid format!*\nUse: `Name - FF_ID`\nExample: `GamerX - 1234567890`", parse_mode=ParseMode.MARKDOWN)
    return WAITING_PLAYER_LIST

# ============================================================
# LEADER PANEL
# ============================================================
async def show_leader_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, tn, tm):
    query = update.callback_query
    if query: await query.answer()
    plist = "\n".join([f"  👤 *{p['user_name']}* - `{p.get('user_ff_id','N/A')}`" for p in tm["players"]]) if tm["players"] else "  (No players yet)"
    msg = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 *LEADER PANEL* 👑\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷️ Team: *{tn}*\n"
        f"🔫 Your FF ID: `{tm['ff_id']}`\n"
        f"✅ Status: *APPROVED*\n\n"
        f"*Your Players ({len(tm['players'])}/{MAX_PLAYERS_PER_TEAM}):*\n{plist}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *Commands*\n"
        f"`/players` → View your team\n"
        f"`/admin <msg>` → Message admin\n"
        f"`/teams` → All teams"
    )
    if query: await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    # ============================================================
# PLAYER REGISTRATION (via /playerson command only)
# ============================================================
async def player_reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ *Players registration is not open yet!*\n\nAdmin will enable it via `/playerson` command.\nPlease wait or contact the admin.", parse_mode=ParseMode.MARKDOWN)

async def playerson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not store.is_admin(user.id):
        await update.message.reply_text("❌ *Unauthorized!* Only admins can use this.", parse_mode=ParseMode.MARKDOWN); return
    approved = store.get_approved_teams()
    if not approved:
        await update.message.reply_text("❌ *No approved teams yet!* Approve teams first.", parse_mode=ParseMode.MARKDOWN); return
    
    # Alert all registered users
    all_uids = store.get_all_user_ids()
    notified = 0
    for uid in all_uids:
        try:
            await context.bot.send_message(uid,
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🎮 *PLAYER REGISTRATION IS NOW OPEN!* 🎮\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Admin has opened player registration!\n\n"
                "Use /start to join a team!",
                parse_mode=ParseMode.MARKDOWN)
            notified += 1
        except: pass
    
    btns = []
    for tn in approved:
        team = store.get_team(tn)
        pc = len(team["players"]) if team else 0
        btns.append([InlineKeyboardButton(f"{tn} ({pc}/{MAX_PLAYERS_PER_TEAM})", callback_data=f"join_{tn}")])
    markup = InlineKeyboardMarkup(btns)
    
    msg = "━━━━━━━━━━━━━━━━━━━━\n🎮 *PLAYER REGISTRATION OPEN!* 🎮\n━━━━━━━━━━━━━━━━━━━━\n\n✅ *Activated by Admin*\n\nSelect a team to join:\n\n👇 *Click a team below:* 👇"
    if notified > 0:
        msg += f"\n\n📢 Alert sent to `{notified}` users!"
    
    await update.message.reply_text(msg, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def player_select_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team_name = query.data.replace("join_","")
    team = store.get_team(team_name)
    if not team or not team.get("approved"):
        await query.edit_message_text("❌ *Team not found or not approved!*", parse_mode=ParseMode.MARKDOWN); return
    if len(team["players"]) >= MAX_PLAYERS_PER_TEAM:
        await query.edit_message_text(f"❌ *{team_name} is full!* ({MAX_PLAYERS_PER_TEAM}/{MAX_PLAYERS_PER_TEAM})", parse_mode=ParseMode.MARKDOWN); return
    store.set_temp(f"p_team_{query.from_user.id}",team_name); store.set_temp(f"p_step_{query.from_user.id}","ff_id")
    await query.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 *JOINING: {team_name}* 🎮\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 *Enter your Free Fire ID:*\n"
        "(Example: `2345678901`)\n\n"
        "└ Send below 👇",
        parse_mode=ParseMode.MARKDOWN)
    return WAITING_PLAYER_FF_ID

async def player_receive_ff_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = store.get_temp(f"p_step_{user_id}")
    if step != "ff_id": return
    ffid = update.message.text.strip()
    store.set_temp(f"p_ffid_{user_id}",ffid); store.set_temp(f"p_step_{user_id}","name")
    await update.message.reply_text("✅ *FF ID Saved!* ✅\n\n📝 *Now enter your Name:*\n└ Send below 👇", parse_mode=ParseMode.MARKDOWN)
    return WAITING_PLAYER_NAME

async def player_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = store.get_temp(f"p_step_{user_id}")
    if step != "name": return
    pname = update.message.text.strip()
    ffid = store.get_temp(f"p_ffid_{user_id}")
    team_name = store.get_temp(f"p_team_{user_id}")
    success = store.add_player_to_team(team_name,user_id,pname,ffid)
    if not success:
        await update.message.reply_text("❌ *Failed to join!* Team might be full or you're already registered.", parse_mode=ParseMode.MARKDOWN)
    else:
        team = store.get_team(team_name)
        if team:
            try:
                plist = "\n".join([f"  👤 *{p['user_name']}* — `{p.get('user_ff_id','N/A')}`" for p in team["players"]])
                await context.bot.send_message(team["leader_id"],
                    f"🎮 *NEW PLAYER REQUEST* 🎮\n\nTeam: *{team_name}*\nName: *{pname}*\nFF ID: `{ffid}`\n\n*Current Team Players:*\n{plist}\n\n👇 *Approve or Reject:*",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve",callback_data=f"lapprove_{team_name}_{user_id}"),InlineKeyboardButton("❌ Reject",callback_data=f"lreject_{team_name}_{user_id}")]]),
                    parse_mode=ParseMode.MARKDOWN)
            except: pass
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✅ *REGISTRATION SUBMITTED!* ✅\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Name: *{pname}*\n"
            f"🔫 FF ID: `{ffid}`\n"
            f"🏷️ Team: *{team_name}*\n\n"
            "⏳ *Waiting for Team Leader's approval...*\n"
            "You will be notified once approved!",
            parse_mode=ParseMode.MARKDOWN)
    for k in [f"p_step_{user_id}",f"p_ffid_{user_id}",f"p_team_{user_id}"]: store.del_temp(k)
    return ConversationHandler.END

# ============================================================
# LEADER APPROVE/REJECT PLAYER
# ============================================================
async def leader_approve_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_",2)
    if len(parts) < 3: return
    team_name = parts[1]; player_uid = int(parts[2])
    team = store.get_team(team_name)
    plist = "\n".join([f"  👤 *{p['user_name']}* — `{p.get('user_ff_id','N/A')}`" for p in team["players"]]) if team else ""
    await query.edit_message_text(f"✅ *Player Approved!*\n\nPlayer ID: `{player_uid}`\nTeam: *{team_name}*\n\n*Current Players:*\n{plist}", parse_mode=ParseMode.MARKDOWN)
    try: await context.bot.send_message(player_uid, f"✅ *Your registration is approved!*\n\nTeam: *{team_name}*\nYou are now a registered player!\n\nUse /start to check your status.", parse_mode=ParseMode.MARKDOWN)
    except: pass

async def leader_reject_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_",2)
    if len(parts) < 3: return
    team_name = parts[1]; player_uid = int(parts[2])
    await query.edit_message_text(f"❌ *Player Rejected!*\n\nPlayer ID: `{player_uid}`\nTeam: *{team_name}*", parse_mode=ParseMode.MARKDOWN)
    try: await context.bot.send_message(player_uid, f"❌ *Registration Rejected*\n\nTeam: *{team_name}*\nThe team leader did not approve your request.", parse_mode=ParseMode.MARKDOWN)
    except: pass

# ============================================================
# /players, /admin, /teams commands
# ============================================================
async def players_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tn, t = store.get_team_by_leader(uid)
    if not tn:
        await update.message.reply_text("❌ *You are not a team leader!*", parse_mode=ParseMode.MARKDOWN); return
    plist = "\n".join([f"  👤 *{p['user_name']}* — `{p.get('user_ff_id','N/A')}`" for p in t["players"]]) if t["players"] else "  (No players yet)"
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 *YOUR TEAM PLAYERS* 👑\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷️ Team: *{tn}*\n"
        f"📊 Status: *{t['status'].upper()}*\n"
        f"🔫 Your FF ID: `{t['ff_id']}`\n\n"
        f"*Players ({len(t['players'])}/{MAX_PLAYERS_PER_TEAM}):*\n{plist}",
        parse_mode=ParseMode.MARKDOWN)

async def admin_msg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tn, t = store.get_team_by_leader(uid)
    if not tn:
        await update.message.reply_text("❌ *You are not a team leader!*", parse_mode=ParseMode.MARKDOWN); return
    text = update.message.text.replace("/admin","",1).strip()
    if not text:
        await update.message.reply_text("Usage: `/admin your message here`", parse_mode=ParseMode.MARKDOWN); return
    for aid in store.get_admins():
        try:
            await context.bot.send_message(aid,
                f"📩 *Message from Leader* 📩\n\n👑 Leader: *{t['leader_name']}*\n🏷️ Team: *{tn}*\n🆔 ID: `{uid}`\n\n📝 Message: _{text}_",
                parse_mode=ParseMode.MARKDOWN)
        except: pass
    await update.message.reply_text("✅ *Your message has been sent to admin!*", parse_mode=ParseMode.MARKDOWN)

async def teams_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allt = store.get_all_teams()
    if not allt:
        await update.message.reply_text("❌ *No teams registered yet!*", parse_mode=ParseMode.MARKDOWN); return
    msg = "━━━━━━━━━━━━━━━━━━━━\n🔥 *ALL TOURNAMENT TEAMS* 🔥\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i,(tn,t) in enumerate(allt.items(),1):
        em = {"pending":"⏳","approved":"✅","rejected":"❌"}.get(t["status"],"❓")
        pl = "\n".join([f"    👤 {p['user_name']}" for p in t["players"]]) if t["players"] else "    (No players)"
        msg += f"{em} *{i}. {tn}*\n👑 Leader: {t['leader_name']} (ID: `{t['leader_id']}`)\n👥 Players ({len(t['players'])}/{MAX_PLAYERS_PER_TEAM}):\n{pl}\n\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    # ============================================================
# ADMIN APPROVE / REJECT TEAM
# ============================================================
async def admin_approve_team_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team_name = query.data.replace("approve_","")
    store.approve_team(team_name)
    team = store.get_team(team_name)
    plist = "\n".join([f"  👤 *{p['user_name']}* — `{p.get('user_ff_id','N/A')}`" for p in team["players"]]) if team and team["players"] else "  (No players)"
    await query.edit_message_text(f"✅ *Team APPROVED!* ✅\n\n🏷️ *{team_name}*\n👑 Leader: *{team['leader_name']}*\n\n📋 *Players:*\n{plist}", parse_mode=ParseMode.MARKDOWN)
    if team:
        try:
            await context.bot.send_message(team["leader_id"],
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ *CONGRATULATIONS!* ✅\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏷️ *{team_name}* has been *APPROVED!*\n\n"
                f"👑 You are now an official *Team Leader!*\n"
                f"👥 Players: `{len(team['players'])}/{MAX_PLAYERS_PER_TEAM}`\n\n"
                "🔥 *Get ready for the tournament!*\n\n"
                "Use /start to open your **LEADER PANEL**\n"
                "Commands: `/players`, `/admin <msg>`, `/teams`",
                parse_mode=ParseMode.MARKDOWN)
        except: pass
    # Send to channel
    for ch in store.get_channels():
        try:
            await context.bot.send_message(ch,
                f"🔥 *NEW TEAM APPROVED!* 🔥\n\n🏷️ Team: *{team_name}*\n👑 Leader: *{team['leader_name']}*\n👥 Players: `{len(team['players'])}/{MAX_PLAYERS_PER_TEAM}`\n\n⚡ Total Teams: `{len(store.get_approved_teams())}/{MAX_TEAMS}`",
                parse_mode=ParseMode.MARKDOWN)
        except: pass

async def admin_reject_team_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team_name = query.data.replace("reject_","")
    store.set_temp(f"reject_team_{query.from_user.id}",team_name)
    await query.edit_message_text(f"❌ *REJECT: {team_name}*\n\nPlease enter the *reason* for rejection:\n└ Send below 👇", parse_mode=ParseMode.MARKDOWN)
    return ADMIN_APPROVAL_REASON

async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reason = update.message.text.strip()
    team_name = store.get_temp(f"reject_team_{user_id}")
    if not team_name: return ConversationHandler.END
    team = store.get_team(team_name)
    store.reject_team(team_name,reason)
    await update.message.reply_text(f"✅ *Team Rejected!*\n\n🏷️ *{team_name}*\n📝 Reason: _{reason}_", parse_mode=ParseMode.MARKDOWN)
    if team:
        try: await context.bot.send_message(team["leader_id"], f"❌ *TEAM REJECTED* ❌\n\n🏷️ Team: *{team_name}*\n📝 Reason: _{reason}_\n\nPlease fix the issue and register again!\nUse /start to try again.", parse_mode=ParseMode.MARKDOWN)
        except: pass
    store.del_temp(f"reject_team_{user_id}")
    return ConversationHandler.END

# ============================================================
# GIVE REVIEW
# ============================================================
async def give_review_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ *GIVE YOUR REVIEW* ⭐\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "We value your feedback!\n\n"
        "Please send your review message below:\n"
        "└ Write and send 👇",
        parse_mode=ParseMode.MARKDOWN)
    return WAITING_REVIEW

async def receive_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    review_text = update.message.text.strip()
    store.add_review(user.id,user.first_name,review_text)
    await update.message.reply_text("✅ *Thank you for your review!* ✅\n\nYour feedback has been sent to the admin.\nUse /start to go back.", parse_mode=ParseMode.MARKDOWN)
    for aid in store.get_admins():
        try: await context.bot.send_message(aid, f"⭐ *NEW REVIEW* ⭐\n\n👤 User: *{user.first_name}*\n🆔 ID: `{user.id}`\n📝 Review: _{review_text}_", parse_mode=ParseMode.MARKDOWN)
        except: pass
    return ConversationHandler.END

# ============================================================
# ADMIN PANEL
# ============================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not store.is_admin(query.from_user.id): await query.edit_message_text("❌ *Unauthorized!*", parse_mode=ParseMode.MARKDOWN); return
    pending = store.get_pending_teams()
    approved = store.get_approved_teams()
    btns = [
        [InlineKeyboardButton(f"📋 Pending Teams ({len(pending)})",callback_data="admin_pending")],
        [InlineKeyboardButton(f"✅ Approved Teams ({len(approved)})",callback_data="admin_approved")],
        [InlineKeyboardButton("➕ Add Admin",callback_data="admin_addadmin")],
        [InlineKeyboardButton("➖ Remove Admin",callback_data="admin_rmadmin")],
        [InlineKeyboardButton("📢 Add Channel",callback_data="admin_addchannel")],
        [InlineKeyboardButton("🔇 Remove Channel",callback_data="admin_rmchannel")],
        [InlineKeyboardButton("💬 Message Leader",callback_data="admin_msgleader")],
        [InlineKeyboardButton("📢 Broadcast",callback_data="admin_broadcast")],
        [InlineKeyboardButton("⭐ Reviews",callback_data="admin_reviews")],
        [InlineKeyboardButton("📜 History",callback_data="admin_history")],
        [InlineKeyboardButton("🔙 Back",callback_data="back_start")]
    ]
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *ADMIN PANEL* ⚙️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Pending: `{len(pending)}`\n"
        f"✅ Approved: `{len(approved)}/{MAX_TEAMS}`\n"
        f"👥 Admins: `{len(store.get_admins())}`\n"
        f"📢 Channels: `{len(store.get_channels())}`\n\n"
        "👇 *Select an option:*",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

async def admin_pending_list(update,ctx):
    q=update.callback_query; await q.answer()
    p=store.get_pending_teams()
    if not p: await q.edit_message_text("✅ *No pending teams!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    await q.edit_message_text("📋 *Pending Teams:*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tn,callback_data=f"viewteam_{tn}")] for tn in p]+[[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN)

async def view_team(update,ctx):
    q=update.callback_query; await q.answer()
    tn=q.data.replace("viewteam_",""); t=store.get_team(tn)
    if not t: return
    ps="\n".join([f"  👤 {p['user_name']} - `{p.get('user_ff_id','N/A')}`" for p in t["players"]]) if t["players"] else "  (No players yet)"
    em={"pending":"⏳","approved":"✅","rejected":"❌"}.get(t["status"],"❓")
    await q.edit_message_text(f"{em} *Team: {tn}*\n\n👑 Leader: *{t['leader_name']}*\n🆔 ID: `{t['leader_id']}`\n🔫 FF ID: `{t['ff_id']}`\n📊 Status: *{t['status'].upper()}*\n👥 Players ({len(t['players'])}/{MAX_PLAYERS_PER_TEAM}):\n{ps}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve",callback_data=f"approve_{tn}"),InlineKeyboardButton("❌ Reject",callback_data=f"reject_{tn}")],[InlineKeyboardButton("🔙 Back",callback_data="admin_pending")]]),parse_mode=ParseMode.MARKDOWN)

async def admin_approved_list(update,ctx):
    q=update.callback_query; await q.answer()
    a=store.get_approved_teams()
    if not a: await q.edit_message_text("❌ *No approved teams!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    lines=[f"{i}. *{tn}* — 👑 {store.get_team(tn)['leader_name']} ({len(store.get_team(tn)['players'])}/{MAX_PLAYERS_PER_TEAM})" for i,tn in enumerate(a,1)]
    await q.edit_message_text("━━━━━━━━━━━━━━━━━━━━\n✅ *APPROVED TEAMS* ✅\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(lines),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN)

async def admin_add_admin_start(update,ctx):
    q=update.callback_query; await q.answer()
    await q.edit_message_text("➕ *Add New Admin*\n\nSend the user's Telegram ID:\n(Example: `123456789`)\n\n└ Send below 👇",parse_mode=ParseMode.MARKDOWN); return ADMIN_ADD_ADMIN
async def admin_receive_add_admin(update,ctx):
    try: store.add_admin(int(update.message.text.strip())); await update.message.reply_text("✅ *Admin added!*",parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("❌ *Invalid ID!*",parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END
async def admin_remove_admin_start(update,ctx):
    q=update.callback_query; await q.answer()
    await q.edit_message_text("➖ *Remove Admin*\n\nSend the user's Telegram ID:\n(Example: `123456789`)\n\n└ Send below 👇",parse_mode=ParseMode.MARKDOWN); return ADMIN_REMOVE_ADMIN
async def admin_receive_remove_admin(update,ctx):
    try:
        uid=int(update.message.text.strip())
        if uid in ADMIN_IDS: await update.message.reply_text("❌ *Cannot remove main admin!*",parse_mode=ParseMode.MARKDOWN)
        else: store.remove_admin(uid); await update.message.reply_text("✅ *Admin removed!*",parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("❌ *Invalid ID!*",parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END
async def admin_add_channel_start(update,ctx):
    q=update.callback_query; await q.answer()
    await q.edit_message_text("📢 *Add Force Join Channel*\n\nSend the channel username or ID:\n(Example: `@my_channel` or `-1001234567890`)\n\n└ Send below 👇",parse_mode=ParseMode.MARKDOWN); return ADMIN_ADD_CHANNEL
async def admin_receive_add_channel(update,ctx):
    store.add_channel(update.message.text.strip()); await update.message.reply_text("✅ *Channel added!*",parse_mode=ParseMode.MARKDOWN); return ConversationHandler.END
async def admin_remove_channel_start(update,ctx):
    q=update.callback_query; await q.answer()
    chs=store.get_channels()
    if not chs: await q.edit_message_text("❌ *No channels!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    btns=[[InlineKeyboardButton(ch,callback_data=f"rmch_{ch}")] for ch in chs]+[[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]
    await q.edit_message_text("📢 *Remove Channel:*",reply_markup=InlineKeyboardMarkup(btns),parse_mode=ParseMode.MARKDOWN)
async def admin_remove_channel_cb(update,ctx):
    q=update.callback_query; await q.answer()
    store.remove_channel(q.data.replace("rmch_","")); await q.edit_message_text("✅ *Channel removed!*",parse_mode=ParseMode.MARKDOWN)
async def admin_msg_leader_start(update,ctx):
    q=update.callback_query; await q.answer()
    a=store.get_approved_teams()
    if not a: await q.edit_message_text("❌ *No approved teams!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    btns=[[InlineKeyboardButton(tn,callback_data=f"msgl_{tn}")] for tn in a]+[[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]
    await q.edit_message_text("💬 *Message a Team Leader*\n\nSelect a team:",reply_markup=InlineKeyboardMarkup(btns),parse_mode=ParseMode.MARKDOWN)
async def admin_msg_leader_select(update,ctx):
    q=update.callback_query; await q.answer()
    tn=q.data.replace("msgl_",""); store.set_temp(f"msg_team_{q.from_user.id}",tn)
    await q.edit_message_text(f"💬 *Message Leader of {tn}*\n\nSend your message below:\n└ Write and send 👇",parse_mode=ParseMode.MARKDOWN); return ADMIN_MSG_LEADER
async def admin_receive_msg_leader(update,ctx):
    uid=update.effective_user.id; tn=store.get_temp(f"msg_team_{uid}")
    if not tn: return ConversationHandler.END
    t=store.get_team(tn)
    if not t: return ConversationHandler.END
    msg=update.message.text.strip()
    try: await ctx.bot.send_message(t["leader_id"],f"📩 *Message from Admin* 📩\n\n_{msg}_",parse_mode=ParseMode.MARKDOWN); await update.message.reply_text(f"✅ *Message sent to* {t['leader_name']}!",parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("❌ *Failed to send message!*",parse_mode=ParseMode.MARKDOWN)
    store.del_temp(f"msg_team_{uid}"); return ConversationHandler.END
async def admin_broadcast(update,ctx):
    q=update.callback_query; await q.answer()
    await q.edit_message_text("📢 *BROADCAST*\n\nSend the message to broadcast to ALL registered users:\n└ Write and send 👇",parse_mode=ParseMode.MARKDOWN)
    store.set_temp(f"broadcast_{q.from_user.id}",True); return ADMIN_MSG_LEADER
async def admin_receive_broadcast(update,ctx):
    uid=update.effective_user.id
    if not store.get_temp(f"broadcast_{uid}"): return
    msg=update.message.text.strip(); s,f=0,0; nf=set()
    for tn,t in store.get_all_teams().items():
        if t["leader_id"] not in nf:
            try: await ctx.bot.send_message(t["leader_id"],f"📢 *BROADCAST* 📢\n\n_{msg}_",parse_mode=ParseMode.MARKDOWN); s+=1
            except: f+=1
            nf.add(t["leader_id"])
        for p in t["players"]:
            if p["user_id"] and p["user_id"] not in nf:
                try: await ctx.bot.send_message(p["user_id"],f"📢 *BROADCAST* 📢\n\n_{msg}_",parse_mode=ParseMode.MARKDOWN); s+=1
                except: f+=1
                nf.add(p["user_id"])
    await update.message.reply_text(f"📢 *Broadcast Complete*\n\n✅ Sent: `{s}`\n❌ Failed: `{f}`",parse_mode=ParseMode.MARKDOWN)
    store.del_temp(f"broadcast_{uid}"); return ConversationHandler.END
async def admin_reviews(update,ctx):
    q=update.callback_query; await q.answer()
    rv=store.get_reviews()
    if not rv: await q.edit_message_text("⭐ *No reviews yet!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    lines=[f"{i}. 👤 *{r['user_name']}*: _{r['review_text']}_" for i,r in enumerate(rv[-10:],1)]
    await q.edit_message_text("━━━━━━━━━━━━━━━━━━━━\n⭐ *RECENT REVIEWS* ⭐\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(lines),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN)
async def admin_history(update,ctx):
    q=update.callback_query; await q.answer()
    h=store.get_history()
    if not h: await q.edit_message_text("📜 *No history yet!*",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN); return
    lines=[f"{i}. 🏷️ *{h['team_name']}* — 👑 {h['leader_name']} ({h['players_count']} players)" for i,h in enumerate(h[-20:],1)]
    await q.edit_message_text("━━━━━━━━━━━━━━━━━━━━\n📜 *TOURNAMENT HISTORY* 📜\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(lines),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back",callback_data="admin_panel")]]),parse_mode=ParseMode.MARKDOWN)
async def back_start(update,ctx):
    q=update.callback_query; await q.answer()
    await start(update,ctx)

# ============================================================
# CALLBACK ROUTER
# ============================================================
async def callback_router(update,ctx):
    q=update.callback_query; d=q.data
    if d=="check_join": await check_join_callback(update,ctx)
    elif d=="leader_reg": await leader_reg_start(update,ctx)
    elif d=="leader_panel":
        uid=q.from_user.id; tn,tm=store.get_team_by_leader(uid)
        if tn: await show_leader_panel(update,ctx,tn,tm)
        else: await q.answer("Not found!")
    elif d=="player_reg": await player_reg_start(update,ctx)
    elif d=="give_review": await give_review_start(update,ctx)
    elif d=="admin_panel": await admin_panel(update,ctx)
    elif d=="admin_pending": await admin_pending_list(update,ctx)
    elif d=="admin_approved": await admin_approved_list(update,ctx)
    elif d=="admin_addadmin": await admin_add_admin_start(update,ctx)
    elif d=="admin_rmadmin": await admin_remove_admin_start(update,ctx)
    elif d=="admin_addchannel": await admin_add_channel_start(update,ctx)
    elif d=="admin_rmchannel": await admin_remove_channel_start(update,ctx)
    elif d=="admin_msgleader": await admin_msg_leader_start(update,ctx)
    elif d=="admin_broadcast": await admin_broadcast(update,ctx)
    elif d=="admin_reviews": await admin_reviews(update,ctx)
    elif d=="admin_history": await admin_history(update,ctx)
    elif d=="back_start": await back_start(update,ctx)
    elif d.startswith("viewteam_"): await view_team(update,ctx)
    elif d.startswith("approve_"): await admin_approve_team_cb(update,ctx)
    elif d.startswith("reject_"): await admin_reject_team_cb(update,ctx)
    elif d.startswith("lapprove_"): await leader_approve_player(update,ctx)
    elif d.startswith("lreject_"): await leader_reject_player(update,ctx)
    elif d.startswith("join_"): await player_select_team(update,ctx)
    elif d.startswith("rmch_"): await admin_remove_channel_cb(update,ctx)
    elif d.startswith("msgl_"): await admin_msg_leader_select(update,ctx)
    else: await q.answer()

# ============================================================
# MAIN
# ============================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    lr_conv = ConversationHandler([CallbackQueryHandler(leader_reg_start,pattern="^leader_reg$")],
        {WAITING_FF_ID:[MessageHandler(filters.TEXT&~filters.COMMAND,receive_ff_id)],
         WAITING_TEAM_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,receive_team_name)],
         WAITING_PLAYER_LIST:[MessageHandler(filters.TEXT&~filters.COMMAND,receive_players)]},
        fallbacks=[],per_message=False)

    pl_conv = ConversationHandler([CallbackQueryHandler(player_select_team,pattern=r"^join_")],
        {WAITING_PLAYER_FF_ID:[MessageHandler(filters.TEXT&~filters.COMMAND,player_receive_ff_id)],
         WAITING_PLAYER_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,player_receive_name)]},
        fallbacks=[],per_message=False)

    rv_conv = ConversationHandler([CallbackQueryHandler(give_review_start,pattern="^give_review$")],
        {WAITING_REVIEW:[MessageHandler(filters.TEXT&~filters.COMMAND,receive_review)]},
        fallbacks=[],per_message=False)

    aa_conv = ConversationHandler([CallbackQueryHandler(admin_add_admin_start,pattern="^admin_addadmin$")],
        {ADMIN_ADD_ADMIN:[MessageHandler(filters.TEXT&~filters.COMMAND,admin_receive_add_admin)]},fallbacks=[],per_message=False)
    ra_conv = ConversationHandler([CallbackQueryHandler(admin_remove_admin_start,pattern="^admin_rmadmin$")],
        {ADMIN_REMOVE_ADMIN:[MessageHandler(filters.TEXT&~filters.COMMAND,admin_receive_remove_admin)]},fallbacks=[],per_message=False)
    ac_conv = ConversationHandler([CallbackQueryHandler(admin_add_channel_start,pattern="^admin_addchannel$")],
        {ADMIN_ADD_CHANNEL:[MessageHandler(filters.TEXT&~filters.COMMAND,admin_receive_add_channel)]},fallbacks=[],per_message=False)
    ml_conv = ConversationHandler([CallbackQueryHandler(admin_msg_leader_select,pattern=r"^msgl_")],
        {ADMIN_MSG_LEADER:[MessageHandler(filters.TEXT&~filters.COMMAND,admin_receive_msg_leader)]},fallbacks=[],per_message=False)
    bc_conv = ConversationHandler([CallbackQueryHandler(admin_broadcast,pattern="^admin_broadcast$")],
        {ADMIN_MSG_LEADER:[MessageHandler(filters.TEXT&~filters.COMMAND,admin_receive_broadcast)]},fallbacks=[],per_message=False)
    rj_conv = ConversationHandler([CallbackQueryHandler(admin_reject_team_cb,pattern=r"^reject_")],
        {ADMIN_APPROVAL_REASON:[MessageHandler(filters.TEXT&~filters.COMMAND,receive_reject_reason)]},fallbacks=[],per_message=False)

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("playerson",playerson_command))
    app.add_handler(CommandHandler("teams",teams_cmd))
    app.add_handler(CommandHandler("players",players_cmd))
    app.add_handler(CommandHandler("admin",admin_msg_cmd))
    app.add_handler(CommandHandler("addchannel",lambda u,c: store.add_channel(u.message.text.replace("/addchannel ","").strip()) and u.message.reply_text("✅ Channel added!") if len(u.message.text.replace("/addchannel ","").strip())>0 and store.is_admin(u.effective_user.id) else u.message.reply_text("❌ Failed!")))
    app.add_handler(CommandHandler("rmchannels",lambda u,c: u.message.reply_text(f"Channels: {store.get_channels()}") if store.is_admin(u.effective_user.id) else None))

    app.add_handler(lr_conv); app.add_handler(pl_conv); app.add_handler(rv_conv)
    app.add_handler(aa_conv); app.add_handler(ra_conv); app.add_handler(ac_conv)
    app.add_handler(ml_conv); app.add_handler(bc_conv); app.add_handler(rj_conv)
    app.add_handler(CallbackQueryHandler(callback_router))

    logger.info("🤖 Free Fire Tournament Bot Started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()