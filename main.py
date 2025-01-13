import requests
import telebot
import os
import sqlite3
import validators
import threading
import imgkit

BOT_TOKEN = os.environ.get('BOT_TOKEN')
START_MESSAGE = """
Hi, I'm a bot that checks every 5 minutes if your websites are down and then alerts you.

Send /add <url> to add a website to the watchlist.
Send /list to list all websites in the watchlist.
Send /remove <website_id> to remove a website from the watchlist.

This bot is open-source. You can find the source code here : https://github.com/judemont/DownAlert.
You can contact me at @judemont.
My website : https://futureofthe.tech .
"""
ADDED_MESSAGE = "Website added to the watchlist.\nYou will be notified if the website is down."

# Thread-local storage for the database connection
thread_local = threading.local()

def get_db_connection():
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect('database.db', check_same_thread=False)
    return thread_local.connection

def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT
        )
    ''')
    conn.commit()

def isDown(url):
    try:
        r = requests.head(url)
        return r.status_code != 200
    except:
        return True

def add_website_db(user_id, url):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sites (user_id, url) VALUES (?, ?)", (user_id, url))
    conn.commit()

def remove_website_db(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sites WHERE ID=?", (id,))
    conn.commit()

def get_websites_user_db(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sites WHERE user_id=?", (user_id,))
    return cursor.fetchall()

def get_websites_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sites")
    return cursor.fetchall()

def check_websites():
    websites = get_websites_db()
    for website in websites:
        if isDown(website[2]):
            bot.send_message(website[1], f"*DOWN ALERT⚠️⚠️: * {website[2]} is down !", parse_mode="Markdown")

def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t    

if __name__ == "__main__":
    create_table()

    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.send_message(message.chat.id, START_MESSAGE)

    @bot.message_handler(commands=['add'])
    def action_add(message):
        args = message.text.split(' ')
        if len(args) != 2:
            bot.reply_to(message, "Invalid command. (e.g '/add https://example.com')")
            return
        url = args[1]
        user_id = message.from_user.id
        if not validators.url(url):
            bot.reply_to(message, "Invalid URL. (e.g '/add https://example.com')")
            return
        
        websites = get_websites_user_db(user_id)
        for i in websites:
            if i[2] == url:
                bot.reply_to(message, "Website already in the watchlist.")
                return
            
        add_website_db(user_id, url)

        bot.reply_to(message, ADDED_MESSAGE)



    @bot.message_handler(commands=['list'])
    def list_websites(message):
        user_id = message.from_user.id
        websites = get_websites_user_db(user_id)
        if len(websites) == 0:
            bot.reply_to(message, "No website in the watchlist.")
            return
        websites_str = []
        for website in websites:
            status = "⏳"
            websites_str.append(f"{website[0]}. {website[2]} {status}")

        botMessage: telebot.Message = bot.reply_to(message, "\n".join(websites_str))

        websites_str = []
        for website in websites:
            status = "✅" if not isDown(website[2]) else "📛"
            websites_str.append(f"{website[0]}. {website[2]} {status}")

        bot.edit_message_text("\n".join(websites_str), message.chat.id, botMessage.message_id)

    @bot.message_handler(commands=['remove'])
    def action_remove(message):
        args = message.text.split(' ')
        if len(args) != 2:
            bot.reply_to(message, "Invalid command. (e.g '/remove 1')")
            return
        website_id = int(args[1])
        user_id = message.from_user.id
        websites = get_websites_user_db(user_id)
        for i in websites:
            if i[0] == website_id:
                remove_website_db(website_id)
                bot.reply_to(message, "Website removed from the watchlist.")
                return
        bot.reply_to(message, "Website not found in the watchlist.")
    
    @bot.message_handler(commands=['screens'])
    def action_screens(message):
        websites = get_websites_db()
        os.mkdir("tempimages")

        for website in websites:
            imgkit.from_url(website[2], f"tempimages/{website[0]}.jpg")
            bot.send_photo(message.chat.id, f"tempimages/{website[0]}.jpg", website[2])
            os.remove(f"tempimages/{website[0]}.jpg")

    @bot.message_handler(commands=['admin'])
    def action_admin(message):
        if message.from_user.username.lower() != "judemont": 
            bot.reply_to(message, "You are not an admin.")
            return
        websites = get_websites_db()
        bot.send_message(message.chat.id, "\n".join([website[2] for website in websites]))



    set_interval(check_websites, 300)
    bot.infinity_polling()