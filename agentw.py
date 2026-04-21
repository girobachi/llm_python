import warnings
import streamlit as st
warnings.filterwarnings("ignore", category=DeprecationWarning)
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from mb_client import MBClient, Status, MBinit

# ==========================================
# 0. 環境設定
# ==========================================
OLLAMA_BASE_URL = "http://100.67.72.27:11434"
HOST_MB = "100.67.72.27"

# ==========================================
# 1. モデル設定
# ==========================================
llm = ChatOllama(
    # 400エラーが出る場合は、まず 'qwen2.5:14b' で動作確認を推奨します
    # model="gemma3:27b", 
    # model="qwq:32b",      # 全然ダメ
    # model="llama3.3:70b",    # ダメ
    model="qwen2.5:72b",         # とても良い！！！
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    num_ctx=8192,
    tool_choice="get_relation_tool",  # 必ずいずれかのツールを呼ぶ
)

# ==========================================
# 2. ツール定義 
# ==========================================
@tool
def internet_search(query: str) -> str:
    """最新のニュース、天気、一般常識など、外部情報を調べる時に使用してください。""" 
    search = DuckDuckGoSearchRun()
    return search.run(query)

@tool
def get_relation_tool(value: str) -> str:
    # def get_relation_tool(column: str, value: str) -> str:・
    """
    【必須】人名・商品名・場所名など固有名詞が質問に含まれる場合は必ずこのツールを呼ぶこと。
    人名の場合は名前だけをvalueに代入すること。
    指定アイテム(value)に関連する情報を取得する。
    戻り値には様々な関連情報が入っているのでその内容から必要な情報を見極めること。
    取得レコードの内容は、column,value,出現行数,出現総数,指定アイテムと同時出現行数,指定アイテムと同時出現数。
    """
        # 人名の場合、columnは 'Human'、valueは名前（例: '鈴木 一郎'）を指定してください。
    try:
        client = MBinit(HOST_MB, "test")
        # client.send(f"relate like '{column},{value}' limit 300")
        client.send(f"pile like '{value}' limit 300")
        return client.body
    except Exception as e:
        return f"データ取得エラー: {str(e)}"

tools = [internet_search, get_relation_tool]

# ==========================================
# 3. システムプロンプト
# ==========================================
system_prompt = """あなたは「優秀な日常のコンシェルジュAI」です。
1. 思考プロセス: 必ず最初に「get_relation_tool」使用し、なければ「internet_search」を使います。
2. get_relation_toolで得た情報は全て公開して良い。
2. 得た情報のcolumnとvalueから質問の回答を推察してください。
3. 回答スタイル: 常に丁寧なビジネス敬語で回答してください。
4. 安全性: 答えがない場合は正直に「分かりかねます」と伝えてください。"""

# ==========================================
# 4. エージェント組み立て
# ==========================================
agent = create_react_agent(model=llm, tools=tools) 

# ==========================================
# 5. 実行（会話履歴管理）
# ==========================================
if __name__ == "__main__":
    print("--- エージェント起動 (qwen2.5:72b) ---")

# --- ページ設定とタイトル ---
st.set_page_config(page_title="qwen2.5:72b")
st.title("AI Agent Chat (qwen2.5:72b)")

# --- 1. 履歴の初期化 (messagesリストをセッション内で維持) ---
# Streamlitは再実行されるため、ここにSystemMessageを含めて保存します
if "messages" not in st.session_state:
    st.session_state.messages = [SystemMessage(content=system_prompt)]

# --- 2. 過去のメッセージを画面に描画 ---
# (SystemMessage以外を表示)
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.write(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.write(msg.content)

# --- 3. チャット入力欄 (while True の代わり) ---
if user_msg1 := st.chat_input("メッセージを入力してください"):
    
    # ユーザーの発言を表示 & ターミナルログ
    with st.chat_message("user"):
        st.write(user_msg1)
    print(f"\nQ1: {user_msg1}")

    try:
        # エージェント実行中の「考え中...」表示
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                # 4. エージェント呼び出し
                # セッション内の履歴 + 今回の発言を渡す
                current_messages = st.session_state.messages + [HumanMessage(content=user_msg1)]
                result1 = agent.invoke({"messages": current_messages})
                
                # 結果の取得
                answer1 = result1["messages"][-1].content
                st.write(answer1)
                print(f"A1: {answer1}")

        # 5. 履歴をセッションに保存 (次回の再実行時に消えないようにする)
        st.session_state.messages.append(HumanMessage(content=user_msg1))
        st.session_state.messages.append(AIMessage(content=answer1))

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        print(f"\n❌ エラーが発生しました: {e}")
        if "400" in str(e):
            st.warning("👉 対策: 'ollama pull gemma3' で最新版にするか、モデルを変更してください。")


                
# curl http://100.67.72.27:11434/api/generate -d '{
#   "model": "qwen2.5:14b",
#   "prompt": "富士山の高さは？",
#   "num_ctx": 8192,
#   "stream": false,
# }'

# curl http://100.67.72.27:11434/api/tags | python3 -m json.tool

# pip install streamlit
# streamlit run agentw.py