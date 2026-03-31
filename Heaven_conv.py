from ollama import Client
import httpx
import time
import csv
import io
import sys

SYSTEM_PROMPT = """
# 役割
あなたは「RFC 4180」規格に完全準拠した、Excel専用CSVデータ成形スペシャリストです。

# 処理ルール（絶対遵守）
1.  **データ構造:** 出力は必ず [commu_id, name, pref, btype_l, btype_s, holiday, shop_type, fst_area, snd_area, access, info] の11カラムで構成すること。
2.  **セル結合の強制:** 11番目のカラム「info」は、値の開始から終了までを必ず一組のダブルクォーテーション（"）のみで囲め。
3.  **改行の封じ込め:** 「info」内部に改行やカンマが含まれていても、次のダブルクォーテーションが出現するまでは、絶対に1つのフィールドとして出力せよ。
4.  **文字クリーンアップ:** - Shift-JIS非対応文字・絵文字は削除せよ。
    - 文末の非対応文字のみ「。」に置換せよ。
    - HTMLタグ等の余計な装飾は全て排除せよ。
5.  **エスケープ処理:** データ内に「"」自体が含まれる場合は「""」と二重にしてエスケープせよ。

# 出力形式（最優先）
- **「```csv」や「```」などのコードブロック記号は一切使用禁止とする。**
- **挨拶、説明、タイトル、補足コメントも一切不要。**
- **出力は「純粋なCSVの生テキスト」のみとし、1行目からデータそのものを開始せよ。**
- 変換後は、行ごとに改行のみを行え。
"""

# SYSTEM_PROMPT = """
# 入力したデータは、カラムがcommu_id,name,pref,btype_l,btype_s,holiday,shop_type,fst_area,snd_area,access,infoの順番で並んでいます。
# commu_id,name,pref,btype_l,btype_s,holiday,shop_type,fst_area,snd_area,access,info
# 毎に対応する値を全て抽出してください。余計なタグははずすこと。絵文字やshiftjisに無い文字は文末なら句点(。)に、文中なら削除する。
# 全ての行を正確に変換すること。変換後は、行ごとに改行してください。
# """

BATCH_SIZE = 1 # 1回のLLM呼び出しに送る行数（調整可能）

def split_csv_into_batches(content: str, batch_size: int) -> list[tuple[str, list[str]]]:
    """
    CSVをヘッダー + batch_size行ずつのチャンクに分割する。
    戻り値: [(ヘッダー行, [データ行, ...]), ...]
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:]

    print(header)
    # print(data_rows)

    batches = []
    for i in range(0, len(data_rows), batch_size):
        chunk = data_rows[i:i + batch_size]
        batches.append((header, chunk))

    return batches


def rows_to_csv_string(header: list[str], rows: list[list[str]]) -> str:
    """ヘッダー + 行リストをCSV文字列に変換する"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def convert_batch(client: Client, header: list[str], rows: list[list[str]], batch_index: int, total_batches: int) -> str:
    """1バッチをLLMに送り、変換結果を返す"""
    csv_chunk = rows_to_csv_string(header, rows)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": csv_chunk},
    ]

    print(f"  [バッチ {batch_index + 1}/{total_batches}] {len(rows)}行を送信中...", end=" ", flush=True)
    t0 = time.time()

    response = client.chat(
        # model="gpt-oss:20b",
        # model="gemma3:27b",
        # model="qwen2.5:27b",
        model="qwen2.5:72b",

        messages=messages,
        options={
            "temperature": 0.0,
            "seed": 42,
            "top_p": 1,
            "top_k": 1,
            "num_ctx": 8192,
        },
    )

    elapsed = time.time() - t0
    answer = response["message"]["content"]
    print(f"完了 ({elapsed:.1f}秒)")
    return answer


def main():
    filename = "shop_data.20260325_095307.csv"
    # filename = "Heaven_samp.csv"
    output_filename = filename.replace(".csv", "_converted.csv")

    print(f"入力ファイル: {filename}")
    print(f"出力ファイル: {output_filename}")
    print(f"バッチサイズ: {BATCH_SIZE}行")

    # ファイル読み込み
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    # バッチ分割
    batches = split_csv_into_batches(content, BATCH_SIZE)
    if not batches:
        print("データが空です。終了します。")
        sys.exit(1)

    total_data_rows = sum(len(rows) for _, rows in batches)
    print(f"総データ行数: {total_data_rows}行 → {len(batches)}バッチに分割\n")

    # Ollamaクライアント初期化
    client = Client(host="http://100.67.72.27:11434", timeout=httpx.Timeout(None))

    # バッチ処理
    all_results: list[str] = []
    start_total = time.time()

    for i, (header, rows) in enumerate(batches):
        if i == 10:
            print(f"\n[停止] {i}バッチ完了で処理を終了します。")
            break
        try:
            result = convert_batch(client, header, rows, i, len(batches))
            all_results.append(result.strip())
        except Exception as e:
            print(f"\n[エラー] バッチ {i + 1} で失敗しました: {e}")
            print("スキップして次のバッチに進みます。")
            continue

    # 結果を結合して出力
    final_output = "\n".join(all_results)

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(final_output)

    elapsed_total = time.time() - start_total
    print(f"\n変換完了！ 合計実行時間: {elapsed_total:.2f}秒")
    print(f"出力先: {output_filename}")

    # 標準出力にも表示
    print("\n--- 変換結果プレビュー（先頭3行）---")
    preview_lines = final_output.split("\n")[:3]
    for line in preview_lines:
        print(line)


if __name__ == "__main__":
    main()





# from ollama import Client  # 直接 ollama ではなく Client を使う
# # from Heaven_shop_prompt import SYSTEM_PROMPT # SYSTEM_PROMPT
# import httpx
# import time

# SYSTEM_PROMPT = """
# 入力したデータは、カラムがcommu_id,name,pref,btype_l,btype_s,holiday,shop_type,fst_area,snd_area,access,infoの順番で並んでいます。
# commu_id,name,pref,btype_l,btype_s,holiday,shop_type,fst_area,snd_area,access,info
# 毎に対応する値を全て抽出してください。余計なタグははずすこと。絵文字やshiftjisに無い文字は文末なら句点(。)に、文中なら削除する。
# 全ての行を正確に変換すること。変換後は、行ごとに改行してください。
#  """

# start = time.time()

# # 1. 外部サーバーのアドレスを指定してクライアントを初期化
# # client = Client(host='http://172.20.240.1:11434', timeout=httpx.Timeout(None))

# # Mac book
# # client = Client(host='http://192.168.0.112:11434', timeout=httpx.Timeout(None))

# # Mac mini
# # client = Client(host='http://192.168.0.118:11434', timeout=httpx.Timeout(None))

# # TTDC
# client = Client(host='http://100.67.72.27:11434', timeout=httpx.Timeout(None))

# # 2. 会話履歴を保存するリスト
# chat_history = [
#     {"role": "system", "content": SYSTEM_PROMPT}
# ]

# # filename = "Heaven_samp.csv"
# filename = "shop_data.20260325_095307.csv"

# with open(filename, "r", encoding="utf-8") as f:
#     content = f.read()

# # print(content)

# # 4. ユーザーの発言を履歴に追加
# chat_history.append({"role": "user", "content": content})

# # 5. 履歴の制限（システムプロンプト1件 + 直近10件）
# try:
#     # 6. 指定したサーバー(client)に履歴を投げる
#     response = client.chat(
# #        model='gpt-oss:20b',
#         # model='gemma3:27b',
#         model='qwen2.5:72b',
#         messages=chat_history,
#         options={
#             "temperature": 0.0, # 最も重要：ランダム性をゼロにする
#             "seed": 42, # 任意の整数でOK
#             "top_p":1, # すべての候補を考慮対象にする（ただしTemp 0なら実質無視される）
#             "top_k":1, # 確率1位の単語のみを選択
#             "num_ctx": 8192
#         }
#     )

#     # 7. 回答の抽出と表示
#     answer = response['message']['content']

#     print(answer)
#     elapsed = time.time() - start

#     print(f"実行時間: {elapsed:.2f}秒")

# except Exception as e:
#     print(f"エラーが発生しました。サーバーが起動しているか確認してください: {e}")


# curl http://100.67.72.27:11434/api/generate -d '{
#   "model": "qwen2.5:14b",
#   "prompt": "富士山の高さは？",
#   "stream": false
# }'