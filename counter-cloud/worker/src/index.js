import {validate} from './validation.js';
const headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer'};
function reply(data, status=200) {return new Response(JSON.stringify(data), {status,headers:{...headers,'Content-Type':'application/json;charset=utf-8'}});}
async function secretMatch(a,b) {
  const digest = s=>crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));
  const [x,y] = await Promise.all([digest(a),digest(b)]);
  const u=new Uint8Array(x),v=new Uint8Array(y);let diff=0;
  for(let i=0;i<u.length;i++) diff|=u[i]^v[i];
  return diff===0;
}
async function bodyLimited(request) {
  const reader=request.body?.getReader();if(!reader)throw Error();
  const chunks=[];let size=0;
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8192){await reader.cancel();throw Error();}chunks.push(value);}
  const b=new Uint8Array(size);let p=0;for(const x of chunks){b.set(x,p);p+=x.length;}
  return JSON.parse(new TextDecoder().decode(b));
}
export default {async fetch(request,env) {
  try {
    const u=new URL(request.url);
    if(u.hostname===env.INGEST_HOST && u.pathname==='/api/upload') {
      if(u.pathname!=='/api/upload' || request.method!=='POST')return reply({error:'not found'},404);
      if(!env.UPLOAD_TOKEN || env.UPLOAD_TOKEN.length<32)return reply({error:'not configured'},503);
      const auth=request.headers.get('Authorization')||'';
      if(auth.length>512 || !await secretMatch(auth,'Bearer '+env.UPLOAD_TOKEN))return reply({error:'unauthorized'},401);
      if(!/^application\/json(?:;|$)/i.test(request.headers.get('Content-Type')||''))return reply({error:'JSON required'},415);
      let d;try{d=validate(await bodyLimited(request));}catch{return reply({error:'invalid data'},400);}
      if(!d)return reply({error:'invalid data or PC clock'},400);
      const captured=Date.parse(d.server_time), received=Date.now();
      await env.DB.prepare(`INSERT INTO gate_snapshots(day,gate_id,captured_ms,received_ms,payload) VALUES(?,?,?,?,?)
        ON CONFLICT(day,gate_id) DO UPDATE SET captured_ms=excluded.captured_ms,received_ms=excluded.received_ms,payload=excluded.payload
        WHERE excluded.captured_ms > gate_snapshots.captured_ms`).bind(d.date,d.gate_id,captured,received,JSON.stringify(d)).run();
      return reply({ok:true});
    }
    if(u.hostname!==env.VIEW_HOST)return reply({error:'not found'},404);
    if(request.method!=='GET')return reply({error:'method not allowed'},405);
    if(u.pathname==='/api/counts') {
      const cloud_time=Date.now(), day=new Date(cloud_time+9*3600000).toISOString().slice(0,10);
      const {results}=await env.DB.prepare('SELECT gate_id,payload,received_ms FROM gate_snapshots WHERE day=?').bind(day).all();
      const gates=['gate-1','gate-2'].map(gate_id=>{
        const row=results.find(r=>r.gate_id===gate_id), data=row?JSON.parse(row.payload):null;
        return {gate_id,data,received_at:row?.received_ms??null,
          online:!!row && cloud_time-row.received_ms<=30000,
          measuring:!!data?.last_frame && cloud_time-Date.parse(data.last_frame)<=15000};
      });
      const available=gates.filter(g=>g.data);
      const totals=available.length?available.reduce((sum,g)=>{
        for(const k of ['enter','exit','current'])sum[k]+=g.data[k];return sum;
      },{enter:0,exit:0,current:0}):null;
      return reply({date:day,totals,complete:gates.every(g=>g.online&&g.measuring),cloud_time});
    }
    return reply({error:'not found'},404);
  } catch {return reply({error:'server unavailable'},503);}
}};
