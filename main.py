import logging
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# === KRİTİK KONFİGÜRASYON ===
TELEGRAM_TOKEN = "8577619209:AAHcyU_K_Y2FPfHwuPA57_JRqaeusXMuClg"
API_KEY = "0c0c1ad20573b309924dd3d7b1bc3e62"
CITY_ID = 50
API_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_OPPONENT = range(1)

async def fetch_api(session, endpoint):
    try:
        async with session.get(f"{API_URL}{endpoint}", headers=HEADERS, timeout=20) as res:
            return await res.json() if res.status == 200 else None
    except: return None

# === 1. KADRO VE CERRAHİ ANALİZ MOTORU ===
async def get_god_lineup_analysis(session, fixture_id, opp_name):
    data = await fetch_api(session, f"/fixtures/lineups?fixture={fixture_id}")
    if not data or not data['response']: return "⚠️ Kadrolar henüz açıklanmadı, pusu sürüyor!"
    
    city = data['response'][0]
    opp = data['response'][1]
    
    report = f"📋 **İLK 11'LER: MAHŞER DÜZENİ**\n\n"
    report += f"🔵 **CITY ({city['formation']}):** {city['coach']['name']}\n"
    report += f"🔴 **{opp_name} ({opp['formation']}):** {opp['coach']['name']}\n\n"
    
    report += "🔪 **OYUNCU CERRAHİ TAHMİNLERİ:**\n"
    for p in city['startXI'][:8]:
        n = p['player']['name']
        if "Haaland" in n: report += f"🤖 **HAALAND:** Kafa golü ve 3+ şut adayı. Rakip stoperlerin kabusu!\n"
        elif "Rodri" in n: report += f"🎯 **RODRI:** 100+ Pas barajı ve merkez hakimiyeti banko.\n"
        elif "Doku" in n or "Savinho" in n: report += f"🏎️ **{n.upper()}:** Rakip beki sarı karta zorlayacak, penaltı bekliyoruz.\n"
    
    report += f"\n🧠 **HOCA SAVAŞI:** {city['coach']['name']} yüksek presle boğacak. {opp['coach']['name']} kontra arıyor."
    return report

# === 2. AGRESİF BAHİS VE MOMENTUM MOTORU ===
def get_leviathan_signals(stats, events, elapsed, score_diff, opp_name):
    c_pos, c_shot, c_corn = 50, 0, 0
    for s in stats:
        v = lambda t: next((i['value'] for i in s['statistics'] if i['type'] == t), 0)
        if s['team']['id'] == CITY_ID:
            c_pos = int(str(v('Ball Possession')).replace('%',''))
            c_shot = v('Shots on Goal') or 0
            c_corn = v('Corner Kicks') or 0

    # Olay Takibi (Kırmızı Kart, Sakatlık, Değişiklik)
    status = "Oyun stabil."
    for e in events[-2:]:
        if e['type'] == 'Card' and e['detail'] == 'Red Card': status = f"🚨 **KIRMIZI KART!** {e['team']['name']} eksildi!"
        elif e['type'] == 'subst': status = f"🔄 **DEĞİŞİKLİK!** {e['player']['name']} oyuna girdi."

    b_skoru = (c_pos * 0.3) + (c_shot * 12) + (c_corn * 8)
    bet = "Fırsat bekleniyor."
    
    if b_skoru > 88: bet = "💰 **GOL GELİYOR!** CITY 0.5 ÜST / SIRADAKİ GOL"
    elif score_diff < 0: bet = f"🚨 **CITY GERİDE:** {opp_name} otobüsü çekti, KORNER ÜST dene!"
    elif elapsed > 75 and b_skoru > 75: bet = "⏳ **ÖLÜM DAKİKALARI:** GEÇ GOL CITY GELİR."

    return int(b_skoru), status, bet

# === 3. SÜREKLİ TAKİP (60 SANİYE) ===
async def god_tracker(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    async with aiohttp.ClientSession() as session:
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        if live and live['response']:
            f = live['response'][0]
            f_id = f['fixture']['id']
            elapsed = f['fixture']['status']['elapsed']
            c_score = f['goals']['home'] if f['teams']['home']['id'] == CITY_ID else f['goals']['away']
            r_score = f['goals']['away'] if f['teams']['home']['id'] == CITY_ID else f['goals']['home']
            
            st = await fetch_api(session, f"/fixtures/statistics?fixture={f_id}")
            ev = await fetch_api(session, f"/fixtures/events?fixture={f_id}")
            
            b_skoru, s_msg, bet = get_leviathan_signals(st['response'], ev['response'], elapsed, (c_score-r_score), job.data['opp'])
            
            report = f"""🐲 **MAHŞER RADARI ({elapsed}')**
📢 **DURUM:** {s_msg}

📊 **SAHA GÜCÜ:**
🔵 City Baskısı: %{b_skoru}
🎯 City Şut: {c_shot if 'c_shot' in locals() else 'Sorgulanıyor'} | 🌪️ Korner: {c_corn if 'c_corn' in locals() else 'Sorgulanıyor'}

💰 **BAHİS KOMUTANI:**
**{bet}**

🧠 **ANALİZ:** City şu an rakibi {job.data['opp']} karşısında vites artırdı. Gol kokusu var!"""
            await context.bot.send_message(chat_id=job.chat_id, text=report, parse_mode='Markdown')
        else:
            job.schedule_removal()
            await context.bot.send_message(chat_id=job.chat_id, text="🏁 Maç bitti veya canlı yayın kesildi.")

# === KOMUTLAR ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑 City Radar Aktif! /analiz ile fırtınayı başlat.")

async def analiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        if not live or not live['response']:
            await update.message.reply_text("🚫 Şu an canlı City maçı yok. Canavar sadece maç anında çalışır! 💤")
            return ConversationHandler.END
        await update.message.reply_text("🎯 Rakibi Gir (Saniye saniye takip başlasın):")
        return ASK_OPPONENT

async def get_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opp = update.message.text
    async with aiohttp.ClientSession() as session:
        live = await fetch_api(session, f"/fixtures?team={CITY_ID}&live=all")
        f_id = live['response'][0]['fixture']['id']
        await update.message.reply_text(f"🔥 **HEDEF: {opp.upper()}**\n\nSistem her 60 saniyede bir analiz gönderecek!")
        ana = await get_god_lineup_analysis(session, f_id, opp)
        await update.message.reply_text(ana, parse_mode='Markdown')
        context.job_queue.run_repeating(god_tracker, interval=60, first=5, chat_id=update.message.chat_id, data={'opp': opp})
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('analiz', analiz_start)],
        states={ASK_OPPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_opponent)]},
        fallbacks=[]
    ))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__': main()
