from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
import base64
import os
import re
import csv
import time

IMAGE_DIR = "./images"
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODELS = [
    "gemma4:31b",
    "gemma4:e4b",
    "nemotron3:33b",
    "qwen3-vl:32b",
    "mistral-medium-3.5:128b",
    "qwen2.5vl:72b",
    "huihui_ai/gemma-4-abliterated:48b",
    "huihui_ai/gpt-oss-abliterated:120b",
    "hf.co/huihui-ai/Huihui-gemma-4-31B-it-qat-q4_0-unquantized-abliterated-GGUF:BF16",
    "hf.co/huihui-ai/Huihui-DeepSeek-V4-Flash-abliterated-ds4-GGUF:IQ2_XXS",
    "hf.co/mmnga-o/llm-jp-4-32b-a3b-thinking-gguf:Q4_K_M",
    "huihui_ai/Qwen3.6-abliterated:35b-Claude-4.7",
    "huihui_ai/glm-4.7-flash-abliterated:latest",
]

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

def make_messages(img_b64, img_id):
    return [
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

def run_model(model_name, files):
    """1モデルで全ファイルを処理。成功数を返す。"""
    print(f"\n{'='*60}")
    print(f"モデル: {model_name}")
    print(f"{'='*60}")

    try:
        llm = ChatOllama(
            model=model_name,
            base_url="http://100.106.118.73:11434",
            temperature=0.0,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            seed=42,
        )
    except Exception as e:
        print(f"  初期化エラー: {e}")
        return 0

    results = []
    errors = 0
    start_total = time.time()

    for i, filename in enumerate(files, 1):
        img_id = extract_id(filename)
        if not img_id:
            continue

        print(f"  [{i}/{len(files)}] {filename}", end="", flush=True)
        start = time.time()

        try:
            img_b64 = image_to_base64(os.path.join(IMAGE_DIR, filename))
            messages = make_messages(img_b64, img_id)
            response = llm.invoke(messages)
            elapsed = time.time() - start
            line = response.content.strip()
            print(f" ({elapsed:.1f}秒) → {line}")
            results.append(line)

        except Exception as e:
            elapsed = time.time() - start
            print(f" ({elapsed:.1f}秒) [エラー] {e}")
            errors += 1
            # 連続エラーが多い場合はモデルスキップ
            if errors >= 3 and len(results) == 0:
                print(f"  → 最初の3件が全てエラー。モデル [{model_name}] をスキップします。")
                return 0

    total = time.time() - start_total
    avg = total / len(results) if results else 0

    # 結果をモデル名ベースのCSVに保存
    safe_name = re.sub(r'[/:.]', '_', model_name)
    output_csv = os.path.join(OUTPUT_DIR, f"result_{safe_name}.csv")
    with open(output_csv, "w", encoding="utf-8") as f:
        for row in results:
            f.write(row + "\n")

    print(f"\n  完了: {len(results)}件成功 / {errors}件エラー")
    print(f"  合計{total:.1f}秒 / 平均{avg:.1f}秒/枚")
    print(f"  → 保存: {output_csv}")
    return len(results)

# ---- メイン ----
files = sorted([f for f in os.listdir(IMAGE_DIR) if re.match(r"img_\d+\.jpg", f)])
print(f"対象ファイル: {len(files)}件")

summary = []
for model_name in MODELS:
    count = run_model(model_name, files)
    summary.append((model_name, count))

# サマリー表示
print(f"\n{'='*60}")
print("テスト結果サマリー")
print(f"{'='*60}")
for model_name, count in summary:
    status = f"{count}件成功" if count > 0 else "スキップ/失敗"
    print(f"  {status:12s} {model_name}")