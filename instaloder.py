import sys
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import instaloader
except ImportError:
    # インポート失敗時に実行中のPythonパスを表示して確認できるようにする
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("インポートエラー", f"ライブラリ 'instaloader' が見つかりません。\n\n現在実行中のPython:\n{sys.executable}\n\nインストール先 (Python 3.14) と一致しているか確認してください。")
    sys.exit(1)

import threading
import re
import os
import subprocess


class InstaDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Downloader")
        self.root.geometry("350x375")
        self.root.resizable(False, False)
        self.is_logged_in = False  # ログイン状態を管理

        # Instaloaderのインスタンス化
        self.L = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True, 
            download_video_thumbnails=False,
            download_geotags=False, 
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )

        # UIの構築
        self.create_widgets()

    def create_widgets(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タイトルラベル
        title_label = ttk.Label(main_frame, text="Instagram URLを入力してください", font=("Helvetica", 12))
        title_label.pack(pady=(0, 10))

        # URL入力フィールド
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(pady=5)
        self.url_entry.focus()

        # ログイン設定エリア
        login_frame = ttk.LabelFrame(main_frame, text="ログイン設定 (任意)", padding="10")
        login_frame.pack(fill=tk.X, pady=10)

        self.use_login_var = tk.BooleanVar(value=False)
        self.login_check = ttk.Checkbutton(login_frame, text="ログインしてダウンロードする", variable=self.use_login_var, command=self.toggle_login_inputs)
        self.login_check.pack(anchor=tk.W, pady=(0, 5))

        # ユーザー名・パスワード入力グリッド
        input_frame = ttk.Frame(login_frame)
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="ユーザー名:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(input_frame, textvariable=self.username_var, state=tk.DISABLED)
        self.username_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)

        ttk.Label(input_frame, text="パスワード:").grid(row=1, column=0, padx=5, sticky=tk.W)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(input_frame, textvariable=self.password_var, show="*", state=tk.DISABLED)
        self.password_entry.grid(row=1, column=1, padx=5, sticky=tk.EW)
        
        input_frame.columnconfigure(1, weight=1)

        # ダウンロードボタン
        self.download_btn = ttk.Button(main_frame, text="ダウンロード開始", command=self.start_download_thread)
        self.download_btn.pack(pady=15)

        # ステータスラベル
        self.status_var = tk.StringVar(value="待機中...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(pady=10)

        # 注意書き
        note_label = ttk.Label(main_frame, text="※ 公開アカウントの投稿のみ対応しています", font=("Helvetica", 10, "bold"))
        note_label.pack(side=tk.BOTTOM)

    def toggle_login_inputs(self):
        state = tk.NORMAL if self.use_login_var.get() else tk.DISABLED
        self.username_entry.config(state=state)
        self.password_entry.config(state=state)

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

    def download_post(self, url):
        try:
            # ログイン処理 (チェックが入っていて、まだログインしていない場合)
            if self.use_login_var.get() and not self.is_logged_in:
                username = self.username_var.get().strip()
                password = self.password_var.get().strip()
                
                if not username or not password:
                    raise ValueError("ログインする場合はユーザー名とパスワードを入力してください。")
                
                self.update_status("ログイン中...")
                try:
                    self.L.login(username, password)
                    self.is_logged_in = True
                except instaloader.TwoFactorAuthRequiredException:
                    raise ValueError("二段階認証が有効なアカウントはこのツールではサポートされていません。")
                except instaloader.BadCredentialsException:
                    raise ValueError("ユーザー名またはパスワードが間違っています。")
                # その他のログインエラーは外側のexceptでキャッチ

            # URLからショートコードを抽出 (例: /p/ShortCode/)
            # 対応: p=通常投稿, reel/reels=リール, tv=IGTV
            match = re.search(r'(p|reel|reels|tv)/([^/?#&]+)', url)
            
            if not match:
                raise ValueError("有効なInstagramの投稿URLではありません。")
            
            shortcode = match.group(2)
            self.update_status(f"メタデータを取得中... ({shortcode})")

            # 保存先ディレクトリの設定
            target_dir = "downloads"
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            # 投稿オブジェクトの取得
            post = instaloader.Post.from_shortcode(self.L.context, shortcode)

            self.update_status("ダウンロード中...")
            
            # ダウンロード実行 (targetディレクトリの中にショートコード名のフォルダが作られないよう調整)
            # Instaloaderはデフォルトでターゲット名のフォルダを作るため、
            # ここではシンプルにdownloadsフォルダへ保存するようchdirを使う方法をとります
            cwd = os.getcwd()
            os.chdir(target_dir)
            
            try:
                self.L.download_post(post, target=shortcode)
            finally:
                # 元のディレクトリに戻る
                os.chdir(cwd)

            self.update_status("ダウンロード完了！")
            
            # 保存先のフルパスを取得してエクスプローラーを開く
            save_path = os.path.abspath(os.path.join(target_dir, shortcode))
            if sys.platform == 'win32':
                os.startfile(save_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', save_path])
            else:  # Linuxなど
                subprocess.Popen(['xdg-open', save_path])

            messagebox.showinfo("成功", f"ダウンロードが完了しました。\n保存先: {save_path}")

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                error_msg = "ログインが必要です（非公開アカウントの可能性があります）。"
            elif "404" in error_msg:
                error_msg = "投稿が見つかりません。"
            
            self.update_status("エラーが発生しました")
            messagebox.showerror("エラー", f"ダウンロードに失敗しました:\n{error_msg}")
        
        finally:
            # ボタンを再度有効化（メインスレッドから操作する必要があるためafterを使用）
            self.root.after(0, lambda: self.download_btn.config(state=tk.NORMAL))

    def update_status(self, message):
        self.status_var.set(message)


if __name__ == "__main__":
    root = tk.Tk()
    app = InstaDownloaderApp(root)
    root.mainloop()