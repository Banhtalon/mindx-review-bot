import {describe,expect,it} from 'vitest';
import {mkdtemp,mkdir,copyFile,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const root=process.cwd();
const run=(cmd,args,cwd)=>execFileSync(cmd,args,{cwd,encoding:'utf8',stdio:['ignore','pipe','pipe']});

async function file(base,relative,content='x'){
  const full=path.join(base,relative);await mkdir(path.dirname(full),{recursive:true});await writeFile(full,content);return full;
}

describe('mindx v10 host wrapper',()=>{
  it('creates one stable ignored write allowlist and refuses silent rewrites',async()=>{
    const dir=await mkdtemp(path.join(tmpdir(),'mindx-v10-'));
    await mkdir(path.join(dir,'scripts'),{recursive:true});
    await mkdir(path.join(dir,'.ai-workflow'),{recursive:true});
    await copyFile(path.join(root,'scripts/qq-setup.mjs'),path.join(dir,'scripts/qq-setup.mjs'));
    await copyFile(path.join(root,'.ai-workflow/BRIDGE_CONFIG.example.json'),path.join(dir,'.ai-workflow/BRIDGE_CONFIG.example.json'));
    await file(dir,'.gitignore','.workflow-local/\n');
    await file(dir,'src/App.tsx','export const app=1;\n');
    await file(dir,'src/App.test.tsx','export const testOnly=1;\n');
    await file(dir,'src/fixtures/student.ts','export const fixture=1;\n');
    await file(dir,'src/auth/session.ts','export const session=1;\n');
    await file(dir,'apps/browser-runner/runner.py','VALUE = 1\n');
    await file(dir,'apps/browser-runner/tests/test_runner.py','VALUE = 1\n');
    run('git',['init'],dir);
    run('git',['config','user.name','QQ test'],dir);
    run('git',['config','user.email','qq-test@example.invalid'],dir);
    run('git',['add','.'],dir);
    run('git',['commit','-m','fixture'],dir);

    const output=run(process.execPath,['scripts/qq-setup.mjs'],dir);
    expect(output).toContain('SETUP_CREATED');
    const config=JSON.parse(await readFile(path.join(dir,'.workflow-local/bridge-config.json'),'utf8'));
    expect(config.write_paths).toEqual([
      'apps/browser-runner/runner.py',
      'src/App.tsx',
      'src/auth/session.ts'
    ]);
    expect(config.github).toEqual({
      repository:'Banhtalon/mindx-review-bot',remote:'origin',base_branch:'main',auto_push_ready:true,auto_open_pr:true
    });
    expect(run('git',['status','--porcelain','--untracked-files=all'],dir)).toBe('');
    expect(()=>run(process.execPath,['scripts/qq-setup.mjs'],dir)).toThrow();
  });
});
