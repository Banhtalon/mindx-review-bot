"""One private app session, ordered fixed-scope commands, existing operator guards."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from app_session_receiver import MAX_INPUT_BYTES, process_input
from api_chain_operator import (
    OperatorLedger, dispatch_existing_job, http_request_once, live_capability_status,
    probe_edge_negative, run_role_probes,
)

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.workflow-local' / 'api-chain-session'
WORKFLOW_HEAD = '1855c37a6f1347cd70d14f9b9eb6eec52596823a'
PHASES = ('nonmember', 'reviewer', 'owner', 'dispatch')


def check_scope(folder=FOLDER, root=ROOT):
    raw = (folder / 'approval.json').read_bytes()
    if len(raw) > 8192:
        raise ValueError('SCOPE_BLOCKED')
    scope = json.loads(raw)
    if (scope.get('workflow_head') != WORKFLOW_HEAD or
        live_capability_status(official_session=SimpleNamespace(verified_official_app_session=True),
                               approved_head=scope.get('head'), final_packet=scope) != 'CAPABILITY_PRESENT_NOT_EXECUTED' or
        scope.get('contract_sha256') != hashlib.sha256((folder / 'TASK.md').read_bytes()).hexdigest()):
        raise ValueError('SCOPE_BLOCKED')
    expected = {'scripts/app_session_host.mjs', 'scripts/lib/app_session.mjs',
                'scripts/app_session_receiver.py', 'scripts/api_chain_operator.py',
                'scripts/api_chain_session.py', 'scripts/api_chain_session_host.mjs'}
    hashes = scope.get('source_sha256')
    if not isinstance(hashes, dict) or set(hashes) != expected:
        raise ValueError('SOURCE_BLOCKED')
    for name, digest in hashes.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('SOURCE_BLOCKED')
    return hashlib.sha256(raw).hexdigest()


def command(value, expected, previous):
    if not isinstance(value, dict):
        raise ValueError('COMMAND_BLOCKED')
    if value == previous:
        return False
    fields = {'phase', 'marker_sha'} if expected == 'dispatch' else {'phase'}
    if set(value) != fields or value.get('phase') != expected:
        raise ValueError('COMMAND_BLOCKED')
    if expected == 'dispatch' and value['marker_sha'] != WORKFLOW_HEAD:
        raise ValueError('MARKER_BLOCKED')
    return True


def execute_phase(phase, context, ledger, sender=http_request_once):
    headers = {'apikey': context['public_key'], 'Authorization': 'Bearer ' + context['access_token'],
               'Prefer': 'return=representation'}
    anon = {'apikey': context['public_key']}
    if phase == 'dispatch':
        result = dispatch_existing_job(headers, sender, ledger, marker_sha=WORKFLOW_HEAD,
                                       approved_sha=WORKFLOW_HEAD, final_scope=True)
        if result['status'] != 'PASS':
            raise ValueError('DISPATCH_INCOMPLETE')
    else:
        for role in (('anonymous', 'nonmember') if phase == 'nonmember' else (phase,)):
            principal = anon if role == 'anonymous' else headers
            result = run_role_probes(role, sender, ledger, auth_headers=principal,
                                     caller_user_id=None if role == 'anonymous' else context['user_uuid'])
            if result['status'] != 'PASS':
                raise ValueError('ROLE_INCOMPLETE')
            if role != 'owner':
                result = probe_edge_negative(role, principal, sender, ledger)
                if result['status'] not in {'AUTH_GATE_ONLY', 'DENIED_OWNER_REQUIRED'}:
                    raise ValueError('EDGE_INCOMPLETE')


def main():
    ledger = None
    try:
        if len(sys.argv) != 1:
            raise ValueError('ARGS_BLOCKED')
        scope_digest = check_scope()
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if process_input(raw) != {'status': 'WAITING_FINAL_SCOPE'}:
            raise ValueError('SESSION_BLOCKED')
        context = json.loads(raw)
        raw = b''
        if context['expires_at'] < time.time() + 360:
            raise ValueError('SESSION_TOO_SHORT')
        ledger = OperatorLedger(FOLDER / 'operator-receipt.json')
        ledger.data.update(session_actor_sha256=hashlib.sha256(context['user_uuid'].encode()).hexdigest(),
                           phase_status='READY_NO_SEND', phases=[])
        ledger.persist()
        print('SESSION_READY', flush=True)
        deadline = time.monotonic() + 300
        previous = None
        for phase in PHASES:
            while True:
                if time.monotonic() >= deadline or context['expires_at'] <= time.time() + 30:
                    raise ValueError('SESSION_EXPIRED')
                if check_scope() != scope_digest:
                    raise ValueError('SCOPE_CHANGED')
                control = FOLDER / 'control.json'
                if control.exists():
                    value = json.loads(control.read_bytes()[:1025])
                    if command(value, phase, previous):
                        break
                time.sleep(0.25)
            ledger.data['phase_status'] = phase + '_STARTED'
            ledger.persist()
            execute_phase(phase, context, ledger)
            ledger.data['phases'].append(phase)
            ledger.data['phase_status'] = phase + '_PASS'
            ledger.persist()
            previous = value
        context.clear()
        return 0
    except Exception:
        if ledger is not None:
            ledger.data['phase_status'] = 'STOPPED_RECONCILE_ONLY'
            ledger.stop('SESSION_OPERATOR_BLOCKED')
        print('SESSION_OPERATOR_BLOCKED', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
