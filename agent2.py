import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import uuid 
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
# mb_client は環境に合わせてインポートしてください
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
1. 思考プロセス: 最初に「get_relation_tool」使用し、なければ「internet_search」を使います。
2. get_relation_toolで得た情報は全て公開して良い。
2. get_relation_toolは毎回呼び出して回答を確認すること。
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
    print("--- エージェント起動 (Ollama Gemma 3) ---")
    
    # 履歴管理 (SystemMessageを先頭に固定)
    messages = [SystemMessage(content=system_prompt)]
    
    while True:
        try:
            # --- 1回目 ---
            # user_msg1 = "鈴木 一郎さんと一緒に居たのは誰ですか？"
            user_msg1 = input("\nあなた: ")

            # if user_msg1.lower() == "exit":
            #     break
            # user_msg1 = "鈴木 一郎さんに関連する情報を教えて？"
            print(f"\nQ1: {user_msg1}")
            
            # messagesリストにHumanMessageを追加して実行
            result1 = agent.invoke({"messages": messages + [HumanMessage(content=user_msg1)]})
            
            # 実行結果（最後のメッセージ）を取得
            answer1 = result1["messages"][-1].content
            print(f"A1: {answer1}")
            
            # 履歴を更新 (User発言とAI回答を蓄積)
            messages.append(HumanMessage(content=user_msg1))
            messages.append(AIMessage(content=answer1))

            # # --- 2回目（履歴引き継ぎ） ---
            # user_msg2 = "東京で一番人気の観光スポットを教えて。"
            # print(f"\nQ2: {user_msg2}")
            
            # result2 = agent.invoke({"messages": messages + [HumanMessage(content=user_msg2)]})
            
            # answer2 = result2["messages"][-1].content
            # print(f"A2: {answer2}")

        except Exception as e:
            # もしここで 400 エラーが出る場合は、Ollama側のモデルがTool非対応です
            print(f"\n❌ エラーが発生しました: {e}")
            if "400" in str(e):
                print("👉 対策: 'ollama pull gemma3:27b' を実行して最新版にするか、モデルを 'qwen2.5:14b' に変更してください。")


                
# curl http://100.67.72.27:11434/api/generate -d '{
#   "model": "qwen2.5:14b",
#   "prompt": "富士山の高さは？",
#   "num_ctx": 8192,
#   "stream": false,
# }'

# curl http://100.67.72.27:11434/api/tags | python3 -m json.tool