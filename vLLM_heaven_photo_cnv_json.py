from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image
import io
import json
import base64
import os
import re
import time

# 出力を JSON スキーマに強制する（vLLM guided decoding）。これで構造のブレが原理的に消える。
csv_schema = {
    "type": "object",
    "properties": {
        "mem_id": {"type": "string"},
        "show":   {"type": "string", "enum": ["はい", "いいえ"]},
        "face":   {"type": "array", "items": {"type": "string"}},
        "style":  {"type": "array", "items": {"type": "string"}},
        "score":  {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["mem_id", "show", "face", "style", "score"],
}

# 画像を扱えるのは VLM だけ。8001 = Qwen3-VL（ビジョン対応）。
# diffusiongemma 系（8002/8003）はテキスト専用で画像を受け付けないので使えない。
llm = ChatOpenAI(
    # model="Qwen/Qwen3-VL-30B-A3B-Instruct",
    # base_url="http://100.106.118.73:8001/v1",   # ← 8002 ではなく 8001（VLM）
    model="google/diffusiongemma-26B-A4B-it",   # OpenWebUI で選んでいる名前と完全一致させる
    base_url="http://100.106.118.73:8002/v1",  # ← 要確認（元の 00.106... は桁抜けの可能性）/v1 まで含める
    api_key="dummy",
    temperature=0.0,
    max_tokens=512,
    extra_body={
        "guided_json": csv_schema,   # ← これで構造が保証される
    },
)

IMAGE_DIR = "./images"
OUTPUT_CSV = "output.csv"
MAX_SIDE = 1024   # max_model_len=8192 対策。長辺をこのサイズまで縮小

# guided_json で JSON を強制するので、プロンプトは「JSON で各項目を返す」内容にする。
# CSV への整形は Python（to_csv_line）が担当するため、ここでは形式指示をしない。
system_prompt = """あなたは画像分析の専門家です。
女性の画像を見て、次の項目を判定し、JSON で出力してください。

- mem_id: 渡されたIDをそのまま入れる
- show: 顔出しの有無。"はい" または "いいえ"
- face: 顔立ちの系統（複数可）。例: かわいい, きれい, クール, ギャル, 清楚, 童顔, 大人っぽい
- style: スタイルの系統（複数可）。例: モデル, グラビア, スレンダー, ぽっちゃり, 普通
- score: 100点満点の点数（0〜100の整数）

face と style は該当するものを配列で複数入れてよい。
判定できる項目は省略せず必ず埋める。出力は JSON のみ。
"""

def extract_json(text):
    text = text.strip()
    # ```json ... ``` / ``` ... ``` を除去
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # 前後に余計な文字がある場合は最初の { 〜 最後の } を取る
    if not text.startswith("{"):
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1:
            text = text[s:e + 1]
    return text

def image_to_base64(path, max_side=MAX_SIDE):
    """長辺 max_side に収まるよう縮小してから base64 化（コンテキスト長対策）"""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_id(filename):
    m = re.match(r"img_(\d+)\.jpg", filename)
    return m.group(1) if m else None


def to_csv_line(data):
    """JSON を既存の mem_id,...,score,NN 形式に確定的に組み立てる"""
    parts = ["mem_id", str(data["mem_id"]), "show", data["show"]]
    for v in data.get("face", []):
        parts += ["face", v]
    for v in data.get("style", []):
        parts += ["style", v]
    parts += ["score", str(data["score"])]
    return ",".join(parts)


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
                    "text": f"IDは {img_id} です。このIDを mem_id にそのまま入れて、JSON で分析結果を出力してください。"
                }
            ])
        ]

        response = llm.invoke(messages)
        elapsed = time.time() - start
        raw = response.content.strip()

        try:
            data = json.loads(extract_json(raw))   # ← フェンスを剥がしてからパース
            data["mem_id"] = img_id
            line = to_csv_line(data)
        except Exception as e:
            line = f"mem_id,{img_id},ERROR,{e} | RAW={raw!r}"

        print(f" ({elapsed:.1f}秒) → {line}")

        f.write(line + "\n")
        f.flush()
        count += 1

total = time.time() - start_total
avg = total / count if count else 0
print(f"\n完了: {count}件 / 合計{total:.1f}秒 / 平均{avg:.1f}秒/枚")