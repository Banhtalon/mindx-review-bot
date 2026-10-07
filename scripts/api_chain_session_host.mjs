import {spawn, spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import process from 'node:process';
import {setTimeout, clearTimeout} from 'node:timers';
import {fileURLToPath} from 'node:url';
import {startAppSessionHost} from './app_session_host.mjs';
import {createAppSession, APP_PROJECT_URL} from './lib/app_session.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PYTHON = 'C:\\Users\\QQ\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';
const GIT = 'D:\\Git\\cmd\\git.exe';
const RECEIVER = resolve(ROOT, 'scripts/api_chain_session.py');
const FOLDER = resolve(ROOT, '.workflow-local/api-chain-session');
const ENV = Object.fromEntries(['SystemRoot', 'WINDIR'].filter(name => process.env[name]).map(name => [name, process.env[name]]));

function checkApproval() {
  const approval = JSON.parse(readFileSync(resolve(FOLDER, 'approval.json'), 'utf8'));
  const head = spawnSync(GIT, ['rev-parse', 'HEAD'], {cwd:ROOT, env:ENV, encoding:'utf8', windowsHide:true, timeout:5000});
  const clean = spawnSync(GIT, ['diff', '--quiet', 'HEAD'], {cwd:ROOT, env:ENV, windowsHide:true, timeout:5000});
  if (head.status !== 0 || clean.status !== 0 || approval.head !== head.stdout.trim()) throw new Error('APPROVAL');
  const checked = spawnSync(PYTHON, ['-c', 'from api_chain_session import check_scope; check_scope()'], {
    cwd:resolve(ROOT, 'scripts'), env:ENV, windowsHide:true, timeout:5000, stdio:'ignore',
  });
  if (checked.status !== 0) throw new Error('APPROVAL');
}

function connect(principal, {children}) {
  checkApproval();
  return new Promise(resolvePromise => {
    const child = spawn(PYTHON, [RECEIVER], {cwd:ROOT, env:ENV, shell:false, windowsHide:true, stdio:['pipe','pipe','pipe']});
    children.add(child);
    let output = '';
    let bytes = 0;
    let settled = false;
    const finish = ready => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (!ready) child.kill();
      resolvePromise({status:ready ? 'WAITING_FINAL_SCOPE' : 'WAITING_AUTH_CAPABILITY'});
    };
    const timer = setTimeout(() => finish(false), 5000);
    child.stdout.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > 1024) return child.kill();
      output += chunk.toString('utf8');
      if (output === 'SESSION_READY\r\n' || output === 'SESSION_READY\n') finish(true);
    });
    child.stderr.on('data', () => {child.kill(); finish(false);});
    child.on('error', () => finish(false));
    child.on('close', () => {children.delete(child); finish(false);});
    child.stdin.on('error', () => finish(false));
    child.stdin.end(JSON.stringify({version:1, attestation:'getUser-confirmed', project_ref:principal.projectRef,
      user_uuid:principal.userUUID, access_token:principal.accessToken, public_key:principal.publicKey,
      expires_at:principal.expiresAt}) + '\n');
  });
}

async function main() {
  if (process.argv.length !== 3 || process.argv[2] !== '--live') throw new Error('ARGS');
  checkApproval();
  if (process.stdin.isTTY) process.stdin.setRawMode(true);
  const deadline = setTimeout(() => {process.stderr.write('SESSION_LAUNCH_BLOCKED\n'); process.exit(1);}, 30_000);
  let input = '';
  let bytes = 0;
  try {
    for await (const chunk of process.stdin) {
      bytes += chunk.length;
      if (bytes > 8192) throw new Error('CONFIG');
      input += chunk.toString('utf8');
      if (/[\r\n]/.test(input)) break;
    }
  } finally {
    clearTimeout(deadline);
    if (process.stdin.isTTY) process.stdin.setRawMode(false);
  }
  const config = JSON.parse(input);
  if (!config || Object.keys(config).sort().join(',') !== 'publicKey,url' || config.url !== APP_PROJECT_URL) throw new Error('CONFIG');
  await createAppSession(config).dispose();
  const host = await startAppSessionHost({mode:'live', liveConfig:config, capabilityCheck:connect});
  process.stdout.write(`SESSION_CHAIN_READY ${host.url}\n`);
  process.once('SIGINT', () => void host.close());
  process.once('SIGTERM', () => void host.close());
}

void main().catch(() => {process.stderr.write('SESSION_LAUNCH_BLOCKED\n'); process.exitCode = 1;});
