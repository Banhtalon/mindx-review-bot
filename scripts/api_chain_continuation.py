"""One explicitly authorized same-job continuation; retain the failed attempt."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import api_chain_operator as o
from app_session_receiver import MAX_INPUT_BYTES, process_input

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.workflow-local/api-chain-session/continuation'
PREVIOUS = FOLDER.parent / 'operator-receipt.json'
ACTOR = '8094ebe396b2a9d2bcbfe02759be0b4a101dedebad0bcc994599f7b7783179a7'
HEAD = '1855c37a6f1347cd70d14f9b9eb6eec52596823a'
MEMBER_PATH = f'/rest/v1/workspace_members?workspace_id=eq.{o.WORKSPACE_ID}&select=role&limit=2'
SOURCES = {'scripts/app_session_host.mjs', 'scripts/lib/app_session.mjs',
           'scripts/app_session_receiver.py', 'scripts/api_chain_operator.py',
           'scripts/api_chain_session_host.mjs', 'scripts/api_chain_continuation.py'}
GIT = 'D:/Git/cmd/git.exe'


def check_source_head(root, approved):
    head = subprocess.run([GIT, 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                          timeout=5, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    clean = subprocess.run([GIT, 'diff', '--quiet', 'HEAD'], cwd=root, capture_output=True,
                           timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    if head.stdout.decode().strip() != approved or clean.returncode != 0:
        raise ValueError('EXACT_HEAD_CHANGED')


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def check_scope(folder=FOLDER, root=ROOT, *, check_head=True):
    scope = json.loads((folder / 'approval.json').read_bytes())
    previous_file = folder.parent / 'operator-receipt.json'
    previous = json.loads(previous_file.read_bytes())
    if (scope.get('status') != 'EXACT_SCOPE_APPROVED' or scope.get('workflow_head') != HEAD or
        scope.get('contract_sha256') != digest(folder / 'TASK.md') or
        scope.get('previous_receipt_sha256') != digest(previous_file) or
        previous.get('session_actor_sha256') != ACTOR or previous.get('stop_forward') is not True or
        previous.get('counts', {}).get('total') != 19 or
        previous.get('counts', {}).get('edge_positive') != 1 or
        previous.get('role_matrix_complete') is not True or
        previous.get('intents', [{}])[-1].get('outcome') != 'HTTP_502'):
        raise ValueError('CONTINUATION_SCOPE_BLOCKED')
    hashes = scope.get('source_sha256', {})
    if set(hashes) != SOURCES or any(digest(root / name) != sha for name, sha in hashes.items()):
        raise ValueError('SOURCE_BLOCKED')
    if check_head:
        check_source_head(root, scope.get('head'))
    return digest(folder / 'approval.json')


def persist(file, data, *, exclusive=False):
    with file.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def execute(context, file, sender=o.http_request_once, *, validate_scope=check_scope):
    if hashlib.sha256(context['user_uuid'].encode()).hexdigest() != ACTOR:
        raise ValueError('ACTOR_CHANGED')
    receipt = {'previous_receipt_sha256': digest(PREVIOUS), 'prior_operator_requests': 19,
               'prior_positive_attempts': 1, 'cumulative_requests': 19,
               'cumulative_positive_attempts': 1, 'intents': [], 'status': 'READY', 'stop_forward': False}
    persist(file, receipt, exclusive=True)
    headers = {'apikey': context['public_key'], 'Authorization': 'Bearer ' + context['access_token']}
    try:
        paths = (o.WORKSPACE_PATH, MEMBER_PATH, o.JOB_GET_PATH, o.EDGE_PATH)
        for ordinal, path in enumerate(paths):
            validate_scope()  # Recheck approved HEAD/clean tree before each bounded send.
            positive = ordinal == 3
            method = 'POST' if positive else 'GET'
            body = o._canonical_body(o.EDGE_BODY) if positive else None
            receipt['cumulative_requests'] += 1
            receipt['cumulative_positive_attempts'] += int(positive)
            intent = {'ordinal': receipt['cumulative_requests'], 'method': method, 'path': path,
                      'body_sha256': hashlib.sha256(body).hexdigest() if body else None, 'outcome': 'UNKNOWN'}
            receipt['intents'].append(intent)
            persist(file, receipt)  # Consume before send; every path is called once only.
            response = sender(method, o.BASE_URL + path, headers, body)
            if not isinstance(response, o.HttpResponse) or len(response.body) > o.MAX_RESPONSE_BYTES:
                raise ValueError('RESPONSE_UNKNOWN')
            intent['outcome'] = f'HTTP_{response.status}'
            value = o._object(response)
            if ordinal == 0:
                passed = o._exact_workspace(response, True)
            elif ordinal == 1:
                passed = response.status == 200 and value == [{'role': 'owner'}]
            elif ordinal == 2:
                passed = (response.status == 200 and isinstance(value, list) and len(value) == 1 and
                          isinstance(value[0], dict) and value[0].get('status') == 'dispatch_failed' and
                          o._exact_job({**value[0], 'status': 'queued'}, context['user_uuid']))
            else:
                passed = response.status == 202 and value == {
                    'job_id': o.JOB_ID, 'status': 'dispatched', 'created': False}
                receipt['http_status'] = response.status
            intent['passed'] = passed
            persist(file, receipt)
            if not passed:
                raise ValueError('CONTINUATION_INCOMPLETE')
        receipt['status'] = 'DISPATCH_ACCEPTED_EXISTING_JOB'
    except Exception:
        receipt.update(status='STOPPED_RECONCILE_ONLY', stop_forward=True)
        raise ValueError('CONTINUATION_BLOCKED') from None
    finally:
        persist(file, receipt)


def transport(method, url, headers, body):
    if method == 'GET' and url == o.BASE_URL + MEMBER_PATH and body is None:
        # Same official endpoint and no redirect; expose only the exact synthetic role.
        request = o.urllib.request.Request(url, headers=headers, method='GET')
        class NoRedirect(o.urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                return None
        try:
            with o.urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
                return o.HttpResponse(response.status, response.read(o.MAX_RESPONSE_BYTES + 1))
        except o.urllib.error.HTTPError as error:
            return o.HttpResponse(error.code, error.read(o.MAX_RESPONSE_BYTES + 1))
    return o.http_request_once(method, url, headers, body)


def main():
    context = {}
    try:
        frozen = check_scope()
        if sys.argv[1:] == ['--reserve-auth']:
            persist(FOLDER / 'auth-intent.json', {'signin_reserved': 1, 'get_user_reserved': 1,
                    'cumulative_signin_reserved': 2, 'cumulative_get_user_reserved': 2,
                    'scope_sha256': frozen}, exclusive=True)
            return 0
        if len(sys.argv) != 1:
            raise ValueError('ARGS')
        intent = json.loads((FOLDER / 'auth-intent.json').read_bytes())
        if intent.get('scope_sha256') != frozen:
            raise ValueError('AUTH_SCOPE')
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if process_input(raw) != {'status': 'WAITING_FINAL_SCOPE'}:
            raise ValueError('SESSION')
        context = json.loads(raw)
        raw = b''
        if hashlib.sha256(context['user_uuid'].encode()).hexdigest() != ACTOR:
            raise ValueError('ACTOR')
        print('SESSION_READY', flush=True)
        deadline = time.monotonic() + 300
        control = FOLDER / 'control.json'
        while not control.exists():
            if time.monotonic() >= deadline or context['expires_at'] <= time.time() + 90:
                raise ValueError('SESSION_EXPIRED')
            time.sleep(0.25)
        if context['expires_at'] <= time.time() + 90 or check_scope() != frozen or json.loads(control.read_bytes()) != {
            'phase': 'dispatch', 'marker_sha': HEAD, 'scope_sha256': frozen}:
            raise ValueError('CONTROL')
        preflight = json.loads((FOLDER / 'preflight.json').read_bytes())
        if preflight != {'status': 'PASS', 'scope_sha256': frozen, 'marker_sha': HEAD}:
            raise ValueError('PREFLIGHT')
        execute(context, FOLDER / 'receipt.json', transport)
        return 0
    except Exception:
        print('SESSION_OPERATOR_BLOCKED', flush=True)
        return 1
    finally:
        context.clear()


if __name__ == '__main__':
    raise SystemExit(main())
