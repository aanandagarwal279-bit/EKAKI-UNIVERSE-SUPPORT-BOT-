import os
import re
import random
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.raw import functions

app = Flask(__name__)

@app.route('/')
def home():
    return "EKAKI Support Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
CONTACT_BOT_TOKEN = os.environ.get("CONTACT_BOT_TOKEN", "")

raw_group_id = os.environ.get("LOG_GROUP_ID", "0").strip()
try:
    LOG_GROUP_ID = int(raw_group_id)
except ValueError:
    LOG_GROUP_ID = 0

bot = Client(
    "ekaki_support_bot_final_v7",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=CONTACT_BOT_TOKEN
)

user_topics = {}          # user_id -> topic_id
topic_users = {}          # topic_id -> user_id
blocked_users = set()     # set of blocked user_ids
all_users = set()         # set of all unique user_ids
awaiting_report = set()   # users in report mode

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    all_users.add(user_id)
    await message.reply_text(
        "👋 **Welcome to EKAKI UNIVERSE Support!** 🌟\n\n"
        "💬 Aapko koi bhi query ho, yahan direct message bhejiye. Hamari team jald hi reply karegi!"
    )

@bot.on_callback_query(filters.regex("^report_issue$"))
async def handle_report_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    awaiting_report.add(user_id)
    await callback.answer("🚨 Report mode activated!")
    await callback.message.reply_text(
        "⚠️ **Report System Mode:**\n\n"
        "Kripya apni problem detail mein likhkar bhejiye. Hum direct admin alert ke zariye is error ko resolve karenge!"
    )

@bot.on_message(filters.private & ~filters.me)
async def handle_user_msg(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    all_users.add(user_id)

    if user_id in blocked_users:
        await message.reply_text("❌ You are blocked from contacting support.")
        return

    if user_id in awaiting_report:
        awaiting_report.remove(user_id)
        if LOG_GROUP_ID != 0:
            try:
                alert_text = (
                    f"🚨 **SYSTEM FAILURE REPORTED BY USER!**\n\n"
                    f"👤 **User:** {user_name} (`{user_id}`)\n"
                    f"📝 **Report/Message:** {message.text or '[Media/File]'}"
                )
                await client.send_message(chat_id=LOG_GROUP_ID, text=alert_text)
                await message.reply_text("✅ **Report Sent!** Hamari technical team ko aapki report mil gayi hai.")
                return
            except Exception as e:
                print(f"REPORT ERROR: {e}")

    if LOG_GROUP_ID == 0:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Report Issue / Complaint", callback_data="report_issue")]])
        await message.reply_text("❌ Message delivery failed!", reply_markup=btn)
        return

    topic_id = user_topics.get(user_id)
    is_new_ticket = False

    if not topic_id:
        try:
            is_new_ticket = True
            chat_obj = await client.get_chat(LOG_GROUP_ID)
            peer = await client.resolve_peer(chat_obj.id)
            
            response = await client.invoke(
                functions.channels.CreateForumTopic(
                    channel=peer,
                    title=f"👤 {user_name} | {user_id}",
                    random_id=random.randint(1, 2147483647)
                )
            )
            
            for update in getattr(response, "updates", []):
                if hasattr(update, "id") and type(update).__name__ == "UpdateChannelTopic":
                    topic_id = update.id
                    break
                elif hasattr(update, "topic_id"):
                    topic_id = update.topic_id
                    break
                elif hasattr(update, "message") and hasattr(update.message, "id"):
                    topic_id = update.message.id
                    break

            if topic_id:
                user_topics[user_id] = topic_id
                topic_users[topic_id] = user_id
                
                await client.send_message(
                    chat_id=LOG_GROUP_ID,
                    reply_to_message_id=topic_id,
                    text=f"🔔 **New Support Ticket Opened!**\n👤 User: {user_name} (ID: `{user_id}`)"
                )
        except Exception as e:
            print(f"TOPIC CREATION ERROR: {e}")

    sent = False
    if topic_id:
        try:
            await client.copy_message(
                chat_id=LOG_GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.id,
                reply_to_message_id=topic_id
            )
            sent = True
        except Exception as e:
            print(f"COPY ERROR: {e}")

    # Show confirmation message ONLY once when new ticket opens
    if sent and is_new_ticket:
        await message.reply_text(
            "✅ **Message Received!** 🚀\n\n"
            "💬 Aapka message hamari support team tak pahunch gaya hai. Hum jald hi reply karenge! ✨"
        )
    elif not sent:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Report Issue / Complaint", callback_data="report_issue")]])
        await message.reply_text("❌ Message delivery failed!", reply_markup=btn)

@bot.on_message(filters.chat(LOG_GROUP_ID))
async def handle_admin_actions(client: Client, message: Message):
    if message.service or (message.from_user and message.from_user.is_bot):
        return

    topic_id = getattr(message, "reply_to_message_id", None) or getattr(message, "message_thread_id", None)
    text = (message.text or message.caption or "").strip()

    # Global Broadcast Command
    if text.lower().startswith("/broadcast") and message.reply_to_message:
        success = 0
        fail = 0
        bc_msg = message.reply_to_message
        for uid in list(all_users):
            try:
                await client.copy_message(chat_id=uid, from_chat_id=bc_msg.chat.id, message_id=bc_msg.id)
                success += 1
            except Exception:
                fail += 1
        await message.reply_text(f"📢 **Broadcast Complete!**\n✅ Sent: {success}\n❌ Failed: {fail}")
        return

    # Global Stats Command
    if text.lower().startswith("/stats"):
        await message.reply_text(
            f"📈 **Bot Statistics:**\n"
            f"👥 Total Users: {len(all_users)}\n"
            f"🎫 Active Tickets: {len(topic_users)}\n"
            f"🚫 Blocked Users: {len(blocked_users)}"
        )
        return

    if not topic_id:
        return

    target_user_id = topic_users.get(topic_id)

    # Backup: Extract User ID directly if topic mapping is missing
    if not target_user_id or target_user_id == 0:
        if message.reply_to_message and message.reply_to_message.text:
            match = re.search(r"ID:\s*`?(\d+)`?", message.reply_to_message.text)
            if match:
                target_user_id = int(match.group(1))

    # Topic Commands
    if text.lower().startswith("/close"):
        if target_user_id:
            user_topics.pop(target_user_id, None)
            topic_users.pop(topic_id, None)
            try:
                await client.send_message(
                    chat_id=target_user_id,
                    text="🔒 **Your support ticket has been closed.** Contact us again anytime if you need help!"
                )
            except Exception:
                pass
        await message.reply_text("🔒 **Ticket Closed Successfully!**")
        return

    if text.lower().startswith("/block"):
        if target_user_id:
            blocked_users.add(target_user_id)
            await message.reply_text(f"🚫 User `{target_user_id}` has been blocked.")
        else:
            await message.reply_text("⚠️ Target User ID not found.")
        return

    if text.lower().startswith("/unblock"):
        if target_user_id:
            blocked_users.discard(target_user_id)
            await message.reply_text(f"✅ User `{target_user_id}` has been unblocked.")
        else:
            await message.reply_text("⚠️ Target User ID not found.")
        return

    if text.lower().startswith("/userinfo"):
        status = "Blocked" if target_user_id in blocked_users else "Active"
        await message.reply_text(
            f"📊 **User Details:**\n"
            f"🆔 User ID: `{target_user_id or 'Unknown'}`\n"
            f"📌 Topic ID: `{topic_id}`\n"
            f"🚫 Status: {status}"
        )
        return

    # Anonymous Admin Reply to User
    if target_user_id:
        try:
            await client.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.id
            )
        except Exception as e:
            print(f"ADMIN REPLY ERROR: {e}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    print("Starting EKAKI Support Bot Client...")
    bot.run()
    
