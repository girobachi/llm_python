import ollama
import fitz
import base64
from pathlib import Path
from ollama import Client
from mb_client import MBClient, Status
# from prompts import SYSTEM_PROMPT # SYSTEM_PROMPT
from prompts_sumo_auto_gemini3 import SYSTEM_PROMPT # SYSTEM_PROMPT
import csv
import sys
import pandas as pd
import time

# 起動方法
# Windows
# C:\Users\girob> taskkill /F /IM "ollama app.exe"
# C:\Users\girob> taskkill /F /IM ollama.exe
# C:\Users\girob> $env:OLLAMA_HOST="0.0.0.0"
# C:\Users\girob> ollama serve &

# TTDC
# export OLLAMA_HOST="0.0.0.0:11434"
# ollama serve &
# nvidia-smi -l 1
# unset OLLAMA_HOST

# TTDC
HOST_OLLAMA='http://100.67.72.27:11434'

# HOST_OLLAMA="http://localhost:11434" # Wsl IP
# HOST_OLLAMA="http://172.20.240.1:11434" # Wsl IP
# tailscale0のIP 100.67.72.27 # TTDC LLM
# HOST_MB=""  # Wsl
HOST_MB="100.67.72.27" # TTDC LLM

# Macbook
# HOST_OLLAMA="http://192.168.0.112:11434" # Mac
# HOST_MB="192.168.0.112" # Mac

# MODEL_LLM="gpt-oss:20b"        # LLMモデル名 gpt-oss:20b
MODEL_LLM="gemma3:27b"       # LLMモデル名 
# MODEL_LLM="qwen2.5:14b"        # LLMモデル名 日本語に強いとされるQwen3を使用。Gemma3は英語に強い。
# MODEL_LLM="qwen3:30b-a3b"

INPUT_FOLDER="./input_folder" # 変換したいファイルを入れるフォルダ

# 固定パラメタ
TEMP_UTF8_CSV="tmp.csv"       # フォルダ内の１ファイルをcsvに変換
TEMP_SJIS_CSV="tmps.csv"      # Shiftjisに変換

class GemmaFileReader:
    def __init__(self, model: str = MODEL_LLM, host: str = "http://localhost:11434"):
        self.model = model
        self.client = Client(host=host, timeout=1800)  # ← リモートホスト指定   
        
    # 対応拡張子
    SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    def ask(self, prompt: str, file_path: str = None) -> str:
        suffix = Path(file_path).suffix.lower() if file_path else ""

        if suffix == ".txt":
            content = self._load_txt(file_path)
            messages = [{"role": "user", "content": f"{prompt}\n\n{content}"}]

        elif suffix == ".pdf":
            content = self._load_pdf(file_path)
            messages = [{"role": "user", "content": f"{prompt}\n\n{content}"}]

        elif suffix in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            messages = [{"role": "user", "content": prompt, "images": [file_path]}]

        else:
            messages = [{"role": "user", "content": prompt}]

        response = self.client.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    def _load_txt(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_pdf(self, path: str) -> str:
        doc = fitz.open(path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    
    def transcribe_folder2csv(self, input_path: str = INPUT_FOLDER, output_file: str = TEMP_UTF8_CSV):
        """ INPUTFOLDER/下のファイルを全てoutput_fileファイルに変換してまとめる """
        print(f"AI: {input_path}内のファイルを文字に変換します--->")

        folder = Path(input_path)

        if not folder.exists() or not folder.is_dir():
            print(f"エラー: フォルダが見つかりません -> {input_path}")
            return

        # 対応ファイルだけ取得してソート
        files = sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ])

        if not files:
            print("対応ファイルが見つかりませんでした")
            return

        print(f"対象ファイル数: {len(files)} 件")

        # 追記モードで一度だけ開く、またはリストに溜めて最後に書く
        with open(output_file, "w", encoding="utf-8") as final_out:
            for i, file in enumerate(files, 1):
                print(f"[{i}/{len(files)}] 処理中: {file.name}")
                try:
                    # 1. 文字起こし (OCR/PDF/Text)
                    raw_text = self.ask(
                        "文字起こしをしてください。内容をそのまま正確に出力してください。",
                        str(file)
                    )
                    # print(raw_text + "\n") # 生テキスト変換データの表示

                    # そのまま構造化(CSV化)メソッドへ渡す
                    csv_line = self.process_text_to_csv_line(f"=== {file.name} ===\n{raw_text}")
                    
                    # 直接最終ファイルに書き込む
                    final_out.write(csv_line + "\n")
                    final_out.flush() # 確実にディスクに書き出す
                    print(csv_line + "\n") # CSV化されたテキストの表示
                    print(f"  → 完了")

                except Exception as e:
                    print(f"  → エラー: {e}")

    def process_text_to_csv_line(self, content: str) -> str:
        """ ファイルではなく文字列を受け取ってLLMで変換する """
        chat_history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
            # {"role": "user", "content": "/no_think\n\n" + content}
        ]
        
        # num_ctxを現実的な数値（例: 8192）に抑える
        response = self.client.chat(
            model=self.model,
            messages=chat_history,
            options={
                "seed": 42, # 任意の整数でOK
                "temperature": 0.0,
                "num_ctx": 8192 
            }
        )
        return response['message']['content']

def check_pair_structure(filepath: str) -> list[dict]:
    """
    カラム・バリューが交互に並ぶCSVの対構造をチェックする。
    例: Date,2025/09/14,Time,17:20:00,...
    Returns: エラーのリスト。各エラーは行番号・問題内容を含む辞書。
    """        
    errors = []

    with open(filepath, encoding="utf-8", newline="") as f:
        for row_num, row in enumerate(csv.reader(f), start=1):
            if not any(row):
                continue

            # ① 要素数が奇数
            if len(row) % 2 != 0:
                errors.append({"row": row_num, "issue": f"要素数が奇数({len(row)}個)"})
                continue

            keys, values = row[0::2], row[1::2]

            # ② キーが空
            for i, k in enumerate(keys):
                if not k.strip():
                    errors.append({"row": row_num, "col": i*2+1, "issue": f"列{i*2+1}: キーが空"})

            # ③ バリューが空
            for i, v in enumerate(values):
                if not v.strip():
                    errors.append({"row": row_num, "col": i*2+2, "issue": f"列{i*2+2}: バリューが空(キー:'{keys[i]}')"})
    return errors
    
def utf82shiftjis(utf8_path: str = TEMP_UTF8_CSV, cp932_path: str = TEMP_SJIS_CSV):
    print(f"{utf8_path}をshiftjisに変換します--->")

    with open(utf8_path, "r", encoding="utf-8") as f:
        content = f.read()
    with open(cp932_path, "w", encoding="cp932", errors="replace") as f:
        f.write(content)
    print(f"{utf8_path}(utf8)を {cp932_path}(shiftjis)に保存しました。")

# 使用例
if __name__ == "__main__":
    start = time.time()
    reader = GemmaFileReader(host = HOST_OLLAMA)

    """ input_folder/下のファイルを全てoutput_fileファイルに変換してまとめる """
    reader.transcribe_folder2csv() 

    """ csv check """
    print(f"チェック対象: {TEMP_UTF8_CSV}\n")
    errors = check_pair_structure(TEMP_UTF8_CSV)
    if not errors:
        print("✅ 問題なし")
    else:
        print(f"❌ {len(errors)}件の問題:")
        for e in errors:
            loc = f"行{e['row']}" + (f"/列{e['col']}" if "col" in e else "")
            print(f"  [{loc}] {e['issue']}")

    """ utf8のファイルをshiftjisに変換 """
    utf82shiftjis()

    """ MBに変換 """
    client = MBClient()
    if client.connect(HOST_MB, 65001) == False:
        print("Failed to connect.")
        elapsed = time.time() - start
        print(f"実行時間: {elapsed:.2f}秒")
        exit(-1)
    client.send("pal test")
    client.send("cre test")
    client.send("use test")
    client.file_send("tmps.csv")

    elapsed = time.time() - start
    print(f"実行時間: {elapsed:.2f}秒")