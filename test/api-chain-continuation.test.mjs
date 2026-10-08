import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import process from 'node:process';
import test from 'node:test';

test('same-job continuation retains prior counts and blocks mismatch, duplicate or unknown sends', () => {
  const result = spawnSync('C:\\Users\\QQ\\AppData\\Local\\Programs\\Python\\Python312\\python.exe', ['-c', String.raw`
import hashlib, json, subprocess, tempfile
from pathlib import Path
import api_chain_continuation as c
import api_chain_operator as o

def blocked(fn):
    try: fn()
    except (ValueError, FileExistsError): return
    raise AssertionError('expected block')

with tempfile.TemporaryDirectory() as name:
    root=Path(name)
    folder=root/'continuation'
    folder.mkdir()
    prior={'session_actor_sha256':c.ACTOR, 'stop_forward':True,
           'counts':{'total':19,'edge_positive':1},'role_matrix_complete':True,
           'intents':[{'outcome':'HTTP_502'}]}
    previous=root/'operator-receipt.json'
    previous.write_text(json.dumps(prior))
    c.PREVIOUS=previous
    (folder/'TASK.md').write_text('frozen synthetic contract')
    scope={'status':'EXACT_SCOPE_APPROVED','workflow_head':c.HEAD,
           'contract_sha256':c.digest(folder/'TASK.md'),'previous_receipt_sha256':c.digest(previous),
           'source_sha256':{p:c.digest(c.ROOT/p) for p in c.SOURCES}}
    (folder/'approval.json').write_text(json.dumps(scope))
    c.check_scope(folder,check_head=False)
    original=previous.read_bytes()
    prior['counts']['total']=0
    previous.write_text(json.dumps(prior))
    blocked(lambda:c.check_scope(folder,check_head=False))
    previous.write_bytes(original)
    context={'user_uuid':'10000000-0000-4000-8000-000000000001',
             'public_key':'synthetic-public-key','access_token':'synthetic-app-token'}
    c.ACTOR=hashlib.sha256(context['user_uuid'].encode()).hexdigest()
    sent=[]
    failure=None
    def sender(method,url,headers,body):
        sent.append((method,url))
        if failure=='unknown': raise RuntimeError('synthetic transport failure')
        if url.endswith(o.WORKSPACE_PATH):
            value=[{'id':o.WORKSPACE_ID,'name':o.WORKSPACE_NAME}]
        elif url.endswith(c.MEMBER_PATH):
            value=[{'role':'reviewer' if failure=='role' else 'owner'}]
        elif url.endswith(o.JOB_GET_PATH):
            value=[{**o._JOB_INSERT,'requested_by':context['user_uuid'],'status':'dispatch_failed',
                    'attempt_count':0,'runner_id':None,'lease_expires_at':None,'heartbeat_at':None}]
        else:
            assert method=='POST' and json.loads(body)==o.EDGE_BODY
            return o.HttpResponse(502 if failure=='edge' else 202,
                json.dumps({'job_id':o.JOB_ID,'status':'dispatched','created':False}).encode())
        return o.HttpResponse(200,json.dumps(value).encode())
    file=folder/'receipt.json'
    c.execute(context,file,sender,validate_scope=lambda:None)
    receipt=json.loads(file.read_text())
    assert len(sent)==4 and receipt['cumulative_requests']==23
    assert receipt['cumulative_positive_attempts']==2
    assert receipt['status']=='DISPATCH_ACCEPTED_EXISTING_JOB'
    blocked(lambda:c.execute(context,file,sender,validate_scope=lambda:None))
    assert len(sent)==4 and previous.read_bytes()==original
    assert context['access_token'] not in file.read_text()
    assert context['user_uuid'] not in file.read_text()
    for mode, expected in [('role',2),('unknown',1),('edge',4)]:
        failure=mode
        sent.clear()
        file=folder/(mode+'.json')
        blocked(lambda:c.execute(context,file,sender,validate_scope=lambda:None))
        receipt=json.loads(file.read_text())
        assert len(sent)==expected and receipt['cumulative_requests']==19+expected
        assert receipt['stop_forward'] is True
        blocked(lambda:c.execute(context,file,sender,validate_scope=lambda:None))
        assert len(sent)==expected
    repo=root/'synthetic-repo'
    repo.mkdir()
    def git(*args):
        return subprocess.run([c.GIT,*args],cwd=repo,capture_output=True,check=True).stdout.decode().strip()
    git('init')
    (repo/'example.txt').write_text('before')
    git('add','example.txt')
    git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','synthetic')
    approved=git('rev-parse','HEAD')
    c.check_source_head(repo,approved)
    (repo/'example.txt').write_text('changed')
    blocked(lambda:c.check_source_head(repo,approved))
    git('add','example.txt')
    git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','changed')
    blocked(lambda:c.check_source_head(repo,approved))
    sent.clear()
    def stale(): raise ValueError('EXACT_HEAD_CHANGED')
    blocked(lambda:c.execute(context,folder/'stale.json',sender,validate_scope=stale))
    assert sent==[] and json.loads((folder/'stale.json').read_text())['cumulative_requests']==19
print('CONTINUATION_SYNTHETIC_CHECKS_PASS')
`], {cwd:resolve('scripts'), encoding:'utf8', timeout:15_000, windowsHide:true,
      env:Object.fromEntries(['SystemRoot','WINDIR'].filter(name => process.env[name]).map(name => [name,process.env[name]]))});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), 'CONTINUATION_SYNTHETIC_CHECKS_PASS');
});
