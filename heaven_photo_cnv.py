from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
import base64
import os
import re
import csv
import time

#pip install langchain-ollama
llm = ChatOllama(
    # model="gemma4:31b",
    # model="gemma4:e4b",
    # model="nemotron3:33b",
    model="qwen3-vl:32b",
    # model="granite4.1:30b", error
    # model="llama3.2:3b", error
    # model="mistral-medium-3.5:128b",
    # model="qwen2.5vl:72b", error
    # model="huihui_ai/gemma-4-abliterated:48b",
    # model="huihui_ai/gpt-oss-abliterated:120b",
    # model="hf.co/huihui-ai/Huihui-DeepSeek-V4-Flash-abliterated-ds4-GGUF:IQ2_XXS",
    base_url="http://100.106.118.73:11434",
    temperature=0.0,
    top_p=0.9,        # 確率上位90%のトークンのみ使用
    top_k=40,         # 上位40トークンのみ候補にする
    repeat_penalty=1.1,  # 同じ内容の繰り返しを抑制
    seed=42,          # 同じ入力なら毎回同じ出力
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

必ずCSV1行のみ返してください。"""

def image_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def extract_id(filename):
    m = re.match(r"img_(\d+)\.jpg", filename)
    return m.group(1) if m else None

results = []

files = sorted([f for f in os.listdir(IMAGE_DIR) if re.match(r"img_\d+\.jpg", f)])

start_total = time.time()
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
                "image_url": f"data:image/jpeg;base64,{img_b64}"
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
    results.append(line)

with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
    for row in results:
        f.write(row + "\n")

total = time.time() - start_total
avg = total / len(results) if results else 0
print(f"\n完了: {len(results)}件 / 合計{total:.1f}秒 / 平均{avg:.1f}秒/枚")