from pathlib import Path


def replace(path: str, old: str, new: str):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Patch target not found in {path}')
    p.write_text(text.replace(old, new), encoding='utf-8')

repo = Path('apps/api/src/watchlist-repository.ts')
text = repo.read_text(encoding='utf-8')
marker = "const APPLICATION_USER_ID = '00000000-0000-4000-8000-000000000001';\n"
proxy_code = r'''
interface QueryResultLike<T> {
  rows: T[];
  rowCount: number | null;
}

interface SqlClientLike {
  query<T = Record<string, unknown>>(text: string, values?: readonly unknown[]): Promise<QueryResultLike<T>>;
  release(): void;
}

interface SqlPoolLike {
  query<T = Record<string, unknown>>(text: string, values?: readonly unknown[]): Promise<QueryResultLike<T>>;
  connect(): Promise<SqlClientLike>;
  end(): Promise<void>;
}

function reviveRemoteValue(value: unknown): unknown {
  if (typeof value === 'string' && /^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?Z$/.test(value)) {
    return new Date(value);
  }
  if (Array.isArray(value)) return value.map(reviveRemoteValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, reviveRemoteValue(item)]));
  }
  return value;
}

class RemoteSqlPool implements SqlPoolLike {
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

  async connect(): Promise<SqlClientLike> {
    return { query: <T = Record<string, unknown>>(text: string, values?: readonly unknown[]) => this.query<T>(text, values), release: () => {} };
  }

  async end(): Promise<void> {}
}

function createSqlPool(databaseUrl: string, proxySecret?: string): SqlPoolLike {
  if (/^https:\\/\\//i.test(databaseUrl)) {
    if (!proxySecret) throw new Error('DATABASE_PROXY_SECRET is required for remote SQL proxy mode');
    return new RemoteSqlPool(databaseUrl, proxySecret);
  }
  return new Pool({ connectionString: databaseUrl, max: 5, idleTimeoutMillis: 30_000 }) as unknown as SqlPoolLike;
}
'''
if 'class RemoteSqlPool' not in text:
    if marker not in text:
        raise SystemExit('APPLICATION_USER_ID marker not found')
    text = text.replace(marker, marker + proxy_code)

old_ctor = """  private readonly pool: InstanceType<typeof Pool>;

  constructor(databaseUrl: string) {
    this.pool = new Pool({ connectionString: databaseUrl, max: 5, idleTimeoutMillis: 30_000 });
  }"""
new_ctor = """  private readonly pool: SqlPoolLike;

  constructor(databaseUrl: string, databaseProxySecret?: string) {
    this.pool = createSqlPool(databaseUrl, databaseProxySecret);
  }"""
if old_ctor in text:
    text = text.replace(old_ctor, new_ctor)

start = text.index('  async add(symbol: VerifiedSymbol)')
end = text.index('  async remove(symbol: string)')
text = text[:start] + r'''  async add(symbol: VerifiedSymbol): Promise<WatchlistEntry> {
    const result = await this.pool.query<EntryRow>(`
      WITH upsert_symbol AS (
        INSERT INTO symbols (
          symbol, contract_type, status, base_asset, quote_asset,
          price_precision, quantity_precision, exchange_info_updated_at
        ) VALUES ($2, $3, $4, $5, $6, $7, $8, now())
        ON CONFLICT (symbol) DO UPDATE SET
          contract_type = EXCLUDED.contract_type,
          status = EXCLUDED.status,
          base_asset = EXCLUDED.base_asset,
          quote_asset = EXCLUDED.quote_asset,
          price_precision = EXCLUDED.price_precision,
          quantity_precision = EXCLUDED.quantity_precision,
          exchange_info_updated_at = now()
        RETURNING id
      ),
      upsert_watchlist AS (
        INSERT INTO watchlists (user_id, symbol_id, state)
        SELECT $1, id, 'ACTIVE' FROM upsert_symbol
        ON CONFLICT (user_id, symbol_id) DO UPDATE SET state = 'ACTIVE', updated_at = now()
        RETURNING symbol_id, state, created_at, updated_at
      )
      SELECT s.symbol, w.state, w.created_at, w.updated_at
      FROM upsert_watchlist w
      JOIN symbols s ON s.id = w.symbol_id
    `, [
      APPLICATION_USER_ID, symbol.symbol, symbol.contractType, symbol.status, symbol.baseAsset,
      symbol.quoteAsset, symbol.pricePrecision, symbol.quantityPrecision,
    ]);
    return rowToEntry(result.rows[0]!);
  }

''' + text[end:]

start = text.index('  async completeBacktest(runId: string')
end = text.index('  async failBacktest(runId: string')
text = text[:start] + r'''  async completeBacktest(runId: string, result: BacktestResult): Promise<void> {
    const trades = result.trades.map((trade) => ({
      signal_id: trade.signalId, symbol: trade.symbol, direction: trade.direction, setup_type: trade.setupType,
      score: Math.round(trade.score), entry_time: new Date(trade.entryTime).toISOString(), entry_price: trade.entryPrice,
      stop: trade.stop, targets: { tp1: trade.tp1, tp2: trade.tp2, tp3: trade.tp3 },
      exit_time: new Date(trade.exitTime).toISOString(), exit_price: trade.exitPrice, exit_reason: trade.exitReason,
      gross_r: trade.grossR, net_r: trade.netR, fees: trade.feesQuotePerUnit, slippage: trade.slippageQuotePerUnit, details: trade,
    }));
    await this.pool.query(`
      WITH updated AS (
        UPDATE backtest_runs
        SET status='COMPLETE', progress=100, dataset_info=$2::jsonb, metrics=$3::jsonb, result=$4::jsonb, completed_at=now()
        WHERE id=$1 RETURNING id
      ), inserted AS (
        INSERT INTO backtest_trades (
          run_id, signal_id, symbol, direction, setup_type, score, entry_time, entry_price, stop,
          targets, exit_time, exit_price, exit_reason, gross_r, net_r, fees, slippage, details
        )
        SELECT updated.id, t.signal_id, t.symbol, t.direction, t.setup_type, t.score, t.entry_time, t.entry_price,
          t.stop, t.targets, t.exit_time, t.exit_price, t.exit_reason, t.gross_r, t.net_r, t.fees, t.slippage, t.details
        FROM updated
        CROSS JOIN jsonb_to_recordset($5::jsonb) AS t(
          signal_id text, symbol text, direction text, setup_type text, score integer, entry_time timestamptz,
          entry_price numeric, stop numeric, targets jsonb, exit_time timestamptz, exit_price numeric,
          exit_reason text, gross_r numeric, net_r numeric, fees numeric, slippage numeric, details jsonb
        )
        ON CONFLICT (run_id, signal_id) DO NOTHING RETURNING id
      ) SELECT (SELECT count(*) FROM inserted)::int AS inserted_count
    `, [runId, JSON.stringify(result.datasetInfo), JSON.stringify(result.metrics), JSON.stringify(result), JSON.stringify(trades)]);
  }

''' + text[end:]
repo.write_text(text, encoding='utf-8')

replace(
    'apps/api/src/config.ts',
    '  databaseUrl: string;\n',
    '  databaseUrl: string;\n  databaseProxySecret: string | null;\n',
)
replace(
    'apps/api/src/config.ts',
    '    databaseUrl,\n    push:',
    "    databaseUrl,\n    databaseProxySecret: env.DATABASE_PROXY_SECRET || null,\n    push:",
)
replace(
    'apps/api/src/server.ts',
    'const repository = new PostgresWatchlistRepository(config.databaseUrl);',
    'const repository = new PostgresWatchlistRepository(config.databaseUrl, config.databaseProxySecret ?? undefined);',
)
print('Render deployment patch applied')
