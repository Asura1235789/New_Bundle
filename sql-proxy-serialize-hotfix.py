from pathlib import Path

p = Path('apps/api/src/watchlist-repository.ts')
text = p.read_text(encoding='utf-8')
old = '''class RemoteSqlPool implements SqlPoolLike {
  constructor(private readonly endpoint: string, private readonly secret: string) {}

  async query<T = Record<string, unknown>>(text: string, values: readonly unknown[] = []): Promise<QueryResultLike<T>> {
    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-fsm-secret': this.secret },
      body: JSON.stringify({ sql: text, params: values }),
      signal: AbortSignal.timeout(30_000),
    });
    const payload = await response.json().catch(() => null) as { rows?: unknown[]; rowCount?: number | null; error?: string } | null;
    if (!response.ok) throw new Error(payload?.error || `Remote SQL proxy failed with HTTP ${response.status}`);
    const rows = (payload?.rows ?? []).map((row) => reviveRemoteValue(row)) as T[];
    return { rows, rowCount: payload?.rowCount ?? rows.length };
  }
'''
new = '''class RemoteSqlPool implements SqlPoolLike {
  private queue: Promise<void> = Promise.resolve();

  constructor(private readonly endpoint: string, private readonly secret: string) {}

  async query<T = Record<string, unknown>>(text: string, values: readonly unknown[] = []): Promise<QueryResultLike<T>> {
    const run = async (): Promise<QueryResultLike<T>> => {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-fsm-secret': this.secret },
        body: JSON.stringify({ sql: text, params: values }),
        signal: AbortSignal.timeout(30_000),
      });
      const payload = await response.json().catch(() => null) as { rows?: unknown[]; rowCount?: number | null; error?: string } | null;
      if (!response.ok) throw new Error(payload?.error || `Remote SQL proxy failed with HTTP ${response.status}`);
      const rows = (payload?.rows ?? []).map((row) => reviveRemoteValue(row)) as T[];
      return { rows, rowCount: payload?.rowCount ?? rows.length };
    };
    const pending = this.queue.then(run, run);
    this.queue = pending.then(() => undefined, () => undefined);
    return pending;
  }
'''
if new in text:
    print('SQL proxy serialization already applied')
elif old in text:
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print('SQL proxy serialization applied')
else:
    raise SystemExit('RemoteSqlPool patch target not found')
