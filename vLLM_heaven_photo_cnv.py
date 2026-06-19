from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import base64
import os
import re
import time

llm = ChatOpenAI(
    # model="Qwen/Qwen3-VL-30B-A3B-Instruct",   # OpenWebUI で選んでいる名前と完全一致させる
    # model="edwixx/diffusiongemma-26B-A4B-it-HERETIC-Uncensored",   # OpenWebUI で選んでいる名前と完全一致させる
    model="google/diffusiongemma-26B-A4B-it",   # OpenWebUI で選んでいる名前と完全一致させる
    base_url="http://100.106.118.73:8002/v1",  # ← 要確認（元の 00.106... は桁抜けの可能性）/v1 まで含める
    api_key="dummy",                           # vLLM 側で --api-key 未設定なら任意の文字列でOK
    temperature=0.0,
    top_p=0.9,
    seed=42,
    max_tokens=512,
    extra_body={                # vLLM 固有のサンプリングパラメータはここに入れる
        "top_k": 40,
        "repetition_penalty": 1.1,   # Ollama の repeat_penalty 相当
    },
)

IMAGE_DIR = "./images"
OUTPUT_CSV = "output.csv"

system_prompt = """あなたは画像分析の専門家です。
女性の画像を見て、以下の形式でCSVの1行を出力してください。
他の文章は一切出力せず、CSV行のみ出力してください。

形式:
mem_id,xxxxx,show,はい,face,かわいい,style,モデル,score,90

各カラムの説明:
- xxxxx: ファイル名から渡されるID（そのまま使用）
- mem_id: xxxxxのIDをmem_idとして先頭に出力してください。例: mem_id,00001
- show: 顔出しの有無。「はい」または「いいえ」
- face: 顔立ちの系統。例: かわいい、きれい、クール、ギャル、清楚、童顔、大人っぽい など
- style: スタイルの系統。例: モデル、グラビア、スレンダー、ぽっちゃり、普通 など
- score: 100点満点の点数

face と style は複数指定可能です。その場合:
xxxxx,show,はい,face,かわいい,face,清楚,style,モデル,style,スレンダー,score,85

必ずCSV1行のみ返してください。
各カラムは値が無い場合以外を除いて省略しない。
他の文章・コードブロック・改行を含めず、CSV1行のみを出力
"""


def image_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_id(filename):
    m = re.match(r"img_(\d+)\.jpg", filename)
    return m.group(1) if m else None


files = sorted([f for f in os.listdir(IMAGE_DIR) if re.match(r"img_\d+\.jpg", f)])

start_total = time.time()
count = 0

with open(OUTPUT_CSV, "a", encoding="utf-8", buffering=1) as f:
    for i, filename in enumerate(files, 1):
        img_id = extract_id(filename)
        if not img_id:
            continue

        start = time.time()
        print(f"[{i}/{len(files)}] 処理中: {filename}", end="", flush=True)

        img_b64 = image_to_base64(os.path.join(IMAGE_DIR, filename))

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                },
                {
                    "type": "text",
                    "text": f"IDは {img_id} です。このIDをそのまま先頭に使って分析結果をCSV1行で出力してください。"
                }
            ])
        ]

        response = llm.invoke(messages)
        elapsed = time.time() - start
        line = response.content.strip()
        print(f" ({elapsed:.1f}秒) → {line}")

        f.write(line + "\n")
        f.flush()
        count += 1

total = time.time() - start_total
avg = total / count if count else 0
print(f"\n完了: {count}件 / 合計{total:.1f}秒 / 平均{avg:.1f}秒/枚")