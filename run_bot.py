import os
import subprocess
import sys

# 先殺掉所有 ngrok process
subprocess.run(["pkill", "-f", "ngrok"], capture_output=True)

from pyngrok import ngrok, conf

token = os.environ.get("NGROK_AUTHTOKEN", "3ElYZrxq5ijSpzHrjQPNuAsskXW_47jKcEYxyUs18d6hPu4kd")
conf.get_default().auth_token = token

url = ngrok.connect(5000)
print(f"\n✅ Bot 網址：{url.public_url}/callback\n")
print("請把這個網址填到 LINE Developers Console 的 Webhook URL\n")

# 啟動 Flask
os.system("python3 /Users/ritalu/rita-bot/app.py")
