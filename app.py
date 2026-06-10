import os
import re
import json
import random
import threading
from datetime import datetime, timedelta
from flask import Flask, request, abort
import gspread
from google.oauth2.service_account import Credentials
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, PushMessageRequest
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ───────────────────────────────────────────────
# 🔮 生日分析：星座 + 生命靈數
# ───────────────────────────────────────────────

STAR_SIGN_DATA = {
    "牡羊座": {
        "emoji": "♈️",
        "dates": ((3,21),(4,19)),
        "personality": "行動派、直接衝、說到做到、沒耐心等結果",
        "sales": [
            "開門見山，直接說優勢，不要繞圈子",
            "強調「馬上生效、立刻保障」",
            "給他做決定的主導感，別讓他覺得被推銷",
            "速戰速決，拖太久他會失去興趣",
        ],
        "gift": "行動感強的禮物，例如運動用品、限量版新品、體驗活動",
    },
    "金牛座": {
        "emoji": "♉️",
        "dates": ((4,20),(5,20)),
        "personality": "重實際、愛穩定、慢熱但忠誠、重享受",
        "sales": [
            "強調保障的穩定性和長期價值",
            "給他充分的時間考慮，不要催",
            "提供具體數字和比較，讓他覺得划算",
            "信任建立後非常忠誠，值得深耕",
        ],
        "gift": "質感好、實用的禮物，例如美食禮盒、品牌保養品、高品質居家用品",
    },
    "雙子座": {
        "emoji": "♊️",
        "dates": ((5,21),(6,21)),
        "personality": "思緒快、話多、好奇心強、容易分心",
        "sales": [
            "說話要有趣有變化，不要照本宣科",
            "多問問題引發他思考和參與感",
            "準備多個方案讓他選，給他「選擇的快感」",
            "跟進要有新鮮感，不要傳一樣的東西",
        ],
        "gift": "新奇有趣的禮物，例如新出的科技小物、有趣的書或桌遊",
    },
    "巨蟹座": {
        "emoji": "♋️",
        "dates": ((6,22),(7,22)),
        "personality": "重感情、顧家、直覺強、需要安全感",
        "sales": [
            "從家人保障切入，讓他感受到你的關心",
            "建立私人情感連結，他買的是你這個人",
            "說話要溫柔，避免強硬或急迫",
            "節日問候非常重要，他記得誰記得他",
        ],
        "gift": "溫馨家庭感的禮物，例如手寫卡片＋伴手禮、家用好物、美食",
    },
    "獅子座": {
        "emoji": "♌️",
        "dates": ((7,23),(8,22)),
        "personality": "愛面子、領導欲強、大方但需被肯定",
        "sales": [
            "先讚美他的眼光和決策力",
            "強調這是「頂級、專屬、VIP」的選擇",
            "讓他覺得買保險是有品味有遠見的表現",
            "公開場合讓他有面子，私下再談細節",
        ],
        "gift": "有排場有面子的禮物，例如精品小物、高端餐廳體驗、限量禮盒",
    },
    "處女座": {
        "emoji": "♍️",
        "dates": ((8,23),(9,22)),
        "personality": "龜毛、完美主義、邏輯強、注重細節",
        "sales": [
            "資料要準備得非常完整，不能有錯誤",
            "讓他慢慢研究，不要催，他需要確認每個細節",
            "條款說明要清楚，他會逐條看",
            "用數據和邏輯說服，情感牌沒那麼有效",
        ],
        "gift": "實用且精緻的禮物，例如文具組、整理收納用品、品質好的日用品",
    },
    "天秤座": {
        "emoji": "♎️",
        "dates": ((9,23),(10,23)),
        "personality": "愛美、重公平、難下決定、重社交",
        "sales": [
            "給他多個方案比較，讓他自己選出「最平衡的」",
            "強調保障的全面性和公平性",
            "環境要舒適，說明要優雅，不要壓迫",
            "幫他做決定，但讓他感覺是自己選的",
        ],
        "gift": "美觀有設計感的禮物，例如香氛蠟燭、漂亮的文具或包裝精美的禮盒",
    },
    "天蠍座": {
        "emoji": "♏️",
        "dates": ((10,24),(11,22)),
        "personality": "疑心重、洞察力強、重深度信任、報復心強",
        "sales": [
            "絕對不能說謊或誇大，他一眼看穿",
            "建立深度信任需要時間，但一旦信任就非常忠誠",
            "讓他感受到你把他當重要客戶，不是在走業績",
            "說明要有深度，不要表面話",
        ],
        "gift": "有深度或神秘感的禮物，例如高質感香水、限量藝術品、私人訂製小物",
    },
    "射手座": {
        "emoji": "♐️",
        "dates": ((11,23),(12,21)),
        "personality": "樂觀自由、愛冒險、不喜被約束、大而化之",
        "sales": [
            "強調保障讓他更自由地去冒險",
            "說明要輕鬆有趣，不要太嚴肅",
            "不要太多細節，抓住大方向就好",
            "給他空間，不要一直追問",
        ],
        "gift": "旅行或冒險類禮物，例如旅遊禮券、戶外用品、新奇體驗",
    },
    "摩羯座": {
        "emoji": "♑️",
        "dates": ((12,22),(1,19)),
        "personality": "務實負責、有野心、重長遠、不輕易相信",
        "sales": [
            "用長期數字說話，強調投資報酬和未來規劃",
            "顯示你的專業度，他不接受不專業的業務",
            "建立關係需要時間，但信任後非常穩定",
            "強調責任感，「對家人的責任」很有效",
        ],
        "gift": "專業感或實用投資型禮物，例如商業書籍、高質感皮件、理財工具",
    },
    "水瓶座": {
        "emoji": "♒️",
        "dates": ((1,20),(2,18)),
        "personality": "獨立思考、反傳統、理性、有點距離感",
        "sales": [
            "強調這個選擇很獨特、跟別人不一樣",
            "用理性和邏輯說服，不要情感轟炸",
            "尊重他的空間，不要太熱情讓他不舒服",
            "讓他覺得自己做了一個聰明又有遠見的決定",
        ],
        "gift": "獨特或科技感的禮物，例如新奇科技產品、設計師款文具、環保創意禮品",
    },
    "雙魚座": {
        "emoji": "♓️",
        "dates": ((2,19),(3,20)),
        "personality": "感性、直覺強、容易被感動、重情義、有點做夢",
        "sales": [
            "用故事和情境打動他，比數字更有效",
            "讓他感受到你真的關心他，不只是賣保險",
            "幫他把複雜的東西簡化，他不喜歡太硬的資料",
            "保持溫暖聯繫，他重視情感維繫",
        ],
        "gift": "有溫度又有趣的禮物，例如手作甜點、療癒小物、有意義的紀念品",
    },
}

LIFE_PATH_DATA = {
    1: {
        "keyword": "獨立領導",
        "personality": "有主見、不服輸、喜歡做決定、天生領袖感",
        "sales": [
            "讓他有主導感，別讓他覺得被說服",
            "強調「這是你自己的選擇，展現你的遠見」",
            "簡短有力，他不需要你幫他想太多",
        ],
        "gift": "限量、獨特、有象徵領導力的禮品",
    },
    2: {
        "keyword": "溫和重關係",
        "personality": "重感情、怕衝突、需要被支持、很會照顧人",
        "sales": [
            "慢慢來，建立情感再談業務",
            "強調「有我在，你不用擔心」",
            "他很在意關係，要讓他覺得你是朋友不是業務",
        ],
        "gift": "溫馨、家庭感的禮物，或手寫感謝卡",
    },
    3: {
        "keyword": "開朗創意",
        "personality": "活潑、愛說話、有創意、容易分心",
        "sales": [
            "說明要生動有趣，配上案例或小故事",
            "讓他參與、讓他說話，他喜歡被聽見",
            "定期有趣的訊息維持關係",
        ],
        "gift": "有趣的體驗型禮物或創意小物",
    },
    4: {
        "keyword": "務實穩健",
        "personality": "邏輯強、按部就班、重細節、不喜意外",
        "sales": [
            "準備完整資料，條理清晰說明",
            "按邏輯步驟走，不要跳躍",
            "給他清楚的計畫和時間表",
        ],
        "gift": "實用型禮物，例如精緻文具、工具組、高品質日常用品",
    },
    5: {
        "keyword": "自由冒險",
        "personality": "主動積極、不喜被約束、變化快、愛嘗試新事物",
        "sales": [
            "強調彈性和自由度，「保障讓你更敢衝」",
            "說明要簡短有力，不要太死板",
            "給他新鮮感，不要每次都一樣的話術",
        ],
        "gift": "體驗類禮物，例如旅遊券、新奇活動、限時體驗",
    },
    6: {
        "keyword": "完美照護",
        "personality": "完美主義、愛照顧人、重視美感、求好心切",
        "sales": [
            "強調對家人的保障，打感情牌最有效",
            "細節要完整，讓他感覺你很用心",
            "讓他覺得這個選擇是「對家人最好的安排」",
        ],
        "gift": "精緻有質感的禮物，或與家庭相關的溫馨禮品",
    },
    7: {
        "keyword": "深度信任",
        "personality": "直覺強、疑心重、需要深度交流、不輕易相信",
        "sales": [
            "建立深度信任，絕不說謊或過度承諾",
            "讓他自己慢慢想通，不要強迫",
            "提供有深度的資料，讓他研究",
        ],
        "gift": "獨特有深度的禮物，例如好書、私人訂製小物",
    },
    8: {
        "keyword": "成就利益",
        "personality": "有野心、重成就、聰明精明、以退為進",
        "sales": [
            "強調長期投資報酬和財務規劃",
            "讓他覺得這是「聰明人才懂的決定」",
            "用數字說話，展現你的專業和實力",
        ],
        "gift": "有品味、高檔感的禮物，展現你懂他的品味",
    },
    9: {
        "keyword": "理想意義",
        "personality": "有智慧、理想主義、慈悲心強、重視意義和價值",
        "sales": [
            "從保險的意義和價值切入，不只談數字",
            "用大格局說話，「這是對家人和社會的責任」",
            "讓他感覺買保險是一件有意義的事",
        ],
        "gift": "有意義的禮物，例如公益捐款卡、精神層面的書或課程",
    },
}

def get_star_sign(month, day):
    """根據月日計算星座"""
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "牡羊座"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "金牛座"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 21):
        return "雙子座"
    elif (month == 6 and day >= 22) or (month == 7 and day <= 22):
        return "巨蟹座"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "獅子座"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "處女座"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 23):
        return "天秤座"
    elif (month == 10 and day >= 24) or (month == 11 and day <= 22):
        return "天蠍座"
    elif (month == 11 and day >= 23) or (month == 12 and day <= 21):
        return "射手座"
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "摩羯座"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "水瓶座"
    else:
        return "雙魚座"

def get_life_path_number(year, month, day):
    """計算生命靈數（把所有數字加總直到個位數）"""
    total = sum(int(d) for d in str(year) + str(month) + str(day))
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total if total != 0 else 9

def analyze_birthday(birthday_str):
    """輸入生日字串，回傳分析結果"""
    # 支援格式：1985/03/15、1985-03-15、19850315
    birthday_str = birthday_str.strip()
    match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", birthday_str)
    if not match:
        match = re.match(r"(\d{4})(\d{2})(\d{2})", birthday_str)
    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None

    sign = get_star_sign(month, day)
    number = get_life_path_number(year, month, day)

    sd = STAR_SIGN_DATA[sign]
    ld = LIFE_PATH_DATA[number]

    lines = [
        f"🔮 {sd['emoji']} {sign} × 生命靈數 {number}（{ld['keyword']}）",
        "",
        f"✨ 個性特質：",
        f"  {sd['personality']}",
        f"  {ld['personality']}",
        "",
        "💼 業務攻略：",
    ]
    # 星座攻略2條 + 靈數攻略2條
    for tip in sd["sales"][:2]:
        lines.append(f"  • {tip}")
    for tip in ld["sales"][:2]:
        lines.append(f"  • {tip}")
    lines += [
        "",
        "🎁 服務與送禮方向：",
        f"  星座方向：{sd['gift']}",
        f"  靈數方向：{ld['gift']}",
    ]

    return "\n".join(lines)

app = Flask(__name__)

# ───────────────────────────────────────────────
# 📊 Google Sheets 設定
# ───────────────────────────────────────────────

SPREADSHEET_ID = "1Ncy3e8I_OaC3BhTl_SNzJeFWMOQMFuEhaOK8Rl1hUV0"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TODO_SHEET = "待辦事項"

# ───────────────────────────────────────────────
# 💪 鼓勵語句
# ───────────────────────────────────────────────

CHEER_MESSAGES = [
    # 🌸 溫暖療癒型
    "你已經很努力了，休息一下也沒關係 🌸",
    "每一次被拒絕，都是離成交更近一步 💕",
    "今天辛苦了，明天又是新的開始 🌅",
    "你的堅持，客戶都看在眼裡 🤍",
    "不是每顆種子都馬上發芽，但你種的每一顆都算數 🌱",
    "慢慢來，你比你想的更有力量 💪",
    "照顧好自己，才能照顧好客戶 🫶",
    "今天的低潮，是明天突破的前兆 🌈",
    "你不是一個人在戰鬥，我們都在 🤝",
    "感覺累的時候，代表你一直都在認真 ✨",
    "沒有白走的路，每一步都在累積 👣",
    "休息是為了走更長的路，給自己一點溫柔 🍵",
    "你選擇了一份有意義的工作，這本身就很了不起 🌟",
    "今天的你，比昨天的你更強了 💛",
    "深呼吸，你可以的 🌬️",
    # 🔥 熱血激勵型
    "困難是成長的燃料，加滿油繼續衝！🔥",
    "業績不會從天上掉下來，但努力的人會把它追下來！💥",
    "拒絕你的客戶只是還沒準備好，你的任務是等他準備好！⚡️",
    "冠軍不是天生的，是每天逼自己一點點練出來的！🏆",
    "今天的汗水，就是明天的獎金！💰",
    "沒有人能阻止一個下定決心的業務員！🦁",
    "打電話前深呼吸，你的聲音就是你的武器！📞",
    "每一個「不要」背後，都藏著一個「還沒」！🎯",
    "業務的字典裡沒有「放棄」，只有「再試一次」！🚀",
    "你不是在賣保險，你是在幫客戶保護最重要的人！❤️‍🔥",
    "今天多打一通電話，就多一個機會！📲",
    "失敗是暫時的，放棄才是永久的！💪",
    "比你優秀的人還在努力，你有什麼理由停下來？⚡️",
    "每一次出門拜訪，都是在投資未來的自己！🌠",
    "高手跟普通人的差別，只是多堅持了一點點！🏅",
    "今天的挑戰，是你明天說故事的材料！📖",
    "被拒絕10次，第11次就是成交！🎰",
    "你是客戶最需要的人，只是他還不知道！💡",
    "不逼自己一把，你不知道自己有多強！⚡️",
    "衝！今天的努力，你未來的自己會感謝你！🙌",
    # 😄 幽默輕鬆型
    "保險業務員不倒翁，彈起來繼續！😄",
    "客戶說不要？沒關係，下一位！（下一位才是真命天子）😂",
    "今天被拒絕了幾次？恭喜你，你又離成交更近了幾步！🎊",
    "保險業務的超能力：被拒絕後5秒鐘恢復滿血！⚡️😎",
    "業務員的一天：被拒絕、被拒絕、被拒絕、成交！撒花🎉",
    "打電話緊張？客戶又不會從電話裡跳出來打你😂",
    "今天沒成交？那是因為今天的任務是「種種子」🌱",
    "業務員進化論：菜鳥→被拒絕→再被拒絕→成為高手😆",
    "記住：每個頂尖業務員都曾經是被拒絕最多次的那個！🏆",
    "今天好累？表示你今天有在動！躺著才不會累😄",
    "客戶說「我再想想」= 我還需要你多關心我一下😂",
    "保險業務員的早餐：一碗被拒絕加一杯正能量，營養均衡！☕️",
    "你不是在推銷，你是在「拯救世界」（認真的）🦸",
    "沮喪的時候想想：你的存在讓多少家庭多了一份保障 😊",
    "今天的你已經很棒了，明天的你會更棒，後天更更棒！📈",
]

CHEER_KEYWORDS = ["加油", "好累", "沮喪", "挫折", "好難", "放棄", "不想做", "撐不住", "好煩", "壓力", "好廢", "廢廢", "煩死", "累死", "好想放棄", "失敗", "沒成功", "完蛋了", "沒信心"]

# 團隊成員名單
TEAM_MEMBERS = ["Rita", "一珊", "力緯", "致齊", "瑋娟", "彥汝"]

# 記錄最近日期 & 各日期已回報成員（記憶體暫存）
latest_date = {}       # {group_id: "2026-06-05"}
reported = {}          # {group_id: {date_full: set(names)}}

def get_sheet_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
    else:
        with open("google-credentials.json") as f:
            creds_dict = json.load(f)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def get_or_create_worksheet(gc, month_str):
    """取得或建立月份分頁，例如 '2026-06'"""
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        try:
            ws = sh.worksheet(month_str)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=month_str, rows=1000, cols=10)
            ws.append_row(["日期", "業務員", "時間", "類型"])
        return ws
    except Exception as e:
        print(f"Sheets error: {e}")
        return None

def parse_time_slots(content, date_full, name):
    """解析 '1300需 1830關' 這種格式，回傳 rows"""
    rows = []
    slots = re.findall(r"(\d{1,2}:?\d{2})\s*([關需建簽服])", content)
    for time_raw, visit_type in slots:
        time_clean = time_raw.replace(":", "")
        if len(time_clean) == 3:
            time_clean = "0" + time_clean
        time_fmt = time_clean[:2] + ":" + time_clean[2:]
        rows.append([date_full, name, time_fmt, visit_type])
    return rows

def roc_to_ad(roc_date_str):
    """民國日期轉西元，支援 1150605（7位）或 150605（6位）"""
    s = roc_date_str.strip()
    # 7位：1150605
    m = re.match(r"^(1\d{2})(\d{2})(\d{2})$", s)
    if m:
        year_roc = int(m.group(1))
        month = m.group(2)
        day = m.group(3)
    else:
        # 6位：150605（補1變成115）
        m = re.match(r"^(\d{2})(\d{2})(\d{2})$", s)
        if not m:
            return None, None
        year_roc = int("1" + m.group(1))
        month = m.group(2)
        day = m.group(3)
    year_ad = 1911 + year_roc
    return f"{year_ad}-{month}-{day}", f"{month}/{day}"

def write_activities_to_sheet(date_full, name, rows):
    """覆蓋寫入：先刪除同日期同人的舊資料，再寫入新資料"""
    try:
        print(f"[Sheets] 寫入 {date_full} {name} 共{len(rows)}筆")
        gc = get_sheet_client()
        year_month = date_full[:7]  # "2026-06"
        ws = get_or_create_worksheet(gc, year_month)
        if not ws:
            print(f"[Sheets] 無法取得工作表 {year_month}")
            return False

        # 讀取所有資料，找出要刪除的列（從後往前刪）
        all_values = ws.get_all_values()
        rows_to_delete = []
        for i, row in enumerate(all_values):
            if i == 0:
                continue
            if len(row) >= 2 and row[0] == date_full and row[1] == name:
                rows_to_delete.append(i + 1)

        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        # 寫入新資料（若無拜訪，寫入一筆休息記錄）
        if rows:
            for row in rows:
                ws.append_row(row)
        else:
            ws.append_row([date_full, name, "-", "休"])
        print(f"[Sheets] ✅ 寫入成功")
        return True
    except Exception as e:
        print(f"[Sheets] ❌ 寫入失敗: {e}")
        return False

def parse_template_report(text):
    """
    解析值日生發的完整模板，例如：
    1150603
    Rita：1240服
    一珊：
    力緯：0
    回傳 (date_full, date_display, {name: rows_or_None})
    """
    lines = text.strip().split("\n")
    if not lines:
        return None, None, {}

    date_full, date_display = roc_to_ad(lines[0].strip())
    if not date_full:
        return None, None, {}

    result = {}
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.+?)[\s　]*[：:](.*)$", line)
        if not m:
            continue
        name = m.group(1).strip()
        content = m.group(2).strip()
        if name not in TEAM_MEMBERS:
            continue
        if content == "":
            result[name] = None  # 空白 = 尚未填寫
        elif content == "0":
            result[name] = []   # 0 = 今天休息，算已回報
        else:
            rows = parse_time_slots(content, date_full, name)
            result[name] = rows

    return date_full, date_display, result

def parse_single_reply(text, date_full):
    """
    解析單行接龍回報，例如：一珊：1300需 1830關
    回傳 (name, rows) 或 (None, None)
    """
    text = text.strip()
    m = re.match(r"^(.+?)[\s　]*[：:](.*)$", text)
    if not m:
        return None, None
    name = m.group(1).strip()
    content = m.group(2).strip()
    if name not in TEAM_MEMBERS:
        return None, None
    if content == "" or content == "0":
        return name, []
    rows = parse_time_slots(content, date_full, name)
    # 有內容但解析不出時間+類型 → 格式錯誤
    if not rows:
        return name, None  # None 代表格式錯誤
    return name, rows

def query_stats(name, start_date, end_date):
    """查詢某人在日期範圍內的統計"""
    try:
        gc = get_sheet_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheets = sh.worksheets()

        total = 0
        type_count = {}

        for ws in worksheets:
            if ws.title == "工作表1":
                continue
            records = ws.get_all_records()
            for row in records:
                row_name = str(row.get("業務員", "")).strip()
                row_date = str(row.get("日期", "")).strip()
                row_type = str(row.get("類型", "")).strip()

                if row_name != name:
                    continue
                try:
                    rd = datetime.strptime(row_date, "%Y-%m-%d").date()
                    if start_date <= rd <= end_date:
                        total += 1
                        type_count[row_type] = type_count.get(row_type, 0) + 1
                except:
                    continue

        return total, type_count
    except Exception as e:
        print(f"Query error: {e}")
        return None, None

def query_weekly_stats():
    """查詢本週所有人統計"""
    try:
        gc = get_sheet_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheets = sh.worksheets()

        tw_now = datetime.utcnow() + timedelta(hours=8)
        # 本週週日到週六
        weekday = tw_now.weekday()  # 0=週一
        start = (tw_now - timedelta(days=(weekday + 1) % 7)).date()
        end = tw_now.date()

        stats = {}  # {name: {type: count}}

        for ws in worksheets:
            if ws.title == "工作表1":
                continue
            records = ws.get_all_records()
            for row in records:
                name = str(row.get("業務員", "")).strip()
                row_date = str(row.get("日期", "")).strip()
                row_type = str(row.get("類型", "")).strip()
                if not name:
                    continue
                try:
                    rd = datetime.strptime(row_date, "%Y-%m-%d").date()
                    if start <= rd <= end:
                        if name not in stats:
                            stats[name] = {}
                        stats[name][row_type] = stats[name].get(row_type, 0) + 1
                except:
                    continue

        return stats, start, end
    except Exception as e:
        print(f"Weekly query error: {e}")
        return None, None, None

# ───────────────────────────────────────────────
# 📝 待辦事項功能
# ───────────────────────────────────────────────

def get_todo_worksheet():
    """取得或建立待辦事項分頁"""
    try:
        gc = get_sheet_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        try:
            ws = sh.worksheet(TODO_SHEET)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=TODO_SHEET, rows=2000, cols=6)
            ws.append_row(["姓名", "日期", "任務", "建立日期", "完成"])
        return ws
    except Exception as e:
        print(f"Todo sheet error: {e}")
        return None

def parse_todo_input(text):
    """
    解析待辦輸入格式（支援多天、分隔線、空行）：
    致齊

    6/8
    Call 陳亮羽
    —————
    6/5
    ✅開會

    回傳 (name, [(date_str, [(task, done), ...]), ...])
    """
    lines = [l.strip() for l in text.strip().split("\n")]

    # 第一個非空行是名字
    name = None
    start_idx = 0
    for i, line in enumerate(lines):
        if line:
            name = line
            start_idx = i + 1
            break

    if not name or name not in TEAM_MEMBERS:
        return None, []

    tw_now = datetime.utcnow() + timedelta(hours=8)
    year = tw_now.year

    # 剩下的行按日期分組
    date_blocks = []  # [(date_str, [(task, done)])]
    current_date = None
    current_tasks = []

    for line in lines[start_idx:]:
        # 分隔線或空行 → 跳過
        if not line or re.match(r"^[—\-─=＝]+$", line):
            continue

        # 日期行
        date_match = re.match(r"^(\d{1,2})/(\d{1,2})$", line)
        if date_match:
            if current_date and current_tasks:
                date_blocks.append((current_date, current_tasks))
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            current_date = f"{year}-{month:02d}-{day:02d}"
            current_tasks = []
            continue

        # 任務行
        if current_date:
            if line.startswith("✅"):
                current_tasks.append((line[1:].strip(), True))
            else:
                current_tasks.append((line, False))

    if current_date and current_tasks:
        date_blocks.append((current_date, current_tasks))

    return name, date_blocks

def save_todos(name, date_str, tasks):
    """儲存待辦：先刪除同人同日期的舊資料，再寫入"""
    try:
        ws = get_todo_worksheet()
        if not ws:
            return False

        tw_now = datetime.utcnow() + timedelta(hours=8)
        created_date = tw_now.strftime("%Y-%m-%d")

        # 刪除同人同日期舊資料
        all_values = ws.get_all_values()
        to_delete = []
        for i, row in enumerate(all_values):
            if i == 0:
                continue
            if len(row) >= 2 and row[0] == name and row[1] == date_str:
                to_delete.append(i + 1)
        for idx in reversed(to_delete):
            ws.delete_rows(idx)

        # 寫入新資料
        for task, done in tasks:
            ws.append_row([name, date_str, task, created_date, "✅" if done else ""])
        print(f"[Todo] ✅ {name} {date_str} 共{len(tasks)}筆")
        return True
    except Exception as e:
        print(f"[Todo] ❌ {e}")
        return False

def get_overdue_todos():
    """取得超過3天未完成的待辦，回傳 {name: [task, ...]}"""
    try:
        ws = get_todo_worksheet()
        if not ws:
            return {}

        tw_now = datetime.utcnow() + timedelta(hours=8)
        today = tw_now.date()
        overdue = {}

        all_values = ws.get_all_values()
        for i, row in enumerate(all_values):
            if i == 0:
                continue
            if len(row) < 5:
                continue
            name, date_str, task, created_date, done = row[0], row[1], row[2], row[3], row[4]
            if done:
                continue
            try:
                created = datetime.strptime(created_date, "%Y-%m-%d").date()
                days = (today - created).days
                if days >= 3:
                    if name not in overdue:
                        overdue[name] = []
                    overdue[name].append(f"{task}（{days}天）")
            except:
                continue
        return overdue
    except Exception as e:
        print(f"[Todo overdue] ❌ {e}")
        return {}

GROUP_IDS = [
    "C036387647981e5c83e65884f9b9286b3",
    "Cdd2f9e9d113d33ed44251a4dd45d1ecd",
]

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")

configuration = Configuration(access_token=CHANNEL_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 拜訪類型說明
VISIT_TYPES = {
    "關": "關係建立（初次見面或久未見的朋友）",
    "需": "需求分析（了解準客戶的財務缺口）",
    "建": "提出建議書說明及締結簽約",
    "簽": "已說明建議書，以簽約為主",
    "服": "保戶服務",
}

# 關鍵字建議
KEYWORD_TIPS = {
    "猶豫": "💡 客戶猶豫時：\n1. 先同理「我理解您需要時間考慮」\n2. 問出真正顧慮「您最擔心的是哪個部分？」\n3. 用故事說明不行動的風險",
    "太貴": "💡 客戶覺得保費太貴時：\n1. 換算每天費用（每天不到一杯咖啡）\n2. 強調保障價值而非保費金額\n3. 詢問「您覺得這個保障對您值多少？」",
    "理賠流程": "💡 理賠問題處理：\n1. 立即表示協助意願\n2. 確認理賠文件清單\n3. 陪同或協助填寫申請\n4. 定期追蹤進度給客戶安心感",
    "約不到": "💡 約不到客戶時：\n1. 跟主管討論！（很重要）\n2. 打電話約訪成功率最高\n3. 打電話時機最好依照客戶的工作性質來打，盡量不要在他最忙的時候打給他",
    "拒絕": "💡 被拒絕後：\n1. 不要立刻放棄，問「方便告訴我是哪個部分不符合您的需求嗎？」\n2. 拒絕通常是時機不對，保持關係\n3. 3個月後再follow up",
    "建議書說明": "💡 建議書說明技巧：\n1. 先確認客戶時間充裕\n2. 從客戶需求出發，不是從產品出發\n3. 用問句引導「您覺得這個保障夠嗎？」\n4. 結尾問「您還有什麼問題嗎？」",
    "轉介紹": "💡 開口要求轉介紹：\n1. 服務完成後是最佳時機\n2. 說「您身邊有沒有跟您一樣重視家人的朋友？」\n3. 不要要求，而是分享價值\n4. 讓客戶知道你會好好照顧他的朋友",
    "成交": "💡 締結技巧：\n1. 觀察客戶點頭、詢問細節等買單訊號\n2. 用二擇一法「您希望月繳還是年繳？」\n3. 不要等客戶說要買，主動引導\n4. 成交後立刻確認下一步流程",
    "沉默": "💡 客戶不回訊息時：\n1. 換個話題再聯絡，不要一直催\n2. 傳有價值的資訊（新聞、節日問候）\n3. 等1-2週再跟進\n4. 跟主管討論是否換接觸方式",
    "競爭": "💡 客戶說別家比較便宜：\n1. 不要批評競爭對手\n2. 強調自己的服務差異「我能提供的是...\"\n3. 比較保障內容而非保費\n4. 強調長期售後服務的價值",
    "家人反對": "💡 家人反對時：\n1. 先了解反對的真正原因\n2. 邀請家人一起來聽說明\n3. 從家人最在意的角度切入\n4. 跟主管討論應對策略",
    "已有保險": "💡 客戶說已經買夠了：\n1. 先肯定「您有保險觀念很好！」\n2. 請客戶拿出保單一起檢視缺口\n3. 用需求分析找出不足的地方\n4. 定期健診是很好的切入點",
    "核保": "💡 客戶擔心被拒保：\n1. 先了解客戶的健康狀況\n2. 說明核保不等於拒保，有很多方式\n3. 鼓勵誠實告知，隱瞞反而有風險\n4. 跟主管討論最適合的商品",
    "退保": "💡 客戶想解約：\n1. 先了解退保原因，不要急著勸阻\n2. 說明退保的損失（解約金、保障中斷）\n3. 看是否有其他解決方式（減額繳清、保單借款）\n4. 立刻跟主管討論應對策略",
    "陌生開發": "💡 陌生開發技巧：\n1. 先建立關係，不要急著談保險\n2. 找共同話題，讓對方對你產生信任\n3. 用提問了解對方的生活和需求\n4. 第一次見面的目標是約到第二次見面",
    "call call": "💡 Call call 提醒：\n1. 請先列好今天要打的客戶名單！\n2. 沒有名單就不會有約訪\n3. 每通電話前先想好目的和開場白\n4. 打完記得記錄結果",
    "Call call": "💡 Call call 提醒：\n1. 請先列好今天要打的客戶名單！\n2. 沒有名單就不會有約訪\n3. 每通電話前先想好目的和開場白\n4. 打完記得記錄結果",
    "簡報": "💡 簡報提醒：\n切記 起／承／轉／合 要素！\n\n因為....所以....我的建議是\n＋ 法源或故事及佐證\n＋ 總結 FAB（特色／優點／利益）",
}

def parse_visit_report(text):
    """解析拜訪預報格式"""
    lines = text.strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        if not line or re.match(r"^\d{7}$", line):
            continue
        # 格式：姓名：時間類型
        match = re.match(r"^(.+?)：(.*)$", line)
        if match:
            name = match.group(1).strip()
            content = match.group(2).strip()
            if content == "0" or content == "":
                results.append(f"  {name}：休息")
            else:
                results.append(f"  {name}：{content}")
    return results

@app.route("/callback", methods=["GET", "POST"])
def callback():
    if request.method == "GET":
        return "OK", 200
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "OK", 200
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    reply = None

    # 查詢指令
    if text == "群組ID" or text == "群组ID":
        source = event.source
        if hasattr(source, 'group_id'):
            reply = f"群組ID：{source.group_id}"
        else:
            reply = f"這是私訊，沒有群組ID\n你的用戶ID：{source.user_id}"

    # 個人查詢：查詢：Rita 0605-0615
    elif re.match(r"^查詢[：:](.+?)\s+(\d{4})-(\d{4})$", text):
        m = re.match(r"^查詢[：:](.+?)\s+(\d{4})-(\d{4})$", text)
        name = m.group(1).strip()
        tw_now = datetime.utcnow() + timedelta(hours=8)
        year = tw_now.year
        try:
            start = datetime.strptime(f"{year}{m.group(2)}", "%Y%m%d").date()
            end = datetime.strptime(f"{year}{m.group(3)}", "%Y%m%d").date()
            total, type_count = query_stats(name, start, end)
            if total is None:
                reply = "❌ 查詢失敗，請稍後再試"
            elif total == 0:
                reply = f"📊 {name} {m.group(2)}-{m.group(3)}\n查無資料"
            else:
                detail = " ".join([f"{t}{c}次" for t, c in sorted(type_count.items())])
                reply = f"📊 {name} {m.group(2)}－{m.group(3)}\n總拜訪：{total}次\n  {detail}"
        except:
            reply = "❌ 日期格式錯誤，請輸入如：查詢：Rita 0605-0615"

    elif text == "本週統計" or text == "週報":
        stats, start, end = query_weekly_stats()
        if not stats:
            reply = "❌ 查詢失敗，請稍後再試"
        elif not stats:
            reply = "本週尚無活動量記錄"
        else:
            lines = [f"📊 本週活動量 {start.strftime('%m/%d')}－{end.strftime('%m/%d')}\n"]
            for name, tc in stats.items():
                total = sum(tc.values())
                detail = " ".join([f"{t}{c}" for t, c in sorted(tc.items())])
                lines.append(f"{name}：{total}次（{detail}）")
            reply = "\n".join(lines)

    elif text == "今天進度" or text == "全隊進度":
        reply = "📊 請輸入「本週統計」查看全隊活動量！"

    elif text == "我的待辦" or text == "待辦事項":
        reply = "📝 功能開發中，敬請期待！\n（未來可查看個人未完成待辦）"

    # 待辦事項輸入（第一行是成員名字）
    elif text.split("\n")[0].strip() in TEAM_MEMBERS and "\n" in text:
        name, date_blocks = parse_todo_input(text)
        if name and date_blocks:
            for date_str, tasks in date_blocks:
                save_todos(name, date_str, tasks)
            # 靜默，不回覆

    # 生日分析（格式：生日：1985/03/15 或 生日分析 1985-03-15）
    elif re.search(r"生日[：:分析\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{8})", text):
        m = re.search(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{8})", text)
        result = analyze_birthday(m.group(1)) if m else None
        reply = result if result else "❌ 格式錯誤，請輸入「生日：1985/03/15」"

    elif re.match(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$", text):
        # 直接輸入生日日期也可以
        result = analyze_birthday(text)
        reply = result if result else "❌ 日期格式有誤，請輸入如 1985/03/15"

    elif text == "說明" or text == "help" or text == "Help":
        reply = (
            "🤖 瑞塔小幫手功能說明\n\n"
            "📋 活動預報（自動記錄到試算表）\n"
            "  值日生發模板，大家接龍補上\n"
            "  Rita：1300需 1800關\n"
            "  沒有拜訪填 0，空白代表未填\n"
            "  全員填完會通知✅\n\n"
            "🔍 活動量查詢\n"
            "  查詢：Rita 0601-0615\n"
            "  本週統計（每週日自動推播）\n\n"
            "🔮 客戶生日分析\n"
            "  輸入「生日：1985/03/15」\n"
            "  自動分析星座＋生命靈數\n"
            "  給出業務攻略和送禮建議\n\n"
            "💡 業務關鍵字\n"
            "  輸入以下詞自動跳出建議：\n"
            "  猶豫／太貴／約不到／拒絕\n"
            "  成交／轉介紹／沉默／競爭\n"
            "  家人反對／已有保險／核保\n"
            "  退保／陌生開發／建議書說明\n"
            "  理賠流程／call call／簡報\n\n"
            "💪 遇到低潮？\n"
            "  輸入「好累」「沮喪」「挫折」等\n"
            "  小幫手送你一句鼓勵 🌟\n\n"
            "⏰ 自動提醒\n"
            "  每天 09:00 提醒值日生發模板\n"
            "  每天 17:00 提醒預報活動量\n"
            "  每晚 20:00 點名未回報成員\n"
            "  每月 25號 提醒回報 FYC 目標\n\n"
            "📌 拜訪類型代碼\n"
            "  關｜需｜建｜簽｜服"
        )

    else:
        # 鼓勵關鍵字
        for keyword in CHEER_KEYWORDS:
            if keyword in text:
                reply = random.choice(CHEER_MESSAGES)
                break

        # 業務關鍵字偵測
        if not reply:
            for keyword, tip in KEYWORD_TIPS.items():
                if keyword in text:
                    reply = tip
                    break

        # 活動預報處理
        if not reply:
            # 取得群組ID（私訊也支援）
            source = event.source
            gid = getattr(source, 'group_id', getattr(source, 'user_id', 'private'))

            first_line = text.split("\n")[0].strip()

            # 情況一：值日生發完整模板（第一行是民國日期）
            if re.match(r"^1?\d{6}$", first_line) and "\n" in text:
                # 支援兩天一起PO：用日期行分割成多個區塊
                blocks = re.split(r"(?=^1?\d{6}$)", text, flags=re.MULTILINE)
                blocks = [b.strip() for b in blocks if b.strip() and re.match(r"^1?\d{6}", b.split("\n")[0].strip())]

                completed_dates = []
                all_dates = []

                for block in blocks:
                    date_full, date_display, member_data = parse_template_report(block)
                    if not date_full:
                        continue
                    all_dates.append(date_display)
                    latest_date[gid] = date_full
                    if gid not in reported:
                        reported[gid] = {}
                    if date_full not in reported[gid]:
                        reported[gid][date_full] = set()
                    for name, rows in member_data.items():
                        if rows is not None:
                            write_activities_to_sheet(date_full, name, rows)
                            reported[gid][date_full].add(name)
                    if set(TEAM_MEMBERS) == reported[gid][date_full]:
                        completed_dates.append(date_display)

                pass  # 靜默，不通知

            # 情況二：單行接龍（名字：內容）
            elif re.match(r"^.+?[：:]", text) and "\n" not in text:
                current_date = latest_date.get(gid)
                if current_date:
                    name, rows = parse_single_reply(text, current_date)
                    if name and rows is None:
                        # 有內容但格式錯誤
                        reply = (
                            "❌ 格式有誤，請重新輸入\n\n"
                            "正確格式：\n"
                            "姓名：時間+類型\n"
                            "例如：\n"
                            "  一珊：1300需 1830關\n"
                            "  力緯：0（沒有拜訪）"
                        )
                    elif name is not None:
                        # 寫入
                        write_activities_to_sheet(current_date, name, rows if rows else [])
                        if gid not in reported:
                            reported[gid] = {}
                        if current_date not in reported[gid]:
                            reported[gid][current_date] = set()
                        reported[gid][current_date].add(name)

                        pass  # 靜默，不通知

    if reply:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )

ACTIVITY_GROUP_ID = "C036387647981e5c83e65884f9b9286b3"
TODO_GROUP_ID = "Cdd2f9e9d113d33ed44251a4dd45d1ecd"

def send_push(group_id, message):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            PushMessageRequest(
                to=group_id,
                messages=[TextMessage(text=message)]
            )
        )

def scheduler():
    while True:
        now = datetime.utcnow()
        # 台灣時間 = UTC+8
        tw_hour = (now.hour + 8) % 24
        tw_minute = now.minute
        tw_weekday = now.weekday()  # 0=週一, 6=週日

        # 每月25號早上9點推播（UTC 1點）
        if now.day == 25 and now.hour == 1 and tw_minute == 0:
            for gid in GROUP_IDS:
                send_push(gid, "月底囉！\n請列好名單，並回報月目標 FYC 🎯")

        # 週日到週四(weekday 0-3, 6) 早上9:00 提醒值日生發模板
        if tw_hour == 9 and tw_minute == 0 and tw_weekday in [0, 1, 2, 3, 6]:
            send_push(ACTIVITY_GROUP_ID, "📋 值日生請發明後兩天活動預報模板！")

        # 週日到週四(weekday 0-3, 6) 傍晚17:00 提醒預報
        if tw_hour == 17 and tw_minute == 0 and tw_weekday in [0, 1, 2, 3, 6]:
            send_push(ACTIVITY_GROUP_ID, "請值日生預報明天和後天活動量 gogogo 💪")
            # 待辦提醒＋未完成點名
            todo_msg = "請靜下心來預報明天的待辦事項 gogogo 🙏"
            overdue = get_overdue_todos()
            if overdue:
                todo_msg += "\n\n⏰ 未完成提醒："
                for name, items in overdue.items():
                    todo_msg += f"\n{name}：" + "／".join(items)
            send_push(TODO_GROUP_ID, todo_msg)

        # 週日到週四 晚上20:00 缺報點名（查試算表）
        if tw_hour == 20 and tw_minute == 0 and tw_weekday in [0, 1, 2, 3, 6]:
            try:
                tw_now_dt = now + timedelta(hours=8)
                today = tw_now_dt.strftime("%Y-%m-%d")
                year_month = today[:7]
                gc = get_sheet_client()
                sh = gc.open_by_key(SPREADSHEET_ID)
                try:
                    ws = sh.worksheet(year_month)
                    all_values = ws.get_all_values()
                    reported_today = set()
                    for row in all_values[1:]:
                        if len(row) >= 2 and row[0] == today:
                            reported_today.add(row[1])
                except:
                    reported_today = set()
                missing = [m for m in TEAM_MEMBERS if m not in reported_today]
                if missing:
                    names = "、".join(missing)
                    send_push(ACTIVITY_GROUP_ID, f"⏰ 提醒：{names} 還沒回報今天活動量喔！")
            except Exception as e:
                print(f"[缺報點名] ❌ {e}")

        # 每週日早上9點推播週報（UTC 1點）
        if tw_weekday == 6 and tw_hour == 9 and tw_minute == 0:
            stats, start, end = query_weekly_stats()
            if stats:
                lines = [f"📊 本週活動量統計 {start.strftime('%m/%d')}－{end.strftime('%m/%d')}\n"]
                mvp_name = None
                mvp_count = 0
                for name, tc in stats.items():
                    total = sum(tc.values())
                    detail = " ".join([f"{t}{c}" for t, c in sorted(tc.items())])
                    lines.append(f"{name}：{total}次（{detail}）")
                    if total > mvp_count:
                        mvp_count = total
                        mvp_name = name
                if mvp_name:
                    lines.append(f"\n🏆 本週MVP：{mvp_name}！繼續衝 ⭐️")
                msg = "\n".join(lines)
                send_push(ACTIVITY_GROUP_ID, msg)

        threading.Event().wait(60)

reminder_thread = threading.Thread(target=scheduler, daemon=True)
reminder_thread.start()

if __name__ == "__main__":
    app.run(port=8080)
