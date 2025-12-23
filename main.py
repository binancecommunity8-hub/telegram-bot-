#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   🌟 Professional Group/Channel Manager Bot with Crypto Payments 🌟  ║
║                                                                       ║
║   ✨ Features:                                                        ║
║   • Beautiful 2-column channel button grid layout                    ║
║   • Admin panel with full group/broadcast control                    ║
║   • Cryptomus USDT payment integration                               ║
║   • Auto payment status polling (30s intervals)                      ║
║   • User statistics & payment analytics                              ║
║   • Auto-install all required packages                               ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""

import sys
import subprocess
import os
import json
import logging
import html
from datetime import datetime
import time
import threading
import asyncio
from typing import Dict, Any, List, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════
# 📦 AUTO-INSTALL REQUIRED PACKAGES
# ═══════════════════════════════════════════════════════════════════════

def install_packages():
    """Auto-install all required packages silently"""
    print("🔧 Checking & installing required packages...")
    packages = ["python-telegram-bot==20.0", "requests"]
    
    for pkg in packages:
        pkg_name = pkg.split("==")[0].replace("-", "_")
        try:
            __import__(pkg_name)
            print(f"  ✅ {pkg.split('==')[0]} - already installed")
        except ImportError:
            print(f"  📦 Installing {pkg}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"  ✅ {pkg.split('==')[0]} - installed successfully")

install_packages()

# ═══════════════════════════════════════════════════════════════════════
# 📚 IMPORTS
# ═══════════════════════════════════════════════════════════════════════

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import TimedOut, NetworkError

import requests

# ═══════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION & FILE PATHS
# ═══════════════════════════════════════════════════════════════════════

# Core files
GROUPS_FILE = "groups.json"
USERS_FILE = "users.txt"
ADMIN_PASSWORD = "Faisal7788"

# Payment system files
CRYPTO_CONFIG_FILE = "cryptomus_config.json"     # {"api_key": "...", "merchant_id": "..."}
PAYMENT_CONFIG_FILE = "payment_config.json"      # {"usdt": 10}
PAYMENTS_FILE = "payments.json"                  # Payment records

# Conversation states
(
    PASSWORD_STATE,
    ADMIN_MENU_STATE,
    ADD_GROUP_NAME_STATE,
    ADD_GROUP_LINK_STATE,
    REMOVE_GROUP_STATE,
    BROADCAST_STATE,
    SET_PAYMENT_AMOUNT_STATE,
) = range(7)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 🛠️ UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def safe_html(text: str) -> str:
    """Escape HTML special characters"""
    return html.escape(text or "", quote=True)

def ensure_files():
    """Create all required files if they don't exist"""
    files_config = {
        GROUPS_FILE: {},
        CRYPTO_CONFIG_FILE: {},
        PAYMENT_CONFIG_FILE: {},
        PAYMENTS_FILE: [],
    }
    
    for fname, default_content in files_config.items():
        if not os.path.isfile(fname):
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(default_content, f, ensure_ascii=False, indent=2)
    
    if not os.path.isfile(USERS_FILE):
        open(USERS_FILE, "w", encoding="utf-8").close()

def load_json(fname: str, default=None):
    """Load JSON file with error handling"""
    try:
        with open(fname, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {fname}: {e}")
        return {} if default is None else default

def save_json(fname: str, data: Any):
    """Save data to JSON file"""
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════
# 👥 USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

def add_user(user_id: int, user_name: str, username: Optional[str] = None):
    """Add new user to database"""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except:
        lines = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{user_id}|{user_name}|{username or 'N/A'}|{timestamp}"
    
    if not any(line.startswith(f"{user_id}|") for line in lines):
        with open(USERS_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
        logger.info(f"✨ New user joined: {user_name} (@{username}) - ID: {user_id}")

def get_users() -> List[Tuple[str, str, str, str]]:
    """Get all registered users"""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except:
        return []
    
    users = []
    for line in lines:
        parts = line.split("|")
        if len(parts) == 4:
            users.append(tuple(parts))
    return users

# ═══════════════════════════════════════════════════════════════════════
# 📋 GROUP/CHANNEL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

def load_groups() -> Dict[str, str]:
    """Load all groups/channels"""
    ensure_files()
    return load_json(GROUPS_FILE, {})

def save_groups(data: Dict[str, str]):
    """Save groups/channels to file"""
    save_json(GROUPS_FILE, data)

def build_channels_keyboard(groups: Dict[str, str]) -> InlineKeyboardMarkup:
    """
    Build beautiful 2-column channel button grid
    Like the image you shared - rounded URL buttons in 2 columns
    """
    rows = []
    items = list(groups.items())
    
    # Create 2-column grid of channel buttons
    for i in range(0, len(items), 2):
        row = []
        for j in range(2):
            if i + j < len(items):
                name, link = items[i + j]
                row.append(InlineKeyboardButton(text=str(name), url=str(link)))
        rows.append(row)
    
    # Add action buttons below channel grid
    rows.append([InlineKeyboardButton("💸 Make Payment", callback_data="make_payment")])
    rows.append([InlineKeyboardButton("🔄 Refresh Channels", callback_data="refresh")])
    
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════════════════
# 💰 CRYPTOMUS PAYMENT SYSTEM
# ═══════════════════════════════════════════════════════════════════════

def get_crypto_config():
    """Get Cryptomus API configuration"""
    ensure_files()
    config = load_json(CRYPTO_CONFIG_FILE, {})
    if not config.get("api_key") or not config.get("merchant_id"):
        return None
    return config

def get_payment_amount() -> int:
    """Get current payment amount in USDT"""
    ensure_files()
    data = load_json(PAYMENT_CONFIG_FILE, {})
    try:
        return int(data.get("usdt", 10))
    except:
        return 10

def set_payment_amount_value(amount: int):
    """Set new payment amount"""
    save_json(PAYMENT_CONFIG_FILE, {"usdt": int(amount)})

def get_payments() -> List[Dict[str, Any]]:
    """Get all payment records"""
    ensure_files()
    try:
        with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_payments(payments: List[Dict[str, Any]]):
    """Save payment records"""
    save_json(PAYMENTS_FILE, payments)

def add_payment(user_id: int, username: str, amount: int, uuid: str, status: str, url: str, date: str):
    """Add new payment record"""
    payments = get_payments()
    payments.append({
        "user_id": user_id,
        "username": username,
        "amount": amount,
        "uuid": uuid,
        "status": status,
        "url": url,
        "date": date,
    })
    save_payments(payments)

def update_payment_status(uuid: str, new_status: str):
    """Update payment status"""
    payments = get_payments()
    for p in payments:
        if p.get("uuid") == uuid:
            p["status"] = new_status
            p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_payments(payments)

def get_invoice_status(uuid: str) -> str:
    """Check invoice status from Cryptomus API"""
    config = get_crypto_config()
    if not config:
        return "unknown"
    
    url = "https://api.cryptomus.com/v1/payment/info"
    payload = {"uuid": uuid}
    headers = {
        "merchant": config["merchant_id"],
        "sign": "",
        "Content-Type": "application/json",
        "Authorization": config["api_key"],
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        data = resp.json()
        if isinstance(data, dict) and "result" in data:
            return data["result"].get("payment_status", "unknown")
        return data.get("payment_status", "unknown")
    except Exception as ex:
        logger.error(f"❌ Error checking invoice status: {ex}")
        return "unknown"

def poll_payments():
    """Background thread to poll payment statuses every 30s"""
    while True:
        try:
            payments = get_payments()
            config = get_crypto_config()
            
            if not config or not payments:
                time.sleep(30)
                continue
            
            for p in payments:
                if p.get("status") == "pending":
                    uuid = p.get("uuid")
                    if not uuid:
                        continue
                    
                    new_status = get_invoice_status(uuid)
                    if new_status and new_status not in ("pending", "unknown"):
                        update_payment_status(uuid, new_status)
                        logger.info(f"💰 Payment {uuid} updated: {new_status}")
        except Exception as e:
            logger.error(f"❌ Payment polling error: {e}")
        
        time.sleep(30)

def create_invoice(user_id: int, username: str):
    """Create new Cryptomus invoice"""
    config = get_crypto_config()
    if not config:
        return None, None
    
    amount = get_payment_amount()
    order_id = f"{user_id}_{int(time.time())}"
    
    payload = {
        "amount": str(amount),
        "currency": "USDT",
        "order_id": order_id,
        "network": "tron",
    }
    
    headers = {
        "merchant": config["merchant_id"],
        "sign": "",
        "Content-Type": "application/json",
        "Authorization": config["api_key"],
    }
    
    try:
        resp = requests.post("https://api.cryptomus.com/v1/payment", 
                            json=payload, headers=headers, timeout=20)
        data = resp.json()
        result = data.get("result", {}) if isinstance(data, dict) else {}
        
        uuid = result.get("uuid")
        url = result.get("url")
        
        if uuid and url:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            add_payment(user_id, username, amount, uuid, "pending", url, now)
            logger.info(f"💸 Invoice created for {username}: {amount} USDT")
            return url, uuid
        
        logger.error(f"❌ Invoice creation failed: {data}")
        return None, None
    except Exception as ex:
        logger.error(f"❌ Error creating invoice: {ex}")
        return None, None

# ═══════════════════════════════════════════════════════════════════════
# 🔐 ADMIN PANEL HANDLERS
# ═══════════════════════════════════════════════════════════════════════

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel menu"""
    menu = [
        ["➕ Add Group", "🗑️ Remove Group"],
        ["📋 View All Groups", "📢 Broadcast Message"],
        ["👥 User Statistics", "💰 Set Payment Amount"],
        ["📊 Payment Statistics", "⬅️ Exit Admin Panel"],
    ]
    
    msg = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  🔐 <b>ADMIN PANEL</b> 🔐      ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "Select an option:"
    )
    
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True),
        parse_mode=ParseMode.HTML,
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for admin panel"""
    await update.message.reply_text(
        "🔑 <b>Admin Authentication</b>\n\nEnter admin password:",
        parse_mode=ParseMode.HTML
    )
    return PASSWORD_STATE

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify admin password"""
    pwd = update.message.text.strip()
    if pwd == ADMIN_PASSWORD:
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE
    
    await update.message.reply_text("❌ Incorrect password. Try again:")
    return PASSWORD_STATE

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin menu selections"""
    choice = (update.message.text or "").strip()

    # ➕ Add Group
    if choice == "➕ Add Group":
        await update.message.reply_text(
            "🌟 <b>Add New Group/Channel</b>\n\nSend the group name:",
            parse_mode=ParseMode.HTML
        )
        return ADD_GROUP_NAME_STATE

    # 🗑️ Remove Group
    elif choice == "🗑️ Remove Group":
        groups = load_groups()
        if not groups:
            await update.message.reply_text(
                "❌ <b>No Groups Available</b>\n\nAdd some groups first!",
                parse_mode=ParseMode.HTML,
            )
            await show_admin_menu(update, context)
            return ADMIN_MENU_STATE

        # 2-column layout for removal
        names = []
        group_names = list(groups.keys())
        for i in range(0, len(group_names), 2):
            row = [group_names[i]]
            if i + 1 < len(group_names):
                row.append(group_names[i + 1])
            names.append(row)
        names.append(["⬅️ Back to Menu"])

        await update.message.reply_text(
            "🗑️ <b>Remove Group</b>\n\nSelect group to remove:",
            reply_markup=ReplyKeyboardMarkup(names, one_time_keyboard=True, resize_keyboard=True),
            parse_mode=ParseMode.HTML,
        )
        return REMOVE_GROUP_STATE

    # 📋 View All Groups
    elif choice == "📋 View All Groups":
        groups = load_groups()
        if not groups:
            await update.message.reply_text("❌ <b>No Groups Available</b>", parse_mode=ParseMode.HTML)
            await show_admin_menu(update, context)
            return ADMIN_MENU_STATE

        msg = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃   📋 <b>ALL GROUPS LIST</b> 📋   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"<b>Total Groups:</b> {len(groups)}\n\n"
        )
        
        for idx, (name, link) in enumerate(groups.items(), 1):
            msg += f"<b>{idx}.</b> {safe_html(name)}\n"
            msg += f"    🔗 {safe_html(link)}\n\n"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE

    # 📢 Broadcast
    elif choice == "📢 Broadcast Message":
        await update.message.reply_text(
            "📢 <b>Broadcast Message</b>\n\nEnter message to send to all users:",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Back to Menu"]], resize_keyboard=True),
            parse_mode=ParseMode.HTML,
        )
        return BROADCAST_STATE

    # 👥 User Statistics
    elif choice == "👥 User Statistics":
        users = get_users()
        msg = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  👥 <b>USER STATISTICS</b> 👥  ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"<b>Total Users:</b> {len(users)}\n\n"
            "<b>Recent 10 Users:</b>\n"
        )
        
        for idx, (uid, name, uname, ts) in enumerate(users[-10:], 1):
            uname_txt = f"@{uname}" if uname and uname != "N/A" else "N/A"
            msg += f"{idx}. {safe_html(name)} ({uname_txt})\n    <code>{uid}</code>\n"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE

    # 💰 Set Payment Amount
    elif choice == "💰 Set Payment Amount":
        await update.message.reply_text(
            "💰 <b>Set Payment Amount</b>\n\nEnter amount in USDT (integer):",
            parse_mode=ParseMode.HTML
        )
        return SET_PAYMENT_AMOUNT_STATE

    # 📊 Payment Statistics
    elif choice == "📊 Payment Statistics":
        payments = get_payments()
        total = len(payments)
        successful = len([p for p in payments if p.get("status") == "paid"])
        pending = len([p for p in payments if p.get("status") == "pending"])
        failed = len([p for p in payments if p.get("status") == "failed"])
        recent = list(reversed(payments))[:5]

        msg = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃ 📊 <b>PAYMENT STATS</b> 📊    ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"📝 Total Payments: <b>{total}</b>\n"
            f"✅ Successful: <b>{successful}</b>\n"
            f"⏳ Pending: <b>{pending}</b>\n"
            f"❌ Failed: <b>{failed}</b>\n\n"
            f"<b>Last 5 Transactions:</b>\n"
        )
        
        if not recent:
            msg += "\n<i>No transactions yet.</i>\n"
        else:
            for idx, tx in enumerate(recent, 1):
                msg += (
                    f"\n{idx}. <b>{safe_html(tx.get('username','User'))}</b>\n"
                    f"   💰 {tx.get('amount')} USDT\n"
                    f"   📊 Status: <code>{tx.get('status')}</code>\n"
                    f"   📅 {tx.get('date')}"
                )

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE

    # ⬅️ Exit
    elif choice == "⬅️ Exit Admin Panel":
        await update.message.reply_text(
            "👋 <b>Logged Out Successfully!</b>\n\nUse /admin to access again.",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    # Default
    else:
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE

async def set_payment_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment amount setting"""
    amt = (update.message.text or "").strip()
    if amt.isdigit() and int(amt) > 0:
        set_payment_amount_value(int(amt))
        await update.message.reply_text(
            f"✅ Payment amount set to <b>{amt} USDT</b>",
            parse_mode=ParseMode.HTML
        )
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE
    
    await update.message.reply_text("❌ Invalid amount. Enter a positive integer.")
    return SET_PAYMENT_AMOUNT_STATE

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    text = update.message.text
    if text == "⬅️ Back to Menu":
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE
    
    users = get_users()
    sent = 0
    failed = 0
    
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=text)
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit protection
        except Exception:
            failed += 1
    
    await update.message.reply_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode=ParseMode.HTML
    )
    await show_admin_menu(update, context)
    return ADMIN_MENU_STATE

async def add_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: Get group name"""
    name = (update.message.text or "").strip()
    context.user_data["group_name"] = name
    await update.message.reply_text(
        "🔗 <b>Send Group Link</b>\n\nPaste the group/channel link:",
        parse_mode=ParseMode.HTML
    )
    return ADD_GROUP_LINK_STATE

async def add_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Get group link and save"""
    link = (update.message.text or "").strip()
    name = context.user_data.get("group_name", "Unnamed")
    
    groups = load_groups()
    groups[name] = link
    save_groups(groups)
    
    await update.message.reply_text(
        f"✅ <b>Group Added Successfully!</b>\n\n"
        f"📝 Name: {safe_html(name)}\n"
        f"🔗 Link: {safe_html(link)}",
        parse_mode=ParseMode.HTML
    )
    await show_admin_menu(update, context)
    return ADMIN_MENU_STATE

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove selected group"""
    choice = (update.message.text or "").strip()
    
    if choice == "⬅️ Back to Menu":
        await show_admin_menu(update, context)
        return ADMIN_MENU_STATE
    
    groups = load_groups()
    if choice in groups:
        groups.pop(choice, None)
        save_groups(groups)
        await update.message.reply_text(
            f"🗑️ <b>Group Removed!</b>\n\n{safe_html(choice)}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("❌ Invalid group selection.")
    
    await show_admin_menu(update, context)
    return ADMIN_MENU_STATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    await update.message.reply_text("❌ Operation canceled.")
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════
# 👤 USER-FACING HANDLERS (Clean UI - No username/ID shown)
# ═══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with beautiful channel button grid"""
    user = update.effective_user
    add_user(user.id, user.first_name or "User", user.username)

    groups = load_groups()
    
    welcome_msg = (
        "👋 <b>Welcome!</b>\n\n"
        "🌟 <b>Professional Channel Manager Bot</b>\n\n"
        "📋 <b>Available Channels</b>:\n"
    )
    
    if not groups:
        welcome_msg += "\n<i>❌ No channels available at the moment.</i>"
    
    kb = build_channels_keyboard(groups)
    
    if update.message:
        await update.message.reply_text(
            welcome_msg,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_msg,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )

async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh channel list"""
    query = update.callback_query
    await query.answer("🔄 Refreshing channels...")

    groups = load_groups()
    
    msg = (
        "👋 <b>Welcome!</b>\n\n"
        "🌟 <b>Professional Channel Manager Bot</b>\n\n"
        "📋 <b>Available Channels</b>:\n"
    )
    
    if not groups:
        msg += "\n<i>❌ No channels available at the moment.</i>"
    
    kb = build_channels_keyboard(groups)
    
    try:
        await query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await query.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

async def make_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment request"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "User"

    # Check if payment system is configured
    config = get_crypto_config()
    if not config:
        try:
            await query.message.reply_text(
                "❌ <b>Payment System Not Configured</b>\n\n"
                "Please contact the administrator.",
                parse_mode=ParseMode.HTML,
            )
        except (TimedOut, NetworkError):
            await asyncio.sleep(1)
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Payment system not configured yet!"
            )
        return

    # Create invoice
    amount = get_payment_amount()
    url, uuid = create_invoice(user_id, username)
    
    if not url:
        try:
            await query.message.reply_text(
                "❌ <b>Unable to Create Invoice</b>\n\n"
                "Please try again later or contact support.",
                parse_mode=ParseMode.HTML
            )
        except (TimedOut, NetworkError):
            await asyncio.sleep(1)
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Unable to create invoice. Try again later."
            )
        return

    # Send payment details
    payment_msg = (
        "💸 <b>Payment Request Created</b>\n\n"
        f"💰 Amount: <b>{amount} USDT</b>\n"
        f"🆔 Invoice ID: <code>{uuid}</code>\n\n"
        f"🔗 <a href='{url}'>Click here to pay via Cryptomus</a>\n\n"
        "⏳ <i>Payment status will update automatically within 30 seconds.</i>"
    )
    
    try:
        await query.message.reply_text(
            payment_msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
    except (TimedOut, NetworkError):
        await asyncio.sleep(1)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"💸 Pay {amount} USDT:\n\n{url}",
                disable_web_page_preview=False
            )
        except Exception as e:
            logger.error(f"❌ Fallback payment message failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error("⚠️ Exception in handler", exc_info=context.error)

# ═══════════════════════════════════════════════════════════════════════
# 🚀 MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Main application entry point"""
    
    print("\n" + "═" * 70)
    print("║                                                                  ║")
    print("║       🌟 Professional Channel Manager Bot with Payments 🌟      ║")
    print("║                                                                  ║")
    print("═" * 70)
    
    # Load or request bot token
    token_file = "bot_token.txt"
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            BOT_TOKEN = f.read().strip()
        print("✅ Bot token loaded from file")
    else:
        print("\n🔑 Bot token not found. Please enter it now.")
        BOT_TOKEN = input("Enter Bot Token: ").strip()
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(BOT_TOKEN)
        print("✅ Token saved to bot_token.txt")

    ensure_files()

    # Check Cryptomus configuration
    if not get_crypto_config():
        print("\n⚠️  Cryptomus payment system not configured!")
        print("📝 Edit 'cryptomus_config.json' with:")
        print('   {"api_key": "YOUR_API_KEY", "merchant_id": "YOUR_MERCHANT_ID"}')
        print("\n💡 Bot will start, but payments won't work until configured.\n")

    # Build application
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Admin conversation handler
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_cmd)],
        states={
            PASSWORD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            ADMIN_MENU_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_menu)],
            ADD_GROUP_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_group_name)],
            ADD_GROUP_LINK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_group_link)],
            REMOVE_GROUP_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_group)],
            BROADCAST_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast)],
            SET_PAYMENT_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_payment_amount_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="admin_conv",
        persistent=False,
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(make_payment_callback, pattern="^make_payment$"))
    app.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh$"))
    app.add_error_handler(error_handler)

    # Start payment polling thread
    threading.Thread(target=poll_payments, daemon=True).start()

    print("\n" + "═" * 70)
    print("✅ Bot is running successfully!")
    print("═" * 70)
    print(f"🔐 Admin Password: {ADMIN_PASSWORD}")
    print("💰 Payment Status Polling: Active (every 30s)")
    print("🛑 Press Ctrl+C to stop the bot")
    print("═" * 70 + "\n")

    # Start bot
    app.run_polling()

if __name__ == "__main__":
    import asyncio
    import sys

    # Fix for Python 3.10+ and especially 3.14 event loop issue
    if sys.platform == 'win32':
        # Windows needs WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Create and set a new event loop (required for Python 3.14+)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        logger.exception("Fatal error in main")
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass
