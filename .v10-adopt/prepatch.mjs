import {readFile,writeFile} from 'node:fs/promises';

const file='.v10-adopt/apply.mjs';
let source=await readFile(file,'utf8');
const writePackage="await writeFile(pkgPath,JSON.stringify(pkg,null,2)+'\\n');";
if(!source.includes(writePackage))throw Error('package write anchor not found');
source=source.replace(writePackage,"pkg.scripts.test='node scripts/check-workflow-v10.mjs && vitest run';\n"+writePackage);
const ciStart='// Ensure ordinary PR CI validates the adopted kit but never invokes subscription CLIs.';
const cleanup='// Remove temporary adoption machinery so the resulting branch contains only the adopted system.';
const start=source.indexOf(ciStart),end=source.indexOf(cleanup);
if(start<0||end<0||end<=start)throw Error('CI patch anchors not found');
source=source.slice(0,start)+cleanup+source.slice(end+cleanup.length);
source=source.replace("await rm(path.join(root,'.github/workflows/v10-adopt-bootstrap.yml'),{force:true});\n",'');
await writeFile(file,source);
