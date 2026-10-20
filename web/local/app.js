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
