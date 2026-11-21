// API evidence envelopes have a stable identity and version; payloads vary by record kind.
export type Row = {id:string;key:string;version:number;created:string;actor:string;[key:string]:any};
export type Workspace = {user:{id:string;name:string;role:string};mode:{database:string;ai:string;demo:boolean;storage:string;document_extractor:string};[key:string]:any};
export const newest = (rows:Row[]) => Object.values(rows.reduce<Record<string,Row>>((acc,r)=>{if(!acc[r.key] || acc[r.key].version<r.version)acc[r.key]=r;return acc;},{}));
export const latestFor = (rows:Row[], key:string) => rows.filter(r=>r.key===key).sort((a,b)=>b.version-a.version)[0];
export const changedFields = (before:Record<string,string>,after:Record<string,string>) => [...new Set([...Object.keys(before),...Object.keys(after)])].map(field=>({field,old:before[field]??'—',value:after[field]??'—',changed:before[field]!==after[field]}));
export function pendingActions(workspace:Workspace){
  const current=(workspace.revisions as Row[]).filter(r=>r.is_latest);
  const review=workspace.user.role==='reviewer'
    ?current.filter(r=>r.state==='Review Ready'&&r.actor!==workspace.user.id).length:0;
  const release=workspace.user.role==='releaser'
    ?current.filter(r=>{
      if(r.state!=='Approved'||(r.stale_reasons||[]).length>0)return false;
      const validation=latestFor(workspace.validations as Row[],r.id);
      const approval=latestFor(workspace.approvals as Row[],r.id);
      const alreadyReleased=(workspace.releases as Row[]).some(x=>x.revision_id===r.id);
      return !alreadyReleased&&!!validation?.passed&&!!approval
        &&approval.artifact_hash===r.artifact_hash
        &&approval.snapshot_hash===r.snapshot_hash
        &&approval.validation_id===validation.id;
    }).length:0;
  const needsRevision=workspace.user.role==='author'
    ?current.filter(r=>r.state==='Stale'||(r.state==='Released'&&r.follow_up_required)).length:0;
  const needsValidation=workspace.user.role==='author'
    ?current.filter(r=>r.state==='Draft'||r.state==='Validation Failed').length:0;
  return {review,release,needsRevision,needsValidation};
}
export const pretty = (value:string) => value.replaceAll('_',' ').replaceAll('.',' / ');
export const short = (value:string) => value?.slice(0,12)??'—';
export async function api(path:string, body?:unknown, method?:string){
  const response=await fetch('/api'+path,{method:method??(body===undefined?'GET':'POST'),credentials:'same-origin',
    headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail+(data.reasons?' · '+data.reasons.join(' · '):''):JSON.stringify(data.detail));
  return data;
}
