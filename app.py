from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, render_template, request

# -----------------------------------------------------------------------------
# configuration ---------------------------------------------------------------
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

RESELLER_USERNAME = os.getenv("GOLDENOTT_USERNAME")
RESELLER_PASSWORD = os.getenv("GOLDENOTT_PASSWORD")
if not (RESELLER_USERNAME and RESELLER_PASSWORD):
    raise RuntimeError("GOLDENOTT_USERNAME / GOLDENOTT_PASSWORD missing in .env")

# -----------------------------------------------------------------------------
# bouquet constants (unchanged) -----------------------------------------------
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# low‑level helpers -----------------------------------------------------------
# -----------------------------------------------------------------------------

def login(session: requests.Session) -> None:
    r = session.get("https://goldenott.net/")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token_inp = soup.select_one('input[name="_csrf_token"]')
    if not token_inp:
        raise RuntimeError("Login CSRF token not found")
    payload = {
        "_username": RESELLER_USERNAME,
        "_password": RESELLER_PASSWORD,
        "_csrf_token": token_inp["value"],
    }
    r = session.post("https://goldenott.net/", data=payload, allow_redirects=True)
    r.raise_for_status()
    if "Dashboard" not in r.text and "Logout" not in r.text:
        raise RuntimeError("Login failed – still on login page")


def fetch_create_token(session: requests.Session) -> str:
    r = session.get("https://goldenott.net/reseller/m3u/new")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token_inp = soup.select_one('input[name="m3u[_token]"]')
    if not token_inp:
        raise RuntimeError("Create-form CSRF token not found")
    return token_inp["value"]


def build_payload(form_csrf: str,
                  user: str,
                  passwd: str,
                  adult_flag: str,
                  forced_country: str) -> list[tuple[str, str]]:
    """Return list-of-tuples payload mirroring the order that worked in the
    first proven‑good version (forcedCountry **always present**, _token last)."""

    pairs: list[tuple[str, str]] = [
        ("m3u[username]",      user),
        ("m3u[id]",            ""),          # empty == new user
        ("m3u[password]",      passwd),
        ("m3u[period]",        "1"),
        ("m3u[fullName]",      ""),
        ("m3u[email]",         ""),
        ("m3u[phone]",         ""),
        ("m3u[note]",          ""),
        ("m3u[forcedCountry]", forced_country),  # always include, "" for Auto, "ALL" for VPN
        ("m3u[adult]",         adult_flag),
        ("m3u[_token]",        form_csrf),       # keep _token last like the browser does
    ]

    pairs.extend(("m3u[bouquetLive][]", b) for b in BOUQUET_LIVE)
    pairs.extend(("m3u[bouquetVod][]",  v) for v in BOUQUET_VOD)
    return pairs


# -----------------------------------------------------------------------------
# single reusable helper  -----------------------------------------------------
# -----------------------------------------------------------------------------

def goldenott_create(username: str,
                     password: str,
                     adult_flag: str,
                     forced_country: str | None) -> str:
    """Full flow but returns raw HTML for caller (Flask route or bot)."""
    with requests.Session() as sess:
        login(sess)
        form_token = fetch_create_token(sess)
        data = build_payload(form_token, username, password, adult_flag, forced_country)

        # ---- diagnostic: forced-country & encoded size -------------------
        encoded = urlencode(data, doseq=True)
        print("[DEBUG] FORCED=", forced_country, "POST SIZE=", len(encoded))
        # -----------------------------------------------------------------

        r = sess.post(
            "https://goldenott.net/reseller/m3u/new",
            data=data,
            headers={"Referer": "https://goldenott.net/reseller/m3u/new"},
            allow_redirects=True,
        )
        r.raise_for_status()
        return r.text

# -----------------------------------------------------------------------------
# Flask web UI ----------------------------------------------------------------
# -----------------------------------------------------------------------------
app = Flask(__name__, template_folder=BASE_DIR / "templates")


@app.route("/")
def form():
    return render_template("form.html")


@app.route("/create", methods=["POST"])
def create():
    user = request.form["username"].strip()
    passwd = request.form["password"].strip()

    # --- username validation ------------------------------------------------
    if not (user.isalnum() and len(user) >= 7):
        return (
            "<h3 style='color:red'>❌ Invalid username</h3>"
            "<p>Username must be at least 7 characters and contain only letters and numbers.</p>"
        )
    # -----------------------------------------------------------------------

    adult = "1" if "adult" in request.form else "0"
    fc_choice = request.form.get("forced_country", "Auto")
    forced_country = "" if fc_choice == "Auto" else "ALL"

    try:
        html_response = goldenott_create(user, passwd, adult, forced_country)

                # ---- heuristic: check for a *real* alert-danger div --------------
        from bs4 import BeautifulSoup as _Bs

        soup = _Bs(html_response, "html.parser")
        err_div = soup.select_one("div.alert-danger")
        if err_div:
            snippet = str(err_div).replace("<", "&lt;")
            return (
                "<h3 style='color:red'>❌ GoldenOTT error</h3>"
                f"<pre>{snippet}</pre>"
            )
        # ------------------------------------------------------------------

        snippet = html_response.replace("<", "&lt;")[:3000]
        return (
            "<h3 style='color:green'>🟢 GoldenOTT replied</h3>"
            "<pre style='white-space:pre-wrap;max-height:600px;overflow-y:auto;"
            "border:1px solid #aaa;padding:.6rem'>"
            f"{snippet}\n\n…trimmed…</pre>"
        )
    except Exception as exc:
        return f"<h3>❌ Error</h3><pre>{exc}</pre>"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, port=port)