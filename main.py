import logging
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackQueryHandler
)

# === AYARLAR ===
TELEGRAM_TOKEN = "8577619209:AAHcyU_K_Y2FPfHwuPA57_JRqaeusXMuClg"
API_FOOTBALL_KEY = "0c0c1ad20573b309924dd3d7b1bc3e62"
ADMIN_ID = 8480843841
CITY_ID = 50 

API_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': API_FOOTBALL_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_OPPONENT = range(1)

# === DB ===
def init_db():
    conn = sqlite3.connect('vip_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expire_date TEXT)''')
    conn.commit()
    conn.close()

def check_vip(user_id):
    if user_id == ADMIN_ID: return True, "Sınırsız"
    try:
        conn = sqlite3.connect('vip_users.db')
        c = conn.cursor()
        c.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
        res = c.fetchone()
        conn.close()
        if res:
            exp = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            if datetime.now() < exp: return True, (exp - datetime.now()).days + 1
    except: pass
    return False, "Yok"

# === BOT AKSİYONLARI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_vip, status = check_vip(update.effective_user.id)
    if is_vip:
        await update.message.reply_text(f"👑 City Radar Aktif!\n⏳ Kalan: {status} Gün\n/analiz ile başla.")
    else:
        await update.message.reply_text("🚫 VİP Üyeliğiniz Yok! @blutad")

async def analiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # BURASI KRİTİK: Botun cevap vermediği yer.
    is_vip, _ = check_vip(update.effective_user.id)
    if not is_vip:
        await update.message.reply_text("VİP Değilsiniz.")
        return ConversationHandler.END
    
    await update.message.reply_text("🎯 Manchester City'nin Rakibi Kim? (Örn: Arsenal)")
    return ASK_OPPONENT

async def get_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opponent = update.message.text
    context.user_data['opp'] = opponent
    
    keyboard = [
        [InlineKeyboardButton("📊 MAÇ ÖNÜ", callback_data='pre'),
         InlineKeyboardButton("🔴 CANLI", callback_data='live'),
         InlineKeyboardButton("🔪 OYUNCU", callback_data='player')]
    ]
    await update.message.reply_text(
        f"🎯 Hedef: CITY vs {opponent.upper()}\nSistem Seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    opp = context.user_data.get('opp', 'Rakip')
    
    # Simülasyon Analizleri
    if query.data == 'pre':
        await query.message.reply_text(f"📊 {opp} Analizi:\n✅ City 1.5 Üst: %88\n✅ City -1.5 Handikap: %72")
    elif query.data == 'live':
        await query.message.reply_text("🔴 CANLI: Baskı Endeksi %85. Sıradaki Gol City!")
    elif query.data == 'player':
        await query.message.reply_text("🔪 OYUNCU: Haaland 1.5 İsabetli Şut Üst!")

# === ANA ÇALIŞTIRICI ===
def main():
    init_db()
    # Railway çökme koruması için bağlantı ayarları
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('analiz', analiz_start)],
        states={
            ASK_OPPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_opponent)],
        },
        fallbacks=[],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(btn_handler))

    print("Bot başlatıldı...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
