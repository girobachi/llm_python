from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image
import io
import base64
import os
import re
import time
import threading
from math import ceil

NUM_THREADS = 10
IMAGE_DIR = "./images"
OUTPUT_DIR = "./output_csvs"

# 画像を扱えるのは VLM だけ。8001 = Qwen3-VL（ビジョン対応）。
# diffusiongemma 系（8002/8003）はテキスト専用で画像を渡せないので使わない。
MODEL_NAME = "google/diffusiongemma-26B-A4B-it"
BASE_URL = "http://100.106.118.73:8002/v1"

MAX_SIDE = 1024     # max_model_len=8192 対策。長辺をこのサイズまで縮小してトークンを抑える
MAX_RETRIES = 2     # ネットワーク一時障害などに対するリトライ回数

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
他の文章・コードブロック・改行を含めず、CSV1行のみを出力
"""


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


print_lock = threading.Lock()


def log(thread_id, msg):
    with print_lock:
        print(f"[Thread-{thread_id:02d}] {msg}", flush=True)


def load_done_ids(csv_path):
    """既存 CSV から処理済み mem_id を読み、再実行時にスキップできるようにする"""
    done = set()
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                # 形式: mem_id,xxxxx,...  → 2列目が ID
                if len(parts) >= 2 and parts[0] == "mem_id":
                    done.add(parts[1])
    return done


def analyze_one(llm, img_id, filename):
    """1枚を分析。一時的な失敗はリトライする"""
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

    last_err = None
    for attempt in range(1, MAX_RETRIES + 2):  # 初回 + リトライ
        try:
            resp = llm.invoke(messages)
            return resp.content.strip()
        except Exception as e:
            last_err = e
            if attempt <= MAX_RETRIES:
                time.sleep(2 * attempt)  # 簡単なバックオフ
    raise last_err


def worker(thread_id, file_list):
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key="dummy",            # vLLM 側で --api-key 未設定なら任意の文字列でOK
        temperature=0.0,
        top_p=0.9,
        seed=42,
        max_tokens=512,
        extra_body={                # vLLM 固有のサンプリングパラメータ
            "top_k": 40,
            "repetition_penalty": 1.1,
        },
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, f"output_{thread_id:02d}.csv")

    done_ids = load_done_ids(csv_path)
    if done_ids:
        log(thread_id, f"再開: 既存 {len(done_ids)} 件をスキップします")

    total = len(file_list)
    # 追記モードで開きっぱなし。行バッファリング + flush で1件ごとに確実にディスク反映
    with open(csv_path, "a", encoding="utf-8", buffering=1) as f:
        for i, filename in enumerate(file_list, 1):
            img_id = extract_id(filename)
            if not img_id:
                log(thread_id, f"[{i}/{total}] スキップ: {filename} (ID抽出失敗)")
                continue
            if img_id in done_ids:
                log(thread_id, f"[{i}/{total}] スキップ済み: {filename}")
                continue

            start = time.time()
            log(thread_id, f"[{i}/{total}] 処理中: {filename}")

            try:
                line = analyze_one(llm, img_id, filename)
                elapsed = time.time() - start
                f.write(line + "\n")
                f.flush()
                log(thread_id, f"[{i}/{total}] 完了 ({elapsed:.1f}秒) → {line}")
            except Exception as e:
                elapsed = time.time() - start
                log(thread_id, f"[{i}/{total}] エラー ({elapsed:.1f}秒): {filename} → {e}")


def main():
    all_files = sorted([
        f for f in os.listdir(IMAGE_DIR)
        if re.match(r"img_\d+\.jpg", f)
    ])

    if not all_files:
        print(f"エラー: {IMAGE_DIR} に対象ファイルが見つかりません。")
        return

    total_files = len(all_files)
    print(f"対象ファイル数: {total_files}件 / スレッド数: {NUM_THREADS}")
    print(f"送信先: {BASE_URL} / モデル: {MODEL_NAME}")

    # ファイルリストをスレッド数で分割（連続チャンク。同じ入力なら毎回同じ割り当て＝再開と整合）
    chunk_size = ceil(total_files / NUM_THREADS)
    chunks = [all_files[i:i + chunk_size] for i in range(0, total_files, chunk_size)]

    actual_threads = len(chunks)
    print(f"実際のスレッド数: {actual_threads}")
    for idx, chunk in enumerate(chunks):
        print(f"  Thread-{idx + 1:02d}: {len(chunk)}件 ({chunk[0]} 〜 {chunk[-1]})")

    start_total = time.time()

    threads = []
    for idx, chunk in enumerate(chunks):
        t = threading.Thread(target=worker, args=(idx + 1, chunk), daemon=True)
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_elapsed = time.time() - start_total
    print(f"\n全スレッド完了: 合計 {total_elapsed:.1f}秒")
    print(f"CSVファイル出力先: {OUTPUT_DIR}/output_01.csv 〜 output_{actual_threads:02d}.csv")


if __name__ == "__main__":
    main()