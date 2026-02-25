from ollama import Client  # 直接 ollama ではなく Client を使う

client = Client(host='http://172.20.240.1:11434', timeout=600)# 1. 外部サーバーのアドレスを指定してクライアントを初期化
# response = client.list()
# print(response)

# client = Client(host='http://192.168.0.112:11434', timeout=600)

# 2. 会話履歴を保存するリスト
chat_history = [
    {"role": "system", "content": "あなたは親切なアシスタントです。"}
]

print("AI: Gemini 3 (External Ollama) へようこそ！('exit'で終了)")

while True:
    # 3. ユーザーの入力を取得
    user_input = input("\nあなた: ")

    if user_input.lower() == "exit":
        break

    # 4. ユーザーの発言を履歴に追加
    chat_history.append({"role": "user", "content": user_input})

    # 5. 履歴の制限（システムプロンプト1件 + 直近10件）
    if len(chat_history) > 11:
        # [0]番目のシステム指示と、後ろから10件を合体
        chat_history = [chat_history[0]] + chat_history[-10:]

    try:
        # 6. 指定したサーバー(client)に履歴を投げる
        response = client.chat(
            model='gemma3:12b',
            messages=chat_history,
            options={
                "temperature": 0.0,
                "seed": 42, # 任意の整数でOK
                "num_ctx": 32768
            }
        )

        # 7. 回答の抽出と表示
        answer = response['message']['content']
        print(f"AI: {answer}")

        # 8. AIの回答も履歴に追加
        chat_history.append({"role": "assistant", "content": answer})

    except Exception as e:
        print(f"エラーが発生しました。サーバーが起動しているか確認してください: {e}")