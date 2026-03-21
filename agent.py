# import os
import uuid 
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import Tool, tool
from langchain_core.messages import SystemMessage
# from typing import Any
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
    model="gemma3:27b",
    # model="qwen2.5:14b",
    base_url=OLLAMA_BASE_URL,
    temperature=0,
)

# ==========================================
# 2. ツール定義
# ==========================================
@tool
def internet_search(query: str) -> str:
    """最新のニュース、天気、一般常識など、社内マニュアルに載っていない外部情報を調べる時に使用してください。"""
    search = DuckDuckGoSearchRun()
    return search.run(query)

@tool
def get_relation_tool(column: str, value: str) -> str:
    """
    指定アイテム(value)に関連するカテゴリ(column)とアイテム(value)の統計情報を取得する。
    例: relate like 'column,value' limit 100
    人名の場合columnはHuman,valueは名前が入る。
    取得レコードの内容は、column,value,出現行数,出現総数,指定アイテムと同時出現行数,指定アイテムと同時出現数。
    このレコード形式で最大100行を返します。
    """
    client = MBinit(HOST_MB, "test")
    client.send(f"relate like '{column}, {value}' limit 100")
    return client.body

tools = [internet_search, get_relation_tool]

# ==========================================
# 3. システムプロンプト
# ==========================================
system_prompt = """あなたは「優秀な日常のコンシェルジュAI」です。
以下のガイドラインに従って行動してください：

1. 思考プロセス:
   - ユーザーの質問に対し、まず「どのツールを使うべきか」を考えてください。
   - 最初に「get_relation_tool」を優先します。
   - 一般的な事柄や最新情報は「internet_search」を使用します。

2. 回答スタイル:
   - 常に丁寧なビジネス敬語（です・ます調）で回答してください。
   - 回答の最後には、必要に応じて「他に不明点はありますか？」と付け加えてください。

3. 安全性:
   - get_relation_toolにもネットにも答えがない場合は、推測で答えず「分かりかねます」と正直に伝えてください。"""

# ==========================================
# 4. エージェント組み立て
# ==========================================
# 1. モデルにシステムプロンプトを事前に「結合」させる
# これにより、create_react_agent の引数問題（modifier）を回避します
# llm_with_system = llm.bind_tools(tools).with_config(
#     {"configurable": {"system_prompt": system_prompt}}
# )

# 2. エージェント作成（引数は model と tools だけにする）
agent = create_react_agent(
    model=llm,
    tools=tools,
    # 引数エラーを避けるため、ここでは modifier を指定しない
    # 代わりに、実行時に最初のメッセージとしてシステムプロンプトを注入します
)
# ==========================================
# 5. 実行（会話履歴管理）
# ==========================================
if __name__ == "__main__":
    print("--- エージェント起動 (Ollama Gemma 3) ---")
    
# システムプロンプトをメッセージ履歴の先頭に固定
    initial_messages = [SystemMessage(content=system_prompt)]

    history = []
    
    try:
        # 1回目
        user1 = "鈴木 一郎さんと一緒に居たのは誰ですか？"
        result1 = agent.invoke({"messages": history + [("user", user1)]})
        answer1 = result1["messages"][-1].content
        print(f"A1: {answer1}")
        
        # 会話履歴に追加
        history += [("user", user1), ("assistant", answer1)]

        # 2回目（履歴引き継ぎ）
        user2 = "東京で一番人気の観光スポットを教えて。"
        result2 = agent.invoke({"messages": history + [("user", user2)]})
        answer2 = result2["messages"][-1].content
        print(f"A2: {answer2}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")