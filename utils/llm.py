"""Ollama を使った日記要約。"""
from __future__ import annotations

import ollama

# Ollama サーバアドレス。リモートなら "http://192.168.x.x:11434" 等に変更
OLLAMA_HOST = "http://192.168.0.117:11434"

# 既定モデル
# DEFAULT_MODEL = "qwen2.5:72b"
DEFAULT_MODEL = "qwen2.5"

SYSTEM_PROMPT = """あなたは女の子の日記を要約するアシスタントです。
入力された日記から以下の3点を読み取り、合計300文字以内でカジュアルにまとめてください。

1. 性格・雰囲気(明るい/おっとり/サバサバ など)
2. 最近の気分や出来事
3. 趣味・好きなもの・話題

ルール:
- プレーンテキストで出力する。markdown、箇条書き、見出しは使わない。
- 装飾の絵文字(💕など)は本文に含めない。ただし語尾の感情表現は自由。
- 推測の度合いが強い情報は「〜らしい」「〜そう」などに留める。
- 個人を特定する情報(本名、住所、電話番号など)が混入していても出力しない。
"""


def summarize(diary_text: str, model: str = DEFAULT_MODEL) -> str:
    """日記テキストを要約して返す。

    Args:
        diary_text: 連結済みの日記本文
        model: 使用する Ollama モデル名

    Returns:
        要約された日本語テキスト
    """
    if not diary_text.strip():
        return "(本文が空のため要約できません)"

    client = ollama.Client(host=OLLAMA_HOST)
    res = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": diary_text},
        ],
        options={
            "temperature": 0.3,
            "num_ctx": 8192,
        },
    )
    return res["message"]["content"].strip()
