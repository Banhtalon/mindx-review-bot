import path from 'node:path';
import {access,mkdir,readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';

const root=process.cwd();
const local=path.join(root,'.workflow-local');
const target=path.join(local,'bridge-config.json');
const templatePath=path.join(root,'.ai-workflow','BRIDGE_CONFIG.example.json');
const exists=p=>access(p).then(()=>true).catch(()=>false);

function trackedProductPaths(){
  const raw=execFileSync('git',['ls-files','-z','--','src','apps/browser-runner'],{cwd:root,encoding:'utf8'});
  return raw.split('\0').filter(Boolean).filter(p=>
    /\.(?:ts|tsx|css|py)$/.test(p) &&
    !/(^|\/)(?:test|tests|fixtures|__pycache__)(\/|$)/.test(p) &&
    !/(^|\/)(?:test_[^/]+\.py|[^/]+\.(?:test|spec)\.[cm]?[jt]sx?)$/.test(p)
  ).sort();
}

async function main(){
  if(await exists(target))throw Error('.workflow-local/bridge-config.json already exists. Refusing to rewrite it because v10 activation is bound to the exact config.');
  const config=JSON.parse(await readFile(templatePath,'utf8'));
  const writePaths=trackedProductPaths();
  if(!writePaths.length)throw Error('No tracked product source files found for the stable write allowlist.');
  config.write_paths=writePaths;
  config.github={
    repository:'Banhtalon/mindx-review-bot',
    remote:'origin',
    base_branch:'main',
    auto_push_ready:true,
    auto_open_pr:true
  };
  if(process.env.QQ_REVIEW_MODEL)config.reviewer.model=process.env.QQ_REVIEW_MODEL;
  if(process.env.QQ_SENIOR_MODEL)config.senior.model=process.env.QQ_SENIOR_MODEL;
  if(process.env.QQ_ELEVATED_REVIEW_MODEL)config.elevated_reviewer.model=process.env.QQ_ELEVATED_REVIEW_MODEL;
  await mkdir(local,{recursive:true});
  await writeFile(target,JSON.stringify(config,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({
    status:'SETUP_CREATED',
    config:'.workflow-local/bridge-config.json',
    stable_write_paths:writePaths.length,
    note:'Do not narrow or expand write_paths per task after activation. A path change invalidates activation and requires a new pilot/quota-drill/activate cycle.',
    next:'Set the probed OpenAI model IDs if placeholders remain, then run npm run qq:doctor.'
  },null,2));
}

main().catch(error=>{console.error(error.message);process.exitCode=1;});
