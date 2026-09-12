import path from 'node:path';
import {access,copyFile,mkdir,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {readJson,freeze} from './lib/workflow.mjs';
import {inspect,runBridge,quotaDrill,activate} from './lib/bridge.mjs';

const root=process.cwd(),local=path.join(root,'.workflow-local');
const configPath=path.join(local,'bridge-config.json'),taskPath=path.join(local,'task.json');
const exists=p=>access(p).then(()=>true).catch(()=>false);
const git=(...a)=>execFileSync('git',a,{cwd:root,encoding:'utf8'}).trim();
const loadConfig=()=>readJson(configPath);
async function ensureTask(){if(!await exists(taskPath))throw Error('Missing .workflow-local/task.json; Lead must prepare the bounded v10 task first.');if(!await exists(taskPath+'.lock.json'))await freeze(taskPath);return readJson(taskPath);}
function branchFor(t){return 'qq/'+t.task_id.toLowerCase().replace(/[^a-z0-9_-]+/g,'-')+'-r'+t.revision;}
async function ensureFeatureBranch(t){if(git('status','--porcelain','--untracked-files=all'))throw Error('Repository must be clean before bridge start.');const b=git('symbolic-ref','--short','HEAD');if(['main','master'].includes(b)){if(git('rev-parse','HEAD')!==t.base_sha)throw Error('Task base_sha must equal current main HEAD before branch creation.');execFileSync('git',['switch','-c',branchFor(t)],{cwd:root,stdio:'inherit'});}}
async function copyActivation(runDir){const src=path.join(local,'activation');for(const f of ['activation.json','quota-drill.json']){const from=path.join(src,f),to=path.join(runDir,f);if(!await exists(from))throw Error('Missing one-time activation receipt: '+from);if(!await exists(to))await copyFile(from,to);}}
async function main(){await mkdir(local,{recursive:true});const cmd=process.argv[2]??'run';if(!await exists(configPath))throw Error('Copy .ai-workflow/BRIDGE_CONFIG.example.json to .workflow-local/bridge-config.json first.');let config=await loadConfig();
if(cmd==='doctor'){const r=await inspect(root,config,path.join(local,'doctor'),true);console.log(JSON.stringify(r,null,2));return;}
const t=await ensureTask();await ensureFeatureBranch(t);const pilotDir=path.join(local,'pilot'),activationDir=path.join(local,'activation'),runDir=path.join(local,'runs',t.task_id+'-r'+t.revision);
if(cmd==='pilot'){const resume=await exists(path.join(pilotDir,'state.json'));const r=await runBridge({cwd:root,taskPath,config,packetDir:pilotDir,pilot:true,resume});console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes},null,2));return;}
if(cmd==='quota-drill'){const r=await quotaDrill(config,pilotDir,activationDir);console.log(JSON.stringify(r,null,2));return;}
if(cmd==='activate'){const r=await activate(config,pilotDir,activationDir);config={...config,mode:'LOCAL_AUTO'};await writeFile(configPath,JSON.stringify(config,null,2)+'\n');console.log(JSON.stringify(r,null,2));return;}
if(cmd!=='run')throw Error('Usage: qq-auto.mjs doctor|pilot|quota-drill|activate|run');if(config.mode!=='LOCAL_AUTO')throw Error('LOCAL_AUTO is not activated. Complete doctor -> pilot -> quota-drill -> activate first.');await mkdir(runDir,{recursive:true});await copyActivation(runDir);const resume=await exists(path.join(runDir,'state.json'));const r=await runBridge({cwd:root,taskPath,config,packetDir:runDir,pilot:false,resume});console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes,error:r.error??null},null,2));}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
