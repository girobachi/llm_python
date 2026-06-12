from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

llm = ChatOllama(model="gemma4:31b", base_url="http://100.106.118.73:11434")

system_prompt = "あなたは優秀なアシスタントです。日本語で答えてください。"

history = [SystemMessage(content=system_prompt)]

while True:
    user_input = input("\nあなた: ")
    if user_input.lower() == "exit":
        break

    history.append(HumanMessage(content=user_input))
    response = llm.invoke(history)
    history.append(response)

    print(f"\nAI: {response.content}")
