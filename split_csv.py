#!/usr/bin/env python3
"""
大容量CSVファイルを指定サイズに分割するスクリプト
使い方: python split_csv.py <入力ファイル> [オプション]
"""

import argparse
import io
import os
import sys
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def parse_size(size_str: str) -> int:
    units = {
        "GB": 1024**3, "MB": 1024**2, "KB": 1024, "B": 1,
        "G":  1024**3, "M":  1024**2, "K":  1024,
    }
    size_str = size_str.strip().upper()
    for unit, factor in sorted(units.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(unit):
            return int(float(size_str[: -len(unit)]) * factor)
    return int(size_str)


def unix_to_jst(unix_str: str):
    """
    UNIXタイム文字列をJSTの (日付文字列, 時刻文字列) に変換。
    変換できない場合は (unix_str, "") を返す。
    """
    try:
        ts = int(unix_str.strip())
        dt = datetime.fromtimestamp(ts, tz=JST)
        return dt.strftime("%Y/%m/%d"), dt.strftime("%H:%M:%S")
    except (ValueError, OSError):
        return unix_str, ""


def parse_record(line_iter):
    """
    ファイルイテレータから1レコード分を読み (fields, quoted_flags) を返す。
    quoted_flags[i] = True なら元データでそのフィールドがクォートされていた。
    EOF なら None を返す。
    """
    record = ""
    for line in line_iter:
        record += line
        if record.count('"') % 2 == 0:
            break
    else:
        if not record:
            return None

    record = record.rstrip("\r\n")
    if record == "":
        return [], []

    fields = []
    quoted_flags = []
    i = 0
    while i <= len(record):
        if i == len(record):
            break
        if record[i] == '"':
            i += 1
            val = ""
            while i < len(record):
                if record[i] == '"':
                    if i + 1 < len(record) and record[i + 1] == '"':
                        val += '"'
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    val += record[i]
                    i += 1
            fields.append(val)
            quoted_flags.append(True)
            if i < len(record) and record[i] == ',':
                i += 1
        else:
            end = record.find(',', i)
            if end == -1:
                fields.append(record[i:])
                quoted_flags.append(False)
                break
            else:
                fields.append(record[i:end])
                quoted_flags.append(False)
                i = end + 1
                if i == len(record):
                    fields.append("")
                    quoted_flags.append(False)
                    break
    return fields, quoted_flags


def fields_to_line(fields, quoted_flags):
    """フィールドとクォートフラグからCSV行文字列（改行なし）を生成"""
    parts = []
    for f, q in zip(fields, quoted_flags):
        if q:
            parts.append('"' + f.replace('"', '""') + '"')
        else:
            parts.append(f)
    return ",".join(parts)

def clean_fields(fields, quoted_flags):
    """フィールド内の改行をスペースに置換"""
    cleaned = [f.replace("\r\n", " ").replace("\r", " ").replace("\n", " ") for f in fields]
    return cleaned, quoted_flags

def expand_unix_time(fields, quoted_flags):
    """
    0列目のUNIXタイムを 日付,時刻 の2フィールドに展開して置き換える。
    例: [1772856950, 60891260, ...] → [2026/03/25, 10:14:13, 60891260, ...]
    """
    if not fields:
        return fields, quoted_flags
    date_str, time_str = unix_to_jst(fields[0])
    new_fields = [date_str, time_str] + fields[1:]
    new_flags  = [False, False] + list(quoted_flags[1:])
    return new_fields, new_flags

def split_csv(
    input_path: str,
    max_size: int,
    output_dir: str = None,
    has_header: bool = True,
    encoding: str = "utf-8",
    prefix: str = None,
    digits: int = 4,
    replace_first_record: str = None,
    insert_before_first: list = None,
    convert_unixtime: bool = False,   # ★ 追加
):
    if not os.path.isfile(input_path):
        print(f"[ERROR] ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    input_size = os.path.getsize(input_path)
    print(f"入力ファイル : {input_path}")
    print(f"ファイルサイズ: {input_size:,} bytes ({input_size/1024**2:.1f} MB)")
    print(f"分割サイズ  : {max_size:,} bytes ({max_size/1024**2:.1f} MB)")

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_path))
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    file_prefix = prefix if prefix else base_name

    header_fields = None
    header_raw    = None
    file_index = 1
    current_size = 0
    out_file = None
    lines_in_file = 0
    total_records = 0
    skipped_records = 0
    created_files = []
    is_first_record = True

    def ensure_newline(s: str) -> str:
        return s if s.endswith("\n") else s + "\n"

    def close_current():
        nonlocal out_file
        if out_file:
            out_file.write("\n")
            out_file.close()
            out_file = None

    def open_next():
        nonlocal out_file, current_size, lines_in_file
        close_current()
        filename = f"{file_prefix}_{str(file_index).zfill(digits)}.csv"
        path = os.path.join(output_dir, filename)
        created_files.append(path)
        out_file = open(path, "w", encoding=encoding, newline="")
        current_size = 0
        lines_in_file = 0

        if has_header and header_fields is not None:
            if insert_before_first is not None:
                for rec in insert_before_first:
                    line = ensure_newline(rec)
                    out_file.write(line)
                    current_size += len(line.encode(encoding))
                    lines_in_file += 1
                commented = ensure_newline("#" + header_raw)
                out_file.write(commented)
                current_size += len(commented.encode(encoding))
                lines_in_file += 1
            else:
                line = ensure_newline(header_raw)
                out_file.write(line)
                current_size += len(line.encode(encoding))
                lines_in_file += 1
        print(f"  → 作成中: {filename}")

    def write_record(fields, quoted_flags):
        nonlocal current_size, lines_in_file, total_records
        line = fields_to_line(fields, quoted_flags) + "\n"
        out_file.write(line)
        current_size += len(line.encode(encoding))
        lines_in_file += 1
        total_records += 1

    with open(input_path, "r", encoding=encoding, newline="") as f:
        line_iter = iter(f)
        record_index = 0

        while True:
            result = parse_record(line_iter)
            if result is None:
                break
            fields, quoted_flags = result

            # ── ヘッダー行 ──────────────────────────────────────
            if record_index == 0 and has_header:
                fields, quoted_flags = clean_fields(fields, quoted_flags)
                # ★ ヘッダーの0列目も展開（time → date, time）
                if convert_unixtime:
                    fields = ["date", "time"] + fields[1:]
                    quoted_flags = [False, False] + list(quoted_flags[1:])
                header_fields = fields
                header_raw = fields_to_line(fields, quoted_flags)
                open_next()
                if insert_before_first is not None:
                    print(f"  [挿入] ヘッダーの前に {len(insert_before_first)} 行を挿入し、元ヘッダーに # を付けました")
                record_index += 1
                continue

            if out_file is None:
                open_next()

            # 空レコードはスキップ
            if len(fields) == 0 or (len(fields) == 1 and fields[0].strip() == ""):
                skipped_records += 1
                record_index += 1
                continue

            # ── 先頭データ行の処理（replace-first のみ）──────────
            if is_first_record:
                is_first_record = False
                if replace_first_record is not None:
                    result2 = parse_record(iter(io.StringIO(replace_first_record)))
                    if result2:
                        fields, quoted_flags = result2
                    print(f"  [置換] 先頭レコードを入力値に置き換えました")

            # フィールド内改行をスペースに置換
            fields, quoted_flags = clean_fields(fields, quoted_flags)

            # ★ UNIXタイム変換
            if convert_unixtime:
                fields, quoted_flags = expand_unix_time(fields, quoted_flags)

            # ── 通常レコード ─────────────────────────────────────
            record_size = len((fields_to_line(fields, quoted_flags) + "\n").encode(encoding))
            min_data_lines = 1 if has_header else 0
            if lines_in_file > min_data_lines and current_size + record_size > max_size:
                file_index += 1
                open_next()

            write_record(fields, quoted_flags)
            record_index += 1

    close_current()

    print(f"\n完了!")
    print(f"  総レコード数 : {total_records:,} 件")
    print(f"  スキップ数   : {skipped_records:,} 件 (空レコード)")
    print(f"  生成ファイル数: {len(created_files)} ファイル")
    print(f"  出力先       : {output_dir}")
    return created_files


def main():
    parser = argparse.ArgumentParser(
        description="大容量CSVファイルを指定サイズに分割します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python split_csv.py data.csv -s 100MB
  python split_csv.py data.csv -s 500MB -o ./output --no-header
  python split_csv.py data.csv -s 1GB -e shift-jis -p chunk -d 3
  python split_csv.py data.csv -s 100MB --replace-first "001,新レコード,値A,値B"
  python split_csv.py data.csv -s 100MB \\
      --insert-before-first '#!mbspd' \\
      --insert-before-first 'time,mem_id,$subject,$body'
  python split_csv.py data.csv -s 100MB --convert-unixtime
        """,
    )
    parser.add_argument("input", help="入力CSVファイルのパス")
    parser.add_argument(
        "-s", "--size", default="100MB",
        help="1ファイルあたりの最大サイズ (例: 100MB, 1GB, 500KB)  [デフォルト: 100MB]",
    )
    parser.add_argument(
        "-o", "--output-dir", default=None,
        help="出力ディレクトリ (デフォルト: 入力ファイルと同じ場所)",
    )
    parser.add_argument(
        "--no-header", action="store_true",
        help="ヘッダー行なし（指定した場合、各分割ファイルにヘッダーをコピーしない）",
    )
    parser.add_argument(
        "-e", "--encoding", default="utf-8",
        help="ファイルエンコーディング (例: utf-8, shift-jis, cp932)  [デフォルト: utf-8]",
    )
    parser.add_argument(
        "-p", "--prefix", default=None,
        help="出力ファイル名のプレフィックス (デフォルト: 入力ファイル名)",
    )
    parser.add_argument(
        "-d", "--digits", type=int, default=4,
        help="通し番号の桁数 (ゼロ埋め)  [デフォルト: 4]",
    )
    parser.add_argument(
        "--replace-first", default=None, metavar="RECORD",
        help="先頭の1レコード（ヘッダー直後の行）を指定した文字列に置き換える\n"
             '例: --replace-first "001,山田太郎,東京,100"',
    )
    parser.add_argument(
        "--insert-before-first", default=None, metavar="RECORD",
        action="append",
        help="ヘッダーの前に挿入する行（複数回指定可）。元のヘッダーには # が付く\n"
             "例: --insert-before-first '#!mbspd' --insert-before-first 'time,mem_id,$subject,$body'",
    )
    parser.add_argument(
        "--convert-unixtime", action="store_true",          # ★ 追加
        help="0列目のUNIXタイムをJSTの 日付,時刻 2フィールドに展開する\n"
             "例: 1772856950 → 2026/03/25,10:14:13",
    )

    args = parser.parse_args()

    max_size = parse_size(args.size)
    if max_size <= 0:
        print("[ERROR] サイズは正の値を指定してください", file=sys.stderr)
        sys.exit(1)

    split_csv(
        input_path=args.input,
        max_size=max_size,
        output_dir=args.output_dir,
        has_header=not args.no_header,
        encoding=args.encoding,
        prefix=args.prefix,
        digits=args.digits,
        replace_first_record=args.replace_first,
        insert_before_first=args.insert_before_first,
        convert_unixtime=args.convert_unixtime,
    )


if __name__ == "__main__":
    main()

    
# 出力イメージ：
# header,col1,col2
# #!mbspd            ← 挿入1行目
# 000,挿入行,X,Y     ← 挿入2行目
# #AAA,1,2           ← 元の先頭レコード（# 付き）
# BBB,3,4
# CCC,5,6

# python split_csv.py data.csv -s 100MB \
#   --insert-before-first "#!mbspd" \
#   --insert-before-first "000,挿入行,X,Y"

# python .\split_csv.py .\diary_data.20260325_101413_sjis.csv \
#  -s 300M -e cp932 -p SPD_diary -d 3  \
#  --insert-before-first '#!mbspd' \
#  --insert-before-first 'time,mem_id,$subject,$body'