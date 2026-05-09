"""
イベント来場者カウンター
YOLOv8 + OpenCV を使ったリアルタイム人数計測
"""
 
import cv2
import argparse
from collections import defaultdict
from ultralytics import YOLO
import numpy as np
 
 
# ── 設定 ────────────────────────────────────────────────────────────────────
# ▼▼▼ iPhoneのIPアドレスをここに入れる ▼▼▼
#IPHONE_IP   = "10.16.45.122"      # ← IP Camera Lite に表示されるIPに変更
#IPHONE_PORT = 554                 # RTSPポート（IP Camera Lite のデフォルト）
 
# ▼ 使用するソースをここで切り替える
DEFAULT_SOURCE = 0      # iPhoneカメラを使う場合
#DEFAULT_SOURCE = 1      # PCの内蔵カメラを使う場合はこちら
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
 
DEFAULT_MODEL    = "yolov8n.pt"
CONFIDENCE_THRES = 0.4
IOU_THRES        = 0.45
PERSON_CLASS_ID  = 0
 
LINE_COLOR = (0, 255, 255)
 
 
def draw_ui(frame: np.ndarray, enter: int, exit_: int, current: int,
            line_y: int) -> np.ndarray:
    h, w = frame.shape[:2]
 
    cv2.line(frame, (0, line_y), (w, line_y), LINE_COLOR, 2)
    cv2.putText(frame, "COUNT LINE", (10, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, LINE_COLOR, 1)
 
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (260, 120), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
 
    texts = [
        (f"入場 (Enter) : {enter}",  (0, 255, 80)),
        (f"退場 (Exit)  : {exit_}",  (0, 100, 255)),
        (f"現在人数     : {current}", (255, 220, 0)),
    ]
    for i, (text, color) in enumerate(texts):
        cv2.putText(frame, text, (10, 30 + i * 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
 
    return frame
 
 
def run(source=DEFAULT_SOURCE,
        model_path=DEFAULT_MODEL,
        conf=CONFIDENCE_THRES,
        iou=IOU_THRES,
        show=True,
        save_video=False):
 
    model = YOLO(model_path)
    print(f"[INFO] モデル読み込み完了: {model_path}")
    print(f"[INFO] 映像ソース: {source}")
 
    cap = cv2.VideoCapture(source)
 
    # RTSPの場合はバッファを最小化して映像遅延を減らす
    if str(source).startswith("rtsp"):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
 
    if not cap.isOpened():
        raise RuntimeError(
            f"映像ソースを開けません: {source}\n"
            "→ iPhoneとPCが同じWi-Fiに接続されているか確認してください"
        )
 
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("最初のフレームを取得できません")
 
    h, w = frame.shape[:2]
    line_y = h // 2
 
    writer = None
    if save_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter("output.mp4", fourcc, 20, (w, h))
 
    track_history = defaultdict(list)
    crossed_ids   = set()
    enter_count   = 0
    exit_count    = 0
 
    print("[INFO] 'q' キーで終了します")
 
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] フレーム取得失敗。再接続を試みます...")
            cap.open(source)
            continue
 
        results = model.track(
            frame,
            persist=True,
            classes=[PERSON_CLASS_ID],
            conf=conf,
            iou=iou,
            tracker="bytetrack.yaml",
            verbose=False,
        )
 
        if results[0].boxes.id is not None:
            boxes     = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            confs     = results[0].boxes.conf.cpu().numpy()
 
            for box, tid, conf_val in zip(boxes, track_ids, confs):
                x1, y1, x2, y2 = map(int, box)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
 
                track_history[tid].append((cx, cy))
                if len(track_history[tid]) > 30:
                    track_history[tid].pop(0)
 
                if tid not in crossed_ids and len(track_history[tid]) >= 2:
                    prev_cy = track_history[tid][-2][1]
                    curr_cy = track_history[tid][-1][1]
 
                    if prev_cy < line_y <= curr_cy:
                        enter_count += 1
                        crossed_ids.add(tid)
                    elif prev_cy > line_y >= curr_cy:
                        exit_count += 1
                        crossed_ids.add(tid)
 
                cv2.rectangle(frame, (x1, y1), (x2, y2), (100, 200, 255), 2)
                cv2.putText(frame, f"ID:{tid} {conf_val:.2f}", (x1, y1 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)
 
                pts = track_history[tid]
                for j in range(1, len(pts)):
                    cv2.line(frame, pts[j - 1], pts[j], (200, 200, 200), 1)
 
        frame = draw_ui(frame, enter_count, exit_count,
                        enter_count - exit_count, line_y)
 
        if show:
            cv2.imshow("People Counter [q:quit]", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
 
        if writer:
            writer.write(frame)
 
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
 
    print("\n===== 計測結果 =====")
    print(f"  入場人数    : {enter_count}")
    print(f"  退場人数    : {exit_count}")
    print(f"  最終在場人数: {enter_count - exit_count}")
 
 
# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8 来場者カウンター")
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help="カメラ番号 / RTSPアドレス / 動画ファイルパス")
    parser.add_argument("--ip", default=None,
                        help="iPhoneのIPアドレス (例: 192.168.1.5)")
    parser.add_argument("--model",  default=DEFAULT_MODEL)
    parser.add_argument("--conf",   type=float, default=CONFIDENCE_THRES)
    parser.add_argument("--iou",    type=float, default=IOU_THRES)
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--save",    action="store_true")
    args = parser.parse_args()
 
    # --ip が指定されたら RTSP URL を自動生成
    source = args.source
    if args.ip:
        source = f"rtsp://{args.ip}:{IPHONE_PORT}/live"
        print(f"[INFO] iPhone接続先: {source}")
 
    run(
        source=int(source) if str(source).isdigit() else source,
        model_path=args.model,
        conf=args.conf,
        iou=args.iou,
        show=not args.no_show,
        save_video=args.save,
    )