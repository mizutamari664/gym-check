# =========================
# ライブラリ
# =========================
import time
import random
import os
import json
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

    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, scope)

    client = gspread.authorize(creds)

    return client.open_by_url(SPREADSHEET_URL).worksheet("data")


# =========================
# 書き込み
# =========================
def write_to_sheet(rows):
    sheet = get_sheet()
    now = time.strftime("%Y-%m-%d %H:%M")

    data = [[now, *r] for r in rows]

    sheet.append_rows(data)
    print(f"[WRITE] {len(rows)}件 書き込み完了")


# =========================
# HTML解析（予約可すべて）
# =========================
def parse(html, name):
    soup = BeautifulSoup(html, "html.parser")
    out = []

    for row in soup.find_all("tr"):
        th = row.find("th")
        tds = row.find_all("td")

        if not th or not tds:
            continue

        time_label = th.get_text(strip=True)

        for td in tds:
            text = td.get_text(" ", strip=True)

            # 予約可のみ
            if "予約可" not in text:
                continue

            # 日付取得
            date = ""
            hidden = td.find("input", {"class": "js_usage_date"})
            if hidden:
                date = hidden.get("value")

            kind = "延長" if "延長" in time_label else "通常"

            out.append((date, name, kind, time_label, text))

    return out


# =========================
# 1施設チェック
# =========================
def check_one(page, name, fid, today):
    print("\n==============================")
    print(f"[施設] {name} ({fid})")
    print("==============================")

    try:
        # ページ移動（安定化）
        try:
            page.goto(URL, timeout=60000)
        except:
            print("[WARN] ページ読み込み失敗")
            return []

        time.sleep(2 + random.random())

        # 施設選択
        print("[STEP] 施設選択")
        page.select_option('[name="facility_id"]', str(fid))

        # 体育室（全面）
        print("[STEP] 体育室（全面）")
        group_id = str(fid) + "0100"
        if page.query_selector('[name="group_id"]'):
            page.select_option('[name="group_id"]', group_id)

        # 1ヶ月表示
        print("[STEP] 1ヶ月表示")
        page.check('input[value="3"]')

        # 日付
        print(f"[STEP] 日付設定: {today}")
        page.fill('input[name="date"]', today)

        # 検索ボタン
        print("[STEP] 検索")
        try:
            page.click('button[type="submit"]', timeout=10000)
        except:
            print("[WARN] クリック失敗")
            return []

        # 読み込み待ち（ゆるく）
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            print("[WARN] 読み込み待ちタイムアウト（続行）")

        time.sleep(2)

        html = page.content()

        results = parse(html, name)

        for r in results:
            print(f"[HIT] {r[1]} {r[0]} {r[3]} {r[2]}")

        print(f"[進捗] {len(results)}件")

        return results

    except Exception as e:
        print(f"[ERROR] {name} スキップ:", e)
        return []


# =========================
# メイン
# =========================
def run(page):
    print("[START] 起動")

    today = datetime.now().strftime("%Y/%m/%d")
    print(f"[DATE] 今日: {today}")

    all_results = []

    for name, fid in FACILITY_IDS.items():
        try:
            data = check_one(page, name, fid, today)
            all_results.extend(data)
        except Exception as e:
            print(f"[ERROR] {name} 完全スキップ:", e)

        time.sleep(2)

    # 保存
    if all_results:
        write_to_sheet(all_results)
    else:
        print("[INFO] 空きなし")

    print("[END] 完了")


# =========================
# 実行
# =========================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # ← GitHub用
    page = browser.new_page()

    run(page)

    browser.close()
