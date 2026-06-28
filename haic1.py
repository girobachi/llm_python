from openai import OpenAI

client = OpenAI(
    base_url="http://100.106.118.73:8001/v1",
    api_key="dummy",  # vLLM は認証不要だが SDK が必須にするのでダミーでOK
)

resp = client.chat.completions.create(
    model="Qwen/Qwen3-VL-30B-A3B-Instruct",
    messages=[
        {"role": "system", "content": "あなたは有能なアシスタントです。"},
        {"role": "user", "content": "富士山の高さは？"},
    ],
    temperature=0.7,
    max_tokens=512,
)

print(resp.choices[0].message.content)