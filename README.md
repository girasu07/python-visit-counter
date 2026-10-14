来場者カウンター(プロトタイプ）

ファイル名
main.py →カウントラインを画面に対して横線で実装
main-tate.py →縦線で実装
main-tate-threaded.py →縦線版。RTSP映像を別スレッドで受信し、人物認識には最新フレームを使用

スレッド版の起動例（Windows PowerShell、仮想環境を有効にして実行）:
```powershell
python -u .\main-tate-threaded.py --source 'rtsp://admin:カメラのパスワード@カメラのIP:554/live/sub'
```
起動前に既存のカウンターを終了してください。人数は従来と同じ `counter.sqlite3` に保存し、Web閲覧は `http://127.0.0.1:8000` です。
`skipped` は認識せずに省いたフレームの累計です。受信と認識の分離はRTSPのみで、HTTP・USBカメラ・動画ファイルは従来の逐次処理です。
実機では映像の遅延と、線を横切る人数が正しく数えられるかを確認してください。

DEFAURT_SOURCEの設定について
基本は
http://（IPアドレス）:（ポート番号）/（使用するソース）
の構成です

IP Camera Lite で実験、その環境では
http://（ユーザー名）:（パスワード）@（IPアドレス）:（ポート番号）/（使用するソース）

