# =========================
# ライブラリ
# =========================
import time
import random
from datetime import datetime

import gspread
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from oauth2client.service_account import ServiceAccountCredentials


# =========================
# 設定
# =========================
URL = "https://shisetsu.city.hachioji.tokyo.jp/reserve/calendar"

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1VTG74O1W1EMLvWnCbQt0OJyZLCGKsUdB1MnkceM1T5E/edit"


FACILITY_IDS = {
    "子安": 304,
    "南大沢": 315,
    "由木中央": 305,
    "由木東": 310,
    "横山南": 318,
    "台町": 314,
    "大和田": 301,
    "由井": 306,
    "長房": 302,
    "恩方": 313,
    "加住": 317,
    "石川": 312,
    "中野": 311,
    "川口": 316,
    "浅川": 303,
    "元八王子": 309
}


# =========================
# スプレッドシート接続
# =========================
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = import os
import json

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, scope)

    client = gspread.authorize(creds)

    return client.open_by_url(SPREADSHEET_URL).worksheet("data")


# =========================
# 書き込み
# =========================
def write_to_sheet(rows):
    print(f"[LOG] 書き込み {len(rows)}件")

    sheet = get_sheet()
    now = time.strftime("%Y-%m-%d %H:%M")

    data = [[now, *r] for r in rows]
    sheet.append_rows(data)


# =========================
# HTML解析（完全対応）
# =========================
def parse(html, name):
    soup = BeautifulSoup(html, "html.parser")
    out = []

    for row in soup.find_all("tr"):

        th = row.find("th")
        if not th:
            continue

        time_label = th.get_text(strip=True)

        blocks = row.find_all("div", class_="collectReserve")

        for b in blocks:

            span = b.find("span")
            if not span:
                continue

            if "予約可" not in span.get_text():
                continue

            # hidden情報取得
            date = b.find("input", class_="js_usage_date")["value"]
            gid = b.find("input", class_="js_group_id")["value"]

            # 体育室（全面）だけ
            if not gid.endswith("0100"):
                continue

            kind = "延長" if "延長" in time_label else "通常"

            print(f"[HIT] {name} {date} {time_label} {kind}")

            out.append((
                date,
                name,
                kind,
                time_label,
                gid
            ))

    return out


# =========================
# 1施設処理
# =========================
def check_one(page, name, fid, today):

    print(f"\n[施設] {name} ({fid})")

    page.goto(URL)
    time.sleep(2 + random.random())

    try:
        # ① 施設選択
        page.wait_for_selector('[name="facility_id"]')
        page.select_option('[name="facility_id"]', str(fid))
        print("[STEP] 施設選択")

        time.sleep(1)

        # ② 体育室（全面）
        place_id = str(fid) + "0100"
        page.select_option('#place', place_id)

        page.evaluate("""
        () => {
            const el = document.querySelector('#place');
            if (el) el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """)
        print("[STEP] 体育室（全面）")

        time.sleep(1)

        # ③ 1ヶ月表示（強制）
        page.evaluate("""
        () => {
            const el = document.querySelector('#user-calendar-disp-type-3');
            if (el) {
                el.checked = true;
                el.click();
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        """)
        print("[STEP] 1ヶ月表示")

        # ④ 今日の日付
        page.fill('[name="date"]', today)
        print(f"[STEP] 日付設定: {today}")

        # ⑤ 検索
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("table")

        print("[STEP] 検索完了")

    except Exception as e:
        print("[ERROR]", e)
        return []

    html = page.content()

    return parse(html, name)


# =========================
# メイン処理
# =========================
def run(page):

    today = datetime.now().strftime("%Y/%m/%d")

    print("\n==============================")
    print(f"[DATE] 今日: {today}")
    print("==============================")

    results = []

    for name, fid in FACILITY_IDS.items():
        data = check_one(page, name, fid, today)
        results.extend(data)

        print(f"[進捗] {len(results)}件")
        time.sleep(1)

    if results:
        write_to_sheet(results)
        print(f"[保存] {len(results)}件")
    else:
        print("[結果] 空きなし")


# =========================
# 実行
# =========================
with sync_playwright() as p:
    print("[START] 起動")

    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    run(page)

    browser.close()

    print("[END] 完了")
