from langchain_ollama import OllamaLLM
from langchain_core.tools import Tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from mb_client import MBClient
import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"

HOST_MB=""  # Wsl

def query_mb(query: str) -> str:
    try:
        result = client.send(query)
        return str(client.body)
    except Exception as e:
        return f"クエリエラー: {e}"

tools = [
    Tool(
        name="mb_db_query",
        description="""
        MBに対してSQLライクなクエリを実行するツール。
        例:
          RELATE like 'Who,Person'
          RELATE like 'Who,鈴木一郎'
        """,
        func=query_mb
    )
]

# 使用例

if __name__ == "__main__":
    client = MBClient()
    if client.connect(HOST_MB, 65001) == False:
        print("Failed to connect.")
        exit(-1)
    client.send("pal 001")
    client.send("cre test")
    client.send("use test")

llm = OllamaLLM(model="gemma3:12b", base_url="http://172.20.240.1:11434")  # ローカルOllamaに接続

# ReActプロンプトをhubから取得
prompt = hub.pull("hwchase17/react")
# print(prompt)
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

while True:
    user_input = input("\nあなた: ")

    if user_input.lower() == "exit":
        break

    result = agent_executor.invoke({"input": user_input})
    print(result["output"])

    # elapsed = time.time() - start
    # print(f"実行時間: {elapsed:.2f}秒")