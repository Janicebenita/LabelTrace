import React,{useEffect,useMemo,useRef,useState} from 'react';
import {ArrowRight,Bot,ListChecks,Lock,Network,Search,Send,ShieldCheck,TriangleAlert,Workflow} from 'lucide-react';
import {api,newest,Row,short,Workspace} from './model';
import {CHAT_DISABLED_NOTICE,RULE_BADGE,RULE_BUTTONS,RULE_NOTICE,RuleKind,describeImpact,ruleQuestion,uniqueActions} from './rules';
import './agent.css';

export type Gate={label_key:string;status:string;blockers:string[];pending_human_actions:string[];workflow_state?:string|null;released:boolean;revision_id?:string|null};
export type Finding={id:string;severity:string;explanation:string;evidence_ids:string[];classification:string;recommended_action:string};
export type Evidence={id:string;kind:string;record_id:string;summary:string;tool:string;cited_by:string[]};
export type Activity={step:number;tool:string;args:Record<string,unknown>;ok:boolean;evidence_ids:string[];elapsed_ms:number;error?:string|null};
export type PlanStep={id:string;title:string;role:string;workflow_page:string;reason:string;evidence_ids:string[];status:string};
export type Plan={label_key:string;gate_status:string;steps:PlanStep[];artifacts_to_regenerate?:boolean;validations_to_repeat?:boolean;approvals_to_renew?:boolean;already_released?:boolean};
export type Report={request_id:string;run_id?:string|null;mode:'claude'|'deterministic';model?:string|null;summary:string;release_status:string;label_statuses:Gate[];affected_variants:string[];findings:Finding[];evidence:Evidence[];recommended_actions:string[];limitations:string[];human_review_required:boolean;tool_activity:Activity[];plans:Plan[]};
type Turn={q:string;res?:Report;err?:string;rule?:RuleKind;impact?:any};

export const statusClass=(s:string)=>s==='READY'?'ready':s==='BLOCKED'?'blocked':s==='REVIEW REQUIRED'?'review':'unknown';
export const CLASS_LABEL:Record<string,string>={deterministic:'Deterministic',ai_advisory:'AI advisory',insufficient_evidence:'Insufficient evidence',human_review:'Human review'};
const Pill=({s}:{s:string})=><span className={'ai-pill '+statusClass(s)}>{s}</span>;
const clip=(v:unknown,n=48)=>{const t=typeof v==='string'?v:JSON.stringify(v);return t&&t.length>n?t.slice(0,n)+'…':t};

export function ImpactGraph({data}:{data:any}){
  const rows:any[]=data.downstream,h=Math.max(200,rows.length*78+16),mid=h/2;
  return <div className="ai-graph-scroll" tabIndex={0} role="group" aria-label="Dependency graph, scrollable"><svg className="ai-graph" viewBox={`0 0 760 ${h}`} role="img" aria-label={`Dependency graph: ${data.fact_key} feeds ${rows.filter(r=>r.status!=='Unaffected').length} of ${rows.length} label variants`}>
    <g><rect className="node fact" x="8" y={mid-38} width="230" height="76" rx="12"/><text x="22" y={mid-12} className="t-sm">APPROVED FACT</text><text x="22" y={mid+8} className="t-b">{clip(data.fact_key,26)}</text><text x="22" y={mid+27} className="t-sm">{clip(data.current_value,30)}</text></g>
    {rows.map((r,i)=>{const y=8+i*78,on=r.status==='Affected',na=r.status==='Needs assessment';
      return <g key={r.label_key}>
        <path className={'edge '+(on?'on':na?'maybe':'off')} d={`M238 ${mid} C 340 ${mid}, 340 ${y+34}, 500 ${y+34}`}/>
        <rect className={'node '+(on?'affected':na?'maybe':'unaffected')} x="500" y={y} width="252" height="68" rx="12"/>
        <text x="514" y={y+22} className="t-b">{r.label_key}</text>
        <text x="514" y={y+40} className="t-sm">{r.status}{r.would_become_stale?' · approval would go stale':''}</text>
        <text x="514" y={y+56} className="t-sm">{r.state?`now: ${r.state}`:'no revision'}{r.current_gate_status?` · gate ${r.current_gate_status}`:''}</text>
      </g>})}
  </svg></div>;
}

export default function AgentWorkspace({ws,go}:{ws:Workspace;go:(page:string)=>void}){
  const labels=useMemo(()=>newest(ws.labels as Row[]),[ws.labels]);
  const facts=useMemo(()=>newest(ws.facts as Row[]).sort((a,b)=>a.key.localeCompare(b.key)),[ws.facts]);
  const stamp=[ws.revisions,ws.validations,ws.approvals,ws.releases,ws.facts].map((x:any[])=>x.length).join('-');
  const [status,setStatus]=useState<{configured:boolean;model?:string|null}|null>(null);
  const [labelKey,setLabelKey]=useState('');
  const [report,setReport]=useState<Report|null>(null);
  const [factKey,setFactKey]=useState(()=>facts.find(f=>f.key.endsWith('manufacturer_address'))?.key||facts[0]?.key||'');
  const [impact,setImpact]=useState<any>(null);
  const [turns,setTurns]=useState<Turn[]>([]);
  const [question,setQuestion]=useState('');
  const [asking,setAsking]=useState(false);
  const [selected,setSelected]=useState('');
  const [kind,setKind]=useState('all');
  const [error,setError]=useState('');
  const explorer=useRef<HTMLElement>(null);

  useEffect(()=>{api('/agent/status').then(setStatus).catch(e=>setError(e.message))},[]);
  useEffect(()=>{let live=true;api('/agent/report'+(labelKey?`?label_key=${encodeURIComponent(labelKey)}`:'')).then(r=>live&&setReport(r)).catch(e=>live&&setError(e.message));return()=>{live=false}},[labelKey,stamp]);
  useEffect(()=>{let live=true;if(!factKey)return;api('/agent/impact?fact_key='+encodeURIComponent(factKey)).then(r=>live&&setImpact(r.data)).catch(e=>live&&(setImpact(null),setError(e.message)));return()=>{live=false}},[factKey,stamp]);

  const last=[...turns].reverse().find(t=>t.res)?.res||null;
  const shown=last||report;
  const scope=labelKey||'a label';
  const gates=report?.label_statuses||[];
  const suggestions=useMemo(()=>{
    const l=labelKey||'this label',list=[`Can ${l} be released now?`,`Why is ${l} blocked from release?`,'What happens if the manufacturer’s address changes?',
      `What corrective actions are required before ${l} can be released?`,`Show me the complete change history and evidence for ${l}.`,'Which variants and approvals are affected if the adult manufacturer address changes?'];
    if(report?.findings.some(f=>f.explanation.includes('INT-BARCODE-DECODE')))list.unshift(`Why is ${l} failing QR verification?`);
    if(gates.some(g=>g.status==='BLOCKED'&&g.workflow_state==='Stale'))list.unshift('Why was my previously approved label blocked?');
    return list.slice(0,6);
  },[labelKey,report,gates]);

  async function ask(q:string){
    q=q.trim();if(q.length<3||asking)return;
    setAsking(true);setError('');setQuestion('');setTurns(t=>[...t,{q}]);
    try{const res:Report=await api('/agent/query',{question:q,label_key:labelKey||undefined});setTurns(t=>t.map((x,i)=>i===t.length-1?{...x,res}:x))}
    catch(e:any){setTurns(t=>t.map((x,i)=>i===t.length-1?{...x,err:e.message}:x))}
    finally{setAsking(false)}
  }
  async function runRule(kind:RuleKind){
    if(asking)return;
    setAsking(true);setError('');
    const q=ruleQuestion(kind,labelKey,factKey);
    setTurns(t=>[...t,{q,rule:kind}]);
    try{
      if(kind==='impact'){const r=await api('/agent/impact?fact_key='+encodeURIComponent(factKey));setTurns(t=>t.map((x,i)=>i===t.length-1?{...x,impact:r.data}:x))}
      else{const res:Report=await api('/agent/report'+(labelKey?`?label_key=${encodeURIComponent(labelKey)}`:''));setTurns(t=>t.map((x,i)=>i===t.length-1?{...x,res}:x))}
    }catch(e:any){setTurns(t=>t.map((x,i)=>i===t.length-1?{...x,err:e.message}:x))}
    finally{setAsking(false)}
  }
  const openEvidence=(id:string)=>{setSelected(id);setKind('all');explorer.current?.scrollIntoView({behavior:'smooth',block:'start'})};
  const evidence=(shown?.evidence||[]).filter(e=>kind==='all'||e.kind===kind);
  const kinds=[...new Set((shown?.evidence||[]).map(e=>e.kind))];
  const EvChips=({ids}:{ids:string[]})=><>{ids.map(id=><button key={id} className="ai-chip" onClick={()=>openEvidence(id)} aria-label={`Open evidence ${id}`}>{id}</button>)}</>;

  return <div className="ai">
    <section className="ai-strip" aria-label="Agent boundaries">
      <div><Bot size={20}/><b>LabelTrace AI</b><span>{status?(status.configured?`Claude · ${status.model}`:'Deterministic mode (no API key configured)'):'Checking agent…'}</span></div>
      <div><Lock size={16}/><span>Read-only: it can analyse and recommend. It cannot approve, regenerate, invalidate or release. The deterministic release gate stays authoritative.</span></div>
      <label>Scope<select aria-label="Label scope" value={labelKey} onChange={e=>setLabelKey(e.target.value)}><option value="">All label variants</option>{labels.map(l=><option key={l.key} value={l.key}>{l.key}</option>)}</select></label>
    </section>
    {error&&<div role="alert" className="alert error"><TriangleAlert size={19}/><div>{error}</div></div>}

    <div className="ai-grid">
      <section className="card ai-chat" aria-label="AI Command Center">
        <div className="card-head"><div><h2><Search size={17}/> AI Command Center</h2><p>Ask about {scope==='a label'?'labels':scope}, validation failures, impact and release readiness.</p></div></div>
        <div className="ai-suggest">{suggestions.map(s=><button key={s} disabled={asking||!status?.configured} onClick={()=>ask(s)}>{s}</button>)}</div>
        {status&&!status.configured&&<p className="ai-note">{CHAT_DISABLED_NOTICE}</p>}
        <div className="ai-rules" role="group" aria-label="Rule-based checks (no LLM)">
          <span className="ai-rules-tag">{RULE_BADGE}</span>
          {RULE_BUTTONS.map(b=><button key={b.kind} disabled={asking||(b.kind==='impact'&&!factKey)} onClick={()=>runRule(b.kind)}>{b.label}</button>)}
        </div>
        <div className="ai-thread" aria-live="polite">
          {turns.length===0&&<p className="ai-empty">{status?.configured?'No questions yet. Answers cite real records; every cited id opens in the Evidence Explorer.':'Nothing run yet. Choose a rule-based check above; results cite real records and every cited id opens in the Evidence Explorer.'}</p>}
          {turns.map((t,i)=><div key={i} className="ai-turn">
            <div className="ai-q">{t.q}</div>
            {!t.res&&!t.impact&&!t.err&&<div className="ai-a ai-wait">{t.rule?'Running rule-based check…':'Retrieving evidence with tools…'}</div>}
            {t.err&&<div className="ai-a ai-err"><TriangleAlert size={16}/> {t.err}</div>}
            {t.impact&&(()=>{const d=describeImpact(t.impact);return <div className="ai-a ai-rule-answer">
              <div className="ai-meta"><span>Hypothetical change impact</span><span className="ai-mode rules">{RULE_BADGE}</span></div>
              <p className="ai-summary">{d.summary}</p>
              <ImpactGraph data={t.impact}/>
              <p className="ai-hr"><ShieldCheck size={14}/> {RULE_NOTICE} Nothing was changed.</p>
            </div>})()}
            {t.res&&<div className={'ai-a'+(t.rule?' ai-rule-answer':'')}>
              <div className="ai-meta"><span>Deterministic gate status</span><Pill s={t.res.release_status}/><span className={'ai-mode'+(t.rule?' rules':'')}>{t.rule?RULE_BADGE:t.res.mode==='claude'?`Claude · ${t.res.model}`:'Deterministic fallback'}</span></div>
              <p className="ai-summary">{t.res.summary}</p>
              {t.rule!=='actions'&&t.res.findings.map(f=><div key={f.id} className={'ai-finding sev-'+f.severity}>
                <div><b>{f.id}</b><span className="ai-sev">{f.severity}</span><span className={'ai-class '+f.classification}>{CLASS_LABEL[f.classification]}</span></div>
                <p>{f.explanation}</p>{f.recommended_action&&<p className="ai-act"><ArrowRight size={13}/> {f.recommended_action}</p>}
                <div className="ai-chips"><EvChips ids={f.evidence_ids}/>{f.evidence_ids.length===0&&<em>no verified evidence cited</em>}</div></div>)}
              {uniqueActions(t.res.recommended_actions).length>0&&<><h3>{t.rule?'Corrective actions (from the deterministic checklist)':'Recommended actions (advisory)'}</h3><ul>{uniqueActions(t.res.recommended_actions).map((a,j)=><li key={j}>{a}</li>)}</ul></>}
              <details><summary>Limitations</summary><ul>{t.res.limitations.map((a,j)=><li key={j}>{a}</li>)}</ul></details>
              <p className="ai-hr"><ShieldCheck size={14}/> {t.rule?RULE_NOTICE+' Human review is still required.':'Human review required. This analysis is not release evidence.'}</p>
            </div>}
          </div>)}
        </div>
        <form className="ai-form" onSubmit={e=>{e.preventDefault();ask(question)}}>
          <input aria-label="Ask LabelTrace AI" maxLength={1000} placeholder={status?.configured?'Ask about a label, change or release blocker…':'AI conversation is not configured'} value={question} disabled={!status?.configured||asking} onChange={e=>setQuestion(e.target.value)}/>
          <button className="primary" disabled={!status?.configured||asking||question.trim().length<3}><Send size={16}/> Ask</button>
        </form>
      </section>

      <section className="card ai-release" aria-label="Release Intelligence Panel">
        <div className="card-head"><div><h2><ShieldCheck size={17}/> Release Intelligence</h2><p>Computed by the deterministic gate. No model involved.</p></div>{report&&<Pill s={report.release_status}/>}</div>
        {!report&&<p className="ai-empty">Loading gate results…</p>}
        {gates.map(g=><div key={g.label_key} className="ai-gate">
          <div className="ai-gate-head"><b>{g.label_key}</b><Pill s={g.status}/><small>{g.released?'Released':g.workflow_state||''}</small></div>
          {g.blockers.length===0?<p className="ai-ok">All configured deterministic release conditions pass.</p>
            :<ul>{g.blockers.map(b=><li key={b} className={g.pending_human_actions.includes(b)?'pending':'hard'}>{b}</li>)}</ul>}
        </div>)}
        <h3 className="ai-h3"><ListChecks size={16}/> Corrective action checklist</h3>
        {report?.plans.every(p=>p.steps.length===0)&&<p className="ai-empty">No corrective action needed.</p>}
        {report?.plans.filter(p=>p.steps.length>0).map(p=><div key={p.label_key} className="ai-plan">
          <b>{p.label_key}</b>
          <ol>{p.steps.map(s=><li key={s.id}><div><span className="ai-step-id">{s.id}</span> {s.title}<small>{s.role} · {s.reason}</small></div><button onClick={()=>go(s.workflow_page)}>{s.workflow_page}<ArrowRight size={14}/></button></li>)}</ol>
          <small className="ai-flags">{[p.artifacts_to_regenerate&&'regenerate artifact',p.validations_to_repeat&&'repeat validation',p.approvals_to_renew&&'renew approval'].filter(Boolean).join(' · ')}</small>
        </div>)}
        <p className="ai-note">Advisory only: each step is performed by an authorized person in the existing workflow.</p>
      </section>
    </div>

    <section className="card" aria-label="Agent reasoning timeline">
      <div className="card-head"><div><h2><Workflow size={17}/> Agent Reasoning Timeline</h2><p>Factual tool activity only. Model reasoning is not shown.</p></div></div>
      {!last?<p className="ai-empty">Ask a question to see which tools ran and what evidence they returned.</p>:<ol className="ai-timeline">
        <li><b>Request</b><span>{[...turns].reverse().find(t=>t.res)?.q}</span></li>
        {last.tool_activity.map(a=><li key={a.step} className={a.ok?'':'bad'}><b>{a.step}. {a.tool}</b><span>{Object.keys(a.args).length?Object.entries(a.args).map(([k,v])=>`${k}=${clip(v,30)}`).join(', '):'no arguments'}</span>
          <small>{a.ok?`${a.evidence_ids.length} evidence item(s)`:`refused/failed: ${a.error}`} · {a.elapsed_ms} ms</small></li>)}
        <li><b>Evidence identified</b><span>{last.evidence.length} record(s); {last.evidence.filter(e=>e.cited_by.length).length} cited by findings</span></li>
        <li><b>Gate status (server-derived)</b><span><Pill s={last.release_status}/> {last.mode==='claude'?'Narrative written by the model; status never set by it.':'Model output unavailable; deterministic results shown.'}</span></li>
      </ol>}
    </section>

    <section className="card" aria-label="Change impact visualization">
      <div className="card-head"><div><h2><Network size={17}/> Change Impact</h2><p>Hypothetical: which variants and approvals depend on a source fact. Nothing is written.</p></div>
        <label className="inline-label">Fact<select aria-label="Source fact" value={factKey} onChange={e=>setFactKey(e.target.value)}>{facts.map(f=><option key={f.key} value={f.key}>{f.key}</option>)}</select></label></div>
      {impact?<><div className="table-wrap"><ImpactGraph data={impact}/></div>
        <ul className="ai-legend"><li><i className="affected"/>Affected</li><li><i className="maybe"/>Needs assessment</li><li><i className="unaffected"/>Unaffected</li></ul>
        <p className="ai-note">{impact.note}</p></>:<p className="ai-empty">Select a fact to trace its dependent variants.</p>}
    </section>

    <section className="card" aria-label="Evidence Explorer" id="ai-evidence" ref={explorer}>
      <div className="card-head"><div><h2><Search size={17}/> Evidence Explorer</h2><p>Real record ids and hashes returned by tools for {last?'the latest answer':'the deterministic report'}.</p></div>
        <label className="inline-label">Type<select aria-label="Evidence type" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">All</option>{kinds.map(k=><option key={k} value={k}>{k.replaceAll('_',' ')}</option>)}</select></label></div>
      {evidence.length===0?<p className="ai-empty">No evidence collected yet.</p>:<div className="table-wrap"><table className="ai-table"><thead><tr><th>ID</th><th>Type</th><th>Record</th><th>Summary</th><th>Tool</th><th>Cited by</th></tr></thead><tbody>
        {evidence.map(e=><tr key={e.id} className={selected===e.id?'sel':''}><td><b>{e.id}</b></td><td>{e.kind.replaceAll('_',' ')}</td><td><code title={e.record_id}>{short(e.record_id)}</code></td><td>{e.summary}</td><td>{e.tool}</td><td>{e.cited_by.join(', ')||'—'}</td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}
