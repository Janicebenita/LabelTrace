import {describe,expect,it} from 'vitest';
import {CHAT_DISABLED_NOTICE,RULE_BADGE,RULE_BUTTONS,RULE_NOTICE,describeImpact,ruleQuestion,uniqueActions} from './rules';

const rows=[
  {label_key:'adult.box',status:'Affected',would_become_stale:true},
  {label_key:'adult.carton',status:'Affected',would_become_stale:false},
  {label_key:'pediatric.box',status:'Unaffected'},
  {label_key:'pediatric.carton',status:'Needs assessment'},
];

describe('rule-based quick checks',()=>{
  it('is always labeled as rule-based and never as AI or a model',()=>{
    expect(RULE_BADGE).toBe('Rule-based · no LLM');
    expect(RULE_NOTICE).toMatch(/No language model was used/);
    for(const text of [RULE_BADGE,RULE_NOTICE,...RULE_BUTTONS.map(b=>b.label)])expect(text).not.toMatch(/\bClaude\b|\bAI-generated analysis\b/i);
  });
  it('states that free-text chat is disabled without a model',()=>{
    expect(CHAT_DISABLED_NOTICE).toMatch(/Free-text conversation is disabled/);
    expect(CHAT_DISABLED_NOTICE).toMatch(/AGENT_ENABLED=1/);
  });
  it('offers exactly the three deterministic checks',()=>{
    expect(RULE_BUTTONS.map(b=>b.kind)).toEqual(['status','actions','impact']);
  });
  it('builds readable questions for each check',()=>{
    expect(ruleQuestion('status','adult.box','x')).toBe('Release status & blockers · adult.box');
    expect(ruleQuestion('actions','','x')).toBe('Corrective actions · all label variants');
    expect(ruleQuestion('impact','adult.box','adult.manufacturer_address')).toBe('Change impact if adult.manufacturer_address changes');
  });
  it('summarizes impact only from returned fields',()=>{
    const d=describeImpact({fact_key:'adult.manufacturer_address',downstream:rows});
    expect(d.affected).toEqual(['adult.box','adult.carton']);
    expect(d.assess).toEqual(['pediatric.carton']);
    expect(d.unaffected).toEqual(['pediatric.box']);
    expect(d.stale).toEqual(['adult.box']);
    expect(d.summary).toBe('adult.manufacturer_address feeds 3 of 4 label variants; 1 existing approval would go stale.');
  });
  it('handles missing or empty impact data without inventing results',()=>{
    expect(describeImpact(null).summary).toBe('No impact data was returned.');
    expect(describeImpact({fact_key:'f',downstream:[]}).affected).toEqual([]);
    expect(describeImpact({fact_key:'f',downstream:[{label_key:'a',status:'Affected',would_become_stale:true},{label_key:'b',status:'Affected',would_become_stale:true}]}).summary).toContain('2 existing approvals');
  });
  it('de-duplicates corrective actions and keeps order',()=>{
    expect(uniqueActions(['b','a','b'])).toEqual(['b','a']);
    expect(uniqueActions(undefined)).toEqual([]);
  });
});
