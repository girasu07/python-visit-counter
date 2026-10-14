"""

イベント来場者カウンター

YOLOv8 + OpenCV を使ったリアルタイム人数計測 (縦線バージョン)

"""

import argparse

from collections import defaultdict

# ── 設定 ────────────────────────────────────────────────────────────────────

# ▼ 使用するソースをここで切り替える

DEFAULT_SOURCE = 0  # --source でカメラ番号またはスマホの映像URLを指定

# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

DEFAULT_MODEL    = "yolov8n.pt"

CONFIDENCE_THRES = 0.4

IOU_THRES        = 0.45

PERSON_CLASS_ID  = 0

LINE_COLOR = (0, 255, 255)

def draw_ui(frame, enter: int, exit_: int, current: int,

            line_x: int):

    import cv2

    h, w = frame.shape[:2]

    # 縦線を引く (X座標を固定して、Yを0からhまで引く)

    cv2.line(frame, (line_x, 0), (line_x, h), LINE_COLOR, 2)

    cv2.putText(frame, "COUNT LINE", (line_x + 10, 20),

                cv2.FONT_HERSHEY_SIMPLEX, 0.5, LINE_COLOR, 1)

    overlay = frame.copy()

    cv2.rectangle(overlay, (0, 0), (260, 120), (20, 20, 20), -1)

    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    texts = [

        (f"Enter : {enter}",  (0, 255, 80)),

        (f"Exit  : {exit_}",  (0, 100, 255)),

        (f"Current : {current}", (255, 220, 0)),

    ]

    for i, (text, color) in enumerate(texts):

        cv2.putText(frame, text, (10, 30 + i * 30),

                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    return frame

class LatestStream:
    """One receiver owns VideoCapture; one consumer takes each latest frame once."""
    def __init__(self, source):
        self.source = source
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = None
        self.sequence = 0
        self.consumed = 0
        self.generation = 0
        self.delivered_generation = 0
        self.skipped = 0
        self.received_at = 0.0
        self.error = None
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    def _receive(self):
        import cv2
        while not self.stop.is_set():
            cap = None
            try:
                cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG, [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
                if not cap.isOpened():
                    raise RuntimeError('open failed')
                with self.condition:
                    self.generation += 1
                while not self.stop.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        break
                    with self.condition:
                        self.sequence += 1
                        self.latest = (frame, time.perf_counter(), self.generation)
                        self.condition.notify_all()
            except Exception as exc:
                # Do not print exception text: some backends include credentials.
                with self.condition:
                    self.error = type(exc).__name__
            finally:
                if cap is not None:
                    cap.release()
                with self.condition:
                    self.latest = None
                    self.condition.notify_all()
            if not self.stop.is_set():
                print('[CAMERA] Connection interrupted; retrying...', flush=True)
                self.stop.wait(1)

    def read(self, timeout=1.0):
        with self.condition:
            ready = self.condition.wait_for(
                lambda: self.stop.is_set() or
                (self.latest is not None and self.sequence > self.consumed),
                timeout=timeout)
            if not ready or self.stop.is_set() or self.latest is None:
                return False, None
            frame, stamp, generation = self.latest
            self.skipped += max(0, self.sequence - self.consumed - 1)
            self.consumed = self.sequence
            self.received_at = stamp
            self.delivered_generation = generation
            # Producer never modifies a published frame; consumer owns this reference.
            return True, frame

    def isOpened(self):
        return self.thread.is_alive() and not self.stop.is_set()

    def set(self, *args):
        return False

    def release(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=7)

def run(source=DEFAULT_SOURCE,

        model_path=DEFAULT_MODEL,

        conf=CONFIDENCE_THRES,

        iou=IOU_THRES,

        show=True,

        save_video=False, store=None):

    import os
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    import cv2

    from ultralytics import YOLO

    model = YOLO(model_path)

    print(f"[INFO] モデル読み込み完了: {model_path}")

    print("[INFO] 映像ソースを開きます（認証情報は表示しません）")

    threaded = isinstance(source, str) and source.lower().startswith(("rtsp://", "rtsps://"))
    cap = LatestStream(source) if threaded else cv2.VideoCapture(source)
    writer = None

    try:
        # RTSPの場合はバッファを最小化して映像遅延を減らす

        if str(source).startswith("rtsp") or str(source).startswith("http"):

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():

            raise RuntimeError(

                "映像ソースを開けません\n"

                "→ iPhoneとPCが同じWi-Fiに接続されているか確認してください"

            )

        ret, frame = cap.read(timeout=15) if threaded else cap.read()

        if not ret:

            raise RuntimeError("最初のフレームを取得できません")

        h, w = frame.shape[:2]

        # 画面の幅の半分を縦線のX座標とする

        line_x = w // 2

        writer = None

        if save_video:

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

            writer = cv2.VideoWriter("output.mp4", fourcc, 20, (w, h))

        track_history = defaultdict(list)

        crossed_ids   = set()

        counts = store.snapshot()

        active_day = counts["date"]

        enter_count, exit_count = counts["enter"], counts["exit"]

        print("[INFO] 'q' キーで終了します")

        stream_generation = cap.delivered_generation if threaded else 0
        previous_frame_time = time.perf_counter()
        warned = False
        profile_report_at = time.perf_counter()
        while True:
            profile_start = time.perf_counter()

            if today() != active_day:

                counts = store.snapshot()

                active_day = counts["date"]

                enter_count, exit_count = counts["enter"], counts["exit"]

            read_start = time.perf_counter()
            ret, frame = cap.read()
            read_ms = (time.perf_counter() - read_start) * 1000

            if not ret:
                store.status("映像待機・再接続中")
                if not warned:
                    print("[WARN] Waiting for camera frames...", flush=True)
                    warned = True
                if show and cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                if threaded:
                    continue  # Receiver alone handles reconnection.
                if isinstance(source, str) and Path(source).is_file():
                    break
                time.sleep(1)
                cap.open(source)
                track_history.clear()
                crossed_ids.clear()
                model = YOLO(model_path)
                continue

            warned = False
            frame_time = cap.received_at if threaded else time.perf_counter()
            reset_tracking = threaded and (cap.delivered_generation != stream_generation or
                                          frame_time - previous_frame_time > 1.0)
            if reset_tracking:
                # Do not infer a crossing across a connection outage / long processing gap.
                track_history.clear()
                crossed_ids.clear()
                predictor = getattr(model, 'predictor', None)
                trackers = getattr(predictor, 'trackers', ())
                if trackers and all(callable(getattr(t, 'reset', None)) for t in trackers):
                    for tracker in trackers:
                        tracker.reset()
                else:
                    model = YOLO(model_path)
                print('[TRACK] Reset after stream gap; crossings during gap may be missed.', flush=True)
            if threaded:
                stream_generation = cap.delivered_generation
            previous_frame_time = frame_time
            line_x = frame.shape[1] // 2

            infer_start = time.perf_counter()
            results = model.track(

                frame,

                persist=True,

                imgsz=480,

                classes=[PERSON_CLASS_ID],

                conf=conf,

                iou=iou,

                tracker="bytetrack.yaml",

                verbose=False,

            )

            infer_ms = (time.perf_counter() - infer_start) * 1000
            post_start = time.perf_counter()
            store.processed()

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

                        # Y座標ではなく、X座標(インデックス0)を取得して比較する

                        prev_cx = track_history[tid][-2][0]

                        curr_cx = track_history[tid][-1][0]

                        # 右から左へ移動したら入場 (元の実動作を維持)

                        if prev_cx > line_x >= curr_cx:

                            counts = store.record("enter")

                            enter_count, exit_count = counts["enter"], counts["exit"]

                            crossed_ids.add(tid)

                        # 左から右へ移動したら退場

                        elif prev_cx < line_x <= curr_cx:

                            counts = store.record("exit")

                            enter_count, exit_count = counts["enter"], counts["exit"]

                            crossed_ids.add(tid)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (100, 200, 255), 2)

                    cv2.putText(frame, f"ID:{tid} {conf_val:.2f}", (x1, y1 - 6),

                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)

                    pts = track_history[tid]

                    for j in range(1, len(pts)):

                        cv2.line(frame, pts[j - 1], pts[j], (200, 200, 200), 1)

            post_ms = (time.perf_counter() - post_start) * 1000
            display_start = time.perf_counter()
            frame = draw_ui(frame, enter_count, exit_count,

                            enter_count - exit_count, line_x)

            if show:

                cv2.imshow("People Counter [q:quit]", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):

                    break

            if writer:

                writer.write(frame)

            profile_end = time.perf_counter()
            if profile_end - profile_report_at >= 2:
                print(f"[PERF] read={read_ms:.0f}ms yolo={infer_ms:.0f}ms count_draw={post_ms:.0f}ms display_video={(profile_end-display_start)*1000:.0f}ms total={(profile_end-profile_start)*1000:.0f}ms", flush=True)
                if threaded:
                    print(f"[STREAM] skipped={cap.skipped} local_age={(profile_end-cap.received_at)*1000:.0f}ms", flush=True)
                profile_report_at = profile_end

    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()

    print("\n===== 計測結果 =====")

    print(f"  Enter : {enter_count}")

    print(f"  Exit  : {exit_count}")

    print(f"  Current : {enter_count - exit_count}")

# LAN閲覧・永続保存。Python 3.9以降。

# 追加依存: python3 -m pip install flask waitress

# カメラなし確認: python3 main-tate.py --web-only

# LAN確認: --host <PCのLAN内IPv4> --allow-subnet <LANのCIDR>

# 例のIPをそのまま使わず、PCの実際のIP/ネットマスクに合わせること。

# データ: このファイルと同じ場所のcounter.sqlite3。削除すると集計履歴が消えます。

# Web画面は閲覧専用。映像・カメラURL・追跡IDはWebに送信しません。

# 当日(JST)の入場-退場を表示。日付が変わると別集計。日跨ぎ在場数は引き継ぎません。

# 同じカメラの集計プログラムを複数起動しないでください。

import ipaddress

import sqlite3

import threading

import time

from datetime import datetime, timezone, timedelta

from pathlib import Path

JST = timezone(timedelta(hours=9))

def now():

    return datetime.now(JST).isoformat(timespec="seconds")

def today():

    return datetime.now(JST).date().isoformat()

class CountStore:

    def __init__(self, path):

        self.lock = threading.RLock()

        self.db = sqlite3.connect(str(path), check_same_thread=False)

        self.db.execute("PRAGMA journal_mode=WAL")

        self.db.execute("PRAGMA synchronous=FULL")

        self.db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, day TEXT NOT NULL, at TEXT NOT NULL, direction TEXT NOT NULL CHECK(direction IN ('enter','exit')))")

        self.db.execute("CREATE INDEX IF NOT EXISTS events_day ON events(day)")

        self.db.commit()

        self.message = "準備中"

        self.last_frame = None

    def status(self, message):

        with self.lock:

            self.message = message

    def processed(self):

        with self.lock:

            self.message = "計測中"

            self.last_frame = now()

    def record(self, direction):
        if direction not in ("enter", "exit"):
            raise ValueError("invalid direction")
        stamp = now()
        started = time.perf_counter()
        with self.lock:
            locked = time.perf_counter()
            with self.db:
                self.db.execute("INSERT INTO events(day, at, direction) VALUES (?,?,?)", (stamp[:10], stamp, direction))
                inserted = time.perf_counter()
            committed = time.perf_counter()
        result = self.snapshot()
        finished = time.perf_counter()
        print(f"[COUNT] {direction} lock={(locked-started)*1000:.1f}ms insert={(inserted-locked)*1000:.1f}ms commit={(committed-inserted)*1000:.1f}ms snapshot={(finished-committed)*1000:.1f}ms total={(finished-started)*1000:.1f}ms", flush=True)
        return result

    def snapshot(self):

        with self.lock:

            day = today()

            rows = dict(self.db.execute("SELECT direction, COUNT(*) FROM events WHERE day=? GROUP BY direction", (day,)))

            last = self.db.execute("SELECT MAX(at) FROM events WHERE day=?", (day,)).fetchone()[0]

            entered, exited = rows.get("enter", 0), rows.get("exit", 0)

            return dict(date=day, enter=entered, exit=exited, current=entered-exited,

                        status=self.message, last_frame=self.last_frame, last_event=last,

                        server_time=now())

    def close(self):

        with self.lock:

            self.db.close()

PAGE = '''<!doctype html><html lang="ja"><meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1"><title>岐大祭 人数カウンター</title>

<style>body{font-family:system-ui,sans-serif;background:#f3f5fa;color:#172238;margin:0;padding:24px}main{max-width:650px;margin:auto}h1{font-size:24px}.card{background:white;border-radius:16px;padding:24px;margin:16px 0;border:1px solid #dce2ed}.big{font-size:64px;font-weight:750;color:#2555b8} .row{display:flex;gap:32px}.row strong{font-size:30px}p{line-height:1.7}small{color:#526078}#connection{font-weight:bold}</style>

<main><h1>岐大祭 人数カウンター</h1><p id="date">接続中…</p>

<div class="card">推定滞在人数<div class="big"><span id="current">—</span><small> 人</small></div>

<div class="row"><div>累計入場<br><strong id="enter">—</strong> 人</div><div>累計退場<br><strong id="exit">—</strong> 人</div></div></div>

<div class="card"><p id="connection">取得中</p><p id="status">—</p><small>最終映像処理：<span id="frame">—</span><br>最終入退場記録：<span id="event">—</span><br>表示更新：<span id="updated">—</span></small></div>

<p><small>滞在人数は当日の入場−退場の推定値です。開始前の在場者や他の出入口は含みません。誤差によって負の値になる場合があります。</small></p></main>

<script>

const el=id=>document.getElementById(id);

const stamp=s=>s?new Date(s).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'}):'記録なし';

async function refresh(){

 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),5000);

 try { const r=await fetch('/api/counts',{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();const d=await r.json();

 for(const k of ['enter','exit','current'])el(k).textContent=d[k].toLocaleString('ja-JP');

 el('date').textContent=d.date+'（日本時間）';el('frame').textContent=stamp(d.last_frame);el('event').textContent=stamp(d.last_event);el('updated').textContent=stamp(d.server_time);

 const stale=!d.last_frame || (Date.parse(d.server_time)-Date.parse(d.last_frame)>15000);

 el('status').textContent=stale?'映像未処理・停止中、または処理に時間がかかっています':d.status;

 el('connection').textContent='ページ接続中';

 }catch(e){el('connection').textContent='接続切れ：表示は最後に取得した値です';el('status').textContent='PCとWi-Fiの接続を確認してください';}

 finally{clearTimeout(timer);setTimeout(refresh,2000);}

}refresh();

</script></html>'''

def create_app(store, allowed_subnet=None):

    from flask import Flask, request, abort, jsonify

    app = Flask(__name__, static_folder=None)

    network = ipaddress.ip_network(allowed_subnet, strict=False) if allowed_subnet else None

    @app.before_request

    def restrict_lan():

        try:

            peer = ipaddress.ip_address(request.remote_addr)

        except ValueError:

            abort(403)

        # X-Forwarded-Forは信用しない。Tunnel/リバースプロキシの背後には置かない。

        if not peer.is_loopback and (network is None or peer not in network):

            abort(403)

    @app.after_request

    def headers(response):

        response.headers['Cache-Control'] = 'no-store'

        response.headers['X-Content-Type-Options'] = 'nosniff'

        response.headers['X-Frame-Options'] = 'DENY'

        return response

    @app.get('/')

    def index():

        return PAGE

    @app.get('/api/counts')

    def counts():

        return jsonify(store.snapshot())

    return app

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='YOLOv8 来場者カウンター / LAN閲覧・自動保存')

    parser.add_argument('--source', default=DEFAULT_SOURCE, help='カメラ番号 / HTTP・RTSPの完全なURL / 動画パス')

    parser.add_argument('--model', default=str(Path(__file__).with_name('yolov8n.pt')))

    parser.add_argument('--conf', type=float, default=CONFIDENCE_THRES)

    parser.add_argument('--iou', type=float, default=IOU_THRES)

    parser.add_argument('--no-show', action='store_true')

    parser.add_argument('--save', action='store_true', help='映像も保存（人数は常に自動保存）')

    parser.add_argument('--web-only', action='store_true', help='カメラなしで閲覧ページのみ確認')

    parser.add_argument('--host', default='127.0.0.1', help='LAN公開時はPCのLAN内IPv4を指定')

    parser.add_argument('--port', type=int, default=8000)

    parser.add_argument('--allow-subnet', help='許可LANのCIDR。例: 192.168.11.0/24（実際の設定に合わせる）')

    parser.add_argument('--db', default=str(Path(__file__).with_name('counter.sqlite3')))

    args = parser.parse_args()

    try:

        host = ipaddress.IPv4Address(args.host)

        if not host.is_loopback:

            if not args.allow_subnet:

                parser.error('LAN公開には --allow-subnet が必要です')

            network = ipaddress.IPv4Network(args.allow_subnet, strict=False)

            if host not in network or not any(network.subnet_of(ipaddress.IPv4Network(n)) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):

                parser.error('PCのLAN内IPv4と、そのLANのプライベートIP範囲を指定してください')

    except ValueError as exc:

        parser.error(str(exc))

    from waitress import create_server

    store = CountStore(args.db)

    server = create_server(create_app(store, args.allow_subnet), host=args.host, port=args.port, threads=4)

    print(f'[WEB] http://{args.host}:{args.port}')

    print(f'[DATA] {Path(args.db).resolve()}')

    try:

        if args.web_only:

            store.status('閲覧テスト中（カメラ未起動）')

            server.run()

        else:

            threading.Thread(target=server.run, daemon=True).start()

            source = int(args.source) if str(args.source).isdigit() else args.source

            run(source=source, model_path=args.model, conf=args.conf, iou=args.iou,

                show=not args.no_show, save_video=args.save, store=store)

    except KeyboardInterrupt:

        pass

    finally:

        store.status('停止')

        server.task_dispatcher.shutdown()

        server.close()

        # DBは各イベントでコミット済み。処理中のHTTPスレッドとの競合を避け、接続は終了時にOSが解放。
