import {createRemoteJWKSet, jwtVerify} from 'jose';
import {validate} from './validation.js';
import {PAGE} from './page.js';
const keys = new Map();
const headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer'};
function reply(data, status=200) {return new Response(JSON.stringify(data), {status,headers:{...headers,'Content-Type':'application/json;charset=utf-8'}});}
async function secretMatch(a,b) {
  const digest = s=>crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));
  const [x,y] = await Promise.all([digest(a),digest(b)]);
  const u=new Uint8Array(x),v=new Uint8Array(y);let diff=0;
  for(let i=0;i<u.length;i++) diff|=u[i]^v[i];
  return diff===0;
}
async function viewer(request,env) {
  if (!env.ACCESS_AUD || env.ACCESS_AUD==='REPLACE' || !/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(env.TEAM_DOMAIN) || env.TEAM_DOMAIN.includes('REPLACE')) return false;
  const token=request.headers.get('Cf-Access-Jwt-Assertion');if(!token)return false;
  try {
    if(!keys.has(env.TEAM_DOMAIN)) keys.set(env.TEAM_DOMAIN,createRemoteJWKSet(new URL(env.TEAM_DOMAIN+'/cdn-cgi/access/certs')));
    const {payload}=await jwtVerify(token,keys.get(env.TEAM_DOMAIN),{issuer:env.TEAM_DOMAIN,audience:env.ACCESS_AUD,algorithms:['RS256'],requiredClaims:['exp','iat','sub']});
    return typeof payload.email==='string' && payload.email.length>0;
  } catch {return false;}
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
    if(u.hostname===env.INGEST_HOST) {
      if(u.pathname!=='/api/upload' || request.method!=='POST')return reply({error:'not found'},404);
      if(!env.UPLOAD_TOKEN || env.UPLOAD_TOKEN.length<32)return reply({error:'not configured'},503);
      const auth=request.headers.get('Authorization')||'';
      if(auth.length>512 || !await secretMatch(auth,'Bearer '+env.UPLOAD_TOKEN))return reply({error:'unauthorized'},401);
      if(!/^application\/json(?:;|$)/i.test(request.headers.get('Content-Type')||''))return reply({error:'JSON required'},415);
      let d;try{d=validate(await bodyLimited(request));}catch{return reply({error:'invalid data'},400);}
      if(!d)return reply({error:'invalid data or PC clock'},400);
      const captured=Date.parse(d.server_time), received=Date.now();
      await env.DB.prepare(`INSERT INTO daily_snapshots(day,captured_ms,received_ms,payload) VALUES(?,?,?,?)
        ON CONFLICT(day) DO UPDATE SET captured_ms=excluded.captured_ms,received_ms=excluded.received_ms,payload=excluded.payload
        WHERE excluded.captured_ms > daily_snapshots.captured_ms`).bind(d.date,captured,received,JSON.stringify(d)).run();
      return reply({ok:true});
    }
    if(u.hostname!==env.VIEW_HOST)return reply({error:'not found'},404);
    if(!await viewer(request,env))return reply({error:'委員のログインが必要です。Access設定を確認してください。'},403);
    if(request.method!=='GET')return reply({error:'method not allowed'},405);
    if(u.pathname==='/') return new Response(PAGE,{headers:{...headers,'Content-Type':'text/html;charset=utf-8','Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}});
    if(u.pathname==='/api/counts') {
      const row=await env.DB.prepare('SELECT payload,received_ms FROM daily_snapshots ORDER BY day DESC LIMIT 1').first();
      return reply({data:row?JSON.parse(row.payload):null,received_at:row?.received_ms??null,cloud_time:Date.now()});
    }
    return reply({error:'not found'},404);
  } catch {return reply({error:'server unavailable'},503);}
}};
