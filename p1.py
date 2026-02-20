from ollama import Client  # 直接 ollama ではなく Client を使う
from prompts import SYSTEM_PROMPT # SYSTEM_PROMPT


# 1. 外部サーバーのアドレスを指定してクライアントを初期化
client = Client(host='http://192.168.0.110:11434')

# 2. 会話履歴を保存するリスト
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

filename = "text0.txt"

with open(filename, "r", encoding="utf-8") as f:
    content = f.read()

print(content)

# 4. ユーザーの発言を履歴に追加
chat_history.append({"role": "user", "content": content})

# 5. 履歴の制限（システムプロンプト1件 + 直近10件）
try:
    # 6. 指定したサーバー(client)に履歴を投げる
    response = client.chat(
#        model='gpt-oss:20b',
        model='gemma3:12b',
        messages=chat_history,
        options={
            "temperature": 0.0,
            "seed": 42 # 任意の整数でOK
        }
    )

    # 7. 回答の抽出と表示
    answer = response['message']['content']
    print(f"AI: {answer}")

except Exception as e:
    print(f"エラーが発生しました。サーバーが起動しているか確認してください: {e}")