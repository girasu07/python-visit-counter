import os
import time
from getpass import getpass
from urllib.parse import quote

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2

password = quote(getpass("カメラのパスワード（入力は表示されません）: "), safe="")
url = f"rtsp://admin:{password}@192.168.0.180:554/live/sub"

cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

try:
    if not cap.isOpened():
        raise RuntimeError("カメラに接続できません")

    print("映像のみ表示します。映像ウィンドウで q を押すと終了。")
    frames = 0
    started = time.perf_counter()

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] 映像の取得に失敗しました")
            break

        frames += 1
        cv2.imshow("Camera test - q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        elapsed = time.perf_counter() - started
        if elapsed >= 2:
            print(f"[CAMERA] {frames / elapsed:.1f} fps", flush=True)
            frames = 0
            started = time.perf_counter()
finally:
    cap.release()
    cv2.destroyAllWindows()