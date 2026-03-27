from ollama import Client  # 直接 ollama ではなく Client を使う
from prompts_sumo_auto import SYSTEM_PROMPT # SYSTEM_PROMPT
import httpx
import time
import streamlit as st

st.set_page_config(page_title="Demo App", page_icon="📊", layout="wide")

st.title("📊 Streamlit Demo App")
st.markdown("Streamlit Community Cloudのデプロイサンプルです。")

start = time.time()

# 1. 外部サーバーのアドレスを指定してクライアントを初期化
# client = Client(host='http://172.20.240.1:11434', timeout=httpx.Timeout(None))

# Mac book
# client = Client(host='http://192.168.0.112:11434', timeout=httpx.Timeout(None))

# Mac mini
# client = Client(host='http://192.168.0.118:11434', timeout=httpx.Timeout(None))

# TTDC
client = Client(host='http://100.67.72.27:11434', timeout=httpx.Timeout(None))

# 2. 会話履歴を保存するリスト
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

filename = "temp.txt"

with open(filename, "r", encoding="utf-8") as f:
    content = f.read()

# print(content)

# 4. ユーザーの発言を履歴に追加
chat_history.append({"role": "user", "content": content})

# 5. 履歴の制限（システムプロンプト1件 + 直近10件）
try:
    # 6. 指定したサーバー(client)に履歴を投げる
    response = client.chat(
#        model='gpt-oss:20b',
        # model='gemma3:27b',
        model='qwen2.5:72b',
        messages=chat_history,
        options={
            "temperature": 0.0,
            "seed": 42, # 任意の整数でOK
            "num_ctx": 8192
        }
    )

    # 7. 回答の抽出と表示
    answer = response['message']['content']
    st.write(answer)
    print(answer)
    elapsed = time.time() - start
    st.subheader(f"実行時間: {elapsed:.2f}秒")
    # print(f"実行時間: {elapsed:.2f}秒")

except Exception as e:
    print(f"エラーが発生しました。サーバーが起動しているか確認してください: {e}")


# curl http://100.67.72.27:11434/api/generate -d '{
#   "model": "qwen2.5:14b",
#   "prompt": "富士山の高さは？",
#   "stream": false
# }'