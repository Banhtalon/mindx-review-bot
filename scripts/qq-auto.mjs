import path from 'node:path';
import {access,copyFile,mkdir,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {readJson,freeze} from './lib/workflow.mjs';
import {inspect,runBridge,quotaDrill,activate} from './lib/bridge.mjs';

const root=process.cwd(),local=path.join(root,'.workflow-local');
const configPath=path.join(local,'bridge-config.json'),taskPath=path.join(local,'task.json');
const exists=p=>access(p).then(()=>true).catch(()=>false);
const git=(...a)=>execFileSync('git',a,{cwd:root,encoding:'utf8'}).trim();
const gh=(...a)=>execFileSync('gh',a,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
const loadConfig=()=>readJson(configPath);

async function ensureTask(){
  if(!await exists(taskPath))throw Error('Missing .workflow-local/task.json; Lead must prepare the bounded v10 task first.');
  if(!await exists(taskPath+'.lock.json'))await freeze(taskPath);
  return readJson(taskPath);
}
function branchFor(t){return 'qq/'+t.task_id.toLowerCase().replace(/[^a-z0-9_-]+/g,'-')+'-r'+t.revision;}
async function ensureFeatureBranch(t){
  if(git('status','--porcelain','--untracked-files=all'))throw Error('Repository must be clean before bridge start.');
  const b=git('symbolic-ref','--short','HEAD');
  if(['main','master'].includes(b)){
    if(git('rev-parse','HEAD')!==t.base_sha)throw Error('Task base_sha must equal current main HEAD before branch creation.');
    execFileSync('git',['switch','-c',branchFor(t)],{cwd:root,stdio:'inherit'});
  }
}
async function copyActivation(runDir){
  const src=path.join(local,'activation');
  for(const f of ['activation.json','quota-drill.json']){
    const from=path.join(src,f),to=path.join(runDir,f);
    if(!await exists(from))throw Error('Missing one-time activation receipt: '+from);
    if(!await exists(to))await copyFile(from,to);
  }
}
function githubTarget(config){
  const h=config.github;
  if(!h||h.repository!=='Banhtalon/mindx-review-bot'||h.remote!=='origin'||h.base_branch!=='main')throw Error('GitHub target must remain Banhtalon/mindx-review-bot origin/main.');
  const remote=git('remote','get-url',h.remote).toLowerCase().replace(/\.git$/,'');
  const expected=h.repository.toLowerCase();
  const ok=remote===`https://github.com/${expected}`||remote===`git@github.com:${expected}`||remote===`ssh://git@github.com/${expected}`;
  if(!ok)throw Error('origin does not point to the configured GitHub repository.');
  return h;
}
function githubCapability(config){
  try{
    const h=githubTarget(config);
    const version=gh('--version').split(/\r?\n/)[0];
    gh('auth','status','--hostname','github.com');
    return {status:'PROBED',repository:h.repository,version};
  }catch{
    return {status:'WAITING_CAPABILITY',reason:'GitHub CLI must be installed and authenticated for automatic PR publication.'};
  }
}
function existingPr(h,branch){
  try{return JSON.parse(gh('pr','view',branch,'--repo',h.repository,'--json','number,url,state'));}
  catch{return null;}
}
function publishReady(t,state,config){
  if(!['READY_FOR_OWNER','DONE'].includes(state.status))return {status:'NOT_READY'};
  let h;
  try{h=githubTarget(config);}catch(error){return {status:'WAITING_CAPABILITY',reason:error.message};}
  const branch=git('symbolic-ref','--short','HEAD');
  if(['main','master'].includes(branch))return {status:'BLOCKED_TECHNICAL',reason:'Refusing to publish an Owner-ready candidate from the default branch.'};
  try{
    if(h.auto_push_ready!==false)execFileSync('git',['push','--set-upstream',h.remote,branch],{cwd:root,stdio:'inherit'});
    if(h.auto_open_pr===false)return {status:'PUSHED',branch};
    gh('auth','status','--hostname','github.com');
    let pr=existingPr(h,branch);
    if(!pr){
      const title=`${t.task_id}: ${t.goal}`.replace(/\s+/g,' ').slice(0,120);
      const body=[
        `Automated QQ Workflow v10 candidate for ${t.task_id}.`,
        '',
        `Bridge status: ${state.status}`,
        `Candidate head: ${state.head}`,
        '',
        'Local deterministic gates and independent review are recorded in ignored local packets. Final merge remains an explicit Owner action.'
      ].join('\n');
      gh('pr','create','--repo',h.repository,'--base',h.base_branch,'--head',branch,'--title',title,'--body',body);
      pr=existingPr(h,branch);
    }
    return pr?{status:'PR_READY',...pr}:{status:'PUSHED',branch,reason:'PR was created but could not be read back.'};
  }catch{
    return {status:'WAITING_CAPABILITY',branch,reason:'Candidate is locally ready, but automatic GitHub push/PR requires working Git and GitHub CLI authentication.'};
  }
}

async function main(){
  await mkdir(local,{recursive:true});
  const cmd=process.argv[2]??'run';
  if(!await exists(configPath))throw Error('Run npm run qq:setup first to create the stable local bridge config.');
  let config=await loadConfig();
  if(cmd==='doctor'){
    const bridge=await inspect(root,config,path.join(local,'doctor'),true);
    console.log(JSON.stringify({bridge,github:githubCapability(config)},null,2));return;
  }
  const t=await ensureTask();await ensureFeatureBranch(t);
  const pilotDir=path.join(local,'pilot'),activationDir=path.join(local,'activation'),runDir=path.join(local,'runs',t.task_id+'-r'+t.revision);
  if(cmd==='pilot'){
    const resume=await exists(path.join(pilotDir,'state.json'));
    const r=await runBridge({cwd:root,taskPath,config,packetDir:pilotDir,pilot:true,resume});
    console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes},null,2));return;
  }
  if(cmd==='quota-drill'){const r=await quotaDrill(config,pilotDir,activationDir);console.log(JSON.stringify(r,null,2));return;}
  if(cmd==='activate'){
    const r=await activate(config,pilotDir,activationDir);config={...config,mode:'LOCAL_AUTO'};
    await writeFile(configPath,JSON.stringify(config,null,2)+'\n');console.log(JSON.stringify(r,null,2));return;
  }
  if(cmd!=='run')throw Error('Usage: qq-auto.mjs doctor|pilot|quota-drill|activate|run');
  if(config.mode!=='LOCAL_AUTO')throw Error('LOCAL_AUTO is not activated. Complete doctor -> pilot -> quota-drill -> activate first.');
  await mkdir(runDir,{recursive:true});await copyActivation(runDir);
  const resume=await exists(path.join(runDir,'state.json'));
  const r=await runBridge({cwd:root,taskPath,config,packetDir:runDir,pilot:false,resume});
  const github=publishReady(t,r,config);
  console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes,error:r.error??null,github},null,2));
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
