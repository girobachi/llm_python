import csv
import re
import sys
from html.parser import HTMLParser


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    s = HTMLStripper()
    s.feed(text)
    text = s.get_data()
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    return text


def replace_all_unencodable(text: str, replacement: str = '。') -> str:
    """全セル対象：Shift-JIS非対応文字をすべて置換"""
    result = []
    for ch in text:
        try:
            ch.encode('shift_jis')
            result.append(ch)
        except (UnicodeEncodeError, UnicodeDecodeError):
            result.append(replacement)
    return ''.join(result)


def replace_trailing_unencodable(text: str, replacement: str = '。') -> str:
    """行末セル専用：末尾の連続するShift-JIS非対応文字のみ置換"""
    chars = list(text)
    i = len(chars) - 1
    while i >= 0:
        try:
            chars[i].encode('shift_jis')
            break
        except (UnicodeEncodeError, UnicodeDecodeError):
            chars[i] = replacement
        i -= 1
    return ''.join(chars)


def clean_cell(cell: str) -> str:
    """HTMLタグ除去 + 空白正規化（全セル共通）"""
    cell = strip_html(cell)
    cell = re.sub(r'[ \t]+', ' ', cell)
    cell = cell.strip()
    return cell


def convert_csv(input_path: str, output_path: str) -> None:
    with open(input_path, encoding='utf-8', newline='') as f_in:
        reader = csv.reader(f_in)
        rows = []
        for row in reader:
            if not row:
                rows.append(row)
                continue

            new_row = []
            last_idx = len(row) - 1

            for i, cell in enumerate(row):
                cell = clean_cell(cell)

                if i == last_idx:
                    # 行末セルのみ：末尾の非対応文字を「。」に置換
                    cell = replace_trailing_unencodable(cell)
                else:
                    # それ以外：非対応文字をすべて置換
                    # cell = replace_all_unencodable(cell)
                    cell = replace_all_unencodable(cell, replacement='')

                new_row.append(cell)

            rows.append(new_row)

    with open(output_path, 'w', encoding='shift_jis', errors='ignore', newline='') as f_out:
        writer = csv.writer(f_out)
        writer.writerows(rows)

    print(f"変換完了: {input_path} → {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("使い方: python convert_csv.py <入力.csv> <出力.csv>")
        sys.exit(1)

    convert_csv(sys.argv[1], sys.argv[2])

# girls_data.20260325_100227.csvからタグ削除、shiftjis化 → girls_data.20260325_100227_sjis.csv
# python .\convert_csv.py  girls_data.20260325_100227.csv  \
# SPD_ girls_data.20260325_100227_sjis.csv
