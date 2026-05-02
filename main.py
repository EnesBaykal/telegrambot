import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Fetch variables
token = os.getenv("BOT_TOKEN")
admin_id_raw = os.getenv("ADMIN_ID")

# Debugging Panel: Warn before starting the bot if variables are missing
if not token or not admin_id_raw:
    print("❌ ERROR: BOT_TOKEN or ADMIN_ID not found in .env file!")
    print(f"Fetched Token: {token}")
    print(f"Fetched ID: {admin_id_raw}")
    exit() # Stop the program here to prevent crashing

BOT_TOKEN = token
ADMIN_ID = int(admin_id_raw)

bot = telebot.TeleBot(BOT_TOKEN)

# Database connection and table creation
try:
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            selected_product TEXT,
            delivery_address TEXT,
            order_date DATETIME,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    conn.commit()
except sqlite3.Error as e:
    print(f"Database error: {e}")

# Dictionary to store user data
user_data = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton('Product 1', callback_data='product1')
        btn2 = InlineKeyboardButton('Product 2', callback_data='product2')
        btn3 = InlineKeyboardButton('Product 3', callback_data='product3')
        markup.row(btn1, btn2, btn3)
        bot.send_message(message.chat.id, "Hello! Please select a product:", reply_markup=markup)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "An error occurred, please try again.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('product'))
def callback_query(call):
    try:
        chat_id = call.message.chat.id
        user_data[chat_id] = {'selected_product': call.data}
        bot.send_message(chat_id, "Please enter your delivery address:")
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(chat_id, "An error occurred, please try again.")

# Authorization Check
def is_admin(user_id):
    return user_id == ADMIN_ID

# Handler catching admin buttons
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    try:
        # 1. Extra Security: Is the clicker really an admin?
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "You are not authorized for this action.")
            return

        # 2. Fetching Pending Orders
        if call.data == "admin_pending":
            cursor.execute("SELECT id, username, selected_product, delivery_address, order_date FROM orders WHERE status = 'Pending'")
            pending_orders = cursor.fetchall()
            
            if not pending_orders:
                bot.send_message(call.message.chat.id, "📦 You have no pending orders right now.")
                bot.answer_callback_query(call.id)
                return
            
            for order in pending_orders:
                message_text = f"📦 **PENDING ORDER**\n\n"
                message_text += f"🆔 Order No: {order[0]}\n"
                message_text += f"👤 Customer: @{order[1]}\n"
                message_text += f"🛍️ Product: {order[2]}\n"
                message_text += f"📍 Address: {order[3]}\n"
                message_text += f"📅 Date: {order[4]}\n"
                
                markup = InlineKeyboardMarkup()
                btn = InlineKeyboardButton("✅ Mark as Completed", callback_data=f"complete_{order[0]}")
                markup.row(btn)
                
                bot.send_message(call.message.chat.id, message_text, reply_markup=markup)
            
            bot.answer_callback_query(call.id)

        # 3. Completed Orders 
        elif call.data == "admin_completed":
            cursor.execute("SELECT id, username, selected_product, delivery_address, order_date FROM orders WHERE status = 'Completed'")
            completed_orders = cursor.fetchall()
            
            if not completed_orders:
                bot.send_message(call.message.chat.id, "✅ You have no completed orders right now.")
                bot.answer_callback_query(call.id)
                return
            
            for order in completed_orders:
                message_text = f"✅ **COMPLETED ORDER**\n\n"
                message_text += f"🆔 Order No: {order[0]}\n"
                message_text += f"👤 Customer: @{order[1]}\n"
                message_text += f"🛍️ Product: {order[2]}\n"
                message_text += f"📍 Address: {order[3]}\n"
                message_text += f"📅 Date: {order[4]}\n"
                
                bot.send_message(call.message.chat.id, message_text)
            
            bot.answer_callback_query(call.id)
            
    except Exception as e:
        print(f"Admin Callback Error: {e}")
        bot.send_message(call.message.chat.id, "An error occurred while fetching orders.")

# Handler for marking order as completed
@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
def complete_order(call):
    try:
        # Security Check
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "You are not authorized for this action.", show_alert=True)
            return

        # Extract ID and update database
        order_id = int(call.data.split('_')[1])
        cursor.execute("UPDATE orders SET status = 'Completed' WHERE id = ?", (order_id,))
        conn.commit()
        
        # Update message (Button disappears automatically)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"✅ Order #{order_id} Completed!")
        
        # UX: Stop the loading icon and show a small notification
        bot.answer_callback_query(call.id, "Order completed!")
        
    except Exception as e:
        print(f"Error while completing order: {e}")
        bot.answer_callback_query(call.id, "An error occurred!")

# Admin command (Must come before the Catch-all handler!)
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return

    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("📦 Pending Orders", callback_data="admin_pending")
    btn2 = InlineKeyboardButton("✅ Completed Orders", callback_data="admin_completed")
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id, 
        "🛠️ Welcome to the Admin Panel.\nPlease select an action:", 
        reply_markup=markup
    )
    
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        chat_id = message.chat.id
        if chat_id in user_data and 'selected_product' in user_data[chat_id]:
            user_data[chat_id]['delivery_address'] = message.text
            user_data[chat_id]['user_id'] = message.from_user.id
            user_data[chat_id]['username'] = message.from_user.username or "No Username"
            user_data[chat_id]['order_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 1. Database Insertion with Correct Schema
            cursor.execute('''
                INSERT INTO orders (user_id, username, selected_product, delivery_address, order_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_data[chat_id]['user_id'],
                user_data[chat_id]['username'],
                user_data[chat_id]['selected_product'],
                user_data[chat_id]['delivery_address'],
                user_data[chat_id]['order_date']
            ))
            
            # 2. Get ID safely right before commit
            order_id = cursor.lastrowid 
            conn.commit()

            # 3. Professional and Aesthetic Order Summary (HTML format)
            receipt_message = (
                "✅ <b>Order Received Successfully!</b>\n\n"
                f"📦 <b>Order No:</b> #{order_id}\n"
                f"🛍️ <b>Product:</b> {user_data[chat_id]['selected_product']}\n"
                f"📍 <b>Delivery Address:</b> {user_data[chat_id]['delivery_address']}\n"
                f"📅 <b>Date:</b> {user_data[chat_id]['order_date']}\n\n"
                "<i>You will be notified when your order is shipped.</i>"
            )

            # 4. Send Message to User (with HTML Parse Mode)
            bot.send_message(chat_id, receipt_message, parse_mode='HTML')

            # 5. Clear Session Data
            del user_data[chat_id]
        else:
            send_welcome(message)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "An error occurred, please try again.")

# Run the bot
try:
    bot.polling(none_stop=True)
except Exception as e:
    print(f"An error occurred while the bot was running: {e}")