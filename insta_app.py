"""
    Instagramの投稿をダウンロードするGUIアプリケーション
    起動ファイル： insta_app.py
"""

import sys
import tkinter as tk
from tkinter import messagebox, ttk
# --- カスタムモジュール ---
from insta_downloader import InstagramDownloader

try:
    import instaloader
except ImportError:
    # インポート失敗時に実行中のPythonパスを表示して確認できるようにする
    root = tk.Tk()
    root.withdraw() # メインウィンドウを表示しない
    messagebox.showerror("インポートエラー", f"ライブラリ 'instaloader' が見つかりません。\n\n'pip install instaloader' が完了しているか確認してください。\n\n現在実行中のPython:\n{sys.executable}")
    sys.exit(1) # 異常終了

import threading # ダウンロード処理を別スレッドで実行するために使用
import os # ファイルパスの操作のために使用
import subprocess # ダウンロード後にフォルダを開くために使用


class InstaDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Downloader")
        self.root.geometry("350x400") # 幅 x 高さ
        self.root.resizable(False, False) # サイズ変更不可

        # ダウンローダーのインスタンス化
        self.downloader = InstagramDownloader()

        # UIの構築
        self.create_widgets()

        # Escキーで終了するイベントをバインド
        self.root.bind("<Escape>", self.exit_app)

        # 起動直後に警告を表示（ウィンドウ表示から少し遅らせる）
        self.root.after(500, self.show_startup_warning)

    def create_widgets(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True) # フレームをウィンドウ全体に広げる

        # タイトルラベル
        title_label = ttk.Label(main_frame, text="Instagram URLを入力してください", font=("Helvetica", 12))
        title_label.pack(pady=(0, 10))

        # URL入力フィールド
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(pady=5)
        self.url_entry.focus()

        # ログイン設定エリア
        login_frame = ttk.LabelFrame(main_frame, text="ログイン設定 (必須)", padding="10")
        login_frame.pack(fill=tk.X, pady=10)

        # ユーザー名・パスワード入力グリッド
        input_frame = ttk.Frame(login_frame)
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="ユーザー名:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(input_frame, textvariable=self.username_var, state=tk.NORMAL)
        self.username_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)

        ttk.Label(input_frame, text="パスワード:").grid(row=1, column=0, padx=5, sticky=tk.W)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(input_frame, textvariable=self.password_var, show="*", state=tk.NORMAL)
        self.password_entry.grid(row=1, column=1, padx=5, sticky=tk.EW)

        input_frame.columnconfigure(1, weight=1)

        # ログインボタン
        self.login_btn = ttk.Button(login_frame, text="ログイン", command=self.start_login_thread, state=tk.NORMAL)
        self.login_btn.pack(pady=(5, 0))

        # ダウンロードボタン
        self.download_btn = ttk.Button(main_frame, text="ダウンロード開始", command=self.start_download_thread)
        self.download_btn.pack(pady=15)

        # ステータスラベル
        self.status_var = tk.StringVar(value="待機中...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(pady=(10, 0))

        # 注意書き
        note_frame = ttk.Frame(main_frame)
        note_frame.pack(side=tk.BOTTOM, pady=(0, 5))

        ttk.Label(note_frame, text="※ 高画質・安定性のために「ログイン」を強く推奨します", font=("Helvetica", 9, "bold"), foreground="blue").pack()
        ttk.Label(note_frame, text="※ 公開アカウントの投稿のみ対応しています", font=("Helvetica", 9), foreground="red").pack()

    def show_startup_warning(self):
        messagebox.showwarning("【重要】利用上の制限とご注意", "短時間に連続して大量のダウンロードを行うと、Instagramからスパム行為と見なされ、一時的なアクセス制限やアカウント停止措置を受ける恐れがあります。\n\n・連続使用は避け、1件ごとに十分な間隔を空けてください。\n・一度に数十件以上の保存は推奨しません。\n・APIの制限を回避するため、ログインしての使用を強く推奨します。")

    def start_download_thread(self):
        """UIのフリーズを防ぐために別スレッドでダウンロードを実行"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("入力エラー", "URLを入力してください。")
            return

        self.download_btn.config(state=tk.DISABLED)
        self.status_var.set("処理中...")

        # スレッド開始
        thread = threading.Thread(target=self.download_post, args=(url,))
        thread.daemon = True
        thread.start()

    def start_login_thread(self):
        """UIのフリーズを防ぐために別スレッドでログインを実行"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            self.root.after(0, lambda: messagebox.showwarning("入力エラー", "ログインするにはユーザー名とパスワードを入力してください。"))
            return

        self.login_btn.config(state=tk.DISABLED) # ログイン中はログインボタンも無効化
        self.download_btn.config(state=tk.DISABLED) # ログイン中はダウンロードボタンも無効化
        self.update_status("ログイン処理中...")

        # ログイン処理を別スレッドで実行
        thread = threading.Thread(target=self.login_account, args=(username, password))
        # メインスレッド終了時に自動的に終了するように設定
        thread.daemon = True
        thread.start() 

    def login_account(self, username, password):
        """Instaloaderでログインを実行するメソッド"""
        self.update_status("ログイン中...")
        success, message = self.downloader.login(username, password)

        if success:
            self.update_status(message)
            self.root.after(0, lambda: messagebox.showinfo("ログイン", message))
        else:
            self.update_status("エラーが発生しました")
            self.root.after(0, lambda: messagebox.showerror("ログインエラー", message))

        self.root.after(0, lambda: self.login_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.download_btn.config(state=tk.NORMAL))

    def download_post(self, url):
        """Instaloaderでダウンロードを実行するメソッド"""
        try:
            # ログインが必要だがまだログインしていない場合
            if not self.downloader.is_logged_in:
                username = self.username_var.get().strip() # usernameを取得
                password = self.password_var.get().strip() # passwordを取得

                if not username or not password:
                    raise ValueError("ログインする場合はユーザー名とパスワードを入力してください。")

                self.update_status("自動ログイン中...")
                success, msg = self.downloader.login(username, password)
                if not success:
                    raise ValueError(msg)

            # 分離したダウンローダーのメソッドを呼び出す
            success, result = self.downloader.download_post(url, self.update_status)

            if not success:
                raise Exception(result)

            self.update_status("ダウンロード完了！")
            # パスの区切り文字などをOSに合わせて正規化
            save_path = os.path.normpath(result)

            if os.path.exists(save_path):
                if sys.platform == 'win32':
                    os.startfile(save_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.Popen(['open', save_path])
                else:  # Linuxなど
                    subprocess.Popen(['xdg-open', save_path])
                self.root.after(0, lambda: messagebox.showinfo("成功", f"ダウンロードが完了しました。\n保存先: {save_path}"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("警告", "処理は終了しましたが、保存先フォルダが見つかりませんでした。"))

        except Exception as e:
            self.update_status("エラーが発生しました")
            self.root.after(0, lambda: messagebox.showerror("エラー", f"ダウンロードに失敗しました:\n{str(e)}"))

        finally:
            # ボタンを再度有効化（メインスレッドから操作する必要があるためafterを使用）
            self.root.after(0, lambda: self.download_btn.config(state=tk.NORMAL))

    def update_status(self, message):
        # UIの更新はメインスレッドで行う
        self.root.after(0, lambda: self.status_var.set(message))

    def exit_app(self, event=None):
        """アプリケーションを終了する"""
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = InstaDownloaderApp(root)
    root.mainloop()