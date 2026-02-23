import ollama
import fitz
import base64
from pathlib import Path
from ollama import Client
from mb_client import MBClient, Status
from prompts import SYSTEM_PROMPT # SYSTEM_PROMPT
import httpx
import pandas as pd

class GemmaFileReader:
    def __init__(self, model: str = "gemma3:12b", host: str = "http://192.168.0.110:11434"):
        self.model = model
        self.client = Client(host=host, timeout=300)  # ← リモートホスト指定   
        
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
    
    def transcribe_folder(self, input_path: str, output_file: str = "tmp.txt"):
        """フォルダ内の全ファイルを文字起こしして1つのファイルに保存"""
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

        with open(output_file, "w", encoding="utf-8") as out:
            for i, file in enumerate(files, 1):
                print(f"[{i}/{len(files)}] 処理中: {file.name}")
                try:
                    result = self.ask(
                        "文字起こしをしてください。内容をそのまま正確に出力してください。",
                        str(file)
                    )
                    # ファイル区切りヘッダーを追加
                    out.write(f"=== {file.name} ===\n")
                    out.write(result)
                    out.write("\n\n")
                    print(f"  → 完了")

                except Exception as e:
                    print(f"  → エラー: {e}")
                    out.write(f"=== {file.name} === [エラー: {e}]\n\n")

        print(f"\n全ファイル保存完了: {input_path}")


    def make_csv(self, input_file: str = "tmp.txt", output_file: str ="tmp.csv"):
        # 2. 会話履歴を保存するリスト
        chat_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

            # 4. ユーザーの発言を履歴に追加
            chat_history.append({"role": "user", "content": content})

            # 5. 履歴の制限（システムプロンプト1件 + 直近10件）
            try:
                # 6. 指定したサーバー(client)に履歴を投げる
                response = self.client.chat(
            #        model='gpt-oss:20b',
                    model='gemma3:12b',
                    messages=chat_history,
                    options={
                        "temperature": 0.0,
                        "seed": 42, # 任意の整数でOK
                        "num_ctx": 32768
                    }
                )

                # 7. 回答の抽出と表示
                answer = response['message']['content']
                print(f"AI: {answer}")

                # ファイルに書き込み
                with open(output_file, "w", encoding="utf-8") as fw:
                    fw.write(answer)
                    print(f"回答を {output_file} に保存しました。")

            except Exception as e:
                print(f"エラーが発生しました。サーバーが起動しているか確認してください: {e}")


def utf82shiftjis(utf8_path: str, cp932_path: str = "tmps.csv"):
    df = pd.read_csv(utf8_path, encoding="utf-8")
    df.to_csv(cp932_path, encoding="cp932", errors="replace", index=False) # 変換できない文字を ? に置換 
    print(f"{utf8_path}(utf8)を {cp932_path}(shiftjis)に保存しました。")


# 使用例

if __name__ == "__main__":
    # reader = GemmaFileReader(host="http://192.168.0.110:11434")

    # """ input_folder/下のファイルを全てoutput_fileファイルに変換してまとめる """
    # reader.transcribe_folder(input_path="./input_folder", output_file="tmp.txt") 

    # """ output_fileファイルをMB用csvに変換する """
    # reader.make_csv(input_file="tmp.txt",output_file="tmp.csv")

    # """ utf8のファイルをshiftjisに変換 """
    # utf82shiftjis("tmp.csv", "tmps.csv")

    client = MBClient()
    if client.connect("192.168.0.110", 65001) == False:
        print("Failed to connect.")
        exit(-1)
    client.send("pal 001")
    client.send("cre test")
    client.send("use test")
    client.send("set file tmps.csv")
