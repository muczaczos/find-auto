
import requests
from bs4 import BeautifulSoup
import schedule
import time
import json
from datetime import date
from dotenv import load_dotenv
import os


# =========================
# KONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL_OTOMOTO = os.getenv("URL_OTOMOTO")
URL_CHODZEN = os.getenv("URL_CHODZEN")
URL_PEWNEAUTO = os.getenv("URL_PEWNEAUTO")

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

DB_FILE = "seen_ads.json"

headers = {
    "User-Agent": "Mozilla/5.0"
}


# =========================
# BAZA DZIENNA
# =========================

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") != str(date.today()):
                print("Nowy dzień - resetuję bazę")
                return {"date": str(date.today()), "sent": []}
            return data
    except:
        return {"date": str(date.today()), "sent": []}


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)


def send_message(db, ad_id, message, skip_duplicate_check=False):
    if not skip_duplicate_check and ad_id in db["sent"]:
        print(f"⏭️ Już wysłane dziś: {ad_id[:60]}")
        return
    try:
        resp = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": message})
        if resp.ok:
            print("✅ Wysłano na Telegram")
            if not skip_duplicate_check:
                db["sent"].append(ad_id)
        else:
            print("Błąd Telegram:", resp.text)
    except Exception as e:
        print("Błąd Telegram:", e)


# =========================
# SCRAPER
# =========================

def check_otomoto():

    db = load_db()

    print("Sprawdzam Otomoto...")

    response = requests.get(URL_OTOMOTO, headers=headers)

    soup = BeautifulSoup(response.text, "lxml")

    # Szukamy wszystkich linków zawierających /oferta/ (tylko te z tekstem - bez linków do zdjęć)
    all_links = soup.find_all("a", href=True)
    
    seen_links = set()
    offer_links = []
    for link in all_links:
        href = link.get("href", "")
        if "/oferta/" in href and href not in seen_links:
            seen_links.add(href)
            offer_links.append(link)

    print(f"Znaleziono: {len(offer_links)} ogłoszeń")

    found_new = False
    for link_tag in offer_links:
        link = link_tag["href"]
        title = link_tag.get_text(strip=True)
        print(f"✅ Ogłoszenie: {title}")
        # Próba wyciągnięcia danych
        lines = title.split()
        year = "?"
        mileage = "?"
        engine = "?"
        for i, word in enumerate(lines):
            # Rok
            if word.isdigit() and len(word) == 4:
                if 2000 <= int(word) <= 2026:
                    year = word
            # Przebieg
            if "km" in word.lower():
                mileage = word
            # Silnik
            if "cm3" in word.lower() or "hybrid" in word.lower():
                engine = word
        message = f"""
🚗 NOWA RAV4 (otomoto.pl)

📌 {title}

📅 Rok: {year}
🛣️ Przebieg: {mileage}
⚙️ Silnik: {engine}

🔗 {link}
"""
        print(message)
        # Sprawdź, czy ogłoszenie jest nowe
        if link not in db["sent"]:
            found_new = True
        send_message(db, link, message)
    if not found_new:
        send_message(db, f"no-new-{date.today()}-otomoto", "Nie ma nic nowego (Otomoto)", skip_duplicate_check=True)
    save_db(db)


def check_chodzen_site(url, site_name, base_url):

    db = load_db()

    print(f"Sprawdzam {site_name}...")

    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, "lxml")

    offers = soup.find_all("div", class_="o-bx")

    print(f"Znaleziono: {len(offers)} ogłoszeń")

    found_new = False
    for offer in offers:
        link_tag = offer.find("a", href=True)
        link = base_url + link_tag["href"] if link_tag else "?"
        title_tag = offer.find("div", class_="o-bx__title")
        if title_tag:
            strong = title_tag.find("strong")
            span = title_tag.find("span")
            title = (strong.get_text(strip=True) if strong else "") + " " + (span.get_text(strip=True) if span else "")
        else:
            title = "?"
        info = offer.find("div", class_="o-bx__info")
        year = "?"
        mileage = "?"
        engine = "?"
        if info:
            items = [li.get_text(strip=True) for li in info.find_all("li")]
            for item in items:
                if item.isdigit() and len(item) == 4:
                    year = item
                elif "km" in item.lower():
                    mileage = item
                elif "cm" in item.lower() or "hybrid" in item.lower():
                    engine = item
        price_tag = offer.find("div", class_="o-bx__price")
        price = price_tag.find("strong").get_text(strip=True) if price_tag and price_tag.find("strong") else "?"
        print(f"✅ Ogłoszenie: {title.strip()}")
        message = f"""
🚗 NOWA RAV4 ({site_name})

📌 {title.strip()}

📅 Rok: {year}
🛣️ Przebieg: {mileage}
⚙️ Silnik: {engine}
💰 Cena: {price}

🔗 {link}
"""
        print(message)
        # Sprawdź, czy ogłoszenie jest nowe
        if link not in db["sent"]:
            found_new = True
        send_message(db, link, message)
    if not found_new:
        send_message(db, f"no-new-{date.today()}-{site_name}", f"Nie ma nic nowego ({site_name})", skip_duplicate_check=True)
    save_db(db)


def check_chodzen():
    check_chodzen_site(URL_CHODZEN, "chodzen.pl", "https://uzywane.chodzen.pl")


def check_pewneauto():
    check_chodzen_site(URL_PEWNEAUTO, "pewneauto.pl", "https://pewneauto.pl")

check_otomoto()
check_chodzen()
check_pewneauto()

schedule.every(1).hours.do(check_otomoto)
schedule.every(1).hours.do(check_chodzen)
schedule.every(1).hours.do(check_pewneauto)

print("Bot uruchomiony...")

while True:
    schedule.run_pending()
    time.sleep(10)