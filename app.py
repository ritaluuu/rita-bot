import os
import re
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

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
    if text == "今天進度" or text == "全隊進度":
        reply = "📊 功能開發中，敬請期待！\n（未來可查看全隊今日拜訪狀況）"

    elif text == "我的待辦" or text == "待辦事項":
        reply = "📝 功能開發中，敬請期待！\n（未來可查看個人未完成待辦）"

    elif text == "說明" or text == "help" or text == "Help":
        reply = (
            "🤖 瑞塔小幫手使用說明\n\n"
            "📌 拜訪類型代碼：\n"
            "  關｜關係建立\n"
            "  需｜需求分析\n"
            "  建｜提出建議書\n"
            "  簽｜簽約\n"
            "  服｜保戶服務\n\n"
            "📌 可輸入的指令：\n"
            "  「今天進度」→ 查看全隊狀況\n"
            "  「我的待辦」→ 查看個人待辦\n"
            "  「說明」→ 顯示此說明\n\n"
            "📌 在待辦事項中輸入關鍵字\n"
            "  會自動跳出業務建議！"
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

if __name__ == "__main__":
    app.run(port=8080)
