import os
import random
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.raw import functions

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
CONTACT_BOT_TOKEN = os.environ.get("CONTACT_BOT_TOKEN", "")

raw_group_id = os.environ.get("LOG_GROUP_ID", "0").strip()
try:
    LOG_GROUP_ID = int(raw_group_id)
except ValueError:
    LOG_GROUP_ID = 0

bot = Client(
    "ekaki_support_bot_final_v2",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=CONTACT_BOT_TOKEN
)

user_topics = {}
topic_users = {}
blocked_users = set()
all_users = set()
awaiting_report = set()

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

    if not topic_id:
        try:
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
                    message_thread_id=topic_id,
                    text=f"🔔 **New Support Ticket Opened!**\n👤 User: {user_name} (ID: `{user_id}`)"
                )
        except Exception as e:
            print(f"TOPIC CREATION ERROR: {e}")

    sent = False
    if topic_id:
        try:
            await message.copy(chat_id=LOG_GROUP_ID, message_thread_id=topic_id)
            sent = True
        except Exception as e:
            print(f"COPY ERROR: {e}")

    if sent:
        await message.reply_text(
            "✅ **Message Received!** 🚀\n\n"
            "💬 Aapka message hamari support team tak pahunch gaya hai. Hum jald hi reply karenge! ✨"
        )
    else:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Report Issue / Complaint", callback_data="report_issue")]])
        await message.reply_text("❌ Message delivery failed!", reply_markup=btn)

@bot.on_message(filters.chat(LOG_GROUP_ID))
async def handle_admin_actions(client: Client, message: Message):
    if message.service or (message.from_user and message.from_user.is_bot):
        return

    topic_id = getattr(message, "message_thread_id", None)
    text = message.text or message.caption or ""

    if text.startswith("/broadcast") and message.reply_to_message:
        success = 0
        fail = 0
        bc_msg = message.reply_to_message
        for uid in list(all_users):
            try:
                await bc_msg.copy(chat_id=uid)
                success += 1
            except Exception:
                fail += 1
        await message.reply_text(f"📢 **Broadcast Complete!**\n✅ Sent: {success}\n❌ Failed: {fail}")
        return

    if text.startswith("/stats"):
        await message.reply_text(
            f"📈 **Bot Statistics:**\n"
            f"👥 Total Users: {len(all_users)}\n"
            f"🎫 Active Tickets: {len(topic_users)}\n"
            f"🚫 Blocked Users: {len(blocked_users)}"
        )
        return

    if not topic_id or topic_id not in topic_users:
        return

    target_user_id = topic_users[topic_id]

    if text.startswith("/close"):
        try:
            del user_topics[target_user_id]
            del topic_users[topic_id]
            await message.reply_text("🔒 **Ticket Closed Successfully!**")
            await client.send_message(
                chat_id=target_user_id,
                text="🔒 **Your support ticket has been closed.** Contact us again anytime if you need help!"
            )
        except Exception as e:
            print(f"CLOSE ERROR: {e}")
        return

    if text.startswith("/block"):
        blocked_users.add(target_user_id)
        await message.reply_text(f"🚫 User `{target_user_id}` has been blocked.")
        return

    if text.startswith("/unblock"):
        if target_user_id in blocked_users:
            blocked_users.remove(target_user_id)
            await message.reply_text(f"✅ User `{target_user_id}` has been unblocked.")
        else:
            await message.reply_text("⚠️ User is not blocked.")
        return

    if text.startswith("/userinfo"):
        await message.reply_text(
            f"📊 **User Details:**\n"
            f"🆔 User ID: `{target_user_id}`\n"
            f"📌 Topic ID: `{topic_id}`\n"
            f"🚫 Blocked Status: {target_user_id in blocked_users}"
        )
        return

    try:
        await message.copy(chat_id=target_user_id)
    except Exception as e:
        print(f"ADMIN REPLY ERROR: {e}")

if __name__ == "__main__":
    print("Starting EKAKI Support Bot...")
    bot.run()
    
