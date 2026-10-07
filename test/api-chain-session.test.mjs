import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import process from 'node:process';
/* global fetch */
import test from 'node:test';
import {startAppSessionHost} from '../scripts/app_session_host.mjs';

test('trusted callback must be callable; original preview remains safe', async () => {
  await assert.rejects(startAppSessionHost({capabilityCheck:true}));
  const host = await startAppSessionHost();
  try {
    const state = await (await fetch(host.url + 'status')).json();
    assert.deepEqual(state, {mode:'synthetic', status:'READY_SYNTHETIC', verified:false});
  } finally {await host.close();}
});

test('ordered commands, frozen sources, synthetic full matrix and exhausted allowance', () => {
  const result = spawnSync('C:\\Users\\QQ\\AppData\\Local\\Programs\\Python\\Python312\\python.exe', ['-c', String.raw`
import hashlib, json, tempfile
from pathlib import Path
import api_chain_session as s
import api_chain_operator as o

def blocked(fn):
    try: fn()
    except (ValueError, o.OperatorBlocked): return
    raise AssertionError('expected block')

assert s.command({'phase':'nonmember'}, 'nonmember', None)
assert not s.command({'phase':'nonmember'}, 'reviewer', {'phase':'nonmember'})
blocked(lambda: s.command({'phase':'owner'}, 'reviewer', None))
blocked(lambda: s.command({'phase':'dispatch','marker_sha':'a'*40}, 'dispatch', None))
blocked(lambda: s.command({'phase':'owner','extra':True}, 'owner', None))
with tempfile.TemporaryDirectory() as name:
    folder=Path(name)
    contract=b'synthetic contract'
    (folder/'TASK.md').write_bytes(contract)
    sources={path:hashlib.sha256((s.ROOT/path).read_bytes()).hexdigest() for path in
             ('scripts/app_session_host.mjs','scripts/lib/app_session.mjs','scripts/app_session_receiver.py',
              'scripts/api_chain_operator.py','scripts/api_chain_session.py','scripts/api_chain_session_host.mjs')}
    approval={'head':'a'*40,'status':'EXACT_SCOPE_APPROVED','workflow_head':s.WORKFLOW_HEAD,
              'contract_sha256':hashlib.sha256(contract).hexdigest(),'source_sha256':sources}
    (folder/'approval.json').write_text(json.dumps(approval))
    s.check_scope(folder)
    (folder/'TASK.md').write_bytes(b'changed')
    blocked(lambda:s.check_scope(folder))
    context={'public_key':'synthetic-public-key','access_token':'synthetic-app-token',
             'user_uuid':'10000000-0000-4000-8000-000000000001'}
    ledger=o.OperatorLedger(folder/'receipt.json')
    current=None
    sent=[]
    def sender(method,url,headers,body):
        sent.append(url)
        if url.endswith(o.EDGE_PATH):
            if current=='anonymous': return o.HttpResponse(401,b'{"error_code":"AUTH_REQUIRED"}')
            if current in ('nonmember','reviewer'): return o.HttpResponse(403,b'{"error_code":"OWNER_REQUIRED"}')
            return o.HttpResponse(202,json.dumps({'job_id':o.JOB_ID,'status':'dispatched','created':False}).encode())
        if '/rpc/' in url or method=='POST' and current!='owner':
            return o.HttpResponse(403,b'{"code":"42501"}')
        if '/workspaces?' in url:
            rows=[] if current in ('anonymous','nonmember') else [{'id':o.WORKSPACE_ID,'name':o.WORKSPACE_NAME}]
            return o.HttpResponse(200,json.dumps(rows).encode())
        row={**o._JOB_INSERT,'requested_by':context['user_uuid'],'attempt_count':0,
             'runner_id':None,'lease_expires_at':None,'heartbeat_at':None}
        return o.HttpResponse(201 if method=='POST' else 200,json.dumps([row]).encode())
    # Label each role by its already reviewed ordered request allowance.
    def by_role(method,url,headers,body):
        global current
        if 'Authorization' not in headers: current='anonymous'
        elif ledger.data['counts']['role_by_name']['owner']: current='owner'
        elif ledger.data['counts']['role_by_name']['reviewer']: current='reviewer'
        else: current='nonmember'
        return sender(method,url,headers,body)
    for phase in s.PHASES: s.execute_phase(phase,context,ledger,by_role)
    assert len(sent)==19 and ledger.data['counts']['edge_positive']==1
    assert ledger.data['status']=='DISPATCH_ACCEPTED_EXISTING_JOB'
    blocked(lambda:s.execute_phase('nonmember',context,ledger,by_role))
    assert len(sent)==19
    assert context['access_token'] not in (folder/'receipt.json').read_text()
    assert context['user_uuid'] not in (folder/'receipt.json').read_text()
print('SYNTHETIC_CONNECTION_CHECKS_PASS')
`], {cwd:resolve('scripts'), encoding:'utf8', timeout:15_000, windowsHide:true,
      env:Object.fromEntries(['SystemRoot','WINDIR'].filter(name => process.env[name]).map(name => [name,process.env[name]]))});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), 'SYNTHETIC_CONNECTION_CHECKS_PASS');
});
