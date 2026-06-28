from openai import OpenAI
from mb_client import MBClient, Status
from utils.haic_llm import SYSTEM_PROMPT
import csv
import io
import time
import json

client = OpenAI(
    base_url="http://100.106.118.73:8001/v1",
    api_key="dummy",  # vLLM は認証不要だが SDK が必須にするのでダミーでOK
)

MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
HOST        = "172.20.250.247"   # サーバホスト
PORT        = 65001            # ポート
PAL         = "heaven"           # palコマンドの引数

# ============================================================
# MB 問い合わせ
# ============================================================
def fetch_mem_id(client, max_count: int = 3, start_mem_id: int = 1) -> list[str]:
    client.send(f"sel col mem_id limit {max_count} {start_mem_id}")
    result = []
    for line in client.body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "mem_id":
            result.append(parts[1])
    return result
# → ["58750883", "64390901", "61691459"]

# 取得する単一カラム（実データのカラム名）。データに無ければ「なし」を入れる
SINGLE_KEYS = [
    "$girlnm", "age", "bust", "waist", "hip",
    "$indivit", "$catch", "$info", "btname_l",
]

def _parse_line(line: str) -> dict:
    """1行を key,value,key,value... として dict 化する。
    "a,b,c" のようなクォート付きフィールドにも対応。"""
    tokens = next(csv.reader(io.StringIO(line)))
    d = {}
    for i in range(0, len(tokens) - 1, 2):   # 偶数=key, 奇数=value
        key = tokens[i].strip()
        if key:                              # 空キーは無視
            d[key] = tokens[i + 1]
    return d

def fetch_mem_id_inform(client, mem_id):
    st = client.send(f"gat like 'mem_id,{mem_id}'")
    if st != Status.OK:
        print(client, f"gat 通信失敗: mem_id={mem_id}, status={st}")
        return None
    try:
        client.raise_on_error()
    except Exception as e:
        print(client, f"gat エラー: mem_id={mem_id}, {e}")
        return None

    opnames = []   # $opname は複数 → 配列
    info = {}      # 単一カラム

    for line in client.body.splitlines():
        if not line.strip():
            continue
        d = _parse_line(line)
        if "$opname" in d:
            opnames.append(d["$opname"])
        else:
            info.update(d)

    result = {"$opname": opnames}
    for key in SINGLE_KEYS:
        result[key] = info.get(key, "なし")

    return result

# ============================================================
# プロンプト
# ============================================================
USER_PROMPT_TEMPLATE = (
    "以下は DB の検索結果です。\n"
    "----- 検索結果 -----\n"
    "{search_results}\n"
    "上記の検索結果のみを根拠に回答してください。"
)

# ============================================================
# LLM 問い合わせ
# ============================================================
def ask_llm(data: dict) -> str:
    # dict を JSON 文字列化（日本語をそのまま出す ensure_ascii=False）
    search_results = json.dumps(data, ensure_ascii=False, indent=2)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        search_results=search_results
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # ---- 回答の振れを最小化する設定 ----
        temperature=0.0,
        top_p=1.0,
        seed=42,
        max_tokens=2048,
    )
    return resp.choices[0].message.content

# ============================================================
# 実行例
# ============================================================
if __name__ == "__main__":

    mb = MBClient()

    t_start = time.time()

    if not mb.connect(HOST, PORT):
        print(mb, f"接続失敗: {HOST}:{PORT}")
        exit(1)
    print(mb, f"connected to {HOST}:{PORT}")

    # pal heaven
    st = mb.send("pal heaven")
    if st != Status.OK:
        print(mb, f"pal heaven 通信失敗: status={st}")
        mb.close()
        exit(1)

    try:
        mb.raise_on_error()
    except Exception as e:
        print(mb, f"pal heaven エラー: {e}")
        mb.close()
        exit(1)

    print(mb, "pal heaven OK")

    mem_ids = fetch_mem_id(mb, max_count=1, start_mem_id=2)

    for mem_id in mem_ids:
        data = fetch_mem_id_inform(mb, mem_id)
        if data is None:
            print(f"mem_id = {mem_id}: データ取得失敗のためスキップ")
            continue
        print(f"mem_id = {mem_id}, data = {data}")
        answer = ask_llm(data)
        print(f"Answer: {answer}")

    t_end = time.time()
    print(f"Wall elapsed:   {t_end - t_start:.2f}s")

