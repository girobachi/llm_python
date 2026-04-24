import streamlit as st
from mb_client import MBClient, Status, MBinit
# from langchain_ollama import ChatOllama

# ==========================================
# 環境設定
# ==========================================
# OLLAMA_BASE_URL = "http://100.67.72.27:11434"
HOST_MB = "172.20.250.247"

# bank 0 diary, bank 2 girl, bank3 shop

# -------------------------------------------------------
# 検索処理（今後ここを実装・差し替え）
# -------------------------------------------------------
def fetch_prefectures(client) -> list[str]:
    """都道府県一覧を取得する。"""
    client.send("sel attr pref")
    body = client.body
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "pref":
            result.append(parts[1])
    return result

def fetch_areas(prefecture: str, client=None) -> list[str]:
    """選択した都道府県の第一エリア一覧を取得する。"""
    client.send(f"rel like 'pref,{prefecture}' col 1starea")
    body = client.body
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "1starea":
            result.append(parts[1])
    return result

def fetch_shops(area: str, client=None) -> list[str]:
    """選択した第一エリアの店舗IDリストを取得する。"""
    client.send(f"rel like '1starea,{area}' col shopname")
    body = client.body
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "shopname":
            result.append(parts[1])
    return result

def fetch_girlname(shop: str, client=None) -> list[str]:
    """選択した店舗の女の子の名前を取得する。"""
    client.send(f"rel like 'shopname,{shop}' col girlname")
    body = client.body
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "girlname":
            result.append(parts[1])
    return result

def fetch_relate(girlname: str, shop: str, client: MBClient) -> tuple[str, float]:
    """girlnameとshopをキーにmem_idを取得する。"""
    client.send(f"rel like 'girlname,{girlname}' like 'shopname,{shop}' col mem_id")
    body = client.body
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "mem_id":
            result.append(parts[1])
    return result

def search_diary(girlname: str, shop: str, client: MBClient) -> tuple[str, float]:
    """girlnameとshopをキーに日記を検索する。"""
    mem_ids = fetch_relate(girlname, shop, client)
    mem_id = mem_ids[0]
    client.send(f"gat like 'mem_id,{mem_id}' col $body limit 5")
    server_time = float(client.header_dict.get("time", 0.0))
    body = client.body  # .replace("\n", "\n\n") を削除
    return body, server_time

def format_diary(body: str) -> str:
    result = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("$body,"):
            line = line[len("$body,"):].strip('"')  # $body, とクォートを除去
        result.append(f"💕 {line}\n\n")
    return "".join(result)

# -------------------------------------------------------
# UI
# -------------------------------------------------------
st.title("Heaven")

client = MBinit(HOST_MB, "heaven", "diary")
if client == False:
    print("Failed to connect.")
    exit(-1)

# セッション初期化
if "history" not in st.session_state:
    st.session_state.history = []       # [(query, result, server_time), ...]
if "prefectures" not in st.session_state:
    st.session_state.prefectures = fetch_prefectures(client)
if "areas" not in st.session_state:
    st.session_state.areas = []  # ← prefecture未定義なので空リストで初期化
if "shops" not in st.session_state:
    st.session_state.shops = []
if "girlname" not in st.session_state:
    st.session_state.girlname = []
if "mem_id" not in st.session_state:
    st.session_state.mem_id = []
if "diary_history" not in st.session_state:
    st.session_state.diary_history = []  # [(label, result, server_time), ...]

# --- 都道府県プルダウン ---
prefecture = st.selectbox(
    "都道府県",
    ["選択してください"] + st.session_state.prefectures,
    key="prefecture_select"
)

# 都道府県が選択されたら第一エリア一覧を取得
if prefecture != "選択してください":
    st.session_state.areas = fetch_areas(prefecture, client)

# --- 第一エリアプルダウン ---
area = st.selectbox(
    "第一エリア",
    ["選択してください"] + st.session_state.areas,
    key="area_select",
    disabled=(prefecture == "選択してください")
)

if area != "選択してください":
    st.session_state.shops = fetch_shops(area, client)

# --- 店舗プルダウン ---
shop = st.selectbox(
    "店舗",
    ["選択してください"] + st.session_state.shops,
    key="shop_select",
    disabled=(area == "選択してください")
)

if shop != "選択してください":
    st.session_state.girlname = fetch_girlname(shop, client)

# --- 女の子プルダウン ---
girlname = st.selectbox(
    "女の子",
    ["選択してください"] + st.session_state.girlname,
    key="girl_select",
    disabled=(shop == "選択してください")
)

st.divider()

if st.button("日記を検索", type="secondary", key="btn_diary_search", disabled=(girlname == "選択してください")):
    with st.spinner("検索中..."):
        result, server_time = search_diary(girlname, shop, client)
    st.session_state.diary_history.append((f"{shop} / {girlname}", result, server_time))

# --- 日記表示（新しい順） ---
if st.session_state.diary_history:
    if st.button("日記履歴をクリア"):
        st.session_state.diary_history = []
        st.rerun()

    for i, (label, result, server_time) in enumerate(reversed(st.session_state.diary_history)):
        with st.expander(f"📖 {label}  ⏱ {server_time * 1000:.0f}ms", expanded=(i == 0)):
            st.markdown(format_diary(result))

