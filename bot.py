"""
Stand-alone Telegram bot:
 • logs in to GoldenOTT
 • creates a 1-day trial M3U line
 • shows a tidy info card with every run
No dependency on app.py.
"""

from __future__ import annotations
import asyncio
import html
import os
from pathlib import Path

from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.error import TimedOut, BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------------------------------------------------
# 0.  environment -------------------------------------------------------
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")      # reads reseller & bot creds

BOT_TOKEN           = os.getenv("TELEGRAM_TOKEN")
RESELLER_USERNAME   = os.getenv("GOLDENOTT_USERNAME")
RESELLER_PASSWORD   = os.getenv("GOLDENOTT_PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN missing from .env")
if not (RESELLER_USERNAME and RESELLER_PASSWORD):
    raise RuntimeError("GOLDENOTT_USERNAME / GOLDENOTT_PASSWORD missing in .env")


# ----------------------------------------------------------------------
# 1.  bouquet constants (full lists) -----------------------------------
# ----------------------------------------------------------------------
BOUQUET_LIVE = [
    "1393", "1357", "1374", "1356", "1353", "1355", "1369", "1354", "1373", "580",
    "1364", "1394", "119", "115", "1331", "118", "1454", "120", "117", "116", "217",
    "561", "650", "1313", "272", "560", "1316", "1317", "1314", "1322", "1385",
    "1321", "1315", "1319", "1323", "574", "12", "16", "563", "15", "1375", "19",
    "26", "1398", "73", "509", "508", "511", "516", "510", "512", "562", "525",
    "513", "514", "270", "517", "518", "520", "1384", "522", "524", "523", "526",
    "1372", "528", "1265", "1267", "1266", "273", "1269", "1268", "1270", "558",
    "47", "51", "74", "254", "192", "48", "56", "1469", "1335", "1474", "566",
    "1336", "1475", "565", "1470", "1337", "1476", "559", "1338", "1477", "1472",
    "1473", "1471", "809", "1478", "53", "45", "107", "124", "810", "811", "812",
    "813", "1376", "814", "815", "816", "817", "61", "1303", "1304", "1305", "1306",
    "1307", "1308", "1351", "1348", "250", "77", "136", "1289", "1332", "164", "25",
    "78", "79", "267", "1379", "1380", "1378", "1383", "20", "32", "27", "82", "81",
    "44", "262", "83", "1382", "42", "21", "22", "23", "28", "35", "24", "76", "31",
    "29", "30", "40", "86", "38", "33", "37", "39", "41", "36", "34", "43", "1287",
    "1278", "1284", "1279", "1280", "1281", "1283", "1285", "1282", "1392", "1286",
    "556", "139", "137", "228", "227", "138", "226", "229", "230", "231", "232",
    "567", "140", "245", "242", "244", "234", "233", "1387", "274", "241", "141",
    "240", "238", "237", "239", "235", "236", "1377", "269", "268", "243", "249",
    "247", "248", "80", "218", "555", "590", "557", "187", "564", "145", "65",
    "220", "57", "1294", "1295", "1296", "1297", "1298", "1299", "1300", "50", "58",
    "596", "54", "104", "607", "100", "109", "89", "64", "1310", "1386", "579",
    "588", "1349", "594"
]

BOUQUET_VOD = [
    "1358", "1368", "1365", "1367", "1366", "1242", "103", "193", "179", "180",
    "913", "185", "256", "259", "904", "897", "922", "902", "896", "901", "920",
    "923", "895", "928", "921", "903", "910", "1311", "911", "898", "912", "571",
    "111", "94", "189", "215", "263", "257", "260", "884", "877", "863", "879",
    "864", "876", "872", "1291", "889", "880", "891", "881", "888", "883", "585",
    "870", "885", "875", "882", "862", "1453", "101", "110", "587", "186", "106",
    "586", "1389", "184", "1391", "1460", "1388", "191", "190", "1293", "1292",
    "1464", "1466", "128", "1224", "1226", "188", "125", "72", "71", "99", "1423",
    "1462", "1438", "1437", "1441", "1442", "1449", "1452", "1440", "1424", "1428",
    "1429", "1463", "264", "1433", "1431", "1468", "1430", "1434", "1432", "1435",
    "1450", "1436", "1448", "1443", "1444", "1446", "1447", "108", "1220", "68",
    "112", "1129", "575", "576", "577", "578", "163", "1264", "1261", "1260",
    "1262", "221", "223", "529", "595", "1231", "1230", "1233", "1228", "1232",
    "1234", "166", "178", "175", "182", "167", "651", "658", "666", "222", "1344",
    "1347", "1390", "659", "1345", "1346", "664", "1399", "174", "168", "531",
    "584", "568", "1465", "532", "573", "252", "214", "581", "173", "169", "572",
    "171", "1312", "172", "181", "1455", "1456", "1457", "1458", "1459", "1326",
    "1327", "1328", "1329", "1330", "277", "278", "279", "280", "281", "266",
    "251", "170", "161", "597", "253", "801", "799", "800", "533", "582", "794"
]

# ----------------------------------------------------------------------
# 2.  raw HTTP helpers --------------------------------------------------
# ----------------------------------------------------------------------
def login(session: requests.Session) -> None:
    r = session.get("https://goldenott.net/")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.select_one('input[name="_csrf_token"]')
    if not token:
        raise RuntimeError("Login CSRF token not found")
    payload = {
        "_username": RESELLER_USERNAME,
        "_password": RESELLER_PASSWORD,
        "_csrf_token": token["value"],
    }
    r = session.post("https://goldenott.net/", data=payload, allow_redirects=True)
    r.raise_for_status()
    if "Dashboard" not in r.text and "Logout" not in r.text:
        raise RuntimeError("Login failed")


def fetch_create_token(session: requests.Session) -> str:
    r = session.get("https://goldenott.net/reseller/m3u/new")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.select_one('input[name="m3u[_token]"]')
    if not token:
        raise RuntimeError("Create-form CSRF token not found")
    return token["value"]


def build_payload(form_csrf: str,
                  user: str,
                  passwd: str,
                  adult_flag: str,
                  forced_country: str) -> list[tuple[str, str]]:
    pairs = [
        ("m3u[username]",      user),
        ("m3u[id]",            ""),
        ("m3u[password]",      passwd),
        ("m3u[period]",        "1"),
        ("m3u[fullName]",      ""),
        ("m3u[email]",         ""),
        ("m3u[phone]",         ""),
        ("m3u[note]",          ""),
        ("m3u[forcedCountry]", forced_country),   # \"\" for Auto, \"ALL\" for VPN
        ("m3u[adult]",         adult_flag),
        ("m3u[_token]",        form_csrf),
    ]
    pairs.extend(("m3u[bouquetLive][]", b) for b in BOUQUET_LIVE)
    pairs.extend(("m3u[bouquetVod][]",  v) for v in BOUQUET_VOD)
    return pairs


def goldenott_create(username: str,
                     password: str,
                     adult_flag: str,
                     forced_country: str) -> str:
    with requests.Session() as sess:
        login(sess)
        form_token = fetch_create_token(sess)
        data = build_payload(form_token, username, password, adult_flag, forced_country)
        r = sess.post(
            "https://goldenott.net/reseller/m3u/new",
            data=data,
            headers={"Referer": "https://goldenott.net/reseller/m3u/new"},
            allow_redirects=True,
            timeout=30,
        )
        r.raise_for_status()
        return r.text

# ----------------------------------------------------------------------
# 3.  Telegram conversation --------------------------------------------
# ----------------------------------------------------------------------
ASK_USERNAME, ASK_PASSWORD, ASK_COUNTRY, ASK_ADULT = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi\\! Send the *username* you want\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ASK_USERNAME


async def got_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candidate = update.message.text.strip()
    if not (candidate.isalnum() and len(candidate) >= 7):
        await update.message.reply_text(
            "🚫 *Invalid username* – letters+numbers, at least 7 characters\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ASK_USERNAME
    context.user_data["username"] = candidate
    await update.message.reply_text("Now the *password*:", parse_mode=ParseMode.MARKDOWN_V2)
    return ASK_PASSWORD


async def got_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["password"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Auto", callback_data="country_auto"),
         InlineKeyboardButton("🔒 VPN",  callback_data="country_vpn")]
    ])
    await update.message.reply_text(
        "Choose *Forced Country*:",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ASK_COUNTRY


async def got_country_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except TimedOut:
        pass
    context.user_data["forced_country"] = "" if q.data == "country_auto" else "ALL"
    try:
        await q.edit_message_reply_markup(None)
    except BadRequest:
        pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes", callback_data="adult_yes"),
         InlineKeyboardButton("🚫 No",  callback_data="adult_no")]
    ])
    await q.message.reply_text("Mark as *adult*?", reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2)
    return ASK_ADULT


async def got_adult_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except TimedOut:
        pass

    adult_flag = "1" if q.data == "adult_yes" else "0"
    u  = context.user_data["username"]
    p  = context.user_data["password"]
    fc = context.user_data["forced_country"]

    try:
        await q.edit_message_reply_markup(None)
    except BadRequest:
        pass

    await q.message.reply_text("⏳ Working…")

    try:
        html_response = await asyncio.to_thread(goldenott_create, u, p, adult_flag, fc)
        soup = BeautifulSoup(html_response, "html.parser")
        err_div = soup.select_one("div.alert-danger")
        if err_div:
            msg_head = f"❌ Error: {err_div.get_text(' ', strip=True)}"
        else:
            msg_head = "✅ User created successfully!"
    except Exception as exc:
        msg_head = f"❌ Error: {exc}"

    info_msg = (
        f"Username : {u}\n"
        f"Password : {p}\n"
        f"actived : 1 day trial\n"
        f"\nThe URL :\n\n"
        f"http://gndk28.xyz:80\n"
        f"http://activefrance.net\n"
        f"http://atg100.xyz\n"
        f"http://teck-tv.com\n"
        f"http://tripleserver3.com:80\n"
        f"http://xrf98.com\n"
        f"http://likan.me\n"
        f"\nM3U Link : http://gndk28.xyz/get.php?username={u}&password={p}&type=m3u_plus&output=mpegts\n"
        f"\nApk link : https://up.goldenott.net\n"
        f"\nSAMSUNG/LG IPTV SMARTERS DNS : http://line.4smart.in\n"
        f"\nMag portal : http://gndk28.xyz/c\n"
        f"\nSAMSUNG/LG IPTV SMARTERS DNS : http://activefrance.net"
    )
    await q.message.reply_text(info_msg)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Conversation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ----------------------------------------------------------------------
# 4.  bootstrap ---------------------------------------------------------
# ----------------------------------------------------------------------
def main():
    builder = Application.builder().token(BOT_TOKEN)
    app = builder.build()

    convo = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_username)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_password)],
            ASK_COUNTRY:  [CallbackQueryHandler(got_country_button, pattern="^country_(auto|vpn)$")],
            ASK_ADULT:    [CallbackQueryHandler(got_adult_button,   pattern="^adult_(yes|no)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="goldenott_convo",
        allow_reentry=True,
    )

    app.add_handler(convo)
    app.add_handler(CommandHandler("cancel", cancel))

    print("Telegram bot running – Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
