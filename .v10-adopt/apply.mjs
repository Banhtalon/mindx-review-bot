import path from 'node:path';
import {cp, mkdir, readFile, writeFile, rm, access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';

const root=process.cwd();
const template=path.join(root,'.v10-template');
const exists=async p=>access(p).then(()=>true).catch(()=>false);
const write=async(p,s)=>{await mkdir(path.dirname(path.join(root,p)),{recursive:true});await writeFile(path.join(root,p),s.endsWith('\n')?s:s+'\n');};
const copy=async(rel)=>{const src=path.join(template,rel),dst=path.join(root,rel);await mkdir(path.dirname(dst),{recursive:true});await cp(src,dst,{recursive:true,force:true});};
const lines=a=>a.join('\n')+'\n';

// Remove active v9 control surfaces. Git history remains the audit trail.
for(const rel of [
  '.ai-workflow/V9_CANONICAL_SPEC.md','.ai-workflow/CONTROLLER_OPERATIONS.md','.ai-workflow/RISK_RULES.json',
  '.ai-workflow/MIGRATION_INVENTORY.md','scripts/qq-ai-workflow','test/workflow-v9.test.mjs','test/workflow-bootstrap-v9.1.test.mjs'
]) await rm(path.join(root,rel),{recursive:true,force:true});
await rm(path.join(root,'.ai-workflow/prompts'),{recursive:true,force:true});
await rm(path.join(root,'.ai-workflow/templates'),{recursive:true,force:true});

// Copy reviewed v10 control documents and bridge implementation exactly from the pinned template.
await copy('.ai-workflow');
for(const rel of ['scripts/bridge.mjs','scripts/fast-lane.mjs','scripts/workflow.mjs','scripts/lib']) await copy(rel);

const profile={
  schema_version:'qq.workflow.profile.v10',routing_mode:'ASSISTED',billing:'SUBSCRIPTION_ONLY',
  max_repairs:2,max_senior_passes:1,max_writers:1,bridge_installed:false,
  bindings:{
    fast:{provider:'google',model:null,effort:null,verified:false},
    senior:{provider:'openai',model:null,effort:null,verified:false},
    elevated_review:{provider:'openai',model:null,effort:'xhigh',verified:false},
    review:{provider:'openai',model:null,effort:'xhigh',verified:false}
  }
};
await write('.ai-workflow/PROJECT_PROFILE.json',JSON.stringify(profile,null,2));

const bridgeExample={
  schema_version:'qq.bridge.v1',billing:'SUBSCRIPTION_ONLY',mode:'ASSISTED',timeout_seconds:600,
  write_paths:['src/App.tsx'],
  gate_paths:['scripts/verify_no_secrets.mjs','scripts/verify_no_live_write.mjs'],
  review_context_paths:['.ai-workflow/MINDX_PROJECT_RULES.md','docs/CURRENT_STATE.md'],
  worker:{provider:'google',cli:'gemini',command:['gemini'],model:'flash'},
  reviewer:{provider:'openai',command:['codex'],model:'REPLACE_WITH_PROBED_TERRA_MODEL',effort:'xhigh'},
  senior:{provider:'openai',command:['codex'],model:'REPLACE_WITH_PROBED_ASTRA_MODEL',effort:'high'},
  elevated_reviewer:{provider:'openai',command:['codex'],model:'REPLACE_WITH_PROBED_ASTRA_MODEL',effort:'xhigh'}
};
await write('.ai-workflow/BRIDGE_CONFIG.example.json',JSON.stringify(bridgeExample,null,2));

await write('.ai-workflow/MINDX_PROJECT_RULES.md',lines([
  '# MindX Review Bot — project constraints',
  '',
  'These are product and data-safety constraints for this repository. Workflow authority remains `.ai-workflow/V10_CANONICAL_SPEC.md`.',
  '',
  '- Teaching/LMS automation remains read-only unless the Owner explicitly approves a later product scope revision.',
  '- Do not add or trigger LMS Save/Submit/comment writes, automatic Zalo send, CAPTCHA/OTP bypass, or guessed identities.',
  '- Student mapping must use stable identifiers; row-order or fuzzy identity guesses are not acceptable.',
  '- Student PII, credentials, tokens, cookies and browser session state must not be sent to models, logs, evidence, frontend output or commits.',
  '- Existing no-secret and no-live-write deterministic guards stay mandatory for implementation work.',
  '- Database migrations, destructive operations, deployment changes and any live write are elevated-risk work and require the v10 elevated path plus explicit Owner intent.',
  '- Local/synthetic evidence must never be described as hosted, live or production acceptance.'
]));

const entry=lines([
  '# MindX Review Bot — QQ Workflow v10',
  '',
  'Read `.ai-workflow/V10_CANONICAL_SPEC.md` first; it is the only workflow-rule authority.',
  'Then read `.ai-workflow/MINDX_PROJECT_RULES.md`, `.ai-workflow/PROJECT_PROFILE.json`, `docs/CURRENT_STATE.md`, and the current local task packet when present.',
  '',
  'Owner supplies product intent, account-only actions, functional acceptance and final merge approval. Do not ask the Owner to inspect code, CI, SQL, schemas, security or logs.',
  'Use the v10 bridge for bounded implementation/review loops. Keep credentials in official CLI/account stores and preserve the project read-only/live-write boundaries.'
]);
await write('AGENTS.md',entry);await write('GEMINI.md',entry);

await write('.ai-workflow/MIGRATION.md',lines([
  '# mindx-review-bot migration to QQ Workflow v10',
  '',
  '- Host baseline: `3370dd287a7e346441f7eed8aca678636cc1a88b` (last active v9.1.2 main).',
  '- v10 source pin: `Banhtalon/qq-ai-workflow@e0c1944268bb328f992b6716cff72a64bc72a936` (`10.0.0-rc.1`).',
  '- Active v9 controller/risk/attempt scripts are removed from the v10 branch; Git history preserves them for audit.',
  '- Existing product history such as GitHub Issue #11 remains project history, but v10 mutable execution packets live under ignored `.workflow-local/`.',
  '- Adoption starts in ASSISTED mode. LOCAL_AUTO is not valid until real Windows account/model probes, a real two-provider repair pilot, quota drill and activation receipt pass.',
  '- Final merge remains an explicit Owner action after CI, independent technical review and functional acceptance where applicable.'
]));

await write('.ai-workflow/OWNER_GUIDE.md',lines([
  '# Owner guide — mindx-review-bot v10',
  '',
  'After the one-time local activation, each prepared task is started with one command: `npm run qq:auto`.',
  'The bridge then runs the configured Gemini worker, deterministic gates, independent reviewer and bounded repair/senior escalation until it reaches READY_FOR_OWNER, WAITING_QUOTA, WAITING_CAPABILITY or BLOCKED_TECHNICAL.',
  '',
  'One-time local setup uses Node 20+, Git, Gemini CLI logged in with the Google account, and Codex CLI logged in with ChatGPT. Copy `.ai-workflow/BRIDGE_CONFIG.example.json` to `.workflow-local/bridge-config.json` and replace the OpenAI model placeholders with model IDs verified on this account. Gemini CLI supports the `flash` alias; the doctor packet records the actually observed model.',
  '',
  'Use `npm run qq:doctor` before any pilot. Run `npm run qq:pilot` with a prepared frozen task, then `npm run qq:quota-drill`, then `npm run qq:activate`. Activation changes only the ignored local config to LOCAL_AUTO; it does not change GitHub code.',
  '',
  'For normal tasks, a Lead prepares `.workflow-local/task.json` and task-scoped `write_paths` in the local bridge config. Then `npm run qq:auto` is the only execution command. Re-running the same command safely resumes a preserved checkpoint when v10 permits it.',
  '',
  'If the task is user-visible and its frozen contract requires browser evidence, the bridge may stop at WAITING_CAPABILITY for a local browser observation before Owner acceptance. This gate is intentionally not bypassed.'
]));

await write('docs/WORKFLOW_V10_LOCAL_AUTO.md',lines([
  '# QQ Workflow v10 — local bridge for mindx-review-bot',
  '',
  '## Architecture',
  '',
  'GitHub stores code, PRs, CI and meaningful milestones. `.workflow-local/` stores mutable task/config/run packets and is ignored by Git. Subscription CLIs run on the Owner laptop; no API-key fallback is allowed.',
  '',
  'Normal loop: Gemini Flash worker -> deterministic gates -> fresh Codex reviewer -> bounded repair. Two initial repair rounds are allowed, then at most one senior pass. The bridge stops for Owner, quota/capability, browser evidence, or a technical blocker.',
  '',
  '## One-time activation',
  '',
  '1. Install Node 20+, Git, Gemini CLI and Codex CLI on Windows.',
  '2. Sign Gemini CLI in with the Google account and Codex CLI in with ChatGPT.',
  '3. Copy `.ai-workflow/BRIDGE_CONFIG.example.json` to `.workflow-local/bridge-config.json`; keep billing SUBSCRIPTION_ONLY and replace only the probed OpenAI model IDs plus task-scoped write paths.',
  '4. Run `npm run qq:doctor`.',
  '5. Run a real supervised repair pilot with `npm run qq:pilot`.',
  '6. Run `npm run qq:quota-drill` and then `npm run qq:activate`.',
  '',
  '## Per task',
  '',
  'The Lead creates/finalizes `.workflow-local/task.json`, including base SHA, acceptance criteria, gates, risk/complexity and GEMINI_FIRST_V1 execution fields, and narrows `write_paths` in the local config. Start or resume with:',
  '',
  '    npm run qq:auto',
  '',
  'When READY_FOR_OWNER appears, test the ordinary user actions supplied by the Lead. Merge remains separate and explicit.'
]));

await write('scripts/qq-auto.mjs',`import path from 'node:path';\nimport {access,copyFile,mkdir,readFile,writeFile} from 'node:fs/promises';\nimport {execFileSync} from 'node:child_process';\nimport {readJson,freeze} from './lib/workflow.mjs';\nimport {inspect,runBridge,quotaDrill,activate} from './lib/bridge.mjs';\n\nconst root=process.cwd(),local=path.join(root,'.workflow-local');\nconst configPath=path.join(local,'bridge-config.json'),taskPath=path.join(local,'task.json');\nconst exists=p=>access(p).then(()=>true).catch(()=>false);\nconst git=(...a)=>execFileSync('git',a,{cwd:root,encoding:'utf8'}).trim();\nconst loadConfig=()=>readJson(configPath);\nasync function ensureTask(){if(!await exists(taskPath))throw Error('Missing .workflow-local/task.json; Lead must prepare the bounded v10 task first.');if(!await exists(taskPath+'.lock.json'))await freeze(taskPath);return readJson(taskPath);}\nfunction branchFor(t){return 'qq/'+t.task_id.toLowerCase().replace(/[^a-z0-9_-]+/g,'-')+'-r'+t.revision;}\nasync function ensureFeatureBranch(t){if(git('status','--porcelain','--untracked-files=all'))throw Error('Repository must be clean before bridge start.');const b=git('symbolic-ref','--short','HEAD');if(['main','master'].includes(b)){if(git('rev-parse','HEAD')!==t.base_sha)throw Error('Task base_sha must equal current main HEAD before branch creation.');execFileSync('git',['switch','-c',branchFor(t)],{cwd:root,stdio:'inherit'});}}\nasync function copyActivation(runDir){const src=path.join(local,'activation');for(const f of ['activation.json','quota-drill.json']){const from=path.join(src,f),to=path.join(runDir,f);if(!await exists(from))throw Error('Missing one-time activation receipt: '+from);if(!await exists(to))await copyFile(from,to);}}\nasync function main(){await mkdir(local,{recursive:true});const cmd=process.argv[2]??'run';if(!await exists(configPath))throw Error('Copy .ai-workflow/BRIDGE_CONFIG.example.json to .workflow-local/bridge-config.json first.');let config=await loadConfig();\nif(cmd==='doctor'){const r=await inspect(root,config,path.join(local,'doctor'),true);console.log(JSON.stringify(r,null,2));return;}\nconst t=await ensureTask();await ensureFeatureBranch(t);const pilotDir=path.join(local,'pilot'),activationDir=path.join(local,'activation'),runDir=path.join(local,'runs',t.task_id+'-r'+t.revision);\nif(cmd==='pilot'){const resume=await exists(path.join(pilotDir,'state.json'));const r=await runBridge({cwd:root,taskPath,config,packetDir:pilotDir,pilot:true,resume});console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes},null,2));return;}\nif(cmd==='quota-drill'){const r=await quotaDrill(config,pilotDir,activationDir);console.log(JSON.stringify(r,null,2));return;}\nif(cmd==='activate'){const r=await activate(config,pilotDir,activationDir);config={...config,mode:'LOCAL_AUTO'};await writeFile(configPath,JSON.stringify(config,null,2)+'\\n');console.log(JSON.stringify(r,null,2));return;}\nif(cmd!=='run')throw Error('Usage: qq-auto.mjs doctor|pilot|quota-drill|activate|run');if(config.mode!=='LOCAL_AUTO')throw Error('LOCAL_AUTO is not activated. Complete doctor -> pilot -> quota-drill -> activate first.');await mkdir(runDir,{recursive:true});await copyActivation(runDir);const resume=await exists(path.join(runDir,'state.json'));const r=await runBridge({cwd:root,taskPath,config,packetDir:runDir,pilot:false,resume});console.log(JSON.stringify({status:r.status,head:r.head,repair_rounds:r.repair_rounds,senior_passes:r.senior_passes,error:r.error??null},null,2));}\nmain().catch(e=>{console.error(e.message);process.exitCode=1;});\n`);

// Pin copied core files to the reviewed source commit, so host CI detects drift.
const core=[
  '.ai-workflow/V10_CANONICAL_SPEC.md','.ai-workflow/CLI_BRIDGE.md','.ai-workflow/DATA_MODEL.md','.ai-workflow/FAST_LANE.md',
  '.ai-workflow/HANDOFF_FILES.md','.ai-workflow/OWNER_STATUS.md','.ai-workflow/POLICY.md','.ai-workflow/ROUTING.md','.ai-workflow/STATE_MACHINE.md',
  '.ai-workflow/ACTOR_REGISTRY.md','.ai-workflow/BOOTSTRAP.md','.ai-workflow/fast-lane.allowlist.json',
  '.ai-workflow/prompts/IMPLEMENTER_BOOTSTRAP.md','.ai-workflow/prompts/LEAD_BOOTSTRAP.md','.ai-workflow/prompts/OWNER_QUICK_PROMPTS.md','.ai-workflow/prompts/REVIEWER_BOOTSTRAP.md',
  '.ai-workflow/templates/implementer-result.md','.ai-workflow/templates/review.json','.ai-workflow/templates/task.json',
  'scripts/bridge.mjs','scripts/fast-lane.mjs','scripts/workflow.mjs','scripts/lib/bridge-adapters.mjs','scripts/lib/bridge-process.mjs','scripts/lib/bridge.mjs','scripts/lib/documentation.mjs','scripts/lib/fast-lane.mjs','scripts/lib/redact.mjs','scripts/lib/workflow.mjs'
];
const pin={schema_version:'mindx.qq.v10-pin.v1',repository:'Banhtalon/qq-ai-workflow',commit:'e0c1944268bb328f992b6716cff72a64bc72a936',version:'10.0.0-rc.1',files:{}};
for(const rel of core) pin.files[rel]=execFileSync('git',['-C',template,'rev-parse','HEAD:'+rel],{encoding:'utf8'}).trim();
await write('.ai-workflow/V10_TEMPLATE_PIN.json',JSON.stringify(pin,null,2));

await write('scripts/check-workflow-v10.mjs',`import {createHash} from 'node:crypto';\nimport {readFile,access} from 'node:fs/promises';\nimport {validateProfile} from './lib/workflow.mjs';\nimport {validateConfig} from './lib/bridge.mjs';\nconst blob=b=>createHash('sha1').update(Buffer.concat([Buffer.from('blob '+b.length+'\\0'),b])).digest('hex');\nconst pin=JSON.parse(await readFile('.ai-workflow/V10_TEMPLATE_PIN.json','utf8'));\nfor(const [p,sha] of Object.entries(pin.files)){const b=await readFile(p);if(blob(b)!==sha)throw Error('Pinned v10 core drift: '+p);}\nvalidateProfile(JSON.parse(await readFile('.ai-workflow/PROJECT_PROFILE.json','utf8')));\nvalidateConfig(JSON.parse(await readFile('.ai-workflow/BRIDGE_CONFIG.example.json','utf8')));\nfor(const p of ['.ai-workflow/V9_CANONICAL_SPEC.md','.ai-workflow/CONTROLLER_OPERATIONS.md','scripts/qq-ai-workflow']){if(await access(p).then(()=>true).catch(()=>false))throw Error('Active v9 artifact remains: '+p);}\nconst ignore=await readFile('.gitignore','utf8');if(!ignore.split(/\\r?\\n/).includes('.workflow-local/'))throw Error('.workflow-local/ must be ignored');\nconst pkg=JSON.parse(await readFile('package.json','utf8'));for(const k of ['workflow:v10-check','workflow:bridge','qq:doctor','qq:pilot','qq:quota-drill','qq:activate','qq:auto'])if(!pkg.scripts?.[k])throw Error('Missing package script '+k);\nconsole.log('PASS: mindx-review-bot QQ Workflow v10 integration is pinned and internally consistent');\n`);

// Ignore local mutable packets.
let ignore=await readFile(path.join(root,'.gitignore'),'utf8');
if(!ignore.split(/\r?\n/).includes('.workflow-local/'))ignore=ignore.trimEnd()+'\n.workflow-local/\n';
await writeFile(path.join(root,'.gitignore'),ignore);

// Replace v9 npm entry points with v10 bridge commands without changing app dependencies.
const pkgPath=path.join(root,'package.json'),pkg=JSON.parse(await readFile(pkgPath,'utf8'));
for(const k of Object.keys(pkg.scripts)) if(k.startsWith('workflow:')||k.startsWith('qq:')) delete pkg.scripts[k];
Object.assign(pkg.scripts,{
  'workflow:v10-check':'node scripts/check-workflow-v10.mjs',
  'workflow:bridge':'node scripts/bridge.mjs',
  'workflow:freeze':'node scripts/workflow.mjs freeze',
  'workflow:route':'node scripts/workflow.mjs route',
  'workflow:verify':'node scripts/workflow.mjs verify',
  'workflow:owner-status':'node scripts/workflow.mjs status',
  'qq:doctor':'node scripts/qq-auto.mjs doctor',
  'qq:pilot':'node scripts/qq-auto.mjs pilot',
  'qq:quota-drill':'node scripts/qq-auto.mjs quota-drill',
  'qq:activate':'node scripts/qq-auto.mjs activate',
  'qq:auto':'node scripts/qq-auto.mjs run'
});
await writeFile(pkgPath,JSON.stringify(pkg,null,2)+'\n');

// Ensure ordinary PR CI validates the adopted kit but never invokes subscription CLIs.
const ciPath=path.join(root,'.github/workflows/ci.yml');let ci=await readFile(ciPath,'utf8');
if(!ci.includes('Verify QQ Workflow v10 integration')){
  const marker='      - name: Lint web\n';
  const step='      - name: Verify QQ Workflow v10 integration\n        run: npm run workflow:v10-check\n\n';
  if(!ci.includes(marker))throw Error('CI insertion point not found');
  ci=ci.replace(marker,step+marker);await writeFile(ciPath,ci);
}

// Remove temporary adoption machinery so the resulting branch contains only the adopted system.
await rm(path.join(root,'.v10-template'),{recursive:true,force:true});
await rm(path.join(root,'.github/workflows/v10-adopt-bootstrap.yml'),{force:true});
await rm(path.join(root,'.v10-adopt'),{recursive:true,force:true});
