import os
import socket
import time
from enum import IntEnum
from dataclasses import dataclass
# from .errors import error_dictionary

class Status(IntEnum):
    OK = 0
    ERROR = -1
    EXIT = -9

@dataclass(frozen=True)
class Config:
    """プロトコル設定"""
    VERSION = b"MB000001"
    HEADER_SIZE = 32
    HEADER_WITH_NL = 33
    MAX_BUFFER = 1024 * 1024 * 10
    ENCODING = "cp932"
    
    PORT = int(os.getenv("SYNAPSE_DEFAULT_PORT", "65001"))
    HOST = os.getenv("SYNAPSE_DEFAULT_URL", "localhost")
    MAX_RETRY = 5
    RETRY_DELAY = 1.0


class Header:
    """プロトコルヘッダー"""
    __slots__ = ('version', 'size', 'error', 'command', 'time')
    
    def __init__(self, data: bytes):
        self.version = data[0:8].decode()
        self.size = int(data[8:16].decode().lstrip("0") or "0", 16)
        self.error = int(data[16:20].decode().lstrip("0") or "0", 16)
        self.command = int(data[20:24].decode(), 16)
        self.time = float(data[24:32].decode())
    
    @property
    def error_msg(self) -> str:
        if not self.error:
            return ""
        hex_str = f"{self.error:04x}".upper()
        return f"{hex_str} : {error_dictionary.get(self.error, 'Unknown')}"
    
    @staticmethod
    def build(cmd: int, err: int, size: int, t: float) -> bytes:
        h = bytearray(28)
        h[0:8] = Config.VERSION
        h[8:16] = f"{size:08x}".encode()
        h[16:20] = f"{err:04x}".encode()
        h[20:24] = f"{cmd:04x}".encode()
        h[24:32] = f"{t:08.2f}".encode()
        return bytes(h)


class MBClient:
    """MBクライアント"""

    def __init__(self):
        pass
    
    def __del__(self):
        self.close()
    
    def connect(self, host: str = Config.HOST, port: int = Config.PORT) -> bool:
        """サーバー接続"""
        for i in range(Config.MAX_RETRY + 1):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((host, port))
                print(f"Connected to {host}:{port}")
                return True
            except OSError as e:
                print(f"Connect failed (attempt {i+1}): {e}")
                if i < Config.MAX_RETRY:
                    time.sleep(Config.RETRY_DELAY)
        return False
    
    def close(self):
        """接続を閉じる"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def send(self, cmd: str) -> Status:
        """コマンド送信"""
        self._response = ""
        if not cmd or not self.sock:
            return Status.OK if not cmd else Status.ERROR
        
        try:
            # 送信
            data = cmd.encode(Config.ENCODING)
            header = Header.build(0, 0, len(data), 0.0)
            self.sock.send(header + b'\n' + data)
            
            # 受信
            raw_header = self.sock.recv(Config.HEADER_WITH_NL)
            if len(raw_header) < Config.HEADER_WITH_NL:
                return Status.ERROR
            
            header = Header(raw_header[:Config.HEADER_SIZE])
            if not 0 <= header.size <= Config.MAX_BUFFER:
                return Status.ERROR
            
            # ボディ受信
            body = b""
            while len(body) < header.size:
                chunk = self.sock.recv(header.size - len(body))
                if not chunk:
                    break
                body += chunk
            
            if len(body) != header.size:
                return Status.ERROR
            
            self._response = raw_header.decode(Config.ENCODING, "ignore") + "\n" + \
                           body.decode(Config.ENCODING, "ignore")
            return Status.OK
            
        except OSError as e:
            print(f"Communication error: {e}")
            return Status.ERROR
    
    # set file command
    def file_send(self, file_name : str) -> Status:
        try:
            if not os.path.exists(file_name):
                print("File not found")
                raise StopIteration
        
            file_size = os.path.getsize(file_name)
        
            if file_size > (1024*1024*1024):
                print(f"ファイルサイズが大き過ぎます({file_size}byte)")
                raise StopIteration
        
            # 'set open file_size filename' コマンド送信
            command = f"set open {file_size} {file_name}"
            print(f"COM={command}")

            # 送信
            data = command.encode(Config.ENCODING)
            header = Header.build(0, 0, len(data), 0.0)
            self.sock.send(header + b'\n' + data)
            
            # 受信
            raw_header = self.sock.recv(Config.HEADER_WITH_NL)
            if len(raw_header) < Config.HEADER_WITH_NL:
                raise StopIteration
            
            header = Header(raw_header[:Config.HEADER_SIZE])
            if not 0 <= header.size <= Config.MAX_BUFFER:
                raise StopIteration
            
            with open(file_name, "rb") as f:
                file_data = f.read()
        
                # 送信
                data = file_data
                header = Header.build(0, 0, len(data), 0.0)
                self.sock.send(header + b'\n' + data)

            # 受信
            raw_header = self.sock.recv(Config.HEADER_WITH_NL)
            if len(raw_header) < Config.HEADER_WITH_NL:
                return Status.ERROR
            
        except StopIteration:
            pass  # C++のbreakに相当
        except FileNotFoundError:
            print("File not found")
        except OSError as e:
            print(f"ファイルエラー: {e}")
        except Exception as e:
            print(f"予期しないエラー: {e}")

    @property
    def header(self) -> str:
        return self._response[:Config.HEADER_WITH_NL] if self._response else ""
    
    @property
    def body(self) -> str:
        return self._response[Config.HEADER_WITH_NL:] if self._response else ""
    
    @property
    def header_dict(self) -> dict:
        if not self._response:
            return {}
        try:
            h = Header(self.header.encode()[:Config.HEADER_SIZE])
            return {
                "version": h.version,
                "size": f"{h.size:08x}",
                "error": h.error_msg,
                "time": f"{h.time:08.2f}",
            }
        except:
            return {}
    
    def raise_on_error(self):
        """エラー時に例外発生"""
        if self._response:
            h = Header(self.header.encode()[:Config.HEADER_SIZE])
            if h.error:
                raise Exception(f"MB ERROR: {h.error_msg}")

def main():
    """テスト"""
    try:
        client = MBClient()
        if client.connect() == False:
            print("Failed to connect.")
            return
        while True:
            cmd = input("Command: ")
            if not cmd or client.send(cmd) != Status.OK:
                break
            print(client.body)
    except (KeyboardInterrupt, Exception) as e:
        print(f"\n{e}")

if __name__ == "__main__":
    main()