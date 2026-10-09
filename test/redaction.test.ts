import { describe, expect, it } from 'vitest';
// @ts-expect-error TS7016: Shared JavaScript safety helper has no TypeScript declarations.
import { boundedOutput, looksLikeSecretArgument, redactText, runRedacted } from '../scripts/lib/redact.mjs';

describe('safe command output', () => {
  it('hides credentials and rejects them before starting a command', async () => {
    const cookie = 'cookie=synthetic-cookie';
    expect(redactText(cookie, {})).not.toContain('synthetic-cookie');
    expect(redactText('Bearer opaque-value', {})).toBe('Bearer [REDACTED]');
    expect(looksLikeSecretArgument(cookie)).toBe(true);
    const result = await runRedacted(['never-invoked', cookie], { env: {} });
    expect(result.code).toBe(78);
    expect(result.stderr).toBe('Secret-like argument rejected');
  });

  it('hides a secret split across output chunks', () => {
    const output = boundedOutput({ TEST_TOKEN: 'synthetic-private-value' });
    output.push(Buffer.from('result: synthetic-pri'));
    output.push(Buffer.from('vate-value\n'));
    expect(output.finish()).toBe('result: [REDACTED_ENV_SECRET]\n');
  });

  it('drops an oversized line before emitting any part of it', () => {
    const output = boundedOutput({}, 64);
    output.push(Buffer.from('private-fragment'.repeat(10) + '\n'));
    expect(output.finish()).toBe('[REDACTED_OVERSIZED_LINE]\n');
  });
});
