import {AuthClient} from '@supabase/supabase-js';

export const APP_PROJECT_REF = 'gnvzjvgfsxfjgldatbwt';
export const APP_PROJECT_URL = `https://${APP_PROJECT_REF}.supabase.co`;
const AUTH_ORIGIN = APP_PROJECT_URL;
const MAX_RESPONSE_BYTES = 128 * 1024;
const REQUEST_TIMEOUT_MS = 10_000;
const MIN_REMAINING_MS = 60_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function safeError(code) {
  return Object.assign(new Error(code), {code});
}

function decodeJwt(token) {
  if (typeof token !== 'string' || token.length > 8192) return null;
  const parts = token.split('.');
  if (parts.length !== 3 || !parts[1]) return null;
  try {
    const text = Buffer.from(parts[1], 'base64url').toString('utf8');
    const claims = JSON.parse(text);
    return claims && typeof claims === 'object' && !Array.isArray(claims) ? claims : null;
  } catch {
    return null;
  }
}

function isPublicKey(value) {
  if (typeof value !== 'string' || value.length > 4096) return false;
  if (/^sb_publishable_[A-Za-z0-9_-]{16,}$/.test(value)) return true;
  const claims = decodeJwt(value);
  return claims?.role === 'anon';
}

function validateConfig(url, publicKey, fetchImpl) {
  if (url !== APP_PROJECT_URL || !isPublicKey(publicKey) || typeof fetchImpl !== 'function') {
    throw safeError('CONFIG_INVALID');
  }
}

function boundedFetch(fetchImpl, publicKey, {maxResponseBytes, timeoutMs}) {
  let requestCount = 0;
  let expectedToken = null;
  let disposed = false;
  const pending = new Set();
  const guardedFetch = async (input, init = {}) => {
    if (disposed) throw safeError('AUTH_UNAVAILABLE');
    requestCount += 1;
    if (requestCount > 2) throw safeError('REQUEST_BUDGET_EXHAUSTED');

    let request;
    try {
      request = new Request(input, init);
      const url = new URL(request.url);
      const apiKey = request.headers.get('apikey');
      const isLogin = requestCount === 1 && request.method === 'POST' &&
        url.origin === AUTH_ORIGIN && url.pathname === '/auth/v1/token' &&
        url.search === '?grant_type=password';
      const isUserCheck = requestCount === 2 && request.method === 'GET' &&
        url.origin === AUTH_ORIGIN && url.pathname === '/auth/v1/user' && !url.search &&
        expectedToken && request.headers.get('authorization') === `Bearer ${expectedToken}`;
      if ((!isLogin && !isUserCheck) || apiKey !== publicKey) throw safeError('REQUEST_NOT_ALLOWED');
      if (isLogin) {
        const body = JSON.parse(await request.clone().text());
        const keys = Object.keys(body).sort();
        if (typeof body.email !== 'string' || body.email.length > 254 ||
            typeof body.password !== 'string' || body.password.length > 1024 ||
            keys.some(key => !['email', 'password', 'gotrue_meta_security'].includes(key)) ||
            (body.gotrue_meta_security && Object.keys(body.gotrue_meta_security).length)) {
          throw safeError('REQUEST_NOT_ALLOWED');
        }
      }

      const controller = new AbortController();
      let timer;
      const boundedRequest = new Request(request, {redirect: 'manual', signal: controller.signal});
      let cancel;
      const cancelled = new Promise((_, reject) => {
        cancel = () => reject(safeError('AUTH_UNAVAILABLE'));
      });
      const pendingRequest = {controller, cancel};
      pending.add(pendingRequest);
      const work = (async () => {
        const response = await fetchImpl(boundedRequest);
        if (!response || response.redirected || response.status >= 300 && response.status < 400) {
          throw safeError('RESPONSE_NOT_ALLOWED');
        }
        const declaredLength = Number(response.headers.get('content-length'));
        if (Number.isFinite(declaredLength) && declaredLength > maxResponseBytes) {
          throw safeError('RESPONSE_TOO_LARGE');
        }
        const reader = response.body?.getReader();
        if (!reader) return new Response(null, {status: response.status, statusText: response.statusText, headers: response.headers});
        const chunks = [];
        let size = 0;
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > maxResponseBytes) {
            await reader.cancel();
            throw safeError('RESPONSE_TOO_LARGE');
          }
          chunks.push(value);
        }
        return new Response(Buffer.concat(chunks.map(chunk => Buffer.from(chunk))), {
          status: response.status, statusText: response.statusText, headers: response.headers,
        });
      })();
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(safeError('REQUEST_TIMEOUT'));
        }, timeoutMs);
      });
      try {
        return await Promise.race([work, timeout, cancelled]);
      } finally {
        clearTimeout(timer);
        controller.abort();
        pending.delete(pendingRequest);
      }
    } catch (error) {
      if (error?.code) throw error;
      throw safeError('AUTH_UNAVAILABLE');
    }
  };
  guardedFetch.setExpectedToken = token => { expectedToken = disposed ? null : token; };
  guardedFetch.dispose = () => {
    if (disposed) return;
    disposed = true;
    expectedToken = null;
    for (const active of pending) {
      active.controller.abort();
      active.cancel();
    }
    pending.clear();
  };
  return guardedFetch;
}

function verifiedPrincipal(session, user, now) {
  const claims = decodeJwt(session?.access_token);
  const exp = Number(claims?.exp);
  const sessionExp = Number(session?.expires_at);
  const userUUID = user?.id;
  const issuer = `${APP_PROJECT_URL}/auth/v1`;
  // JWT claims are consistency checks only; getUser above is the server-side identity confirmation.
  if (!claims || claims.iss !== issuer || !UUID.test(userUUID ?? '') || claims.sub !== userUUID ||
      claims.role !== 'authenticated' || claims.aud !== 'authenticated' || claims.is_anonymous !== false ||
      session.token_type?.toLowerCase() !== 'bearer' || !Number.isFinite(exp) ||
      !Number.isFinite(sessionExp) || Math.abs(exp - sessionExp) > 60 ||
      exp * 1000 < now + MIN_REMAINING_MS) {
    throw safeError('SESSION_INVALID');
  }
  return {
    projectRef: APP_PROJECT_REF,
    userUUID,
    accessToken: session.access_token,
    publicKey: session.publicKey,
    expiresAt: exp,
    issuer,
    role: claims.role,
    audience: claims.aud,
  };
}

export function createAppSession({
  url = APP_PROJECT_URL,
  publicKey,
  fetchImpl = globalThis.fetch,
  now = Date.now,
  maxResponseBytes = MAX_RESPONSE_BYTES,
  timeoutMs = REQUEST_TIMEOUT_MS,
} = {}) {
  validateConfig(url, publicKey, fetchImpl);
  if (!Number.isInteger(maxResponseBytes) || maxResponseBytes < 1 || maxResponseBytes > MAX_RESPONSE_BYTES ||
      !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > REQUEST_TIMEOUT_MS) {
    throw safeError('CONFIG_INVALID');
  }
  let fetch = boundedFetch(fetchImpl, publicKey, {maxResponseBytes, timeoutMs});
  const headers = {apikey: publicKey};
  if (!publicKey.startsWith('sb_publishable_')) headers.Authorization = `Bearer ${publicKey}`;
  let client = new AuthClient({
    url: `${url}/auth/v1`,
    headers,
    fetch,
    persistSession: false,
    autoRefreshToken: false,
    detectSessionInUrl: false,
    skipAutoInitialize: true,
  });
  let used = false;
  let disposed = false;
  let disposePromise;
  const dispose = () => {
    if (disposePromise) return disposePromise;
    disposed = true;
    const currentClient = client;
    client = null;
    fetch?.dispose();
    fetch = null;
    disposePromise = Promise.resolve().then(() => currentClient?.dispose()).catch(() => undefined);
    return disposePromise;
  };

  return {
    dispose,
    async login({email, password} = {}) {
      if (used) throw safeError('ATTEMPT_USED');
      used = true;
      if (disposed || !client || !fetch) throw safeError('AUTH_UNAVAILABLE');
      const sessionClient = client;
      const sessionFetch = fetch;
      try {
        if (typeof email !== 'string' || !email || email.length > 254 ||
            typeof password !== 'string' || !password || password.length > 1024) {
          throw safeError('INPUT_INVALID');
        }
        const {data: signedIn, error: signInError} = await sessionClient.signInWithPassword({email, password});
        if (disposed) throw safeError('AUTH_UNAVAILABLE');
        const session = signedIn?.session;
        if (signInError?.name === 'AuthRetryableFetchError') throw safeError('AUTH_UNAVAILABLE');
        if (signInError || !session?.access_token || !Number.isFinite(Number(session.expires_at))) throw safeError('AUTH_REJECTED');
        const token = session.access_token;
        // The second and final network request must validate this exact token.
        sessionFetch.setExpectedToken(token);
        let confirmed;
        let userError;
        try {
          ({data: confirmed, error: userError} = await sessionClient.getUser(token));
        } finally {
          sessionFetch.setExpectedToken(null);
        }
        if (disposed) throw safeError('AUTH_UNAVAILABLE');
        if (userError || !confirmed?.user || confirmed.user.id !== signedIn.user?.id || confirmed.user.is_anonymous !== false) {
          throw safeError('USER_UNCONFIRMED');
        }
        const principal = verifiedPrincipal({...session, publicKey}, confirmed.user, now());
        return principal;
      } catch (error) {
        if (error?.code && ['AUTH_REJECTED', 'USER_UNCONFIRMED', 'SESSION_INVALID', 'INPUT_INVALID'].includes(error.code)) throw error;
        throw safeError('AUTH_UNAVAILABLE');
      } finally {
        await dispose();
      }
    },
  };
}
