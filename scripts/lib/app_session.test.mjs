import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import test from 'node:test';
import {createAppSession} from './app_session.mjs';
import {startAppSessionHost, runCapabilityCheck} from '../app_session_host.mjs';

const projectRef = 'gnvzjvgfsxfjgldatbwt';
const projectUrl = `https://${projectRef}.supabase.co`;
const publicKey = 'sb_publishable_synthetic_public_key_1234567890';
const userUUID = '1c2a7a18-6bb8-4ab1-9f29-3117f3670864';
const accessToken = (claims = {}) => {
  const now = Math.floor(Date.now() / 1000);
  return `eyJhbGciOiJub25lIn0.${Buffer.from(JSON.stringify({
    iss: `${projectUrl}/auth/v1`, sub: userUUID, role: 'authenticated',
    aud: 'authenticated', exp: now + 1800, ...claims,
  })).toString('base64url')}.synthetic-signature`;
};
const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: {'content-type': 'application/json'},
});

function safeCheck(condition, failureCode) {
  assert.ok(Boolean(condition), failureCode);
}

function safeThrows(operation, expectedCode, failureCode) {
  let error;
  try { operation(); } catch (caught) { error = caught; }
  safeCheck(error?.code === expectedCode, failureCode);
}

async function safeRejects(promise, expectedCode, failureCode, privateValues = ['synthetic-password']) {
  let error;
  try { await promise; } catch (caught) { error = caught; }
  const message = String(error?.message ?? '');
  safeCheck(error?.code === expectedCode && privateValues.every(value => !message.includes(value)), failureCode);
}

function authFixture({token = accessToken(), userId = userUUID, transport} = {}) {
  const calls = [];
  const fetchImpl = transport ?? (async (input) => {
    const request = input instanceof Request ? input : new Request(input);
    const url = new URL(request.url);
    calls.push({method: request.method, path: url.pathname, search: url.search});
    if (url.pathname === '/auth/v1/token') return json({
      access_token: token, token_type: 'bearer', expires_in: 1800,
      expires_at: JSON.parse(Buffer.from(token.split('.')[1], 'base64url')).exp,
      refresh_token: 'synthetic-refresh-token', user: {id: userId},
    });
    if (url.pathname === '/auth/v1/user') return json({id: userId, is_anonymous: false});
    return json({message: 'unexpected fake request'}, 404);
  });
  return {
    calls,
    client: createAppSession({url: projectUrl, publicKey, fetchImpl}),
  };
}

test('official SDK fake transport performs only password sign-in and getUser, then projects a short-lived principal', async () => {
  const {calls, client} = authFixture();
  const principal = await client.login({email: 'user@example.invalid', password: 'synthetic-password'});
  assert.deepEqual(calls.map(({method, path}) => [method, path]), [
    ['POST', '/auth/v1/token'], ['GET', '/auth/v1/user'],
  ]);
  safeCheck(principal.userUUID === userUUID, 'SAFE_PRINCIPAL_USER');
  safeCheck(principal.projectRef === projectRef, 'SAFE_PRINCIPAL_PROJECT');
  safeCheck(principal.accessToken.split('.').length === 3, 'SAFE_PRINCIPAL_TOKEN_SHAPE');
  safeCheck(!('password' in principal), 'SAFE_PRINCIPAL_PASSWORD_ABSENT');
  safeCheck(!('refresh_token' in principal), 'SAFE_PRINCIPAL_REFRESH_ABSENT');
});

test('invalid project, privileged key, failed transport, redirects, and oversized response fail closed without retries', async () => {
  let calls = 0;
  const noNetwork = async () => { calls += 1; throw Error('private transport detail'); };
  safeThrows(() => createAppSession({url: 'https://other.supabase.co', publicKey, fetchImpl: noNetwork}), 'CONFIG_INVALID', 'SAFE_URL_CONFIG_REJECTED');
  safeThrows(() => createAppSession({url: projectUrl, publicKey: 'sb_secret_service_role_value_123', fetchImpl: noNetwork}), 'CONFIG_INVALID', 'SAFE_KEY_CONFIG_REJECTED');

  const transportFailure = createAppSession({url: projectUrl, publicKey, fetchImpl: noNetwork});
  await safeRejects(transportFailure.login({email: 'user@example.invalid', password: 'synthetic-password'}),
    'AUTH_UNAVAILABLE', 'SAFE_TRANSPORT_FAILURE', ['private transport detail', 'synthetic-password']);
  assert.equal(calls, 1);

  let redirects = 0;
  const redirectClient = createAppSession({url: projectUrl, publicKey, fetchImpl: async () => {
    redirects += 1;
    return new Response('', {status: 302, headers: {location: 'https://elsewhere.invalid'}});
  }});
  await safeRejects(redirectClient.login({email: 'user@example.invalid', password: 'synthetic-password'}), 'AUTH_UNAVAILABLE', 'SAFE_REDIRECT_REJECTED');
  assert.equal(redirects, 1);

  let oversized = 0;
  const oversizedClient = createAppSession({url: projectUrl, publicKey, maxResponseBytes: 32, fetchImpl: async () => {
    oversized += 1;
    return new Response('x'.repeat(33), {status: 200});
  }});
  await safeRejects(oversizedClient.login({email: 'user@example.invalid', password: 'synthetic-password'}), 'AUTH_UNAVAILABLE', 'SAFE_OVERSIZE_REJECTED');
  assert.equal(oversized, 1);

  let timedOut = 0;
  const slowClient = createAppSession({url: projectUrl, publicKey, timeoutMs: 10, fetchImpl: () => {
    timedOut += 1;
    return new Promise(() => {});
  }});
  await safeRejects(slowClient.login({email: 'user@example.invalid', password: 'synthetic-password'}), 'AUTH_UNAVAILABLE', 'SAFE_TIMEOUT_REJECTED');
  assert.equal(timedOut, 1);
});

test('getUser confirmation, matching nonanonymous identity, JWT audience and expiry are required', async () => {
  for (const fixture of [
    {token: accessToken({role: 'anon'}), userId: userUUID},
    {token: accessToken({aud: 'anon'}), userId: userUUID},
    {token: accessToken({exp: Math.floor(Date.now() / 1000) + 5}), userId: userUUID},
    {token: accessToken(), userId: '2d7ad7e5-e496-44dc-86ed-9a161a86a350'},
  ]) {
    const {client} = authFixture(fixture);
    await safeRejects(client.login({email: 'user@example.invalid', password: 'synthetic-password'}), 'SESSION_INVALID', 'SAFE_INVALID_SESSION_REJECTED');
  }
});

test('a second helper login is denied before another request can be sent', async () => {
  const {calls, client} = authFixture();
  await client.login({email: 'user@example.invalid', password: 'synthetic-password'});
  await safeRejects(client.login({email: 'user@example.invalid', password: 'synthetic-password'}), 'ATTEMPT_USED', 'SAFE_SECOND_ATTEMPT_REJECTED');
  assert.equal(calls.length, 2);
});

test('preview is same-origin, CSRF-bound, one-attempt, and synthetic', async t => {
  const host = await startAppSessionHost();
  t.after(() => host.close());
  const page = await fetch(host.url);
  const html = await page.text();
  safeCheck(/Đăng nhập thử bằng dữ liệu giả/.test(html), 'SAFE_PREVIEW_TITLE');
  safeCheck(/mô phỏng/i.test(html), 'SAFE_PREVIEW_LABEL');
  safeCheck(!/<script|https?:\/\//i.test(html), 'SAFE_PREVIEW_NO_EXTERNAL_CONTENT');
  const csrf = html.match(/name="csrf" value="([^"]+)"/)?.[1];
  safeCheck(Boolean(csrf), 'SAFE_PREVIEW_CSRF_PRESENT');

  const post = (fields, headers = {}) => fetch(`${host.url}login`, {
    method: 'POST', headers: {origin: host.url.slice(0, -1), ...headers},
    body: new URLSearchParams({csrf, email: 'user@example.invalid', password: 'synthetic-password', ...fields}),
  });
  assert.equal((await post({}, {origin: 'http://attacker.invalid'})).status, 403);
  assert.equal((await post({csrf: 'wrong'})).status, 403);

  const [first, parallel] = await Promise.all([post({}), post({})]);
  assert.ok([first.status, parallel.status].includes(200));
  assert.ok([first.status, parallel.status].includes(409));
  assert.equal((await post({})).status, 409);
  const status = await (await fetch(`${host.url}status`)).json();
  safeCheck(status.mode === 'synthetic' && status.status === 'PREVIEW_COMPLETE' && status.verified === false,
    'SAFE_PREVIEW_STATUS');
  safeCheck(!/synthetic-password|user@example.invalid|csrf/i.test(JSON.stringify(status)), 'SAFE_PREVIEW_STATUS_REDACTED');
});

test('local live-shaped flow uses fake SDK transport and private receiver, with safe status only', async t => {
  const calls = [];
  const host = await startAppSessionHost({mode: 'live', liveConfig: {
    url: projectUrl, publicKey, fetchImpl: async (input, init) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      calls.push({method: request.method, path: url.pathname, search: url.search});
      if (url.pathname === '/auth/v1/token') {
        const token = accessToken();
        return json({access_token: token, token_type: 'bearer', expires_in: 1800,
          expires_at: JSON.parse(Buffer.from(token.split('.')[1], 'base64url')).exp,
          refresh_token: 'synthetic-refresh-token', user: {id: userUUID}});
      }
      if (url.pathname === '/auth/v1/user') return json({id: userUUID, is_anonymous: false});
      return json({message: 'unexpected fake request'}, 404);
    },
  }});
  t.after(() => host.close());
  const page = await (await fetch(host.url)).text();
  const csrf = page.match(/name="csrf" value="([^"]+)"/)?.[1];
  safeCheck(Boolean(csrf), 'SAFE_FLOW_CSRF_PRESENT');
  const result = await fetch(`${host.url}login`, {
    method: 'POST', headers: {origin: host.url.slice(0, -1)},
    body: new URLSearchParams({csrf, email: 'user@example.invalid', password: 'synthetic-password'}),
  });
  const resultHtml = await result.text();
  assert.equal(result.status, 200);
  safeCheck(/WAITING_FINAL_SCOPE|Chưa có phạm vi thử được phê duyệt/.test(resultHtml), 'SAFE_FLOW_WAITING_SCOPE');
  safeCheck(!/synthetic-password|synthetic-refresh-token|1c2a7a18|sb_publishable/.test(resultHtml), 'SAFE_FLOW_OUTPUT_REDACTED');
  assert.deepEqual(calls.map(({method, path}) => [method, path]), [
    ['POST', '/auth/v1/token'], ['GET', '/auth/v1/user'],
  ]);
  const status = await (await fetch(`${host.url}status`)).json();
  safeCheck(status.mode === 'application' && status.status === 'WAITING_FINAL_SCOPE' && status.verified === true,
    'SAFE_FLOW_STATUS');
});

test('preview rejects oversized bodies and an incorrect Host without reflecting fields or adding CORS', async t => {
  const host = await startAppSessionHost();
  t.after(() => host.close());
  const page = await (await fetch(host.url)).text();
  const csrf = page.match(/name="csrf" value="([^"]+)"/)?.[1];
  safeCheck(Boolean(csrf), 'SAFE_OVERSIZE_CSRF_PRESENT');
  const origin = host.url.slice(0, -1);
  const oversized = await fetch(`${host.url}login`, {
    method: 'POST', headers: {origin, 'content-type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({csrf, email: 'user@example.invalid', password: 'x'.repeat(9000)}),
  });
  assert.equal(oversized.status, 413);
  const body = await oversized.text();
  safeCheck(!/user@example.invalid|x{20}/.test(body), 'SAFE_OVERSIZE_BODY_REDACTED');
  const port = new URL(host.url).port;
  const wrongHost = await new Promise((resolve, reject) => {
    const request = http.request({hostname: '127.0.0.1', port, path: '/', headers: {host: '127.0.0.1:1'}}, response => {
      response.resume();
      resolve(response);
    });
    request.on('error', reject);
    request.end();
  });
  assert.equal(wrongHost.statusCode, 421);
  assert.equal('access-control-allow-origin' in wrongHost.headers, false);
});

test('private receiver pipe returns only safe status and does not echo principal fields', async () => {
  const token = accessToken();
  const result = await runCapabilityCheck({
    projectRef, userUUID, accessToken: token, publicKey,
    expiresAt: JSON.parse(Buffer.from(token.split('.')[1], 'base64url')).exp,
  });
  safeCheck(result.status === 'WAITING_FINAL_SCOPE' && Object.keys(result).length === 1, 'SAFE_PIPE_STATUS');
  safeCheck(!new RegExp(`${userUUID}|${token}|${publicKey}`).test(JSON.stringify(result)), 'SAFE_PIPE_OUTPUT_REDACTED');
});

test('preview close form shuts down only its own server', async () => {
  const host = await startAppSessionHost();
  const page = await (await fetch(host.url)).text();
  const csrf = page.match(/name="csrf" value="([^"]+)"/)?.[1];
  safeCheck(Boolean(csrf), 'SAFE_CLOSE_CSRF_PRESENT');
  const closed = once(host.server, 'close');
  const response = await fetch(`${host.url}close`, {
    method: 'POST', headers: {origin: host.url.slice(0, -1)},
    body: new URLSearchParams({csrf}),
  });
  assert.equal(response.status, 200);
  await closed;
});
