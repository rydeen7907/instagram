import instaloader # Instagramの投稿をダウンロードするためのライブラリ
import re # 正規表現
import os # ファイルパスの操作
import time # 待機時間のために使用
import random # ランダムな待機時間を生成するために使用


class InstagramDownloader:
    def __init__(self):
        # Instaloaderの初期化
        self.L = instaloader.Instaloader(
            # 画像をダウンロードするか
            download_pictures=True,
            # 動画をダウンロードするか
            download_videos=True,
            # 動画のサムネイルをダウンロードするか
            download_video_thumbnails=False,
            # ジオタグをダウンロードするか
            download_geotags=False,
            # コメントをダウンロードするか
            download_comments=False,
            # メタデータを保存するか
            save_metadata=False,
            # JSONを圧縮するか
            compress_json=False,
            # ユーザーエージェントを指定
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" 
        )
        self.is_logged_in = False # ログイン状態を管理するフラグ

    def login(self, username, password):
        """Instagramにログインする(セッションの保存と再利用をサポート)"""
        try:
            # 1. 保存されたセッションの読み込みを試行 (ログインの手間と制限を回避)
            try:
                self.L.load_session_from_file(username)
                self.is_logged_in = True
                return True, "保存されたセッションを使用してログインしました。"
            except FileNotFoundError:
                # セッションファイルがない場合は通常のログインへ進む
                pass
            except Exception:
                # セッションが無効などの場合も通常のログインへ進む
                pass

            # 2. 通常のログインを実行
            self.L.login(username, password)
            
            # 3. ログイン成功後にセッションを保存
            self.L.save_session_to_file()
            
            self.is_logged_in = True
            return True, "ログイン成功！"
        
        except instaloader.TwoFactorAuthRequiredException:
            self.is_logged_in = False
            return False, "二段階認証が必要です。ブラウザでログインを確認してから再度試してください。"
        except instaloader.BadCredentialsException:
            self.is_logged_in = False
            return False, "ユーザー名またはパスワードが間違っています。"
        except Exception as e:
            self.is_logged_in = False
            return False, f"ログインに失敗しました:\n{str(e)}"
        
    def extract_shortcode(self, url):
        """URLからショートコードを抽出する"""
        match = re.search(r'(p|reel|reels|tv)/([^/?#&]+)', url)
        if match:
            return match.group(2) 
        return None

    def download_post(self, url, status_callback):
        """投稿をダウンロードする。status_callbackは進捗メッセージを送るための関数"""
        try:
            shortcode = self.extract_shortcode(url)
            if not shortcode:
                raise ValueError("有効なInstagramの投稿URLではありません。")

            status_callback("準備中...")

            # 自動操作の検知回避
            time.sleep(random.uniform(1.0, 3.0)) # 1〜3秒のランダムな待機時間を追加

            status_callback(f"メタデータを取得中... ({shortcode})")

            # システムの「ダウンロード」フォルダのパスを取得し、その中にInstagram用のフォルダを作成
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            target_base = os.path.join(downloads_dir, "Instagram_Downloads")

            if not os.path.exists(target_base): 
                os.makedirs(target_base)

            # 投稿オブジェクトの取得
            post = instaloader.Post.from_shortcode(self.L.context, shortcode)
            # 投稿者のユーザー名を取得
            username = post.owner_username

            status_callback("ダウンロード中...")

            # 保存先の絶対パスを作成（ユーザー別のフォルダ）
            abs_target_path = os.path.join(target_base, username)

            # instaloaderが絶対パスを「フォルダ名」として誤認しないよう、
            # 保存先の親ディレクトリへ一時的に移動してダウンロードを実行する
            current_cwd = os.getcwd()
            os.chdir(target_base)
            try:
                self.L.download_post(post, target=username)
            finally:
                # 作業ディレクトリを元に戻す
                os.chdir(current_cwd)

            return True, abs_target_path

        except Exception as e:
            # エラーメッセージをユーザーフレンドリーなものに変換
            error_msg = str(e) 
            # エラーメッセージを取得
            friendly_msg = self._get_friendly_error_message(error_msg)
            # エラーメッセージを返す 
            return False, friendly_msg 

    def _get_friendly_error_message(self, error_msg):
        """エラーメッセージをユーザーフレンドリーなものに変換する"""
        if "403" in error_msg or "login_required" in error_msg:
            return "Instagramから一時的な制限を受けています (403 Forbidden)。\n\n原因:\n・ログイン済みでも、高画質メタデータの取得が拒否されることがあります（Instagram側の厳しい制限）。\n・短時間の連続操作による制限。\n\n状況:\nフォルダ内にファイルが保存されている場合は、そのまま利用可能です。ファイルがない場合は、1時間ほど時間を置いてから再度試してください。"
        elif "401" in error_msg:
            return "ログインが必要です（非公開アカウントの可能性があります）。"
        elif "404" in error_msg:
            return "投稿が見つかりません。"
        elif "Too many queries" in error_msg:
            return "リクエスト制限に達しました。しばらく時間を置いてください。"
        return f"エラーが発生しました:\n{error_msg}"