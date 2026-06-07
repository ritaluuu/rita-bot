import os
import re
import threading
from datetime import datetime
from flask import Flask, request, abort
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
    "保費": "💡 保費說明技巧：\n1. 先說保障內容再說保費\n2. 與日常開銷比較\n3. 強調長期累積的價值",
    "理賠": "💡 理賠問題處理：\n1. 立即表示協助意願\n2. 確認理賠文件清單\n3. 陪同或協助填寫申請\n4. 定期追蹤進度給客戶安心感",
    "約不到": "💡 約不到客戶時：\n1. 跟主管討論！（很重要）\n2. 打電話約訪成功率最高\n3. 打電話時機最好依照客戶的工作性質來打，盡量不要在他最忙的時候打給他",
    "拒絕": "💡 被拒絕後：\n1. 不要立刻放棄，問「方便告訴我是哪個部分不符合您的需求嗎？」\n2. 拒絕通常是時機不對，保持關係\n3. 3個月後再follow up",
    "建議書": "💡 建議書說明技巧：\n1. 先確認客戶時間充裕\n2. 從客戶需求出發，不是從產品出發\n3. 用問句引導「您覺得這個保障夠嗎？」\n4. 結尾問「您還有什麼問題嗎？」",
    "轉介紹": "💡 開口要求轉介紹：\n1. 服務完成後是最佳時機\n2. 說「您身邊有沒有跟您一樣重視家人的朋友？」\n3. 不要要求，而是分享價值\n4. 讓客戶知道你會好好照顧他的朋友",
    "成交": "💡 締結技巧：\n1. 觀察客戶點頭、詢問細節等買單訊號\n2. 用二擇一法「您希望月繳還是年繳？」\n3. 不要等客戶說要買，主動引導\n4. 成交後立刻確認下一步流程",
    "沉默": "💡 客戶不回訊息時：\n1. 換個話題再聯絡，不要一直催\n2. 傳有價值的資訊（新聞、節日問候）\n3. 等1-2週再跟進\n4. 跟主管討論是否換接觸方式",
    "競爭": "💡 客戶說別家比較便宜：\n1. 不要批評競爭對手\n2. 強調自己的服務差異「我能提供的是...\"\n3. 比較保障內容而非保費\n4. 強調長期售後服務的價值",
    "家人反對": "💡 家人反對時：\n1. 先了解反對的真正原因\n2. 邀請家人一起來聽說明\n3. 從家人最在意的角度切入\n4. 跟主管討論應對策略",
    "等等": "💡 客戶一直拖延時：\n1. 問「您還有什麼疑慮嗎？」找出真正原因\n2. 說明拖延的風險（健康、費率可能改變）\n3. 設定一個具體的下次跟進時間\n4. 跟主管討論！",
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

    elif text == "今天進度" or text == "全隊進度":
        reply = "📊 功能開發中，敬請期待！\n（未來可查看全隊今日拜訪狀況）"

    elif text == "我的待辦" or text == "待辦事項":
        reply = "📝 功能開發中，敬請期待！\n（未來可查看個人未完成待辦）"

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
            "🤖 瑞塔小幫手使用說明\n\n"
            "📌 拜訪類型代碼：\n"
            "  關｜關係建立（初次見面或久未見的朋友）\n"
            "  需｜需求分析（了解準客戶的財務缺口）\n"
            "  建｜提出建議書說明及締結簽約\n"
            "  簽｜已說明建議書，以簽約為主\n"
            "  服｜保戶服務\n\n"
            "📌 業務關鍵字（輸入以下任一字會跳出建議）：\n"
            "  猶豫、太貴、保費、理賠\n"
            "  約不到、拒絕、建議書、簡報\n"
            "  轉介紹、成交、沉默、競爭\n"
            "  家人反對、等等、已有保險\n"
            "  核保、退保、陌生開發\n"
            "  Call call\n\n"
            "📌 自動提醒時間：\n"
            "  每天17:00 提醒預報活動量及待辦事項\n"
            "  每月25號提醒回報月目標 FYC\n\n"
            "📌 怎麼使用：\n"
            "  1️⃣ 在聊天室輸入關鍵字\n"
            "     例如：「約不到」「猶豫」「理賠」\n"
            "     小幫手會立刻跳出業務建議！\n\n"
            "  2️⃣ 每天17:00 小幫手會提醒預報\n"
            "     依照格式回報：\n"
            "     Rita：1300需 1800關\n\n"
            "  3️⃣ 每月25號小幫手提醒回報 FYC\n\n"
            "📌 客戶生日分析：\n"
            "  輸入「生日：1985/03/15」\n"
            "  小幫手自動計算星座＋生命靈數\n"
            "  給你專屬的業務攻略和送禮建議 🎁\n\n"
            "📌 其他指令：\n"
            "  「說明」→ 顯示此說明"
        )

    else:
        # 關鍵字偵測
        for keyword, tip in KEYWORD_TIPS.items():
            if keyword in text:
                reply = tip
                break

        # 如果是拜訪預報格式
        if not reply and ("：" in text or ":" in text):
            lines = text.split("\n")
            if len(lines) >= 2:
                parsed = parse_visit_report(text)
                if parsed:
                    reply = "✅ 收到拜訪預報！\n\n" + "\n".join(parsed)

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

        # 週日到週四(weekday 0-3, 6) 傍晚17:00 台灣時間
        if tw_hour == 17 and tw_minute == 0 and tw_weekday in [0, 1, 2, 3, 6]:
            send_push(ACTIVITY_GROUP_ID, "請值日生預報明天和後天活動量 gogogo 💪")
            send_push(TODO_GROUP_ID, "請靜下心來預報明天的待辦事項 gogogo 🙏")

        threading.Event().wait(60)

reminder_thread = threading.Thread(target=scheduler, daemon=True)
reminder_thread.start()

if __name__ == "__main__":
    app.run(port=8080)
