const el=id=>document.getElementById(id);
let shownDay=null;
function clearCounts(){for(const k of ['enter','exit','current'])el(k).textContent='—';}
async function refresh(){const c=new AbortController(),t=setTimeout(()=>c.abort(),5000);try{
const r=await fetch('/api/counts',{cache:'no-store',signal:c.signal});if(!r.ok)throw Error();const x=await r.json();shownDay=x.date;
el('date').textContent=x.date+'（日本時間の集計）';for(const k of ['enter','exit','current'])el(k).textContent=x.totals?x.totals[k].toLocaleString('ja-JP'):'—';
el('connection').textContent=!x.totals?'本日の人数データはまだ届いていません':x.complete?'最新データを受信しています':'人数データの受信に遅れがあります。合計は参考値です。';el('connection').className=x.complete?'':'warning';
}catch{const today=new Date(Date.now()+9*3600000).toISOString().slice(0,10);if(shownDay&&shownDay!==today)clearCounts();el('connection').textContent='取得失敗：表示は最後の取得値です。';el('connection').className='warning';}finally{clearTimeout(t);setTimeout(refresh,10000);}}refresh();
