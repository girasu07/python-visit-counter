# 来場者カウンター

YOLOv8で人物を検出し、ByteTrackで追跡した人物が画面中央の線を横切ると入退場を記録するプロトタイプです。縦線版は人数のSQLite保存とブラウザでの閲覧に対応しています。

RTSPカメラで受信と認識を分ける場合は `visitor_counter.py` を使用します。

## ファイル構成

| ファイル | 内容 |
| --- | --- |
| `visitor_counter.py` | 縦線版。RTSP受信を別スレッドで行い、最新フレームを認識。自動再接続・人数保存・Web閲覧・処理時間ログに対応 |
| `web/local/` | PC内ページのHTML・CSS・JavaScriptを分けて配置 |
| `web/local/` | PC内ページのHTML・CSS・JavaScriptを分けて配置 |
| `camera-test.py` | 人物認識をせず、RTSP映像の表示と約2秒ごとのFPS出力を行う接続テスト |
| `yolov8n.pt` | 既定の人物検出モデル |
| `counter.sqlite3` | 既定の人数記録DB。2台運用ではゲートごとに別DBを指定 |
| `counter-cloud/upload_counts.py` | Web送信係。`--gate-id` を付けた計測起動から自動で呼び出す |
| `counter-cloud/worker/public/` | 公開ページのHTML・CSS・JavaScript |
| `counter-cloud/worker/src/` | Cloudflare Workerの人数受信・集計API |
| `counter-cloud/` | クラウド送信関連。詳細は[専用README](counter-cloud/README.md)を参照 |

## 準備

Pythonの仮想環境に、次のパッケージを用意します。画面表示を使うため、OpenCVはGUI対応の `opencv-python` を使用します。依存バージョンを固定するファイルは現在ありません。

### macOS / zsh

プロジェクトのフォルダで実行します。既存の `venv` があれば作成は省略できます。

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install ultralytics opencv-python flask waitress
```

### Windows / PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install ultralytics opencv-python flask waitress
```

仮想環境は各PCで作成してください。カメラにアクセスできるネットワークへ接続し、同じカメラを数えるカウンターは1つだけ起動します。

## 1台での起動方法

URL内のユーザー名・パスワード・IP・映像パスはカメラの設定に合わせます。以下の `PASSWORD` とIPは例です。パスワードに `@`、`:`、`#` などが含まれる場合、その部分をURLエンコードしてください。コマンドに入力したURLはシェル履歴に残る場合があります。

### macOS

```sh
python -u ./visitor_counter.py --source 'rtsp://admin:PASSWORD@192.168.0.181:554/live/sub'
```

### Windows

```powershell
python -u .\visitor_counter.py --source 'rtsp://admin:PASSWORD@192.168.0.181:554/live/sub'
```

Macでは `./`、Windows PowerShellでは `.\` を使います。Macで `.\visitor_counter.py` と書くと、シェルがバックスラッシュを解釈し、`.visitor_counter.py` を探して起動に失敗します。

起動後、映像ウィンドウと `http://127.0.0.1:8000` の人数ページを確認できます。終了は映像ウィンドウで `q`、またはターミナルで `Ctrl+C` です。

USBカメラや動画ファイルも指定できます。この場合は受信スレッドを使用しません。

```sh
python visitor_counter.py --source 0
python visitor_counter.py --source ./sample.mp4
```

HTTP映像URLも指定できますが、スレッド分離の対象は `rtsp://` と `rtsps://` のみです。動画ファイルは終端で終了します。動画内の撮影日時ではなく、実行時の日本時間で人数を記録するため、テスト用DBを使うと本番記録への混入を避けられます。

```sh
python visitor_counter.py --source ./sample.mp4 --db ./test-counter.sqlite3
```

## 2ゲート運用の起動コマンド

計測プログラムが送信プログラムを自動で起動・終了するため、カメラ1台につきターミナル1つで動かせます。同じPCで2台を使う場合はターミナル2つです。
カメラURLの `PASSWORD` と `CAMERA_1_IP` / `CAMERA_2_IP` を実機の値に置き換えてください。
`/live/sub` とユーザー名もカメラ設定に合わせます。下記は動画を保存しません。
2台のPCで動かす場合も同じゲートID・DB名・ポートの組み合わせを使えます。

| 用途 | ゲートID | 人数DB | APIポート |
| --- | --- | --- | --- |
| カメラ1 | `gate-1` | `counter-gate-1.sqlite3` | 8000 |
| カメラ2 | `gate-2` | `counter-gate-2.sqlite3` | 8001 |

ゲートごとに別DBを使用し、再起動後も同じDBを指定します。新しいDBは空の人数から始まります。
既存の `counter.sqlite3` の記録は自動移行しません。既存DBを2ゲートで共有しないでください。

### Mac：ゲートごとにターミナル1つ

```sh
cd ~/dev/visiter_counter
source venv/bin/activate
```

ゲート1：

```sh
python -u visitor_counter.py --source 'rtsp://admin:PASSWORD@CAMERA_1_IP:554/live/sub' --db counter-gate-1.sqlite3 --port 8000 --gate-id gate-1
```

ゲート2：

```sh
python -u visitor_counter.py --source 'rtsp://admin:PASSWORD@CAMERA_2_IP:554/live/sub' --db counter-gate-2.sqlite3 --port 8001 --gate-id gate-2
```

送信プログラムは計測と同時にバックグラウンドで起動し、計測終了時に一緒に終了します。
起動時に送信専用トークンを非表示で入力します。送信先は `https://counter.gidaisai.jp/api/upload` です。
送信は10秒間隔です。

### Windows：ゲートごとにターミナル1つ

リポジトリのフォルダで仮想環境を有効にし、ゲートごとの計測コマンドを実行します。
`PASSWORD` とカメラIPは実機の値に置き換えてください。送信トークンは起動時に非表示で入力します。

ゲート1：

```powershell
.\venv\Scripts\Activate.ps1
python -u visitor_counter.py --source 'rtsp://admin:PASSWORD@CAMERA_1_IP:554/live/sub' --db counter-gate-1.sqlite3 --port 8000 --gate-id gate-1
```

ゲート2は別ターミナルで：

```powershell
.\venv\Scripts\Activate.ps1
python -u visitor_counter.py --source 'rtsp://admin:PASSWORD@CAMERA_2_IP:554/live/sub' --db counter-gate-2.sqlite3 --port 8001 --gate-id gate-2
```

### 確認と終了

- ゲート1のローカル表示：`http://127.0.0.1:8000`
- ゲート2のローカル表示：`http://127.0.0.1:8001`
- 全体の公開表示：https://counter.gidaisai.jp
- 計測を `q` または `Ctrl+C` で終了すると、送信も一緒に終了します。
- カメラなしでページだけ確認するときは、`--gate-id` を付けず `--web-only` を指定します。

## 計数の仕組み

1. YOLOv8で人物クラスだけを検出します。既定の信頼度しきい値は `0.4`、IoUしきい値は `0.45` です。
2. ByteTrackで人物に追跡IDを付けます。
3. 人物の検出枠の中心座標を追跡し、前回と今回のX座標を比較します。
4. 画面中央の縦線を右から左へ横切ると `Enter`、左から右へ横切ると `Exit` を記録します。
5. 入退場イベントをSQLiteに保存し、映像上の人数とWeb APIに反映します。

画面の値は次の意味です。

| 表示 | 意味 |
| --- | --- |
| `Enter` | 日本時間の当日に記録した入場回数 |
| `Exit` | 日本時間の当日に記録した退場回数 |
| `Current` | 当日の `Enter - Exit` |

同じ追跡IDは、追跡履歴をリセットするまで一度だけ計数します。同じIDのまま往復しても再計数しません。一方、同じ人でもIDが変わると別の人物として扱われます。追跡位置はIDごとに最大30点を保持しますが、消えたIDの履歴を定期的に削除する処理はありません。

カウント方向はカメラの設置方向に依存します。現在は方向・線の位置・回転を指定する起動オプションがありません。実際の入口と逆になる場合はコードの判定を変更する必要があります。

### Currentが負になる場合

画像のように `Enter: 15`、`Exit: 32` なら、`Current` は `-17` になります。コードは負の値を0に補正していません。これは画面内の検出人数ではなく、当日の入退場差です。

開始前からいた人の退場、過去のテスト記録、入退場方向の不一致、数え漏れ、追跡IDの切り替わりなどで実際の在場人数とずれることがあります。画像だけでは原因は特定できません。現在は初期在場人数や手動補正を入力する機能はありません。

## RTSP受信スレッド

`LatestStream` がOpenCVのFFmpegバックエンドで映像を読み続け、最新の1枚を共有します。メイン処理はその時点の最新フレームで人物認識・計数・描画を行います。同じフレームを重複して渡さず、未処理の古いフレームは省きます。

```text
受信スレッド：RTSP受信 → 最新フレームを更新 → 受信を継続
                              ↓
メイン処理  ：最新フレーム取得 → YOLO・追跡 → 計数・保存 → 表示
Webスレッド ：SQLiteから当日の人数を取得 → 閲覧ページ・API
```

- RTSPの転送方式はTCPを指定します。
- 接続タイムアウトは5秒、読み取りタイムアウトは3秒を指定します。動作は利用するOpenCV・FFmpeg環境にも依存します。
- 切断時は受信スレッドが接続をやり直します。最初のフレーム取得は最大15秒待ち、取得できなければ起動を終了します。
- 再接続後、または処理対象フレームの受信時刻が前回から1秒を超えて離れた場合は追跡をリセットします。断絶の前後をつないで誤計数することを避けますが、その間の横断は数え漏れる可能性があります。
- 終了時は受信停止を通知し、最大7秒待って受信スレッドの終了を待ちます。

この仕組みは古い映像の処理待ちを減らすためのものです。YOLO自体の速度を上げるものではなく、表示更新も人物認識の速度に左右されます。フレームを省くため、実機では速い移動や混雑時の数え漏れを確認してください。

## 保存と日付

既定ではスクリプトと同じフォルダの `counter.sqlite3` に保存します。`events` テーブルに日付・記録時刻・方向を保存し、入退場のたびにコミットします。SQLiteはWALモード、`synchronous=FULL` を使用します。

- 再起動しても当日の人数をDBから復元します。
- 日本時間の日付ごとに別集計です。前日の在場人数は引き継ぎません。
- 日付変更だけでは追跡履歴・計数済みIDはリセットしません。
- 人数の保存に `--save` は不要です。`--save` は処理結果の動画保存用です。
- 本番DBを削除すると入退場履歴が失われます。動作確認には `--db` で別のDBを指定してください。

## ブラウザ閲覧・API

既定の接続先は `http://127.0.0.1:8000` です。ページは約2秒間隔で `/api/counts` を取得します。映像処理が15秒を超えて更新されていなければ、停止・遅延の案内を表示します。

カメラを使わず、保存済み人数とページだけ確認できます。

```sh
python visitor_counter.py --web-only
```

LAN内の別端末から閲覧する場合は、PC自身のLAN内IPv4と許可するネットワークを指定します。次はPCが `192.168.0.100`、LANが `/24` の場合の例です。

```sh
python visitor_counter.py --web-only --host 192.168.0.100 --allow-subnet 192.168.0.0/24
```

別端末では `http://192.168.0.100:8000` を開きます。計測も行う場合は `--web-only` を外して `--source` を指定します。OSのファイアウォールでも接続を許可する必要があります。

ローカルページにはログイン機能はなく、接続元IPで制限します。映像・カメラURL・追跡IDはAPIに含めません。リバースプロキシやトンネル越しの公開は想定していません。

`GET /api/counts` の返却項目:

| 項目 | 内容 |
| --- | --- |
| `date` | 集計日（日本時間） |
| `enter`, `exit`, `current` | 当日の入場・退場・差分 |
| `status` | 計測中、映像待機などの状態 |
| `last_frame` | 最後に人物認識処理を終えた時刻。カメラの撮影時刻ではない |
| `last_event` | 当日の最終入退場記録時刻 |
| `server_time` | 応答生成時刻 |

クラウド送信プログラムは `http://127.0.0.1:指定ポート/api/counts` を参照します。計測側の `--port` と送信側の `--port` を一致させてください。クラウド設定は[専用README](counter-cloud/README.md)を参照してください。

## 主な起動オプション

以下は `visitor_counter.py` のオプションです。

| オプション | 既定値・動作 |
| --- | --- |
| `--source` | `0`。カメラ番号・映像URL・動画パス |
| `--model` | スクリプトと同じ場所の `yolov8n.pt` |
| `--conf` | `0.4` |
| `--iou` | `0.45` |
| `--no-show` | 映像ウィンドウを表示しない。終了は `Ctrl+C` |
| `--save` | 描画済み映像を実行ディレクトリの `output.mp4` に固定20fpsで保存。処理速度と異なると再生時間が実時間とずれる |
| `--web-only` | カメラを起動せずWeb配信のみ実行 |
| `--host` | `127.0.0.1` |
| `--port` | `8000` |
| `--allow-subnet` | LAN閲覧を許可するCIDR |
| `--db` | スクリプトと同じ場所の `counter.sqlite3` |

全オプションは `python visitor_counter.py --help` でも確認できます。

## カメラ単体テスト・ログの見方

```sh
python camera-test.py
```

パスワードを非表示で入力します。接続先はコード内の `192.168.0.181:554/live/sub`、ユーザー名は `admin` 固定です。カメラが異なる場合は `camera-test.py` のURLを変更してください。人物認識・人数保存・自動再接続は行いません。

| ログ | 意味 |
| --- | --- |
| `[CAMERA] ... fps`（単体テスト） | 読み取り・表示ループでの平均処理枚数。映像の遅延量を示す値ではない |
| `[PERF]` | 約2秒ごとに、その時点の1フレームの受信待ち・YOLO・計数描画・表示保存・合計時間をmsで出力。区間平均ではない |
| `[STREAM] skipped` | 認識に渡さず省いたフレームの累計。増加自体は最新フレーム方式の通常動作 |
| `[STREAM] local_age` | OpenCVで読み取りを終えてから表示・保存処理終了までの経過時間。カメラ撮影からの総遅延ではない |
| `[COUNT]` | 入退場保存時のロック待ち・挿入・コミット・集計取得時間 |
| `[TRACK]` | 接続断や処理間隔の拡大による追跡リセット |

実機確認では、カメラ単体テストを終了してからカウンターを起動し、入場・退場をそれぞれ目視と照合してください。FPSだけでなく、実際の動きとの遅延、追跡IDの維持、往復時の挙動、再接続後の計数も確認します。
