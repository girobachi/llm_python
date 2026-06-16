from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
import base64
import os
import re
import time
import threading
from math import ceil

NUM_THREADS = 6
IMAGE_DIR = "./images"
OUTPUT_DIR = "./output_csvs"

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


print_lock = threading.Lock()


def log(thread_id, msg):
    with print_lock:
        print(f"[Thread-{thread_id:02d}] {msg}", flush=True)


def worker(thread_id, file_list):
    llm = ChatOllama(
        model="qwen3-vl:32b",
        base_url="http://100.106.118.73:11434",
        temperature=0.0,
        top_p=0.9,
        top_k=40,
        repeat_penalty=1.1,
        seed=42,
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, f"output_{thread_id:02d}.csv")

    total = len(file_list)
    for i, filename in enumerate(file_list, 1):
        img_id = extract_id(filename)
        if not img_id:
            log(thread_id, f"スキップ: {filename} (ID抽出失敗)")
            continue

        start = time.time()
        log(thread_id, f"[{i}/{total}] 処理中: {filename}")

        try:
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

            # 1件ごとに即書き込み（追記モード）
            with open(csv_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

            log(thread_id, f"[{i}/{total}] 完了 ({elapsed:.1f}秒) → {line}")

        except Exception as e:
            elapsed = time.time() - start
            log(thread_id, f"[{i}/{total}] エラー ({elapsed:.1f}秒): {filename} → {e}")


def main():
    # 全ファイルをソートして取得
    all_files = sorted([
        f for f in os.listdir(IMAGE_DIR)
        if re.match(r"img_\d+\.jpg", f)
    ])

    if not all_files:
        print(f"エラー: {IMAGE_DIR} に対象ファイルが見つかりません。")
        return

    total_files = len(all_files)
    print(f"対象ファイル数: {total_files}件 / スレッド数: {NUM_THREADS}")

    # ファイルリストをスレッド数で分割
    chunk_size = ceil(total_files / NUM_THREADS)
    chunks = [all_files[i:i + chunk_size] for i in range(0, total_files, chunk_size)]

    # 実際のスレッド数（ファイル数がスレッド数より少い場合に対応）
    actual_threads = len(chunks)
    print(f"実際のスレッド数: {actual_threads}")
    for idx, chunk in enumerate(chunks):
        print(f"  Thread-{idx+1:02d}: {len(chunk)}件 ({chunk[0]} 〜 {chunk[-1]})")

    start_total = time.time()

    threads = []
    for idx, chunk in enumerate(chunks):
        t = threading.Thread(
            target=worker,
            args=(idx + 1, chunk),
            daemon=True
        )
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
