import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {validate} from './src/validation.js';
const now=Date.parse('2026-10-13T00:00:01+09:00');
const good={gate_id:'gate-1',date:'2026-10-13',enter:4,exit:1,current:3,status:'計測中',server_time:'2026-10-13T00:00:01+09:00',last_frame:'2026-10-13T00:00:00+09:00',last_event:null};
test('JST day and allowlist',()=>{assert.deepEqual(validate({...good,password:'secret'},now),good);assert.equal(validate({...good,date:'2026-10-12'},now),null);});
test('reject corrupt and stale counts',()=>{for(const d of [{...good,enter:-1},{...good,current:99},{...good,exit:1.5},{...good,last_frame:'bad'}])assert.equal(validate(d,now),null);assert.equal(validate(good,now+360000),null);});
test('negative estimated occupancy is allowed',()=>{assert.ok(validate({...good,enter:0,current:-1},now));});
import worker from './src/index.js';
const env={VIEW_HOST:'counter.gidaisai.jp',INGEST_HOST:'counter.gidaisai.jp',UPLOAD_TOKEN:'x'.repeat(43)};
test('public page is split into HTML, CSS and JavaScript assets',async()=>{const base=new URL('./public/',import.meta.url);const html=await readFile(fileURLToPath(new URL('index.html',base)),'utf8');const css=await readFile(fileURLToPath(new URL('assets/page.css',base)),'utf8');const js=await readFile(fileURLToPath(new URL('assets/page-client.js',base)),'utf8');assert.match(html,/href="\/assets\/page.css"/);assert.match(html,/src="\/assets\/page-client.js"/);assert.match(css,/\.warning/);assert.match(js,/api\/counts/);});
test('ingest cannot read counts or upload without secret',async()=>{assert.equal((await worker.fetch(new Request('https://counter.gidaisai.jp/api/upload',{method:'POST'}),env)).status,401);});
test('authenticated snapshot saved with bound parameters',async()=>{const d={...good,server_time:new Date().toISOString(),last_frame:null};d.date=new Date(Date.now()+9*3600000).toISOString().slice(0,10);let args;const e={...env,DB:{prepare:()=>({bind:(...a)=>{args=a;return {run:async()=>({success:true})};}})}};const r=await worker.fetch(new Request('https://counter.gidaisai.jp/api/upload',{method:'POST',headers:{Authorization:'Bearer '+env.UPLOAD_TOKEN,'Content-Type':'application/json'},body:JSON.stringify(d)}),e);assert.equal(r.status,200);assert.equal(JSON.parse(args[4]).current,3);});

test('unknown or missing gate rejected',()=>{for(const gate_id of [undefined,'gate-3',''])assert.equal(validate({...good,gate_id},now),null);});
test('two gates aggregate; missing/stale gate marks incomplete',async()=>{
 const day=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
 for(const rows of [[],[{gate_id:'gate-1',payload:JSON.stringify({...good,enter:10,exit:2,current:8,last_frame:new Date().toISOString()}),received_ms:Date.now()}],['gate-1','gate-2'].map(gate_id=>({gate_id,payload:JSON.stringify({...good,last_frame:new Date().toISOString()}),received_ms:Date.now()}))]){
 let bound;
 const e={...env,DB:{prepare:sql=>({bind:d=>{bound=d;return {all:async()=>({results:rows})};}})}};
 const r=await worker.fetch(new Request('https://counter.gidaisai.jp/api/counts'),e),x=await r.json();assert.equal(r.status,200);assert.equal(bound,day);assert.equal('gates' in x,false);assert.equal(x.totals?.current??null,rows.length===2?6:rows.length===1?8:null);assert.equal(x.complete,rows.length===2);
 }
 const e={...env,DB:{prepare:()=>({bind:()=>({all:async()=>({results:[{gate_id:'gate-1',payload:JSON.stringify(good),received_ms:Date.now()-60000}]})})})}};
 const x=await (await worker.fetch(new Request('https://counter.gidaisai.jp/api/counts'),e)).json();assert.equal('gates' in x,false);assert.equal(x.complete,false);
});
