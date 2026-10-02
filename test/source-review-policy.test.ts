import { describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { configHash, reviewSource, sourceAllowed, validateConfig } from '../scripts/lib/bridge.mjs';
import { looksLikeSecretArgument, redactText, runRedacted } from '../scripts/lib/redact.mjs';

const sha = (text: string) => createHash('sha256').update(text).digest('hex');
const digest = (value: unknown) => sha(JSON.stringify(value));
const testPath = 'tests/test_synthetic.py';
const dependency = 'scripts/lib/redact.mjs';
const cookie = 'cookie=synthetic-cookie';
const bearer = 'Bearer [REDACTED]';
const testContent = `raise RuntimeError("${cookie}")\n`;
const dependencyContent = `export const placeholder = "${bearer}";\n`;
const binding = { provider: 'openai', command: ['codex'], model: 'synthetic-model' };
const approval = (file: string, content: string, kind = 'synthetic-test-data') => ({
  path: file, sha256: sha(content), kind, reason: 'Personally inspected synthetic source',
});
const config = (approvals = [approval(testPath, testContent)]) => ({
  schema_version: 'qq.bridge.v1', billing: 'SUBSCRIPTION_ONLY', mode: 'ASSISTED',
  timeout_seconds: 60, write_paths: [testPath], gate_paths: ['scripts/check.mjs'],
  review_context_paths: [dependency], synthetic_source_approvals: approvals,
  worker: binding, reviewer: binding, senior: binding,
});

describe('exact inspected source policy', () => {
  it('admits the complete synthetic cookie error only with matching test path and bytes', () => {
    expect(sourceAllowed(testPath, testContent, config(), {})).toBe(true);
    expect(sourceAllowed(testPath, testContent, config([]), {})).toBe(false);
    expect(sourceAllowed('tests/other.py', testContent, config(), {})).toBe(false);
    expect(sourceAllowed(testPath, testContent + '# changed\n', config(), {})).toBe(false);
    expect(sourceAllowed(dependency, testContent, config([approval(dependency, testContent)]), {})).toBe(false);
    const singleQuoted = `raise RuntimeError('${cookie}')\n`;
    expect(sourceAllowed(testPath, singleQuoted, config([approval(testPath, singleQuoted)]), {})).toBe(true);
  });

  it('admits a static placeholder only in an exact declared, hash-approved non-test dependency', () => {
    const a = approval(dependency, dependencyContent, 'static-review-dependency');
    const c = config([a]);
    expect(() => validateConfig(c)).not.toThrow();
    expect(sourceAllowed(dependency, dependencyContent, c, {})).toBe(true);
    expect(sourceAllowed(dependency, dependencyContent, config([]), {})).toBe(false);
    expect(sourceAllowed(dependency, dependencyContent + '// stale\n', c, {})).toBe(false);
    const gate = { ...c, gate_paths: [dependency], review_context_paths: [] };
    expect(() => validateConfig(gate)).not.toThrow();
    expect(sourceAllowed(dependency, dependencyContent, gate, {})).toBe(true);
    for (const paths of [[], ['scripts'], ['scripts/lib']]) {
      const undeclared = { ...c, review_context_paths: paths };
      expect(() => validateConfig(undeclared)).toThrow();
      expect(sourceAllowed(dependency, dependencyContent, undeclared, {})).toBe(false);
    }
    expect(sourceAllowed(testPath, dependencyContent,
      config([approval(testPath, dependencyContent, 'static-review-dependency')]), {})).toBe(false);
    expect(sourceAllowed(dependency, testContent,
      config([approval(dependency, testContent, 'static-review-dependency')]), {})).toBe(false);
    expect(sourceAllowed(testPath, dependencyContent,
      config([approval(testPath, dependencyContent)]), {})).toBe(false);
  });

  it('rejects unknown kinds, malformed hashes, duplicate approvals and wildcard paths', () => {
    for (const a of [
      approval(testPath, testContent, 'credential-exemption'),
      approval(dependency, dependencyContent),
      approval(testPath, dependencyContent, 'static-review-dependency'),
      approval('tests/*', testContent),
      { ...approval(testPath, testContent), sha256: 'bad-hash' },
    ]) expect(() => validateConfig(config([a]))).toThrow();
    const a = approval(testPath, testContent);
    expect(() => validateConfig(config([a, a]))).toThrow();
    expect(sourceAllowed('tests/child.py', testContent,
      config([approval('tests', testContent)]), {})).toBe(false);
  });

  it('requires the entire quoted marker, not a prefix, suffix or extended header value', () => {
    for (const [file, marker, kind] of [
      [testPath, cookie, 'synthetic-test-data'],
      [dependency, bearer, 'static-review-dependency'],
    ]) {
      for (const value of [marker + 'x', marker + '.tail', marker + '/tail', marker + '-tail',
        marker + '=tail', marker + '; tail', marker + ' tail', 'prefix-' + marker,
        marker.toUpperCase(), marker + '\\ntrailing']) {
        const source = `const value = "${value}";\n`;
        expect(sourceAllowed(file, source, config([approval(file, source, kind)]), {})).toBe(false);
      }
      const unquoted = marker + '\n';
      expect(sourceAllowed(file, unquoted, config([approval(file, unquoted, kind)]), {})).toBe(false);
      for (const source of [`const value = "${marker}" + "tail";`,
        `const value = "prefix" + "${marker}";`, `value = "${marker}" "tail"`,
        `value = "prefix" "${marker}"`]) {
        expect(sourceAllowed(file, source, config([approval(file, source, kind)]), {})).toBe(false);
      }
    }
  });

  it('never exempts other headers, recognizable credentials, invalid text or current secrets', () => {
    const forbidden = [
      'Authorization: opaque-value', 'Proxy-Authorization: opaque-value',
      'Set-Cookie: synthetic-cookie', 'Cookie: synthetic-cookie', 'cookie=unknown-value',
      'Bearer opaque-value', 'ghp_' + 'a'.repeat(20), 'github_pat_' + 'b'.repeat(20),
      'sk-' + 'c'.repeat(20), 'xoxb-' + 'd'.repeat(20),
      ['a'.repeat(16), 'b'.repeat(16), 'c'.repeat(16)].join('.'),
      'https://' + 'user:opaque-value@example.invalid',
      '-----BEGIN ' + 'PRIVATE KEY-----', '\0', '\ufffd',
    ];
    for (const [file, source, kind] of [
      [testPath, testContent, 'synthetic-test-data'],
      [dependency, dependencyContent, 'static-review-dependency'],
    ]) {
      for (const value of forbidden) {
        const full = source + value;
        expect(sourceAllowed(file, full, config([approval(file, full, kind)]), {})).toBe(false);
      }
      const c = config([approval(file, source, kind)]);
      expect(sourceAllowed(file, source, c, { SYNTHETIC_SECRET: file === testPath ? cookie : bearer })).toBe(false);
    }
    const extra = dependencyContent + 'const value = "password=unknown-value";\n';
    expect(sourceAllowed(dependency, extra,
      config([approval(dependency, extra, 'static-review-dependency')]), {})).toBe(false);
    const existing = 'const fixture = "password=synthetic-value";\n';
    expect(sourceAllowed(testPath, existing, config([approval(testPath, existing)]), {})).toBe(true);
  });

  for (const [file, marker, kind] of [
    [testPath, cookie, 'synthetic-test-data'],
    [dependency, bearer, 'static-review-dependency'],
  ]) {
    it.each([
      ['grouped concatenation', `const value = ("${marker}") + "tail";`],
      ['nested larger string', `const value = "prefix ('${marker}') tail";`],
      ['array join', `const value = ["${marker}", "tail"].join("");`],
      ['nested grouping', `const value = (("${marker}")) + "tail";`],
      ['grouped prefix', `const value = "prefix" + ("${marker}");`],
      ['multiline triple string', `value = '''prefix\nraise RuntimeError("${marker}")\ntail'''`],
      ['template string', 'const value = `prefix\nexport const placeholder = "' + marker + '";\ntail`;'],
      ['commented statement', `/*\nexport const placeholder = "${marker}";\n*/`],
      ['error argument expression', `raise RuntimeError(("${marker}") + "tail")`],
      ['nested formatted multiline string', `value = f"""{"""prefix\nraise RuntimeError("${marker}")\ntail"""}"""`],
    ])(`rejects %s for ${kind}`, (_label, source) => {
      expect(sourceAllowed(file, source, config([approval(file, source, kind)]), {})).toBe(false);
    });
  }

  it('continues to admit the complete original Python tests and redaction dependency', async () => {
    for (const [file, kind] of [
      ['apps/browser-runner/tests/unit/test_browser_driver.py', 'synthetic-test-data'],
      ['apps/browser-runner/tests/unit/test_live_adapter.py', 'synthetic-test-data'],
      [dependency, 'static-review-dependency'],
    ]) {
      const source = await readFile(new URL('../' + file, import.meta.url), 'utf8');
      expect(sourceAllowed(file, source, config([approval(file, source, kind)]), {})).toBe(true);
      expect(sourceAllowed(file, source, config([]), {})).toBe(false);
    }
  });

  it('accepts a standalone replacement table but rejects transformations of the enclosing array', () => {
    const table = `const replacements = [\n  [/example/g, "${bearer}"],\n]`;
    const standalone = table + ';\n';
    expect(sourceAllowed(dependency, standalone,
      config([approval(dependency, standalone, 'static-review-dependency')]), {})).toBe(true);
    for (const suffix of ['.join("");', '.concat("tail");', ' + "tail";', '[0] + "tail";']) {
      const source = table + suffix;
      expect(sourceAllowed(dependency, source,
        config([approval(dependency, source, 'static-review-dependency')]), {})).toBe(false);
    }
    for (const source of [`const text = \`prefix\n${standalone}tail\`;`,
      'const text = "prefix\\\n' + standalone.replaceAll('"', "'") + 'tail";',
      `/* prefix\n${standalone}tail */`]) {
      expect(sourceAllowed(dependency, source,
        config([approval(dependency, source, 'static-review-dependency')]), {})).toBe(false);
    }
  });

  it('preserves runtime redaction and argument rejection', async () => {
    expect(redactText(cookie, {})).not.toContain('synthetic-cookie');
    expect(redactText('Bearer opaque-value', {})).toBe(bearer);
    expect(looksLikeSecretArgument(cookie)).toBe(true);
    expect(looksLikeSecretArgument(bearer)).toBe(true);
    const result = await runRedacted(['never-invoked', cookie], { env: {} });
    expect(result.code).toBe(78);
    expect(result.stderr).toBe('Secret-like argument rejected');
  });

  it('generates a full raw Git source packet with base/head and dependency bindings', async () => {
    const dir = await mkdtemp(path.join(tmpdir(), 'mindx-source-policy-'));
    const git = (...args: string[]) => execFileSync('git', args, {
      cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
    const put = async (file: string, content: string) => {
      await mkdir(path.dirname(path.join(dir, file)), { recursive: true });
      await writeFile(path.join(dir, file), content);
    };
    const rawDependency = await readFile(new URL('../scripts/lib/redact.mjs', import.meta.url), 'utf8');
    const before = testContent + '# base-only source\n';
    const after = testContent + '# head-only source\n';
    await put(testPath, before);
    await put(dependency, rawDependency);
    await put('scripts/check.mjs', 'export const checked = true;\n');
    await put('package.json', '{"name":"synthetic-review-source"}\n');
    git('init');
    git('config', 'user.name', 'Synthetic Source Test');
    git('config', 'user.email', 'source-test@example.invalid');
    git('config', 'core.autocrlf', 'false');
    git('add', '.');
    git('commit', '-m', 'synthetic base');
    const base = git('rev-parse', 'HEAD');
    await put(testPath, after);
    git('add', '.');
    git('commit', '-m', 'synthetic candidate');
    const head = git('rev-parse', 'HEAD');
    const c = config([approval(testPath, before), approval(testPath, after),
      approval(dependency, rawDependency, 'static-review-dependency')]);
    const t = {
      task_id: 'SYNTHETIC-SOURCE', revision: 1, base_sha: base, candidate_head: head,
      contract_sha256: sha('synthetic frozen contract'),
      gates: [{ argv: ['node', 'scripts/check.mjs'] }],
      execution: { source_approvals_sha256: digest(c.synthetic_source_approvals) },
    };
    const source = reviewSource(dir, t, c);
    expect(source).toMatchObject({ base, head, contract_sha256: t.contract_sha256,
      config_hash: configHash(c), synthetic_source_approvals: c.synthetic_source_approvals });
    expect(source.base_files).toContainEqual({ path: testPath, content: before, sha256: sha(before) });
    for (const [file, content] of [[testPath, after], [dependency, rawDependency],
      ['scripts/check.mjs', 'export const checked = true;\n'],
      ['package.json', '{"name":"synthetic-review-source"}\n']]) {
      expect(source.files).toEqual(expect.arrayContaining([expect.objectContaining({
        path: file, content, sha256: sha(content),
      })]));
    }
    expect(source.baseline).toContainEqual({ path: testPath, base_sha256: sha(before),
      head_sha256: sha(after), unchanged: false });
    expect(source.baseline).toContainEqual({ path: dependency, base_sha256: sha(rawDependency),
      head_sha256: sha(rawDependency), unchanged: true });
    expect(source.declared_context_paths).toContain(dependency);
    expect(source.diff).toContain('-# base-only source');
    expect(source.diff).toContain('+# head-only source');
    expect(source.diff).toContain(cookie);
    expect(digest(JSON.parse(JSON.stringify(source)))).toBe(digest(source));
    expect(() => reviewSource(dir, { ...t, execution: { source_approvals_sha256: sha('stale') } }, c)).toThrow();
    expect(() => reviewSource(dir, { ...t, candidate_head: base }, c)).toThrow();
    const missing = { ...c, review_context_paths: [dependency, 'missing.mjs'] };
    expect(() => reviewSource(dir, t, missing)).toThrow('declared review context is missing');
    const directory = { ...c, review_context_paths: [dependency, 'scripts'],
      synthetic_source_approvals: [...c.synthetic_source_approvals,
        approval('scripts', rawDependency, 'static-review-dependency')] };
    expect(() => reviewSource(dir, { ...t, execution: {
      source_approvals_sha256: digest(directory.synthetic_source_approvals),
    } }, directory)).toThrow('static review approval must name a declared file');
    const stale = { ...c, synthetic_source_approvals: c.synthetic_source_approvals.slice(1) };
    expect(() => reviewSource(dir, { ...t, execution: {
      source_approvals_sha256: digest(stale.synthetic_source_approvals),
    } }, stale)).toThrow('review source contains binary or secret-like content');
    expect(git('status', '--porcelain')).toBe('');
  }, 20000);
});
