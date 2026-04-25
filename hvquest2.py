import streamlit as st
from mb_client import MBClient, Status, MBinit

# ==========================================
# 環境設定
# ==========================================
HOST_MB = "172.20.250.247"

# bank 0 diary, bank 2 girl, bank3 shop

# -------------------------------------------------------
# 毎回新規接続でコマンド送信
# -------------------------------------------------------
def send_command(cmd: str) -> tuple[str, float]:
    """毎回新規接続してコマンドを送信する。残データ問題を回避。"""
    client = MBinit(HOST_MB, "heaven", "diary")
    client.send(cmd)
    body = client.body
    server_time = float(client.header_dict.get("time", 0.0))
    client.close()
    return body, server_time


# -------------------------------------------------------
# 検索処理
# -------------------------------------------------------
def fetch_prefectures() -> list[str]:
    """都道府県一覧を取得する。"""
    body, _ = send_command("sel attr pref")
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "pref":
            result.append(parts[1])
    return result


def fetch_areas(prefecture: str) -> list[str]:
    """選択した都道府県の第一エリア一覧を取得する。"""
    body, _ = send_command(f"rel like 'pref,{prefecture}' col 1starea")
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "1starea":
            result.append(parts[1])
    return result


def fetch_shops(area: str) -> list[str]:
    """選択した第一エリアの店舗リストを取得する。"""
    body, _ = send_command(f"rel like '1starea,{area}' col shopname")
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "shopname":
            result.append(parts[1])
    return result


def fetch_girlname(shop: str) -> list[str]:
    """選択した店舗の女の子の名前を取得する。"""
    body, _ = send_command(f"rel like 'shopname,{shop}' col girlname")
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "girlname":
            result.append(parts[1])
    return result


def fetch_relate(girlname: str, shop: str) -> list[str]:
    """girlnameとshopをキーにmem_idを取得する。"""
    body, _ = send_command(f"rel like 'girlname,{girlname}' like 'shopname,{shop}' col mem_id")
    result = []
    for line in body.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "mem_id":
            result.append(parts[1])
    return result


def search_diary(girlname: str, shop: str) -> tuple[str, float]:
    """girlnameとshopをキーに日記を検索する。"""
    mem_ids = fetch_relate(girlname, shop)
    if not mem_ids:
        return "該当データなし", 0.0
    mem_id = mem_ids[0]
    body, server_time = send_command(f"gat like 'mem_id,{mem_id}' col $body limit 5")
    return body, server_time


def format_diary(body: str) -> str:
    """日記のフォーマット: $body,を除去してハートを付ける。"""
    result = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("$body,"):
            line = line[len("$body,"):].strip('"')
        result.append(f"💕 {line}\n\n")
    return "".join(result)


# -------------------------------------------------------
# UI
# -------------------------------------------------------
st.set_page_config(layout="wide")
st.title("Heaven")

# sort 2 を初回だけ実行
if "initialized" not in st.session_state:
    client = MBinit(HOST_MB, "heaven", "diary")
    client.send("sort 2")
    client.close()
    st.session_state.initialized = True

# セッション初期化
if "prefectures" not in st.session_state:
    st.session_state.prefectures = fetch_prefectures()
if "areas" not in st.session_state:
    st.session_state.areas = []
if "shops" not in st.session_state:
    st.session_state.shops = []
if "girlname" not in st.session_state:
    st.session_state.girlname = []
if "diary_history" not in st.session_state:
    st.session_state.diary_history = []  # [(label, result, server_time), ...]

# --- 都道府県プルダウン ---
prefecture = st.selectbox(
    "都道府県",
    ["選択してください"] + st.session_state.prefectures,
    key="prefecture_select"
)

if prefecture != "選択してください":
    if st.session_state.get("last_prefecture") != prefecture:
        st.session_state.areas = fetch_areas(prefecture)
        st.session_state.last_prefecture = prefecture
        st.session_state.shops = []
        st.session_state.girlname = []

# --- 第一エリアプルダウン ---
area = st.selectbox(
    "第一エリア",
    ["選択してください"] + st.session_state.areas,
    key="area_select",
    disabled=(prefecture == "選択してください")
)

if area != "選択してください":
    if st.session_state.get("last_area") != area:
        st.session_state.shops = fetch_shops(area)
        st.session_state.last_area = area
        st.session_state.girlname = []

# --- 店舗プルダウン ---
shop = st.selectbox(
    "店舗",
    ["選択してください"] + st.session_state.shops,
    key="shop_select",
    disabled=(area == "選択してください")
)

if shop != "選択してください":
    if st.session_state.get("last_shop") != shop:
        st.session_state.girlname = fetch_girlname(shop)
        st.session_state.last_shop = shop

# --- 女の子プルダウン ---
girlname = st.selectbox(
    "女の子",
    ["選択してください"] + st.session_state.girlname,
    key="girl_select",
    disabled=(shop == "選択してください")
)

st.divider()

# --- 日記検索ボタン ---
if st.button("日記を検索", type="secondary", key="btn_diary_search",
             disabled=(girlname == "選択してください")):
    with st.spinner("検索中..."):
        result, server_time = search_diary(girlname, shop)
    st.session_state.diary_history.append((f"{shop} / {girlname}", result, server_time))

# --- 日記履歴表示（新しい順） ---
if st.session_state.diary_history:
    if st.button("日記履歴をクリア", key="btn_diary_clear"):
        st.session_state.diary_history = []
        st.rerun()

    for i, (label, result, server_time) in enumerate(reversed(st.session_state.diary_history)):
        with st.expander(f"📖 {label}  ⏱ {server_time * 1000:.0f}ms", expanded=(i == 0)):
            st.markdown(format_diary(result))