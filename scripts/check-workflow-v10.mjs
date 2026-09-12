import {createHash} from 'node:crypto';
import {readFile,access} from 'node:fs/promises';
import {validateProfile} from './lib/workflow.mjs';
import {validateConfig} from './lib/bridge.mjs';
const blob=b=>createHash('sha1').update(Buffer.concat([Buffer.from('blob '+b.length+'\0'),b])).digest('hex');
const pin=JSON.parse(await readFile('.ai-workflow/V10_TEMPLATE_PIN.json','utf8'));
for(const [p,sha] of Object.entries(pin.files)){const b=await readFile(p);if(blob(b)!==sha)throw Error('Pinned v10 core drift: '+p);}
validateProfile(JSON.parse(await readFile('.ai-workflow/PROJECT_PROFILE.json','utf8')));
const example=JSON.parse(await readFile('.ai-workflow/BRIDGE_CONFIG.example.json','utf8'));
validateConfig(example);
if(example.github?.repository!=='Banhtalon/mindx-review-bot'||example.github?.remote!=='origin'||example.github?.base_branch!=='main'||example.github?.auto_push_ready!==true||example.github?.auto_open_pr!==true)throw Error('Guarded GitHub publication target is missing or changed');
for(const p of ['.ai-workflow/V9_CANONICAL_SPEC.md','.ai-workflow/CONTROLLER_OPERATIONS.md','scripts/qq-ai-workflow']){if(await access(p).then(()=>true).catch(()=>false))throw Error('Active v9 artifact remains: '+p);}
const ignore=await readFile('.gitignore','utf8');if(!ignore.split(/\r?\n/).includes('.workflow-local/'))throw Error('.workflow-local/ must be ignored');
const pkg=JSON.parse(await readFile('package.json','utf8'));for(const k of ['workflow:v10-check','workflow:bridge','qq:setup','qq:doctor','qq:pilot','qq:quota-drill','qq:activate','qq:auto'])if(!pkg.scripts?.[k])throw Error('Missing package script '+k);
console.log('PASS: mindx-review-bot QQ Workflow v10 integration is pinned and internally consistent');
