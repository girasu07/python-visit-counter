# 岐大祭 来場者カウンター：委員限定公開の追加セット

既存の main-tate.py は変更しません。このフォルダを既存Gitリポジトリに追加して使います。
添付Markdownは引用符・インデントが変換されているためPythonとして上書きしないでください。
既存のローカルAPI http://127.0.0.1:8000/api/counts を送信プログラムが10秒ごとに読みます。
映像・カメラURL・パスワード・追跡IDは送信しません。

## 構成
- counter.girasu.dev：委員がAccessログインして閲覧するサイト
- counter-ingest.girasu.dev/api/upload：Windows専用の送信先。32文字以上の専用トークンで認証
- D1：各日最後に届いた累計を保存（1台用）
- Windows：従来どおりSQLiteに入退場イベントを保存。送信は別プロセス

## 1. Cloudflareの準備（MacでもWindowsでも可）
Node.js/npmを利用できるPCで、workerフォルダに移動し、以下を1つずつ実行。

```sh
npm install
npx wrangler login
npx wrangler d1 create gidaisai-counter
```
作成結果の database_id を wrangler.jsonc の REPLACE に設定。
npm install が作成した package-lock.json もGitに含めて、次回以降は npm ci を使用。

## 2. 閲覧用のCloudflare Accessを先に設定
Cloudflare Zero Trust → Access → Applications → Add an application → Self-hosted。
- ホスト名 counter.girasu.dev、パス指定なし（サイト全体）。
- Allowポリシー：閲覧を許可する委員のメールアドレスを指定。
- ワンタイムPIN等、利用するログイン方式を有効にする。
- Everyone / Bypass のポリシーは追加しない。
- アプリのAUDを wrangler.jsonc の ACCESS_AUD に設定。
- チームドメイン（https://チーム名.cloudflareaccess.com、末尾スラッシュなし）を TEAM_DOMAIN に設定。
- counter-ingest.girasu.dev は閲覧用Accessアプリの対象に含めない。送信専用Bearer認証で保護する。
  既存の *.girasu.dev アプリがある場合は競合するため、その構成を確認してから進める。

WorkerもJWTの署名・発行者・対象アプリ・有効期限を検証します。Access未設定や設定漏れでは閲覧を拒否します。
送信先ホストから人数を読むことはできません。workers.dev / preview URL は無効です。

## 3. 送信トークンとDBを用意
送信専用のランダムなトークンを生成し、パスワード管理ツールなどに保管。
Mac例：
```sh
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Windowsでは python3 を、利用中のPython実行ファイルに読み替えてください。
カメラのパスワードやCloudflare APIトークンを流用しないでください。

workerフォルダで実行し、先ほど生成した送信専用トークンを入力：
```sh
npx wrangler secret put UPLOAD_TOKEN
npx wrangler d1 migrations apply gidaisai-counter --remote
npm test
npx wrangler deploy
```
最後のコマンドが実際の公開操作です。Cloudflareアカウントに girasu.dev のゾーンが必要です。
このセットはまだデプロイされていません。DB・Access・ドメインはユーザーの環境で設定してください。

## 4. Windowsで人数を送信
通常どおり main-tate.py を起動。カメラがなくても --web-only で配信確認ができます（表示は計測停止）。
もう1つPowerShellを開き、追加セットのあるフォルダへ移動して実行：

```powershell
$env:COUNTER_UPLOAD_URL = 'https://counter-ingest.girasu.dev/api/upload'
& 'C:\dev\visiter-counter\.venv\Scripts\python.exe' .\upload_counts.py
```
「送信専用トークン」に手順3の値を入力（非表示）。Python標準機能のみで追加pip不要。
Windowsの時計は自動同期を有効にしてください（サーバーと5分超ずれると送信を拒否）。
終了はCtrl+C。計測と送信の両方を稼働し続ける必要があります。
Macなら同じフォルダで export COUNTER_UPLOAD_URL='https://counter-ingest.girasu.dev/api/upload' の後 python3 upload_counts.py。

## 5. 公開後に確認
1. 許可メールでサイトにログインできる。未許可メールは拒否される。
2. サイトの入場・退場・滞在人数がlocalhost画面と一致する。
3. 送信プログラムだけ停止し、約40秒後に通信断表示となる。
4. 再起動すると、差分加算でなく最新累計の上書きで復旧する（二重加算しない）。
5. カメラ未接続／--web-only では「映像処理が停止・遅延」と表示する。
6. counter-ingest.girasu.dev にブラウザでアクセスしても人数は表示されない。

## 保存と制約
- ローカルSQLiteが正本。DBを削除しないでください。MacとWindowsのDBは自動統合されません。
- 各日最後の受信値をD1に保存。時間帯別の推移や入退場イベントのクラウドバックアップは未実装。
- 通信断後は最新の日次累計を送信。日をまたぐ通信断では前日最終値を自動補完しません。前日の完全な記録はPC内SQLiteにあります。
- 現在のカウントはJST日次集計で、日をまたぐ滞在人数は引き継ぎません。
- カメラ1台／送信元PC1台用。同じ集計をMacとWindowsから同時に送らないでください。
- 古い／重複した時刻の送信では保存値や受信時刻を更新しません。
- 計測中にPC時計を戻した場合は新しい時刻が前回を超えるまで更新が拒否されます。
- Wi-Fi由来の映像エラーやYOLOの遅延を直す変更は含みません。有線で別途確認します。
- 通信・D1・Accessの利用料金／ユーザー数上限は契約プランで確認してください。

公式資料：
https://developers.cloudflare.com/d1/get-started/
https://developers.cloudflare.com/d1/reference/migrations/
https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
