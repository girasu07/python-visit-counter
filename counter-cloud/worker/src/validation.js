export function validate(d, now = Date.now()) {
  if (!d || typeof d !== 'object' || Array.isArray(d)) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.date)) return null;
  for (const k of ['enter','exit']) if (!Number.isSafeInteger(d[k]) || d[k]<0 || d[k]>10000000) return null;
  if (d.current !== d.enter-d.exit) return null;
  const captured = Date.parse(d.server_time);
  if (!Number.isFinite(captured) || Math.abs(now-captured)>300000) return null;
  const jst = new Date(captured+9*3600000).toISOString().slice(0,10);
  if (d.date !== jst) return null;
  if (typeof d.status !== 'string' || d.status.length>120) return null;
  for (const k of ['last_frame','last_event']) {
    if (d[k] !== null && (typeof d[k] !== 'string' || !Number.isFinite(Date.parse(d[k])) || Date.parse(d[k])>captured+1000)) return null;
  }
  return {date:d.date, enter:d.enter, exit:d.exit, current:d.current, status:d.status,
    last_frame:d.last_frame, last_event:d.last_event, server_time:d.server_time};
}
