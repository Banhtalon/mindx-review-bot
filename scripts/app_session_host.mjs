import {Buffer} from 'node:buffer';
import {spawn} from 'node:child_process';
import {randomBytes, timingSafeEqual} from 'node:crypto';
import {existsSync} from 'node:fs';
import http from 'node:http';
import {dirname, resolve} from 'node:path';
import process from 'node:process';
import {clearTimeout, setImmediate, setTimeout} from 'node:timers';
import {fileURLToPath, URL, URLSearchParams} from 'node:url';
import {createAppSession, APP_PROJECT_REF, APP_PROJECT_URL} from './lib/app_session.mjs';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PYTHON = 'C:\\Users\\QQ\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';
const RECEIVER = resolve(SCRIPT_DIR, 'app_session_receiver.py');
const MAX_FORM_BYTES = 8 * 1024;
const MAX_CHILD_OUTPUT = 4096;
const HOST_TTL_MS = 15 * 60 * 1000;
const SAFE_STATUSES = new Set(['WAITING_FINAL_SCOPE', 'WAITING_AUTH_CAPABILITY']);

const json = value => JSON.stringify(value);
const html = value => `<!doctype html>
<html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Công cụ thử đăng nhập</title>
<style>body{font:16px system-ui,sans-serif;max-width:38rem;margin:3rem auto;padding:0 1rem;color:#17202a}label{display:block;margin:1rem 0 .3rem}input{box-sizing:border-box;width:100%;padding:.65rem}button{margin-top:1rem;padding:.65rem 1rem}small{display:block;margin-top:1.5rem;color:#455a64}</style>
<main><h1>${value.title}</h1><p>${value.note}</p>
${value.result ? `<p role="status">${value.result}</p>` : ''}
${value.showLogin ? `<form method="post" action="/login" autocomplete="off"><input type="hidden" name="csrf" value="${value.csrf}"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="off" required maxlength="254"><label for="password">Mật khẩu</label><input id="password" name="password" type="password" autocomplete="new-password" required maxlength="1024"><button type="submit">Thử đăng nhập một lần</button></form>` : ''}
<form method="post" action="/close"><input type="hidden" name="csrf" value="${value.csrf}"><button type="submit">Đóng công cụ</button></form>
<small>Công cụ không tự lưu thông tin đăng nhập vào bộ nhớ trình duyệt, tệp hay nhật ký.</small></main></html>`;

function write(res, status, body, contentType = 'text/html; charset=utf-8') {
  res.writeHead(status, {
    'content-type': contentType,
    'cache-control': 'no-store, max-age=0',
    'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; connect-src 'none'; img-src 'none'; script-src 'none'",
    'referrer-policy': 'same-origin',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
  });
  res.end(body);
}

function safePrincipal(value) {
  if (!value || value.projectRef !== APP_PROJECT_REF || typeof value.userUUID !== 'string' ||
      typeof value.accessToken !== 'string' || typeof value.publicKey !== 'string' ||
      !Number.isInteger(value.expiresAt) || value.expiresAt <= Math.floor(Date.now() / 1000)) return null;
  return {
    version: 1,
    attestation: 'getUser-confirmed',
    project_ref: value.projectRef,
    user_uuid: value.userUUID,
    access_token: value.accessToken,
    public_key: value.publicKey,
    expires_at: value.expiresAt,
  };
}

export async function runCapabilityCheck(principal, {children} = {}) {
  const context = safePrincipal(principal);
  if (!context || !existsSync(PYTHON) || !existsSync(RECEIVER)) return {status: 'WAITING_AUTH_CAPABILITY'};
  return new Promise(resolvePromise => {
    const child = spawn(PYTHON, [RECEIVER], {
      cwd: SCRIPT_DIR,
      env: Object.fromEntries(['SystemRoot', 'WINDIR'].filter(name => process.env[name]).map(name => [name, process.env[name]])),
      shell: false,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    children?.add(child);
    let output = '';
    let stderr = '';
    let outputBytes = 0;
    let stderrBytes = 0;
    let finished = false;
    const timer = setTimeout(() => child.kill(), 5000);
    const finish = code => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      children?.delete(child);
      let result = {status: 'WAITING_AUTH_CAPABILITY'};
      if (code === 0 && outputBytes <= MAX_CHILD_OUTPUT && stderrBytes === 0 && stderr === '') {
        try {
          const parsed = JSON.parse(output);
          if (Object.keys(parsed).length === 1 && SAFE_STATUSES.has(parsed.status)) result = {status: parsed.status};
        } catch { /* raw child output is private and discarded */ }
      }
      resolvePromise(result);
    };
    child.stdout.on('data', chunk => {
      outputBytes += chunk.length;
      if (outputBytes <= MAX_CHILD_OUTPUT) output += chunk.toString('utf8');
      else child.kill();
    });
    child.stderr.on('data', chunk => {
      stderrBytes += chunk.length;
      if (stderrBytes <= MAX_CHILD_OUTPUT) stderr += chunk.toString('utf8');
      if (stderrBytes > MAX_CHILD_OUTPUT) child.kill();
    });
    child.on('error', () => finish(127));
    child.on('close', finish);
    child.stdin.on('error', () => {});
    child.stdin.end(json(context) + '\n');
  });
}

async function readForm(req) {
  const contentType = String(req.headers['content-type'] ?? '').split(';', 1)[0].trim().toLowerCase();
  const declared = Number(req.headers['content-length']);
  if (contentType !== 'application/x-www-form-urlencoded' || Number.isFinite(declared) && declared > MAX_FORM_BYTES) {
    req.resume();
    return {error: 413};
  }
  const chunks = [];
  let size = 0;
  let tooLarge = false;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_FORM_BYTES) {
      tooLarge = true;
      chunks.length = 0;
    } else if (!tooLarge) chunks.push(chunk);
  }
  if (tooLarge) return {error: 413};
  const params = new URLSearchParams(Buffer.concat(chunks).toString('utf8'));
  const fields = Object.fromEntries(params.entries());
  if (params.size !== Object.keys(fields).length) return {error: 400};
  return {fields};
}

function resultText(mode, status) {
  if (mode === 'preview') return 'Mô phỏng hoàn tất. Không có tài khoản thật được xác thực.';
  if (status === 'WAITING_FINAL_SCOPE') return 'Máy chủ đã xác nhận đăng nhập. Chưa có phạm vi thử được phê duyệt; chưa đọc dữ liệu.';
  return 'Không thể xác nhận khả năng đăng nhập. Chưa đọc dữ liệu.';
}

export async function startAppSessionHost({mode = 'preview', liveConfig} = {}) {
  if (!['preview', 'live'].includes(mode)) throw new Error('Invalid local host settings');
  if (mode === 'live' && (!liveConfig || liveConfig.url !== APP_PROJECT_URL)) {
    throw new Error('Live configuration unavailable');
  }
  const auth = mode === 'live' ? createAppSession(liveConfig) : null;
  const csrf = randomBytes(32).toString('hex');
  const children = new Set();
  let tried = false;
  let status = mode === 'preview' ? 'READY_SYNTHETIC' : 'WAITING_AUTH_CAPABILITY';
  let principal = null;
  let closed = false;
  let server;
  let baseUrl;
  let ttl;
  const stopChildren = () => {
    for (const child of children) child.kill();
    children.clear();
  };
  const close = () => new Promise(resolvePromise => {
    if (closed) return resolvePromise();
    closed = true;
    clearTimeout(ttl);
    principal = null;
    stopChildren();
    if (!server.listening) return resolvePromise();
    server.close(() => resolvePromise());
  });

  server = http.createServer((req, res) => {
    void (async () => {
    if (req.socket.remoteAddress !== '127.0.0.1' || !baseUrl || req.headers.host !== baseUrl.host) {
      return write(res, 421, '<!doctype html><title>Địa chỉ không hợp lệ</title>');
    }
    if (principal && principal.expiresAt * 1000 <= Date.now()) {
      principal = null;
      status = 'WAITING_AUTH_CAPABILITY';
    }
    if (req.headers.origin && req.headers.origin !== baseUrl.origin) {
      return write(res, 403, '<!doctype html><title>Yêu cầu bị từ chối</title>');
    }
    if (req.method === 'GET' && req.url === '/') {
      return write(res, 200, html({
        title: tried ? 'Lượt thử đã kết thúc' : mode === 'preview' ? 'Đăng nhập thử bằng dữ liệu giả' : 'Đăng nhập ứng dụng',
        note: mode === 'preview'
          ? 'Chế độ mô phỏng: nhập dữ liệu giả để xem luồng hoạt động. Không có kết nối mạng.'
          : 'Đăng nhập một lần với dự án ứng dụng đã cấu hình. Phiên chỉ tồn tại tạm thời trong bộ nhớ máy này.',
        csrf, showLogin: !tried, result: tried ? resultText(mode, status) : null,
      }));
    }
    if (req.method === 'GET' && req.url === '/status') {
      return write(res, 200, json({mode: mode === 'preview' ? 'synthetic' : 'application', status, verified: Boolean(principal) && status === 'WAITING_FINAL_SCOPE'}), 'application/json; charset=utf-8');
    }
    if (!['/login', '/close'].includes(req.url) || req.method !== 'POST') {
      return write(res, 404, '<!doctype html><title>Không tìm thấy</title>');
    }
    if (req.headers.origin !== baseUrl.origin) return write(res, 403, '<!doctype html><title>Yêu cầu bị từ chối</title>');
    const parsed = await readForm(req);
    if (parsed.error) return write(res, parsed.error, '<!doctype html><title>Yêu cầu không hợp lệ</title>');
    const fields = parsed.fields;
    const expectedFields = req.url === '/login' ? ['csrf', 'email', 'password'] : ['csrf'];
    const validCsrf = typeof fields.csrf === 'string' && /^[a-f0-9]{64}$/.test(fields.csrf) &&
      timingSafeEqual(Buffer.from(fields.csrf), Buffer.from(csrf));
    if (Object.keys(fields).sort().join(',') !== expectedFields.join(',') || !validCsrf) {
      return write(res, 403, '<!doctype html><title>Yêu cầu bị từ chối</title>');
    }
    if (req.url === '/close') {
      write(res, 200, '<!doctype html><title>Đã đóng</title><p>Công cụ đã đóng.</p>');
      setImmediate(() => void close());
      return;
    }
    if (tried) return write(res, 409, '<!doctype html><title>Đã dùng lượt thử</title><p>Công cụ chỉ nhận một lượt đăng nhập.</p>');
    tried = true;
    if (!fields.email || fields.email.length > 254 || !fields.password || fields.password.length > 1024) {
      status = mode === 'preview' ? 'PREVIEW_COMPLETE' : 'WAITING_AUTH_CAPABILITY';
      fields.email = '';
      fields.password = '';
      return write(res, 400, html({title: 'Thông tin chưa hợp lệ', note: 'Email hoặc mật khẩu trống hay quá dài.', csrf, showLogin: false}));
    }
    if (mode === 'preview') {
      status = 'PREVIEW_COMPLETE';
      fields.email = '';
      fields.password = '';
      return write(res, 200, html({title: 'Mô phỏng hoàn tất', note: resultText(mode, status), csrf, showLogin: false}));
    }
    try {
      const verified = await auth.login({email: fields.email, password: fields.password});
      if (closed) return write(res, 410, '<!doctype html><title>Đã đóng</title>');
      principal = verified;
      const capability = await runCapabilityCheck(principal, {children});
      if (closed) {
        principal = null;
        return write(res, 410, '<!doctype html><title>Đã đóng</title>');
      }
      status = capability.status;
      clearTimeout(ttl);
      ttl = setTimeout(() => void close(), Math.min(HOST_TTL_MS, principal.expiresAt * 1000 - Date.now()));
      ttl.unref();
    } catch {
      status = 'WAITING_AUTH_CAPABILITY';
      principal = null;
    } finally {
      fields.email = '';
      fields.password = '';
    }
    return write(res, 200, html({title: 'Đăng nhập đã được kiểm tra', note: resultText(mode, status), csrf, showLogin: false}));
    })().catch(() => {
      if (res.headersSent) return res.destroy();
      return write(res, 400, '<!doctype html><title>Yêu cầu không hợp lệ</title>');
    });
  });
  server.requestTimeout = 8000;
  server.headersTimeout = 10000;
  server.keepAliveTimeout = 1000;
  await new Promise((resolvePromise, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolvePromise);
  });
  const address = server.address();
  baseUrl = new URL(`http://127.0.0.1:${address.port}`);
  ttl = setTimeout(() => void close(), HOST_TTL_MS);
  ttl.unref();
  return {url: `${baseUrl.origin}/`, server, close};
}

async function main() {
  if (process.argv.length !== 3 || process.argv[2] !== '--preview') {
    process.stdout.write('Chỉ hỗ trợ xem trước dữ liệu giả: node scripts/app_session_host.mjs --preview\n');
    process.exitCode = 2;
    return;
  }
  const host = await startAppSessionHost({mode: 'preview'});
  process.stdout.write(`Trạng thái: READY_SYNTHETIC\nMở tại: ${host.url}\n`);
  process.once('SIGINT', () => void host.close());
  process.once('SIGTERM', () => void host.close());
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  void main().catch(() => {
    process.stderr.write('Không thể mở chế độ xem trước.\n');
    process.exitCode = 1;
  });
}
