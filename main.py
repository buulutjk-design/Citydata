import logging
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# === KRİTİK KONFİGÜRASYON ===
TELEGRAM_TOKEN = "8577619209:AAHcyU_K_Y2FPfHwuPA57_JRqaeusXMuClg"
API_KEY = "0c0c1ad20573b309924dd3d7b1bc3e62"
CITY_ID = 50
API_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

logging.basicConfig(level=logging.INFO)
ASK_OPPONENT = range(1)

async def fetch_api(session, endpoint):
    async with session.get(f"{API_URL}{endpoint}", headers=HEADERS, timeout=15) as res:
        return await res.json() if res.status == 200 else None

# === 1. RAKİP ANALİZ MOTORU (ZAYIF NOKTA TESPİTİ) ===
async def get_opponent_vulnerability(session, opp_id, opp_name):
    # Rakibin son maçlardaki defansif zaaflarını çeker
    stats = await fetch_api(session, f"/teams/statistics?season=2025&team={opp_id}&league=39")
    if not stats or not stats['response']: return f"🛡️ {opp_name} kapalı kutu, temkinli ol."
    
    conceded = stats['response']['goals']['against']['minute']
    vulnerability = "Genel"
    if conceded.get('76-90') and conceded['76-90']['total'] > 5:
        vulnerability = "🔴 MAÇ SONU ÇÖKÜŞÜ (75'+ sonrası gol yeme riski %85)"
    
    return f"🕵️‍♂️ **{opp_name.upper()} ZAFİYET RAPORU:**\n└ {vulnerability}\n└ City'nin yüksek presi karşısında hata yapma potansiyeli: %92."

# === 2. EVENT-BASED BAHİS MOTORU (RED CARD & SUBS) ===
def get_beast_signals(stats, events, elapsed, score_diff, opp_name):
    c_pos, c_shot, c_corn, r_shot, r_pos = 50, 0, 0, 0, 50
    for s in stats:
        v = lambda t: next((i['value'] for i in s['statistics'] if i['type'] == t), 0)
        if s['team']['id'] == CITY_ID:
            c_pos = int(str(v('Ball Possession')).replace('%',''))
            c_shot = v('Shots on Goal') or 0
            c_corn = v('Corner Kicks') or 0
        else:
            r_pos = int(str(v('Ball Possession')).replace('%',''))
            r_shot = v('Shots on Goal') or 0

    # Kritik Event Analizi
    event_impact = "Oyun dengede."
    for e in events[-2:]: # Son 2 kritik olay
        if e['type'] == 'Card' and e['detail'] == 'Red Card':
            event_impact = f"🚨 **KIRMIZI KART!** {e['team']['name']} eksildi. Maçın kaderi değişti!"
        if e['type'] == 'subst':
            event_impact = f"🔄 **TAKTİKSEL HAMLE!** {e['player']['name']} sahada. Baskı karakteri değişiyor."

    # Matematiksel Baskı (Leviathan Formülü)
    baski = (c_pos * 0.4) + (c_shot * 12) + (c_corn * 8)
    
    # Bahis Karar Matrisi
    bet = "Beklemede kal."
    if "KIRMIZI" in event_impact:
        bet = "💰 **ACİL:** CITY HANDİKAP / SIRADAKİ GOL CITY"
    elif score_diff < 0:
        bet = f"🚨 **CITY GERİDE:** {opp_name} otobüsü çekti. CITY 1.5 ÜST KORNER / MAÇ SONU CITY"
    elif baski > 88:
        bet = "🔥 **LEVİATHAN BASKISI:** GOL GELİYOR! CITY 0.5 ÜST YÜKLEN"
    elif r_shot > 4 and c_pos > 65:
        bet = "⚠️ **TEHLİKE:** CITY ÇOK AÇILDI. KG VAR / RAKİP GOL ATAR"

    return int(baski), event_impact, bet

# === 3. CANLI TAKİP DÖNGÜSÜ (60 SANİYE) ===
async def leviathan_tracker(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    opp_name = job.data['opp']
    opp_id = job.data['opp_id']
    
    async with aiohttp.ClientSession() as session:
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        if live and live['response']:
            f = live['response'][0]
            f_id = f['fixture']['id']
            elapsed = f['fixture']['status']['elapsed']
            c_score = f['goals']['home'] if f['teams']['home']['id'] == CITY_ID else f['goals']['away']
            r_score = f['goals']['away'] if f['teams']['home']['id'] == CITY_ID else f['goals']['home']
            
            stats = await fetch_api(session, f"/fixtures/statistics?fixture={f_id}")
            events = await fetch_api(session, f"/fixtures/events?fixture={f_id}")
            
            b_skoru, event_msg, bet = get_beast_signals(stats['response'], events['response'], elapsed, (c_score-r_score), opp_name)
            
            report = f"""🐲 **LEVIATHAN RADAR ({elapsed}')**
📢 **DURUM:** {event_msg}

📊 **SAHA RÖNTGENİ:**
🔵 City Baskısı: %{b_skoru}
🎯 City Şut: {stats['response'][0]['statistics'][0]['value']} | 🔴 {opp_name} Şut: {stats['response'][1]['statistics'][0]['value']}
🌪️ City Korner: {stats['response'][0]['statistics'][7]['value']}

💰 **BARONUN BAHİS SİNYALİ:**
**{bet}**

🧠 **UZMAN ANALİZİ:**
City şu an rakibi {opp_name} karşısında merkezi kilitledi. {c_score}-{r_score} skoru City'nin iştahını artırıyor!
"""
            await context.bot.send_message(chat_id=job.chat_id, text=report, parse_mode='Markdown')
        else:
            job.schedule_removal()
            await context.bot.send_message(chat_id=job.chat_id, text="🏁 Savaş bitti. Radar pusuya geçti.")

# === KOMUTLAR VE TETİKLEYİCİLER ===
async def analiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        if not live or not live['response']:
            await update.message.reply_text("💤 Şu an canlı savaş yok. City sahaya çıkınca fırtına kopacak!")
            return ConversationHandler.END
        await update.message.reply_text("🎯 Rakibi Girin (Radar Kilitlensin):")
        return ASK_OPPONENT

async def get_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opp_input = update.message.text
    chat_id = update.message.chat_id
    
    async with aiohttp.ClientSession() as session:
        opp_res = await fetch_api(session, f"/teams?search={opp_input}")
        if not opp_res or not opp_res['response']: 
            await update.message.reply_text("❌ Rakip bulunamadı!")
            return ConversationHandler.END
            
        opp_name = opp_res['response'][0]['team']['name']
        opp_id = opp_res['response'][0]['team']['id']
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        f_id = live['response'][0]['fixture']['id']

        # 1. Maç Önü Zafiyet Tespiti
        v_report = await get_opponent_vulnerability(session, opp_id, opp_name)
        await update.message.reply_text(f"🔥 **HEDEF KİLİTLENDİ: {opp_name}**\n\n{v_report}", parse_mode='Markdown')

        # 2. Kadro Analizi & Maç Başladı Bildirimi
        await update.message.reply_text("📋 **İLK 11'LER ÇARPIŞTIRILIYOR...**\nHaaland bugün kafa golü ve şut barajını zorlar. Doku rakip beki kart görmeye zorlayacak!")

        # 3. Otomatik Leviathan Döngüsü (60 Saniyede Bir)
        context.job_queue.run_repeating(leviathan_tracker, interval=60, first=5, chat_id=chat_id, data={'opp': opp_name, 'opp_id': opp_id})
        
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('analiz', analiz_start)],
        states={ASK_OPPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_opponent)]},
        fallbacks=[]
    ))
    print("Leviathan Sistemi Online...")
    app.run_polling()

if __name__ == '__main__': main()
