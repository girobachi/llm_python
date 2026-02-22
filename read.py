import ollama
import fitz
import base64
from pathlib import Path
from ollama import Client

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
    
    def transcribe_folder(self, folder_path: str, output_path: str = "tmp.txt"):
        """フォルダ内の全ファイルを文字起こしして1つのファイルに保存"""
        folder = Path(folder_path)

        if not folder.exists() or not folder.is_dir():
            print(f"エラー: フォルダが見つかりません -> {folder_path}")
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

        with open(output_path, "w", encoding="utf-8") as out:
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

        print(f"\n全ファイル保存完了: {output_path}")

# 使用例

if __name__ == "__main__":
    reader = GemmaFileReader(host="http://192.168.0.110:11434")
    reader.transcribe_folder("./input_folder", output_path="tmp.txt")
    # reader.transcribe_to_file("text0.txt")         # txtの文字起こし
    # reader.transcribe_to_file("7.pdf")    # PDFの文字起こし
    # reader.transcribe_to_file("memo.jpg")        # 手書き画像の文字起こし
