import requests
import time
import os
import math
from datetime import datetime, timezone, timedelta

# ── Konfigurasi ───────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID")
FETCH_INTERVAL = 15
SR_TOLERANCE   = 10

if not BOT_TOKEN or not CHAT_ID:
    print("[ERROR] BOT_TOKEN dan CHAT_ID harus diset!")
    exit(1)

WIB = timezone(timedelta(hours=7))

def now_wib():
    return datetime.now(WIB)

def get_session():
    t = now_wib().hour + now_wib().minute / 60
    if t < 9:   return "asia"
    if t < 14:  return "pre"
    if t < 22:  return "london"
    return "ny"

def market_open():
    n = datetime.now(timezone.utc)
    d, h = n.weekday(), n.hour
    if d == 6: return False
    if d == 5: return False
    if d == 4 and h >= 22: return False
    return True

def get_day_name():
    days = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    return days[now_wib().weekday()]

def get_month_name(m=None):
    months = ["","Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]
    return months[m or now_wib().month]

# ── Telegram ──────────────────────────────────────────────
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"[TG ERROR] {e}")
        return False

def get_updates(offset=None):
    try:
        params = {"timeout": 1, "allowed_updates": ["message"]}
        if offset: params["offset"] = offset
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params=params, timeout=5)
        return r.json().get("result", [])
    except:
        return []

# ── Harga Gold ────────────────────────────────────────────
def fetch_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        return float(r.json()["price"])
    except Exception as e:
        print(f"[PRICE ERROR] {e}")
        return None

# ── Indikator ─────────────────────────────────────────────
def detect_bos(candles, lb=5):
    if len(candles) < lb + 2: return None
    rec = candles[-(lb+1):]
    last, prev = rec[-1], rec[:-1]
    if last["close"] > max(c["high"] for c in prev): return "BULL"
    if last["close"] < min(c["low"]  for c in prev): return "BEAR"
    return None

def detect_rejection(c):
    body = abs(c["close"] - c["open"])
    uw   = c["high"] - max(c["open"], c["close"])
    lw   = min(c["open"], c["close"]) - c["low"]
    tot  = c["high"] - c["low"]
    if tot == 0: return None
    if lw > body * 1.5 and lw > tot * 0.4: return "BULLISH"
    if uw > body * 1.5 and uw > tot * 0.4: return "BEARISH"
    return None

def calc_fib(lo, hi):
    r = hi - lo
    return {
        "f0":   round(hi, 2),
        "f382": round(hi - r * 0.382, 2),
        "f618": round(hi - r * 0.618, 2),
        "f786": round(hi - r * 0.786, 2),
        "f100": round(lo, 2),
        "f127": round(lo - r * 0.272, 2),
        "f161": round(lo - r * 0.618, 2),
    }

# ── 🌙 ASTROLOGI ──────────────────────────────────────────
def get_moon_phase():
    now = datetime.now(timezone.utc)
    known_new_moon = datetime(2026, 3, 18, 0, 23, 0, tzinfo=timezone.utc)
    lunar_cycle = 29.53058867
    diff = (now - known_new_moon).total_seconds() / 86400
    phase_days = diff % lunar_cycle
    if phase_days < 0: phase_days += lunar_cycle
    illumination = round((1 - math.cos(2 * math.pi * phase_days / lunar_cycle)) / 2 * 100)
    if phase_days < 1.85:    phase, phase_en = "🌑 New Moon",         "new_moon"
    elif phase_days < 7.38:  phase, phase_en = "🌒 Waxing Crescent",  "waxing_crescent"
    elif phase_days < 9.22:  phase, phase_en = "🌓 First Quarter",    "first_quarter"
    elif phase_days < 14.77: phase, phase_en = "🌔 Waxing Gibbous",   "waxing_gibbous"
    elif phase_days < 16.61: phase, phase_en = "🌕 Full Moon",        "full_moon"
    elif phase_days < 22.15: phase, phase_en = "🌖 Waning Gibbous",   "waning_gibbous"
    elif phase_days < 23.99: phase, phase_en = "🌗 Last Quarter",     "last_quarter"
    else:                    phase, phase_en = "🌘 Waning Crescent",  "waning_crescent"
    next_full = round(14.77 - phase_days, 1) if phase_days < 14.77 else round(lunar_cycle - phase_days + 14.77, 1)
    next_new  = round(lunar_cycle - phase_days, 1)
    return {"phase": phase, "phase_en": phase_en, "days": round(phase_days, 1),
            "illumination": illumination, "next_full": next_full, "next_new": next_new,
            "days_to_next": round(lunar_cycle - phase_days, 1)}

def get_moon_impact(phase_en):
    impacts = {
        "new_moon":        {"bias": "⚠️ NETRAL — Siklus Baru",     "signal": "neutral",
                            "desc": "Sering terjadi REVERSAL. Hindari posisi besar. Siklus baru dimulai.",
                            "trading": "⛔ Hindari posisi besar\n✅ Tunggu konfirmasi arah\n🔄 Reversal sering terjadi",
                            "storm_factor": "🌑 NEW MOON = Trigger Perfect Storm!"},
        "waxing_crescent": {"bias": "📈 BULLISH",                   "signal": "bullish",
                            "desc": "Energi tumbuh. Gold cenderung naik. BUY lebih disukai.",
                            "trading": "✅ Fokus BUY di support\n✅ Fibonacci BUY valid",
                            "storm_factor": "🌒 Waxing = Energi naik, BUY dominant"},
        "first_quarter":   {"bias": "📈 BULLISH KUAT",              "signal": "bullish",
                            "desc": "Momentum naik kuat. Breakout ke atas lebih sering.",
                            "trading": "✅ BUY setiap pullback\n✅ Breakout valid",
                            "storm_factor": "🌓 First Quarter = Konfirmasi bullish"},
        "waxing_gibbous":  {"bias": "📈 BULLISH — Waspada Puncak",  "signal": "bullish_caution",
                            "desc": "Mendekati puncak. Naik tapi momentum melemah.",
                            "trading": "✅ Hold BUY profit\n⚠️ Siap SELL di Full Moon",
                            "storm_factor": "🌔 Waxing Gibbous = Puncak mendekat"},
        "full_moon":       {"bias": "📉 BEARISH — Reversal Zone",   "signal": "bearish",
                            "desc": "Puncak siklus. Titik REVERSAL dari naik ke turun.",
                            "trading": "✅ Fokus SELL\n✅ High Full Moon = resistance",
                            "storm_factor": "🌕 FULL MOON = Perfect Storm SELL!"},
        "waning_gibbous":  {"bias": "📉 BEARISH",                   "signal": "bearish",
                            "desc": "Energi melemah. Gold cenderung turun.",
                            "trading": "✅ SELL di resistance\n✅ Fibonacci SELL valid",
                            "storm_factor": "🌖 Waning = SELL dominant"},
        "last_quarter":    {"bias": "📉 BEARISH — Melemah",         "signal": "bearish",
                            "desc": "Momentum turun melemah. Market mulai ranging.",
                            "trading": "⚠️ Market ranging\n📌 Siap BUY di New Moon",
                            "storm_factor": "🌗 Last Quarter = Konsolidasi"},
        "waning_crescent": {"bias": "⚠️ NETRAL — Menjelang Reset",  "signal": "neutral",
                            "desc": "Energi paling lemah. Choppy. Kurangi trading.",
                            "trading": "⛔ Kurangi trading\n📌 Tunggu siklus baru",
                            "storm_factor": "🌘 Dark Moon = Volatile, hati-hati"},
    }
    return impacts.get(phase_en, impacts["new_moon"])

def get_planet_info():
    now = now_wib()
    month, day = now.month, now.day
    planets = []
    if (month == 2 and day >= 15) or month == 3 or (month == 4 and day <= 9):
        planets.append("☿ *Mercury Retrograde* — Banyak fake move & liquidity sweep ekstrem")
    if month == 3 or (month == 2 and day >= 1):
        planets.append("♀ *Venus di Pisces* — Sentiment tidak menentu, volatilitas tinggi")
    if month == 3 and day <= 22:
        planets.append("♂ *Mars di Pisces* — Pergerakan tidak linear, spike brutal tiba-tiba")
    planets.append("♄ *Saturn di Aries* — Support/Resistance sangat kuat, breakout butuh momentum besar")
    planets.append("☀️ *Sun di Pisces/Aries* — Anchor energy, pergerakan besar mendekat")
    return planets

# ── 🌪️ PERFECT STORM DETECTION ───────────────────────────
def detect_perfect_storm(candles, price):
    score = 0
    factors = []
    warnings = []

    moon   = get_moon_phase()
    impact = get_moon_impact(moon["phase_en"])

    # 1. Moon Phase Extreme
    if moon["phase_en"] in ["new_moon", "full_moon"]:
        score += 3
        factors.append(f"🌙 {impact['storm_factor']} (+3)")
    elif moon["phase_en"] in ["first_quarter", "last_quarter"]:
        score += 2
        factors.append(f"🌙 Quarter Moon — Momentum kuat (+2)")

    # 2. Mercury Retrograde
    now = now_wib()
    if (now.month == 2 and now.day >= 15) or now.month == 3 or (now.month == 4 and now.day <= 9):
        score += 2
        factors.append("☿ Mercury Retrograde aktif — Fake moves extreme (+2)")

    # 3. Anchor Day (Rabu = FOMC/News besar)
    if now.weekday() == 2:
        score += 2
        factors.append("☀️ Anchor Day (Rabu) — News besar potential (+2)")

    # 4. Brutal Sideways Asia
    if len(candles) >= 20:
        asia_candles = [c for c in candles[-60:]]
        if len(asia_candles) >= 5:
            highs = [c["high"] for c in asia_candles[-10:]]
            lows  = [c["low"]  for c in asia_candles[-10:]]
            asia_range = max(highs) - min(lows)
            if asia_range < 15:
                score += 2
                factors.append(f"😴 Brutal Sideways Asia — Range hanya {asia_range:.1f} poin (+2)")
                warnings.append(f"⚠️ Range Asia sangat sempit! Potensi Hurricane London!")

    # 5. Liquidity buildup (banyak equal highs/lows)
    if len(candles) >= 10:
        last10 = candles[-10:]
        eq_highs = sum(1 for i in range(len(last10)-1)
                      if abs(last10[i]["high"] - last10[i+1]["high"]) < 3)
        eq_lows  = sum(1 for i in range(len(last10)-1)
                      if abs(last10[i]["low"] - last10[i+1]["low"]) < 3)
        if eq_highs >= 3 or eq_lows >= 3:
            score += 2
            factors.append("💧 Liquidity buildup — Equal highs/lows terdeteksi (+2)")
            warnings.append("⚡ Stop loss banyak menumpuk! Sweep akan brutal!")

    # 6. Round Number proximity
    base = int(price / 100) * 100
    for rn in [base, base+100, base+50]:
        if abs(price - rn) <= 15:
            score += 1
            factors.append(f"🎯 Dekat Round Number ${rn} — Magnet likuiditas (+1)")
            break

    # Tentukan level storm
    if score >= 9:
        level = "🌪️🌪️🌪️ PERFECT STORM EXTREME!"
        action = "💥 DOMINANT STRATEGY AKTIF!\nSiapkan diri — pergerakan BRUTAL akan terjadi!"
    elif score >= 6:
        level = "🌪️🌪️ HURRICANE WARNING!"
        action = "⚡ Pergerakan besar mendekat!\nTunggu konfirmasi arah, jangan overtrading!"
    elif score >= 3:
        level = "⛈️ STORM BUILDING"
        action = "⚠️ Kondisi memanas. Waspada fake move."
    else:
        level = "☀️ NORMAL"
        action = "✅ Kondisi market normal. Trading seperti biasa."

    return {
        "score": score,
        "level": level,
        "factors": factors,
        "warnings": warnings,
        "action": action
    }

# ── 🌅 MORNING BRIEFING ───────────────────────────────────
def send_morning_briefing(price):
    now    = now_wib()
    moon   = get_moon_phase()
    impact = get_moon_impact(moon["phase_en"])
    planets = get_planet_info()
    storm  = detect_perfect_storm(state["candles"], price)
    day    = get_day_name()

    planet_text = "\n".join([f"  • {p}" for p in planets])
    factor_text = "\n".join([f"  {f}" for f in storm["factors"]]) if storm["factors"] else "  Tidak ada faktor signifikan"
    warning_text = "\n".join([f"  {w}" for w in storm["warnings"]]) if storm["warnings"] else ""

    # Setup hari berdasarkan hari
    if day in ["Sabtu", "Minggu"]:
        market_note = "🔴 PASAR TUTUP"
        setup_plan  = "Istirahat & persiapkan strategi minggu depan!"
    elif day == "Senin":
        market_note = "🟡 SENIN — Range Asia belum sempurna"
        setup_plan  = "⚠️ Skip Asia, fokus London & NY saja"
    elif day == "Rabu":
        market_note = "🟡 RABU — Anchor Day! Waspada news besar"
        setup_plan  = "⚠️ Kurangi posisi, tunggu arah jelas\n⚠️ Jangan hold posisi besar saat news"
    elif day == "Jumat":
        market_note = "🟡 JUMAT — Profit taking day!"
        setup_plan  = "⚠️ Close posisi sebelum 22:00 WIB\n✅ Reversal sering terjadi Jumat"
    else:
        market_note = "🟢 PASAR BUKA — Hari trading normal"
        setup_plan  = (
            "✅ Asia: Cari Low Asia → BUY BOS\n"
            "✅ London: SELL di High Asia + Fib\n"
            "✅ 61.8%: BUY ke-2 rejection\n"
            "✅ London sweep Low Asia → BUY 61.8%"
        )

    # Bias
    if impact["signal"] == "bullish":
        bias = "📈 BULLISH"
        targets = f"🎯 Naik: ${price+50:.0f} → ${price+100:.0f} → ${price+150:.0f}"
    elif impact["signal"] == "bearish":
        bias = "📉 BEARISH"
        targets = f"🎯 Turun: ${price-50:.0f} → ${price-100:.0f} → ${price-150:.0f}"
    else:
        bias = "⚠️ NETRAL"
        targets = f"🎯 Range: ${price-50:.0f} – ${price+50:.0f}"

    base = int(price/100)*100
    send_telegram(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌅 *GOLD MORNING BRIEFING*\n"
        f"📅 {day}, {now.day} {get_month_name()} {now.year}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"☀️ *Selamat pagi, Trader!*\n"
        f"Siapkan kopi & fokus! ☕\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 *HARGA GOLD*\n"
        f"━━━━━━━━━━━━━━\n"
        f"Harga saat ini: *${price:.2f}*\n"
        f"Support round:  *${base}*\n"
        f"Half round:     *${base+50}*\n"
        f"Resistance:     *${base+100}*\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *STATUS MARKET*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{market_note}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌪️ *PERFECT STORM METER*\n"
        f"━━━━━━━━━━━━━━\n"
        f"Level: {storm['level']}\n"
        f"Score: {storm['score']}/12\n\n"
        f"Faktor aktif:\n{factor_text}\n\n"
        f"{warning_text}\n"
        f"{storm['action']}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 *BIAS & TARGET*\n"
        f"━━━━━━━━━━━━━━\n"
        f"Bias: {bias}\n"
        f"{targets}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📋 *SETUP HARI INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{setup_plan}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"⏰ *JADWAL SESI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌏 Asia:    00:00–09:00 WIB\n"
        f"⏳ Pre-Lon: 09:00–14:00 WIB\n"
        f"🇬🇧 London:  14:00–22:00 WIB\n"
        f"🇺🇸 New York: 19:00–03:00 WIB\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌙 *ASTROLOGI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"Fase: {moon['phase']} ({moon['illumination']}%)\n"
        f"Bias: {impact['bias']}\n"
        f"📝 {impact['desc']}\n\n"
        f"🪐 Planet aktif:\n{planet_text}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"💡 *SARAN HARI INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{impact['trading']}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ *GOLDEN RULES*\n"
        f"━━━━━━━━━━━━━━\n"
        f"✅ Tunggu BOS konfirmasi\n"
        f"✅ SL wajib sebelum entry\n"
        f"✅ R:R minimal 1:2\n"
        f"✅ Max 2 trade per hari\n"
        f"✅ 61.8% = zona golden ratio\n"
        f"❌ No revenge trade!\n"
        f"❌ No FOMO!\n"
        f"❌ No hold posisi saat news!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Ketik /status untuk update\n"
        f"Semangat trading! 💪🥇\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Bukan saran investasi_"
    )
    print(f"[BRIEFING] Daily briefing terkirim")

# ── 📅 WEEKLY BRIEFING ────────────────────────────────────
def send_weekly_briefing(price):
    now    = now_wib()
    moon   = get_moon_phase()
    impact = get_moon_impact(moon["phase_en"])
    planets = get_planet_info()
    planet_text = "\n".join([f"  • {p}" for p in planets])

    # Kalender minggu ini
    monday = now - timedelta(days=now.weekday())
    week_days = []
    day_notes = {
        0: "Senin  → Range Asia mungkin tidak sempurna",
        1: "Selasa → Hari trading terbaik 🌟",
        2: "Rabu   → ⚠️ Anchor Day — Waspada news",
        3: "Kamis  → Hari trading bagus 🌟",
        4: "Jumat  → Profit taking, reversal possible",
    }
    for i in range(5):
        d = monday + timedelta(days=i)
        note = day_notes.get(i, "")
        week_days.append(f"  {d.strftime('%d %b')} {note}")
    calendar_text = "\n".join(week_days)

    # Perfect storm minggu ini
    storm_days = []
    if moon["phase_en"] in ["new_moon", "full_moon"]:
        storm_days.append(f"🌪️ {moon['phase']} aktif minggu ini → Volatilitas ekstrem!")
    if moon["next_full"] <= 7:
        storm_days.append(f"🌕 Full Moon dalam {moon['next_full']:.0f} hari → Siap SELL zone")
    if moon["next_new"] <= 7:
        storm_days.append(f"🌑 New Moon dalam {moon['next_new']:.0f} hari → Reversal potential")
    storm_text = "\n".join(storm_days) if storm_days else "  Tidak ada event ekstrem minggu ini"

    # Bias mingguan
    if impact["signal"] in ["bullish", "bullish_caution"]:
        weekly_bias = "📈 BULLISH MINGGU INI"
        weekly_strategy = (
            "✅ Prioritas: Cari setup BUY\n"
            "✅ Buy on dip di support\n"
            "✅ Fibonacci BUY di 61.8%\n"
            "⚠️ SELL hanya di resistance kuat"
        )
    elif impact["signal"] == "bearish":
        weekly_bias = "📉 BEARISH MINGGU INI"
        weekly_strategy = (
            "✅ Prioritas: Cari setup SELL\n"
            "✅ Sell on rally di resistance\n"
            "✅ High Asia = zona SELL\n"
            "⚠️ BUY hanya di support sangat kuat"
        )
    else:
        weekly_bias = "⚠️ NETRAL MINGGU INI"
        weekly_strategy = (
            "⚠️ Market tidak menentu\n"
            "✅ Tunggu konfirmasi kuat\n"
            "✅ Kurangi ukuran posisi\n"
            "✅ Fokus R:R 1:3 ke atas"
        )

    # Level kunci mingguan
    base = int(price/100)*100
    send_telegram(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *GOLD WEEKLY BRIEFING*\n"
        f"Minggu {monday.strftime('%d')}–{(monday+timedelta(days=4)).strftime('%d')} {get_month_name(monday.month)} {now.year}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *HARGA GOLD*: *${price:.2f}*\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *BIAS MINGGU INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{weekly_bias}\n\n"
        f"{weekly_strategy}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🗓️ *KALENDER MINGGU INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{calendar_text}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌪️ *PERFECT STORM WATCH*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{storm_text}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌙 *LUNAR CALENDAR*\n"
        f"━━━━━━━━━━━━━━\n"
        f"Fase: {moon['phase']}\n"
        f"Illuminasi: {moon['illumination']}%\n"
        f"Next Full Moon: {moon['next_full']:.0f} hari lagi\n"
        f"Next New Moon: {moon['next_new']:.0f} hari lagi\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🪐 *PLANET MINGGU INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{planet_text}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 *LEVEL KUNCI MINGGU INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔴 Resistance: ${base+100} → ${base+150} → ${base+200}\n"
        f"📍 Harga kini: ${price:.2f}\n"
        f"🟢 Support:    ${base} → ${base-50} → ${base-100}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🧠 *DOMINANT STRATEGY*\n"
        f"━━━━━━━━━━━━━━\n"
        f"1️⃣ Asia sideway → London hurricane\n"
        f"   → Sweep Low/High Asia\n"
        f"   → Entry di 61.8% Fib\n\n"
        f"2️⃣ London sweep Low Asia\n"
        f"   → NY reversal BUY\n"
        f"   → 61.8% tidak ditembus\n\n"
        f"3️⃣ Perfect Storm terbentuk\n"
        f"   → Tunggu BOS konfirmasi\n"
        f"   → Entry dominant direction\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ *RULES MINGGU INI*\n"
        f"━━━━━━━━━━━━━━\n"
        f"✅ Max 2 trade/hari\n"
        f"✅ SL wajib setiap posisi\n"
        f"✅ Close semua sebelum weekend\n"
        f"❌ No trading saat news merah\n"
        f"❌ No revenge trade\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Briefing harian jam 07:00 WIB\n"
        f"Semangat minggu ini! 💪🥇\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Bukan saran investasi_"
    )
    print(f"[BRIEFING] Weekly briefing terkirim")

# ── Auto S&R ──────────────────────────────────────────────
def get_auto_sr(candles, current_price):
    levels = []
    if len(candles) < 10: return levels
    day = 288
    if len(candles) >= day * 2:
        yesterday = candles[-(day*2):-(day)]
        pdh = round(max(c["high"] for c in yesterday), 2)
        pdl = round(min(c["low"]  for c in yesterday), 2)
        levels.append({"price": pdh, "label": "PDH", "type": "resistance"})
        levels.append({"price": pdl, "label": "PDL", "type": "support"})
    week = 2016
    if len(candles) >= week:
        wk = candles[-week:]
        levels.append({"price": round(max(c["high"] for c in wk), 2), "label": "Weekly High", "type": "resistance"})
        levels.append({"price": round(min(c["low"]  for c in wk), 2), "label": "Weekly Low",  "type": "support"})
    base = int(current_price / 100) * 100
    for mult in range(-3, 5):
        rn = base + mult * 100
        if rn > 0 and abs(current_price - rn) <= 150:
            levels.append({"price": float(rn), "label": f"Round ${rn}", "type": "resistance" if rn > current_price else "support"})
    unique = []
    for lv in sorted(levels, key=lambda x: x["price"]):
        if not unique or abs(lv["price"] - unique[-1]["price"]) >= 5:
            unique.append(lv)
    return unique

# ── State ─────────────────────────────────────────────────
state = {
    "candles": [], "cur_candle": None, "prev_price": None,
    "asia_lo": None, "asia_hi": None, "fib": None, "fib_locked": False,
    "buy_done": False, "sell_done": False, "buy2_done": False,
    "alerted": set(), "sr_alerted": set(), "last_day": None,
    "last_update": 0, "briefing_sent": False, "weekly_sent": False,
    "storm_alerted": False, "low_asia_swept": False,
}

def reset_daily():
    today = now_wib().strftime("%Y-%m-%d")
    if state["last_day"] == today: return
    print(f"[RESET] Hari baru: {today}")
    state.update({
        "asia_lo": None, "asia_hi": None, "fib": None, "fib_locked": False,
        "buy_done": False, "sell_done": False, "buy2_done": False,
        "alerted": set(), "sr_alerted": set(), "cur_candle": None,
        "last_day": today, "briefing_sent": False,
        "storm_alerted": False, "low_asia_swept": False,
    })

def check_briefings():
    now = now_wib()
    p   = state["prev_price"]
    if not p: return

    # Daily briefing jam 07:00 WIB
    if now.hour == 7 and now.minute < 1 and not state["briefing_sent"]:
        state["briefing_sent"] = True
        send_morning_briefing(p)

    # Weekly briefing Senin jam 07:30 WIB
    if now.weekday() == 0 and now.hour == 7 and now.minute >= 30 and now.minute < 31 and not state["weekly_sent"]:
        state["weekly_sent"] = True
        send_weekly_briefing(p)

def signal(sig_type, price, detail):
    key = f"{sig_type}-{now_wib().strftime('%Y-%m-%d-%H')}"
    if key in state["alerted"]: return
    state["alerted"].add(key)
    labels = {
        "BUY1": "📈 BUY — Sesi Asia",
        "SELL": "📉 SELL — London Open",
        "BUY2": "🔄 BUY ke-2 — Level 61.8%",
    }
    moon   = get_moon_phase()
    impact = get_moon_impact(moon["phase_en"])
    send_telegram(
        f"🥇 *XAUUSD SIGNAL M5*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{labels[sig_type]}\n"
        f"💰 Harga: *${price:.2f}*\n"
        f"{detail}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌙 {moon['phase']} | {impact['bias']}\n"
        f"🕐 {now_wib().strftime('%H:%M:%S')} WIB\n"
        f"⚠️ _Bukan saran investasi_"
    )
    print(f"[SIGNAL] {labels[sig_type]} @ ${price:.2f}")

def check_perfect_storm(candle, all_candles):
    if not market_open(): return
    if state["storm_alerted"]: return
    price = candle["close"]
    storm = detect_perfect_storm(all_candles, price)
    if storm["score"] >= 6:
        state["storm_alerted"] = True
        factor_text = "\n".join([f"  {f}" for f in storm["factors"]])
        warning_text = "\n".join([f"  {w}" for w in storm["warnings"]])
        moon   = get_moon_phase()
        impact = get_moon_impact(moon["phase_en"])
        send_telegram(
            f"🌪️ *PERFECT STORM DETECTED!*\n"
            f"━━━━━━━━━━━━━━\n"
            f"Level: {storm['level']}\n"
            f"Score: {storm['score']}/12\n\n"
            f"📋 Faktor aktif:\n{factor_text}\n\n"
            f"{warning_text}\n\n"
            f"💥 *{storm['action']}*\n\n"
            f"🌙 {moon['phase']} | {impact['bias']}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🎯 *Strategi Perfect Storm:*\n"
            f"1. Tunggu brutal sideways Asia\n"
            f"2. London open = Hurricane sweep\n"
            f"3. NY = Dominant direction\n"
            f"4. Entry di 61.8% Fib konfirmasi\n"
            f"━━━━━━━━━━━━━━\n"
            f"🕐 {now_wib().strftime('%H:%M:%S')} WIB\n"
            f"⚠️ _Siapkan diri! Pergerakan besar mendekat!_"
        )

def check_low_asia_sweep(candle):
    """Deteksi London sweep Low Asia"""
    if not state["asia_lo"] or not state["asia_hi"]: return
    if get_session() != "london": return
    if state["low_asia_swept"]: return
    if candle["low"] < state["asia_lo"]:
        state["low_asia_swept"] = True
        f = calc_fib(state["asia_lo"], state["asia_hi"])
        send_telegram(
            f"🌊 *LONDON SWEEP LOW ASIA!*\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚡ London menembus Low Asia!\n\n"
            f"📍 Low Asia: *${state['asia_lo']:.2f}*\n"
            f"📍 Candle Low: *${candle['low']:.2f}*\n"
            f"━━━━━━━━━━━━━━\n"
            f"🎯 *TESIS AKTIF:*\n"
            f"London sweep → NY turun lebih dalam\n"
            f"ATAU reversal dari 61.8%!\n\n"
            f"📐 *Level Golden Ratio:*\n"
            f"🔴 61.8%: *${f['f618']:.2f}* ← ZONA KUNCI!\n"
            f"🟡 78.6%: *${f['f786']:.2f}*\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 *Strategi:*\n"
            f"→ Monitor 61.8% *${f['f618']:.2f}*\n"
            f"→ Kalau ada rejection + BOS\n"
            f"  → Entry BUY!\n"
            f"→ Kalau tembus 61.8%\n"
            f"  → NY lanjut turun\n"
            f"  → Target: *${f['f786']:.2f}* → *${f['f100']:.2f}*\n"
            f"━━━━━━━━━━━━━━\n"
            f"🕐 {now_wib().strftime('%H:%M:%S')} WIB"
        )

def check_sr(candle, all_candles):
    if not market_open(): return
    price = candle["close"]
    b = detect_bos(all_candles)
    rej = detect_rejection(candle)
    check_perfect_storm(candle, all_candles)
    check_low_asia_sweep(candle)
    for sr in get_auto_sr(all_candles, price):
        level, label, sr_type = sr["price"], sr["label"], sr["type"]
        if abs(price - level) > SR_TOLERANCE: continue
        touch_key = f"touch-{label}-{now_wib().strftime('%Y-%m-%d-%H')}"
        if touch_key not in state["sr_alerted"]:
            state["sr_alerted"].add(touch_key)
            emoji = "🔴" if sr_type == "resistance" else "🟢"
            send_telegram(
                f"📍 *Harga Menyentuh {sr_type.upper()}*\n"
                f"━━━━━━━━━━━━━━\n"
                f"{emoji} {label}: *${level:.2f}*\n"
                f"💰 Harga: *${price:.2f}*\n"
                f"📏 Jarak: {abs(price-level):.1f} poin\n"
                f"🕐 {now_wib().strftime('%H:%M:%S')} WIB\n"
                f"⏳ _Tunggu konfirmasi candle..._"
            )
        if rej:
            rej_key = f"rej-{label}-{now_wib().strftime('%Y-%m-%d-%H-%M')}"
            if rej_key not in state["sr_alerted"]:
                state["sr_alerted"].add(rej_key)
                action = "BUY 📈" if rej == "BULLISH" else "SELL 📉"
                send_telegram(
                    f"🕯 *Rejection di {sr_type.upper()}!*\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"*{action}* Signal\n"
                    f"📍 {label}: *${level:.2f}*\n"
                    f"💰 Harga: *${price:.2f}*\n"
                    f"🕯 Pola: {rej} Rejection\n"
                    f"🕐 {now_wib().strftime('%H:%M:%S')} WIB"
                )
        if b:
            bos_key = f"bos-{label}-{b}-{now_wib().strftime('%Y-%m-%d-%H-%M')}"
            if bos_key not in state["sr_alerted"]:
                state["sr_alerted"].add(bos_key)
                if b == "BULL" and sr_type == "support":
                    send_telegram(
                        f"💥 *BOS Bullish di SUPPORT!*\n"
                        f"━━━━━━━━━━━━━━\n"
                        f"📈 *KONFIRMASI BUY*\n"
                        f"📍 {label}: *${level:.2f}*\n"
                        f"💰 Harga: *${price:.2f}*\n"
                        f"✅ BOS M5 terkonfirmasi\n"
                        f"🎯 Target: Resistance terdekat\n"
                        f"🛡 SL: Di bawah {label}\n"
                        f"🕐 {now_wib().strftime('%H:%M:%S')} WIB"
                    )
                elif b == "BEAR" and sr_type == "resistance":
                    send_telegram(
                        f"💥 *BOS Bearish di RESISTANCE!*\n"
                        f"━━━━━━━━━━━━━━\n"
                        f"📉 *KONFIRMASI SELL*\n"
                        f"📍 {label}: *${level:.2f}*\n"
                        f"💰 Harga: *${price:.2f}*\n"
                        f"✅ BOS M5 terkonfirmasi\n"
                        f"🎯 Target: Support terdekat\n"
                        f"🛡 SL: Di atas {label}\n"
                        f"🕐 {now_wib().strftime('%H:%M:%S')} WIB"
                    )

def process_candle(candle):
    if not market_open(): return
    sess  = get_session()
    all_c = state["candles"]
    b     = detect_bos(all_c)
    check_sr(candle, all_c)
    if sess == "asia":
        state["asia_lo"] = candle["low"]  if state["asia_lo"] is None else min(state["asia_lo"], candle["low"])
        state["asia_hi"] = candle["high"] if state["asia_hi"] is None else max(state["asia_hi"], candle["high"])
        if b == "BULL" and not state["buy_done"]:
            state["buy_done"] = True
            signal("BUY1", candle["close"],
                f"📍 Low Asia: *${state['asia_lo']:.2f}*\n"
                f"🎯 Target: High Asia *${state['asia_hi']:.2f}*\n"
                f"🛡 SL: Di bawah Low Asia\n📊 TF: M5")
    if sess in ("pre", "london"):
        if state["asia_lo"] and state["asia_hi"] and not state["fib_locked"]:
            state["fib"] = calc_fib(state["asia_lo"], state["asia_hi"])
            state["fib_locked"] = True
            f = state["fib"]
            send_telegram(
                f"📐 *Fibonacci Terbentuk*\n"
                f"━━━━━━━━━━━━━━\n"
                f"🟦 Low Asia:  *${f['f100']:.2f}*\n"
                f"🟡 38.2%:    *${f['f382']:.2f}*\n"
                f"🔴 61.8%:    *${f['f618']:.2f}* ← Golden Ratio\n"
                f"🟤 78.6%:    *${f['f786']:.2f}*\n"
                f"🟢 High Asia: *${f['f0']:.2f}*\n"
                f"🚀 Ext 127%: *${f['f127']:.2f}*\n"
                f"🚀 Ext 161%: *${f['f161']:.2f}*\n"
                f"🕐 {now_wib().strftime('%H:%M')} WIB"
            )
    if sess == "london" and state["asia_hi"] and state["fib"]:
        hi, f = state["asia_hi"], state["fib"]
        if abs(candle["close"] - hi) <= 8 and b == "BEAR" and not state["sell_done"]:
            state["sell_done"] = True
            signal("SELL", candle["close"],
                f"📍 High Asia: *${hi:.2f}*\n"
                f"🎯 TP1: 61.8% *${f['f618']:.2f}*\n"
                f"🎯 TP2: 78.6% *${f['f786']:.2f}*\n"
                f"🛡 SL: Di atas High Asia\n📊 TF: M5")
        if abs(candle["close"] - f["f618"]) <= 8 and b == "BULL" and not state["buy2_done"]:
            state["buy2_done"] = True
            signal("BUY2", candle["close"],
                f"📍 Golden Ratio 61.8%: *${f['f618']:.2f}*\n"
                f"🎯 TP1: High Asia *${hi:.2f}*\n"
                f"🎯 TP2: Extension 127% *${f['f127']:.2f}*\n"
                f"🛡 SL: Bawah 61.8%\n📊 TF: M5")

# ── Command Handler ───────────────────────────────────────
def handle_commands():
    updates = get_updates(offset=state["last_update"])
    for upd in updates:
        state["last_update"] = upd["update_id"] + 1
        text = upd.get("message", {}).get("text", "").strip()
        if not text: continue
        print(f"[CMD] {text}")

        if text in ("/start", "/help"):
            send_telegram(
                f"🥇 *XAUUSD Bot v6 — Perfect Storm*\n"
                f"━━━━━━━━━━━━━━\n"
                f"/briefing  → Morning briefing sekarang\n"
                f"/weekly    → Weekly briefing sekarang\n"
                f"/storm     → Cek Perfect Storm meter\n"
                f"/status    → Status + astrologi\n"
                f"/moon      → Fase bulan detail\n"
                f"/astro     → Planet hari ini\n"
                f"/listsr    → Level S&R aktif\n"
                f"/help      → Menu ini\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌅 Daily briefing: *07:00 WIB*\n"
                f"📅 Weekly briefing: *Senin 07:30 WIB*\n"
                f"🌪️ Perfect Storm auto-alert\n"
                f"🌊 London Sweep Low Asia alert\n"
                f"🌙 Astrologi terintegrasi\n"
                f"━━━━━━━━━━━━━━\n"
                f"Bot aktif 24 jam • gold-api.com"
            )

        elif text == "/briefing":
            p = state["prev_price"]
            if p: send_morning_briefing(p)
            else: send_telegram("⏳ Harga belum tersedia.")

        elif text == "/weekly":
            p = state["prev_price"]
            if p: send_weekly_briefing(p)
            else: send_telegram("⏳ Harga belum tersedia.")

        elif text == "/storm":
            p = state["prev_price"] or 0
            storm = detect_perfect_storm(state["candles"], p)
            factor_text = "\n".join([f"  {f}" for f in storm["factors"]]) if storm["factors"] else "  Tidak ada faktor"
            send_telegram(
                f"🌪️ *PERFECT STORM METER*\n"
                f"━━━━━━━━━━━━━━\n"
                f"Level: {storm['level']}\n"
                f"Score: {storm['score']}/12\n\n"
                f"Faktor aktif:\n{factor_text}\n\n"
                f"💥 {storm['action']}\n"
                f"━━━━━━━━━━━━━━\n"
                f"🎯 Dominant Strategy:\n"
                f"1. Asia sideway → London Hurricane\n"
                f"2. Sweep Low Asia → 61.8% Golden Ratio\n"
                f"3. NY Breakout = Arah Dominan\n"
                f"━━━━━━━━━━━━━━\n"
                f"🕐 {now_wib().strftime('%H:%M:%S')} WIB"
            )

        elif text == "/status":
            p = state["prev_price"] or 0
            moon = get_moon_phase()
            impact = get_moon_impact(moon["phase_en"])
            planets = get_planet_info()
            storm = detect_perfect_storm(state["candles"], p)
            planet_text = "\n".join([f"  • {pl}" for pl in planets])
            sess_map = {"asia":"🌏 Asia","pre":"⏳ Pre-London","london":"🇬🇧 London","ny":"🇺🇸 New York"}
            send_telegram(
                f"📊 *STATUS BOT XAUUSD*\n"
                f"━━━━━━━━━━━━━━\n"
                f"💰 Harga: *${p:.2f}*\n"
                f"🌏 Sesi: *{sess_map.get(get_session())}*\n"
                f"📍 Low Asia: *{'$'+str(state['asia_lo']) if state['asia_lo'] else 'Belum'}*\n"
                f"📍 High Asia: *{'$'+str(state['asia_hi']) if state['asia_hi'] else 'Belum'}*\n"
                f"📐 Fibonacci: {'✅' if state['fib'] else '⏳'}\n"
                f"📈 BUY Asia: {'✅' if state['buy_done'] else '⏳'}\n"
                f"📉 SELL London: {'✅' if state['sell_done'] else '⏳'}\n"
                f"🔄 BUY 61.8%: {'✅' if state['buy2_done'] else '⏳'}\n"
                f"🌊 Low Asia Swept: {'✅' if state['low_asia_swept'] else '❌'}\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌪️ Storm: {storm['level']} ({storm['score']}/12)\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌙 {moon['phase']} ({moon['illumination']}%)\n"
                f"Bias: {impact['bias']}\n"
                f"📝 {impact['desc']}\n\n"
                f"🪐 Planet:\n{planet_text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"🕐 {now_wib().strftime('%d %b %Y %H:%M:%S')} WIB"
            )

        elif text == "/moon":
            moon = get_moon_phase()
            impact = get_moon_impact(moon["phase_en"])
            send_telegram(
                f"🌙 *FASE BULAN & GOLD*\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌑🌒🌓🌔🌕🌖🌗🌘\n\n"
                f"Fase: {moon['phase']}\n"
                f"Hari ke-{moon['days']} dari 29.5\n"
                f"Illuminasi: {moon['illumination']}%\n"
                f"Next Full Moon: {moon['next_full']:.0f} hari\n"
                f"Next New Moon: {moon['next_new']:.0f} hari\n"
                f"━━━━━━━━━━━━━━\n"
                f"Bias: {impact['bias']}\n"
                f"📝 {impact['desc']}\n\n"
                f"💡 {impact['trading']}\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌑 New Moon → Reversal/Siklus baru\n"
                f"🌒🌓 Waxing → Gold naik\n"
                f"🌕 Full Moon → High/Reversal\n"
                f"🌖🌗 Waning → Gold turun\n"
                f"🌘 Dark → Volatile"
            )

        elif text == "/astro":
            moon = get_moon_phase()
            impact = get_moon_impact(moon["phase_en"])
            planets = get_planet_info()
            planet_text = "\n".join([f"• {p}" for p in planets])
            send_telegram(
                f"🔭 *ASTROLOGI — {now_wib().strftime('%d %b %Y')}*\n"
                f"━━━━━━━━━━━━━━\n"
                f"🌙 {moon['phase']} ({moon['illumination']}%)\n\n"
                f"🪐 Planet aktif:\n{planet_text}\n\n"
                f"📊 Bias: {impact['bias']}\n"
                f"📝 {impact['desc']}\n\n"
                f"💡 {impact['trading']}\n"
                f"━━━━━━━━━━━━━━\n"
                f"⚠️ _Astro = panduan tambahan_"
            )

        elif text == "/listsr":
            p = state["prev_price"] or 0
            levels = get_auto_sr(state["candles"], p)
            if not levels:
                send_telegram("⏳ Data S&R belum cukup.")
            else:
                res = sorted([l for l in levels if l["type"]=="resistance" and l["price"]>p], key=lambda x:x["price"])[:5]
                sup = sorted([l for l in levels if l["type"]=="support" and l["price"]<p], key=lambda x:x["price"], reverse=True)[:5]
                msg = [f"📋 *Level S&R* (${p:.2f})\n"]
                if res:
                    msg.append("🔴 *Resistance:*")
                    for l in res: msg.append(f"  • {l['label']}: *${l['price']:.2f}* (+{l['price']-p:.1f})")
                if sup:
                    msg.append("\n🟢 *Support:*")
                    for l in sup: msg.append(f"  • {l['label']}: *${l['price']:.2f}* (-{p-l['price']:.1f})")
                send_telegram("\n".join(msg))

# ── Main Loop ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  XAUUSD Bot v6 — Perfect Storm Edition")
    print("  Daily + Weekly Briefing + Storm Detection")
    print("=" * 50)
    moon   = get_moon_phase()
    impact = get_moon_impact(moon["phase_en"])
    send_telegram(
        f"🚀 *XAUUSD Bot v6 — Perfect Storm!*\n"
        f"━━━━━━━━━━━━━━\n"
        f"📡 gold-api.com (unlimited)\n"
        f"📊 Timeframe: M5\n"
        f"🌅 Daily briefing: *07:00 WIB*\n"
        f"📅 Weekly briefing: *Senin 07:30 WIB*\n"
        f"🌪️ Perfect Storm auto-detection\n"
        f"🌊 London Sweep Low Asia alert\n"
        f"🌙 {moon['phase']} | {impact['bias']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Ketik /briefing untuk briefing sekarang!\n"
        f"Ketik /weekly untuk weekly briefing!\n"
        f"🕐 {now_wib().strftime('%d %b %Y %H:%M')} WIB"
    )

    while True:
        try:
            reset_daily()
            check_briefings()
            handle_commands()
            price = fetch_price()
            if price:
                prev  = state["prev_price"]
                chg   = round(price - prev, 2) if prev else 0
                arrow = "▲" if chg >= 0 else "▼"
                print(f"[{now_wib().strftime('%H:%M:%S')}] ${price:.2f} {arrow}{abs(chg):.2f} | {get_session()} | Lo:{state['asia_lo']} Hi:{state['asia_hi']}")
                mk = int(time.time() // 300)
                if state["cur_candle"] is None or state["cur_candle"]["mk"] != mk:
                    if state["cur_candle"] is not None:
                        closed = {k: state["cur_candle"][k] for k in ["open","high","low","close"]}
                        state["candles"] = state["candles"][-8640:] + [closed]
                        process_candle(closed)
                    state["cur_candle"] = {"mk": mk, "open": price, "high": price, "low": price, "close": price}
                else:
                    c = state["cur_candle"]
                    c["high"] = max(c["high"], price)
                    c["low"]  = min(c["low"],  price)
                    c["close"] = price
                state["prev_price"] = price
        except KeyboardInterrupt:
            print("\n[STOP] Bot dihentikan.")
            send_telegram("⏹ *XAUUSD Bot dihentikan.*")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
