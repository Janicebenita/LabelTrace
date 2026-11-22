// Rule-based quick checks: deterministic gate/validator/impact results shown without any LLM.
export type RuleKind='status'|'actions'|'impact';

export const RULE_BADGE='Rule-based · no LLM';
export const RULE_NOTICE='Rule-based result computed by the deterministic release gate and validators. No language model was used and nothing here is AI-generated.';
export const CHAT_DISABLED_NOTICE='Free-text conversation is disabled because no model is configured (it needs AGENT_ENABLED=1 and ANTHROPIC_API_KEY on the server). The rule-based checks below work without it.';

export const RULE_BUTTONS:{kind:RuleKind;label:string}[]=[
  {kind:'status',label:'Release status & blockers'},
  {kind:'actions',label:'Corrective actions'},
  {kind:'impact',label:'Change impact'},
];

export function ruleQuestion(kind:RuleKind,scope:string,factKey:string):string{
  if(kind==='impact')return `Change impact if ${factKey||'the selected fact'} changes`;
  return `${kind==='status'?'Release status & blockers':'Corrective actions'} · ${scope||'all label variants'}`;
}

/** Plain-language summary of a what-if impact result, built only from the fields the server returned. */
export function describeImpact(data:{fact_key?:string;downstream?:{label_key:string;status:string;would_become_stale?:boolean}[]}|null|undefined){
  const rows=data?.downstream??[];
  const named=(s:string)=>rows.filter(r=>r.status===s).map(r=>r.label_key);
  const affected=named('Affected'),assess=named('Needs assessment'),unaffected=named('Unaffected');
  const stale=rows.filter(r=>r.would_become_stale).map(r=>r.label_key);
  const summary=rows.length===0?'No impact data was returned.'
    :`${data?.fact_key??'This fact'} feeds ${affected.length+assess.length} of ${rows.length} label variants; ${stale.length} existing approval${stale.length===1?'':'s'} would go stale.`;
  return {summary,affected,assess,unaffected,stale};
}

/** Recommended actions from a report, de-duplicated, order preserved. */
export function uniqueActions(actions:string[]|undefined):string[]{return [...new Set(actions??[])]}
