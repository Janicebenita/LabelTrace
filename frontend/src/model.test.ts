import {describe,it,expect} from 'vitest';
import {newest,latestFor,changedFields,pendingActions,pretty,Row,Workspace} from './model';
const row=(key:string,version:number)=>({key,version,id:key+version,created:'',actor:''}) as Row;
describe('Evidence workspace projections',()=>{
 it('keeps the newest approved version without deleting history',()=>{const history=[row('adult',1),row('adult',2),row('pediatric',1)];expect(newest(history).map(r=>r.id)).toEqual(['adult2','pediatric1']);expect(history).toHaveLength(3)});
 it('selects the correct immutable label history',()=>{expect(latestFor([row('a',1),row('b',9),row('a',2)],'a').version).toBe(2)});
 it('compares added, removed, and edited fields',()=>{const result=changedFields({a:'old',b:'same',d:'removed'},{a:'new',b:'same',c:'added'});expect(result.filter(x=>x.changed).map(x=>x.field)).toEqual(['a','d','c'])});
 it('does not flag identical label content',()=>{expect(changedFields({a:'same'},{a:'same'})[0].changed).toBe(false)});
 it('formats evidence keys for readers',()=>expect(pretty('adult.manufacturer_address')).toBe('adult / manufacturer address'));
 it('shows reviewers only their current review-ready revisions',()=>{
  const ws={user:{id:'checker',name:'Checker',role:'reviewer'},revisions:[
   {id:'r1',is_latest:true,state:'Review Ready',actor:'jayashree'},
   {id:'r2',is_latest:true,state:'Review Ready',actor:'checker'},
   {id:'r3',is_latest:false,state:'Review Ready',actor:'jayashree'},
   {id:'r4',is_latest:true,state:'Stale',actor:'jayashree'}
  ]} as unknown as Workspace;
  expect(pendingActions(ws).review).toBe(1);
 });
 it('counts only current, validated, exactly approved and unreleased revisions for release managers',()=>{
  const revision={id:'r1',is_latest:true,state:'Approved',stale_reasons:[],artifact_hash:'hash',snapshot_hash:'snapshot'};
  const validation={id:'v1',key:'r1',version:1,passed:true};
  const approval={id:'a1',key:'r1',version:1,artifact_hash:'hash',snapshot_hash:'snapshot',validation_id:'v1'};
  const base={user:{id:'releaser',name:'Releaser',role:'releaser'},revisions:[revision],validations:[validation],approvals:[approval],releases:[]} as unknown as Workspace;
  expect(pendingActions(base).release).toBe(1);
  expect(pendingActions({...base,releases:[{revision_id:'r1'}]} as unknown as Workspace).release).toBe(0);
  expect(pendingActions({...base,revisions:[{...revision,state:'Stale'}]} as unknown as Workspace).release).toBe(0);
 });
});
