from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Expected source block not found in {path}: {old[:120]!r}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


notification_path = 'apps/api/src/notification-service.ts'
replace_once(
    notification_path,
    "import { sendWebPush } from './web-push.ts';",
    "import { isAutomaticNotificationEventAllowed, type NotificationEventType } from './notification-policy.ts';\n"
    "import { sendWebPush } from './web-push.ts';",
)
replace_once(
    notification_path,
    "type NotificationEventType = 'LONG' | 'SHORT' | 'ENTRY' | 'TP' | 'STOP' | 'DATA_ERROR';\n\n",
    "",
)
replace_once(
    notification_path,
    "  private async dispatch(message: NotificationMessage, ignoreSettings = false): Promise<{ sent: number; failed: number; revoked: number }> {\n"
    "    const webPushConfigured = Boolean(",
    "  private async dispatch(message: NotificationMessage, ignoreSettings = false): Promise<{ sent: number; failed: number; revoked: number }> {\n"
    "    if (!ignoreSettings && !isAutomaticNotificationEventAllowed(message.eventType)) {\n"
    "      return { sent: 0, failed: 0, revoked: 0 };\n"
    "    }\n"
    "    const webPushConfigured = Boolean(",
)

notification_policy = Path('apps/api/src/notification-policy.ts')
notification_policy.write_text("""export type NotificationEventType = 'LONG' | 'SHORT' | 'ENTRY' | 'TP' | 'STOP' | 'DATA_ERROR';

const AUTOMATIC_NOTIFICATION_ALLOWLIST = new Set<NotificationEventType>(['LONG', 'SHORT', 'TP', 'STOP']);

export function isAutomaticNotificationEventAllowed(eventType: NotificationEventType): boolean {
  return AUTOMATIC_NOTIFICATION_ALLOWLIST.has(eventType);
}
""", encoding='utf-8')

replace_once(
    notification_path,
    "    if (this.config.ntfy.enabled && this.config.ntfy.baseUrl && this.config.ntfy.topic) {\n"
    "      try {\n"
    "        await this.sendToNtfy(message);\n"
    "        counts.sent += 1;\n"
    "      } catch (error) {\n"
    "        counts.failed += 1;\n"
    "        console.error(JSON.stringify({\n"
    "          level: 'error',\n"
    "          message: 'Honor/ntfy fallback delivery failed',\n"
    "          symbol: message.symbol,\n"
    "          eventKey: message.eventKey,\n"
    "          error: error instanceof Error ? error.message : String(error),\n"
    "        }));\n"
    "      }\n"
    "    }",
    "    if (this.config.ntfy.enabled && this.config.ntfy.baseUrl && this.config.ntfy.topic) {\n"
    "      // Audit only automatic trading events. Creating this record never emits a push.\n"
    "      const auditId = ignoreSettings ? -1 : await this.repository.claimNotificationAudit({\n"
    "        eventKey: message.eventKey, symbol: message.symbol, eventType: message.eventType,\n"
    "        signalUid: message.signalUid, title: message.title, body: message.body, payload: message.data,\n"
    "      });\n"
    "      // A claimed event is sent once; an existing event is already audited and suppressed as a duplicate.\n"
    "      if (ignoreSettings || auditId !== null) {\n"
    "        try {\n"
    "          await this.sendToNtfy(message);\n"
    "          counts.sent += 1;\n"
    "          if (auditId !== -1 && auditId !== null) await this.repository.finishNotificationAudit(auditId, 'SENT');\n"
    "        } catch (error) {\n"
    "          counts.failed += 1;\n"
    "          const errorMessage = error instanceof Error ? error.message : String(error);\n"
    "          if (auditId !== -1 && auditId !== null) await this.repository.finishNotificationAudit(auditId, 'FAILED', errorMessage);\n"
    "          console.error(JSON.stringify({\n"
    "            level: 'error', message: 'Honor/ntfy fallback delivery failed',\n"
    "            symbol: message.symbol, eventKey: message.eventKey, error: errorMessage,\n"
    "          }));\n"
    "        }\n"
    "      }\n"
    "    }",
)


market_path = 'apps/api/src/market-service.ts'
replace_once(
    market_path,
    "import { SubscriptionTracker, type SocketKind, type SubscriptionMethod } from './subscription-tracker.ts';",
    "import { parseTicker24hChangePercent } from './binance-ticker.ts';\n"
    "import { compactMarketStructureForPublicSnapshot } from './public-snapshot.ts';\n"
    "import { SubscriptionTracker, type SocketKind, type SubscriptionMethod } from './subscription-tracker.ts';",
)
replace_once(
    market_path,
    "interface MutableSymbolState {\n  symbol: string;\n  lastPrice: string | null;",
    "interface MutableSymbolState {\n  symbol: string;\n  lastPrice: string | null;\n  change24hPercent: number | null;",
)
replace_once(
    market_path,
    "function numericString(value: unknown): value is string {\n"
    "  return typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value));\n"
    "}",
    "function numericString(value: unknown): value is string {\n"
    "  return typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value));\n"
    "}",
)
replace_once(
    market_path,
    "    lastPrice: null,\n    bestBid: null,",
    "    lastPrice: null,\n    change24hPercent: null,\n    bestBid: null,",
)

binance_ticker = Path('apps/api/src/binance-ticker.ts')
binance_ticker.write_text("""export function parseTicker24hChangePercent(payload: unknown): number | null {
  if (typeof payload !== 'object' || payload === null || !('P' in payload)) return null;
  const value = (payload as { P?: unknown }).P;
  if (typeof value !== 'string' || value.trim() === '') return null;
  const percent = Number(value);
  return Number.isFinite(percent) ? percent : null;
}
""", encoding='utf-8')

public_snapshot = Path('apps/api/src/public-snapshot.ts')
public_snapshot.write_text("""export interface PublicZone {
  currentRole: 'SUPPORT' | 'RESISTANCE';
  center: number;
}

/** Keep internal pivot history on the server and send only dashboard-visible zones. */
export function compactMarketStructureForPublicSnapshot<
  TZone extends PublicZone,
  TStructure extends { byInterval: unknown; zones: readonly TZone[] },
>(structure: TStructure, currentPrice: number) {
  const { byInterval: _algorithmOnly, zones, ...publicFields } = structure;
  const nearest = (role: PublicZone['currentRole']) => zones
    .filter((zone) => zone.currentRole === role)
    .sort((left, right) => Math.abs(left.center - currentPrice) - Math.abs(right.center - currentPrice))
    .slice(0, 4);
  return { ...publicFields, zones: [...nearest('SUPPORT'), ...nearest('RESISTANCE')] };
}
""", encoding='utf-8')
replace_once(
    market_path,
    "        const oneHourSeries = this.candles.get(`${state.symbol}:1h`);\n"
    "        const reference24h = oneHourSeries?.closed.length && oneHourSeries.closed.length >= 24\n"
    "          ? Number(oneHourSeries.closed.at(-24)?.open ?? Number.NaN)\n"
    "          : Number.NaN;\n"
    "        const latestNumeric = state.lastPrice === null ? Number.NaN : Number(state.lastPrice);\n"
    "        const change24hPercent = Number.isFinite(reference24h) && reference24h > 0 && Number.isFinite(latestNumeric)\n"
    "          ? ((latestNumeric - reference24h) / reference24h) * 100\n"
    "          : null;\n",
    "",
)
replace_once(
    market_path,
    "          change24hPercent,\n",
    "          change24hPercent: state.change24hPercent,\n",
)
replace_once(
    market_path,
    "      `${symbol.toLowerCase()}@markPrice@1s`,\n"
    "      ...INTERVALS.map((interval) => `${symbol.toLowerCase()}@kline_${interval}`),",
    "      `${symbol.toLowerCase()}@markPrice@1s`,\n"
    "      `${symbol.toLowerCase()}@ticker`,\n"
    "      ...INTERVALS.map((interval) => `${symbol.toLowerCase()}@kline_${interval}`),",
)
replace_once(
    market_path,
    "    } else if (stream.endsWith('@markPrice@1s') && numericString(data.p)) {\n"
    "      state.markPrice = data.p;\n"
    "      state.receiveTimes.markPrice = receivedAt;\n"
    "      this.touchEvent(state, eventTime, receivedAt);\n"
    "    } else if (stream.includes('@kline_') && isRecord(data.k)) {",
    "    } else if (stream.endsWith('@markPrice@1s') && numericString(data.p)) {\n"
    "      state.markPrice = data.p;\n"
    "      state.receiveTimes.markPrice = receivedAt;\n"
    "      this.touchEvent(state, eventTime, receivedAt);\n"
    "    } else if (stream.endsWith('@ticker')) {\n"
    "      const change24hPercent = parseTicker24hChangePercent(data);\n"
    "      if (change24hPercent !== null) state.change24hPercent = change24hPercent;\n"
    "      this.touchEvent(state, eventTime, receivedAt);\n"
    "    } else if (stream.includes('@kline_') && isRecord(data.k)) {",
)
replace_once(
    market_path,
    "    for (const listener of this.listeners) listener(snapshot);",
    "    for (const listener of this.listeners) {\n"
    "      try {\n"
    "        listener(snapshot);\n"
    "      } catch (error) {\n"
    "        log('error', 'Market snapshot listener failed', { error: error instanceof Error ? error.message : String(error) });\n"
    "      }\n"
    "    }",
)
replace_once(
    market_path,
    "          structure: state.structure,",
    "          structure: compactMarketStructureForPublicSnapshot(state.structure, Number(state.lastPrice ?? 0)),",
)


app_path = 'apps/api/src/app.ts'
replace_once(
    app_path,
    "      const message = error instanceof Error ? error.message : '内部错误';\n"
    "      if (!response.headersSent) writeJson(request, response, config, statusCode, { error: { code, message } });",
    "      const message = error instanceof Error ? error.message : '内部错误';\n"
    "      console.error(JSON.stringify({\n"
    "        level: 'error', message: 'API request failed', method: request.method ?? null,\n"
    "        path: request.url?.split('?')[0] ?? null, statusCode, code, error: message,\n"
    "      }));\n"
    "      if (!response.headersSent) writeJson(request, response, config, statusCode, { error: { code, message } });",
)
replace_once(
    app_path,
    "      for (const key of ['notifyLong','notifyShort','notifyEntry','notifyTp','notifyStop','notifyDataError'] as const) {",
    "      if (body.notifyEntry === true || body.notifyDataError === true) {\n"
    "        throw new MarketServiceError(400, 'QUIET_MODE_ENFORCED', '低噪声模式只允许做多、做空、止盈、止损自动通知');\n"
    "      }\n"
    "      for (const key of ['notifyLong','notifyShort','notifyEntry','notifyTp','notifyStop','notifyDataError'] as const) {",
)
replace_once(
    app_path,
    "    if (request.method === 'POST' && url.pathname === '/notifications/test') {",
    "    if (request.method === 'GET' && url.pathname === '/notifications/audit') {\n"
    "      if (!repository) throw new MarketServiceError(503, 'NOTIFICATIONS_UNAVAILABLE', '通知服务未启用');\n"
    "      const requestedHours = Number.parseInt(url.searchParams.get('hours') ?? '24', 10);\n"
    "      const requestedLimit = Number.parseInt(url.searchParams.get('limit') ?? '200', 10);\n"
    "      const hours = Number.isFinite(requestedHours) ? Math.max(1, Math.min(720, requestedHours)) : 24;\n"
    "      const limit = Number.isFinite(requestedLimit) ? Math.max(1, Math.min(500, requestedLimit)) : 200;\n"
    "      writeJson(request, response, config, 200, { hours, items: await repository.listNotificationAudit(hours, limit) });\n"
    "      return;\n"
    "    }\n\n"
    "    if (request.method === 'POST' && url.pathname === '/notifications/test') {",
)


backtest_path = 'apps/api/src/backtest-service.ts'
replace_once(
    backtest_path,
    "      saveCandles: (candles) => repository.saveCandles(candles),",
    "      // Historical backtests are fetched into memory. Persisting millions of 1m candles\n"
    "      // can exhaust a small production database and is not required for correctness.\n"
    "      saveCandles: async () => {},",
)
replace_once(
    backtest_path,
    "    this.history = new BinanceHistoricalDataClient(config.binance.restBaseUrl, cache);",
    "    this.history = new BinanceHistoricalDataClient(config.binance.restBaseUrl, cache, 500);",
)

# The replay fills an entry at a resting preferred/zone-edge price, then exits on a
# touched stop/target. Charge the configured maker rate for entry and taker rate for
# exit; the previous implementation accidentally charged taker on both legs and
# never used makerFee.
engine_path = 'packages/backtest-engine/src/index.ts'
replace_once(
    engine_path,
    "  const feesQuotePerUnit = (active.entryPrice + exitPrice) * config.takerFee;",
    "  const feesQuotePerUnit = active.entryPrice * config.makerFee + exitPrice * config.takerFee;",
)
replace_once(
    backtest_path,
    "  private readonly gitCommit: string | null;",
    "  private readonly gitCommit: string | null;\n"
    "  private queue: Promise<void> = Promise.resolve();",
)
replace_once(
    backtest_path,
    "    setImmediate(() => void this.execute(runId, request));\n"
    "    return runId;",
    "    // Only one dataset is fetched/replayed at a time to cap API memory and Binance load.\n"
    "    this.queue = this.queue.then(() => this.execute(runId, request)).catch((error: unknown) => {\n"
    "      console.error(JSON.stringify({\n"
    "        level: 'error', message: 'Backtest queue failed', runId,\n"
    "        error: error instanceof Error ? error.message : String(error),\n"
    "      }));\n"
    "    });\n"
    "    return runId;",
)


repository_path = 'apps/api/src/watchlist-repository.ts'
replace_once(
    repository_path,
    "export interface BacktestRunRecord {",
    "export interface NotificationAuditRow {\n"
    "  id: number; eventKey: string; symbol: string; eventType: string; signalUid: string | null;\n"
    "  title: string; body: string; payload: Record<string, unknown>;\n"
    "  status: 'QUEUED' | 'SENT' | 'FAILED'; errorMessage: string | null;\n"
    "  createdAt: string; sentAt: string | null;\n"
    "}\n\n"
    "export interface BacktestRunRecord {",
)
replace_once(
    repository_path,
    "      ON CONFLICT (signal_uid) WHERE signal_uid IS NOT NULL DO UPDATE SET\n"
    "        lifecycle = EXCLUDED.lifecycle, state = EXCLUDED.state, snapshot = EXCLUDED.snapshot,",
    "      -- The original schema already guarantees this fingerprint is unique. Older rows\n"
    "      -- can have a null signal_uid, so targeting signal_uid alone misses their conflict.\n"
    "      ON CONFLICT (symbol_id, interval, structure_fingerprint) DO UPDATE SET\n"
    "        signal_uid = EXCLUDED.signal_uid, direction = EXCLUDED.direction, score = EXCLUDED.score,\n"
    "        current_price = EXCLUDED.current_price, entry_low = EXCLUDED.entry_low, entry_high = EXCLUDED.entry_high,\n"
    "        invalidation_price = EXCLUDED.invalidation_price, tp1 = EXCLUDED.tp1, tp2 = EXCLUDED.tp2, tp3 = EXCLUDED.tp3,\n"
    "        risk_reward = EXCLUDED.risk_reward, reasons = EXCLUDED.reasons, conditions = EXCLUDED.conditions,\n"
    "        lifecycle = EXCLUDED.lifecycle, state = EXCLUDED.state, snapshot = EXCLUDED.snapshot,",
)
replace_once(
    repository_path,
    "  async close(): Promise<void> {\n"
    "    await this.pool.end();\n"
    "  }",
    "  async claimNotificationAudit(input: { eventKey: string; symbol: string; eventType: string; signalUid: string | null; title: string; body: string; payload: Record<string, unknown> }): Promise<number | null> {\n"
    "    const result = await this.pool.query<{ id: string }>(`\n"
    "      INSERT INTO notification_audit (event_key,symbol,event_type,signal_uid,title,body,payload,status)\n"
    "      VALUES ($1,$2,$3,$4,$5,$6,$7,'QUEUED')\n"
    "      ON CONFLICT (event_key) DO NOTHING RETURNING id\n"
    "    `, [input.eventKey,input.symbol,input.eventType,input.signalUid,input.title,input.body,JSON.stringify(input.payload)]);\n"
    "    return result.rows[0] ? Number(result.rows[0].id) : null;\n"
    "  }\n\n"
    "  async finishNotificationAudit(id: number, status: 'SENT' | 'FAILED', errorMessage: string | null = null): Promise<void> {\n"
    "    await this.pool.query(`UPDATE notification_audit SET status=$2,error_message=$3,sent_at=CASE WHEN $2='SENT' THEN now() ELSE NULL END WHERE id=$1`, [id,status,errorMessage]);\n"
    "  }\n\n"
    "  async listNotificationAudit(hours = 24, limit = 200): Promise<NotificationAuditRow[]> {\n"
    "    const safeHours = Math.max(1, Math.min(720, Math.trunc(hours)));\n"
    "    const safeLimit = Math.max(1, Math.min(500, Math.trunc(limit)));\n"
    "    const result = await this.pool.query<{ id:string;event_key:string;symbol:string;event_type:string;signal_uid:string|null;title:string;body:string;payload:Record<string,unknown>;status:NotificationAuditRow['status'];error_message:string|null;created_at:Date;sent_at:Date|null }>(`\n"
    "      SELECT id,event_key,symbol,event_type,signal_uid,title,body,payload,status,error_message,created_at,sent_at\n"
    "      FROM notification_audit WHERE created_at >= now() - ($1 * interval '1 hour')\n"
    "      ORDER BY created_at DESC LIMIT $2\n"
    "    `, [safeHours,safeLimit]);\n"
    "    return result.rows.map((row) => ({ id:Number(row.id),eventKey:row.event_key,symbol:row.symbol,eventType:row.event_type,signalUid:row.signal_uid,title:row.title,body:row.body,payload:row.payload,status:row.status,errorMessage:row.error_message,createdAt:row.created_at.toISOString(),sentAt:row.sent_at?.toISOString() ?? null }));\n"
    "  }\n\n"
    "  async close(): Promise<void> {\n"
    "    await this.pool.end();\n"
    "  }",
)
replace_once(
    repository_path,
    "    try {\n"
    "      await client.query(`\n"
    "        CREATE TABLE IF NOT EXISTS schema_migrations (",
    "    try {\n"
    "      // Emergency one-time cleanup: a failed historical backtest can fill a small\n"
    "      // database so completely that even migration bookkeeping cannot allocate a page.\n"
    "      // Only reproducible Binance candle cache rows are removed, and only before 0005.\n"
    "      const migrationTable = await client.query<{ exists: boolean }>(\n"
    "        `SELECT to_regclass('public.schema_migrations') IS NOT NULL AS exists`,\n"
    "      );\n"
    "      if (migrationTable.rows[0]?.exists) {\n"
    "        const quietMigration = await client.query<{ applied: boolean }>(\n"
    "          `SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE filename='0005_quiet_notifications.sql') AS applied`,\n"
    "        );\n"
    "        if (!quietMigration.rows[0]?.applied) {\n"
    "          // TRUNCATE itself needs a new relfilenode and can fail at absolute zero free space.\n"
    "          // DROP unlinks the oversized cache first; then recreate its original schema.\n"
    "          await client.query('DROP TABLE IF EXISTS candles');\n"
    "          await client.query(`\n"
    "            CREATE TABLE candles (\n"
    "              symbol_id uuid NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,\n"
    "              interval text NOT NULL, open_time timestamptz NOT NULL, close_time timestamptz NOT NULL,\n"
    "              open numeric NOT NULL, high numeric NOT NULL, low numeric NOT NULL, close numeric NOT NULL,\n"
    "              base_volume numeric NOT NULL, quote_volume numeric NOT NULL, trade_count integer NOT NULL,\n"
    "              is_closed boolean NOT NULL, PRIMARY KEY (symbol_id, interval, open_time)\n"
    "            )\n"
    "          `);\n"
    "          await client.query('CREATE INDEX candles_recent_idx ON candles (symbol_id, interval, open_time DESC)');\n"
    "        }\n"
    "      }\n"
    "      await client.query(`\n"
    "        CREATE TABLE IF NOT EXISTS schema_migrations (",
)


replace_once(
    market_path,
    "  private readonly repairingSymbols = new Set<string>();\n"
    "  private publicSocket: WebSocket | null = null;",
    "  private readonly repairingSymbols = new Set<string>();\n"
    "  private readonly backfillRetryTimers = new Map<string, NodeJS.Timeout>();\n"
    "  private publicSocket: WebSocket | null = null;",
)
replace_once(
    market_path,
    "    for (const entry of this.entries.values()) {\n"
    "      if (entry.state === 'ACTIVE') await this.activateSymbol(entry.symbol, false);\n"
    "    }",
    "    for (const entry of this.entries.values()) {\n"
    "      if (entry.state !== 'ACTIVE') continue;\n"
    "      try {\n"
    "        await this.activateSymbol(entry.symbol, false);\n"
    "      } catch (error) {\n"
    "        this.markBackfillFailed(entry.symbol, error);\n"
    "        this.scheduleBackfillRetry(entry.symbol, 60_000);\n"
    "      }\n"
    "    }",
)
replace_once(
    market_path,
    "    for (const timer of [this.reconnectTimer, this.rotationTimer, this.stableResetTimer, this.freshnessTimer, this.broadcastTimer]) {\n"
    "      if (timer) clearTimeout(timer);\n"
    "    }",
    "    for (const timer of [this.reconnectTimer, this.rotationTimer, this.stableResetTimer, this.freshnessTimer, this.broadcastTimer, ...this.backfillRetryTimers.values()]) {\n"
    "      if (timer) clearTimeout(timer);\n"
    "    }\n"
    "    this.backfillRetryTimers.clear();",
)
replace_once(
    market_path,
    "        log('error', 'Symbol activation failed', {\n"
    "          symbol,\n"
    "          error: error instanceof Error ? error.message : String(error),\n"
    "        });\n"
    "        this.emitNow();",
    "        log('error', 'Symbol activation failed', {\n"
    "          symbol,\n"
    "          error: error instanceof Error ? error.message : String(error),\n"
    "        });\n"
    "        this.scheduleBackfillRetry(symbol, 60_000);\n"
    "        this.emitNow();",
)
replace_once(
    market_path,
    "  private async backfillSymbol(symbol: string): Promise<void> {",
    "  private markBackfillFailed(symbol: string, error: unknown): void {\n"
    "    const state = this.states.get(symbol) ?? blankState(symbol);\n"
    "    this.states.set(symbol, state);\n"
    "    state.repairing = false;\n"
    "    state.dataStatus = 'DATA STALE';\n"
    "    state.staleReason = `Binance 历史数据暂不可用，后台重试中：${error instanceof Error ? error.message : String(error)}`;\n"
    "    log('warn', 'Backfill deferred; API remains online', { symbol, error: error instanceof Error ? error.message : String(error) });\n"
    "  }\n\n"
    "  private scheduleBackfillRetry(symbol: string, delayMs: number): void {\n"
    "    if (this.stopped || this.backfillRetryTimers.has(symbol) || !this.entries.has(symbol)) return;\n"
    "    const timer = setTimeout(() => {\n"
    "      this.backfillRetryTimers.delete(symbol);\n"
    "      if (this.stopped || this.entries.get(symbol)?.state !== 'ACTIVE') return;\n"
    "      void this.activateSymbol(symbol, false).then(() => {\n"
    "        log('info', 'Deferred Binance backfill recovered', { symbol });\n"
    "        this.emitNow();\n"
    "      }).catch((error: unknown) => {\n"
    "        this.markBackfillFailed(symbol, error);\n"
    "        this.scheduleBackfillRetry(symbol, Math.min(delayMs * 2, 15 * 60_000));\n"
    "        this.emitNow();\n"
    "      });\n"
    "    }, delayMs);\n"
    "    this.backfillRetryTimers.set(symbol, timer);\n"
    "  }\n\n"
    "  private async backfillSymbol(symbol: string): Promise<void> {",
)
replace_once(
    market_path,
    "  private releaseSymbolMemory(symbol: string): void {\n"
    "    this.states.delete(symbol);",
    "  private releaseSymbolMemory(symbol: string): void {\n"
    "    const retryTimer = this.backfillRetryTimers.get(symbol);\n"
    "    if (retryTimer) clearTimeout(retryTimer);\n"
    "    this.backfillRetryTimers.delete(symbol);\n"
    "    this.states.delete(symbol);",
)


migration = Path('packages/database/migrations/0005_quiet_notifications.sql')
migration.write_text("""-- Candle rows are a reproducible Binance cache, not user-authored records.
-- Clear the oversized cache left by backtests; live monitoring immediately repopulates
-- the latest 500 candles per interval while future backtests remain memory-only.
TRUNCATE TABLE candles;

ALTER TABLE user_settings
  ALTER COLUMN minimum_signal_score SET DEFAULT 70,
  ALTER COLUMN notify_entry SET DEFAULT false,
  ALTER COLUMN notify_data_error SET DEFAULT false;

UPDATE user_settings
SET minimum_signal_score = 70,
    notify_long = true,
    notify_short = true,
    notify_entry = false,
    notify_tp = true,
    notify_stop = true,
    notify_data_error = false,
    updated_at = now();
""", encoding='utf-8')

audit_migration = Path('packages/database/migrations/0006_notification_audit.sql')
audit_migration.write_text("""CREATE TABLE IF NOT EXISTS notification_audit (
  id bigserial PRIMARY KEY,
  event_key text NOT NULL UNIQUE,
  symbol text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('LONG','SHORT','TP','STOP')),
  signal_uid text,
  title text NOT NULL,
  body text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL CHECK (status IN ('QUEUED','SENT','FAILED')),
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);
CREATE INDEX IF NOT EXISTS notification_audit_created_idx ON notification_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS notification_audit_symbol_created_idx ON notification_audit (symbol, created_at DESC);
""", encoding='utf-8')


notification_test = Path('apps/api/test/quiet-notifications.test.ts')
notification_test.parent.mkdir(parents=True, exist_ok=True)
notification_test.write_text("""import assert from 'node:assert/strict';
import test from 'node:test';
import { parseTicker24hChangePercent } from '../src/binance-ticker.ts';
import { isAutomaticNotificationEventAllowed } from '../src/notification-policy.ts';
import { compactMarketStructureForPublicSnapshot } from '../src/public-snapshot.ts';

test('automatic notifications use the low-noise allowlist', () => {
  assert.equal(isAutomaticNotificationEventAllowed('LONG'), true);
  assert.equal(isAutomaticNotificationEventAllowed('SHORT'), true);
  assert.equal(isAutomaticNotificationEventAllowed('TP'), true);
  assert.equal(isAutomaticNotificationEventAllowed('STOP'), true);
  assert.equal(isAutomaticNotificationEventAllowed('ENTRY'), false);
  assert.equal(isAutomaticNotificationEventAllowed('DATA_ERROR'), false);
});

test('24h ticker percentage uses Binance rolling ticker field', () => {
  assert.equal(parseTicker24hChangePercent({ P: '30.125' }), 30.125);
  assert.equal(parseTicker24hChangePercent({ P: '-8.25' }), -8.25);
  assert.equal(parseTicker24hChangePercent({ P: 'not-a-number' }), null);
  assert.equal(parseTicker24hChangePercent(null), null);
});

test('public snapshots omit pivot history and keep four nearest zones per role', () => {
  const zones = [
    ...[90, 80, 70, 60, 50].map((center) => ({ currentRole: 'SUPPORT' as const, center })),
    ...[110, 120, 130, 140, 150].map((center) => ({ currentRole: 'RESISTANCE' as const, center })),
  ];
  const compact = compactMarketStructureForPublicSnapshot({ byInterval: { '15m': { pivots: [1, 2, 3] } }, zones, marker: true }, 100);
  assert.equal('byInterval' in compact, false);
  assert.deepEqual(compact.zones.map((zone) => zone.center), [90, 80, 70, 60, 110, 120, 130, 140]);
  assert.equal(compact.marker, true);
});
""", encoding='utf-8')

# Backtest-only balanced strategy. The live evaluator continues using
# DEFAULT_SIGNAL_CONFIG; CURRENT and BALANCED_V1 can be compared safely with the
# same production notification score floor before changing any live behaviour.
signal_engine_path = 'packages/signal-engine/src/index.ts'
replace_once(signal_engine_path,
    "  maxRetestDistanceAtr: number;\n  expiresAfterMs: number;",
    "  maxRetestDistanceAtr: number;\n  minimumRejectionWickAtr: number;\n  minimumRejectionBodyAtr: number;\n  minimumTrendSeparationAtr: number;\n  requireTrendSlope: boolean;\n  continuationMinimumVolumeRatio: number;\n  expiresAfterMs: number;")
replace_once(signal_engine_path,
    "  maxRetestDistanceAtr: 1.5,\n  expiresAfterMs:",
    "  maxRetestDistanceAtr: 1.5,\n  minimumRejectionWickAtr: 0,\n  minimumRejectionBodyAtr: 0,\n  minimumTrendSeparationAtr: 0,\n  requireTrendSlope: false,\n  continuationMinimumVolumeRatio: 0,\n  expiresAfterMs:")
replace_once(signal_engine_path,
"""function lowerRejection(candle: Candle, zone: StructureZone): boolean {
  const shape = candleShape(candle);
  return shape.low <= zone.upper && shape.lowerWick >= Math.max(shape.body, Number.EPSILON) * 1.5 && shape.close >= zone.lower && shape.closeLocation >= 0.55;
}
function upperRejection(candle: Candle, zone: StructureZone): boolean {
  const shape = candleShape(candle);
  return shape.high >= zone.lower && shape.upperWick >= Math.max(shape.body, Number.EPSILON) * 1.5 && shape.close <= zone.upper && shape.closeLocation <= 0.45;
}""",
"""function lowerRejection(candle: Candle, zone: StructureZone, atr: number, config: SignalConfig): boolean {
  const shape = candleShape(candle);
  return shape.low <= zone.upper && shape.lowerWick >= Math.max(shape.body, Number.EPSILON) * 1.5
    && shape.lowerWick >= atr * config.minimumRejectionWickAtr && shape.body >= atr * config.minimumRejectionBodyAtr
    && shape.close >= zone.lower && shape.closeLocation >= 0.55;
}
function upperRejection(candle: Candle, zone: StructureZone, atr: number, config: SignalConfig): boolean {
  const shape = candleShape(candle);
  return shape.high >= zone.lower && shape.upperWick >= Math.max(shape.body, Number.EPSILON) * 1.5
    && shape.upperWick >= atr * config.minimumRejectionWickAtr && shape.body >= atr * config.minimumRejectionBodyAtr
    && shape.close <= zone.upper && shape.closeLocation <= 0.45;
}
function trendQuality(input: SignalInput, direction: Exclude<SignalBias, 'NEUTRAL'>, atr: number, config: SignalConfig): boolean {
  const indicator = input.indicators['1h'];
  if (!indicator?.ma25 || !indicator.ma99 || !(atr > 0)) return false;
  const separationPassed = Math.abs(indicator.ma25 - indicator.ma99) / atr >= config.minimumTrendSeparationAtr;
  if (!config.requireTrendSlope) return separationPassed;
  const closes = closedCandles(input, '1h').map((candle) => value(candle.close));
  if (closes.length < 26) return false;
  const current = closes.slice(-25).reduce((sum, close) => sum + close, 0) / 25;
  const previous = closes.slice(-26, -1).reduce((sum, close) => sum + close, 0) / 25;
  return separationPassed && (direction === 'LONG' ? current > previous : current < previous);
}""")
replace_once(signal_engine_path, "lowerRejection(latest15, support)", "lowerRejection(latest15, support, atr, config)")
replace_once(signal_engine_path, "upperRejection(latest15, resistance)", "upperRejection(latest15, resistance, atr, config)")
replace_once(signal_engine_path,
    "  const fiveMinuteTiming = executionTiming(input, direction);",
    "  const fiveMinuteTiming = executionTiming(input, direction);\n  const alignedTrendQuality = oneHourBias === direction && trendQuality(input, direction, atr, config);")
replace_once(signal_engine_path,
    "addScore('TREND', oneHourBias === direction, config.scoreWeights.trend, `1h ${oneHourBias} 与方向一致`);",
    "addScore('TREND', alignedTrendQuality, config.scoreWeights.trend, `1h ${oneHourBias} 方向、斜率与均线分离度合格`);")
replace_once(signal_engine_path, "const strongTrendContinuation = oneHourBias === direction", "const strongTrendContinuation = alignedTrendQuality")
replace_once(signal_engine_path,
    "const volumeConfirmedOrContinuation = (volumeRatio ?? 0) >= config.minimumClosedVolumeRatio || strongTrendContinuation;",
    "const volumeConfirmedOrContinuation = (volumeRatio ?? 0) >= config.minimumClosedVolumeRatio\n    || (strongTrendContinuation && (volumeRatio ?? 0) >= config.continuationMinimumVolumeRatio);")

backtest_types_path = 'packages/backtest-engine/src/types.ts'
replace_once(backtest_types_path,
    "export type EntryBarPolicy = 'STOP_IF_TOUCHED_IGNORE_TARGETS' | 'MARK_AMBIGUOUS';",
    "export type EntryBarPolicy = 'STOP_IF_TOUCHED_IGNORE_TARGETS' | 'MARK_AMBIGUOUS';\nexport type BacktestStrategyProfile = 'CURRENT' | 'BALANCED_V1';")
replace_once(backtest_types_path,
    "  executionConfig?: Partial<BacktestExecutionConfig>;\n  appVersion?: string;",
    "  executionConfig?: Partial<BacktestExecutionConfig>;\n  strategyProfile?: BacktestStrategyProfile;\n  minimumSignalScore?: number;\n  appVersion?: string;")
replace_once(backtest_types_path,
    "  strategyConfigVersion: 'phase-4.1';\n  executionConfig:",
    "  strategyConfigVersion: 'phase-4.1';\n  strategyProfile: BacktestStrategyProfile;\n  minimumSignalScore: number;\n  executionConfig:")

replace_once(engine_path,
    "import { evaluateSignal, SignalLifecycleRegistry, type SignalSnapshot } from '@fsm/signal-engine';",
    "import { DEFAULT_SIGNAL_CONFIG, evaluateSignal, SignalLifecycleRegistry, type SignalConfig, type SignalSnapshot } from '@fsm/signal-engine';")
replace_once(engine_path,
    "  type BacktestExecutionConfig,\n  type BacktestMetrics,",
    "  type BacktestExecutionConfig,\n  type BacktestStrategyProfile,\n  type BacktestMetrics,")
replace_once(engine_path, "function defaultEvaluate(context: ReplayStrategyContext): SignalSnapshot {", """const BALANCED_V1_SIGNAL_CONFIG: SignalConfig = {
  ...DEFAULT_SIGNAL_CONFIG,
  minimumClosedVolumeRatio: 0.85, minimumTp1RR: 1.3, stopAtrBuffer: 0.4,
  opposingZoneTooCloseAtr: 0.7, maxRetestSignalAgeBars: 4, maxRetestDistanceAtr: 1.3,
  minimumRejectionWickAtr: 0.18, minimumRejectionBodyAtr: 0.03,
  minimumTrendSeparationAtr: 0.12, requireTrendSlope: true, continuationMinimumVolumeRatio: 0.65,
  scoreWeights: { trend: 14, zone: 13, rejection: 12, retest: 12, volume: 10, confluence: 9, execution: 10, riskReward: 10, opposingSpace: 6, health: 4 },
};
function signalConfigFor(profile: BacktestStrategyProfile): SignalConfig {
  return profile === 'BALANCED_V1' ? BALANCED_V1_SIGNAL_CONFIG : DEFAULT_SIGNAL_CONFIG;
}
function defaultEvaluate(context: ReplayStrategyContext, signalConfig: SignalConfig): SignalSnapshot {""")
replace_once(engine_path,
    "    evaluatedAt: context.now,\n  });",
    "    evaluatedAt: context.now,\n  }, signalConfig);")
replace_once(engine_path,
    "  const config: BacktestExecutionConfig = { ...DEFAULT_EXECUTION_CONFIG, ...request.executionConfig, fundingIncluded: false };\n  validateBacktestExecutionConfig(config);\n  const evaluator = options.evaluator ?? defaultEvaluate;",
    "  const config: BacktestExecutionConfig = { ...DEFAULT_EXECUTION_CONFIG, ...request.executionConfig, fundingIncluded: false };\n  const strategyProfile: BacktestStrategyProfile = request.strategyProfile ?? 'CURRENT';\n  if (!['CURRENT', 'BALANCED_V1'].includes(strategyProfile)) throw new BacktestValidationError('INVALID_STRATEGY_PROFILE', '不支持的策略配置');\n  const minimumSignalScore = request.minimumSignalScore ?? 70;\n  if (!Number.isFinite(minimumSignalScore) || minimumSignalScore < 0 || minimumSignalScore > 100) throw new BacktestValidationError('INVALID_MINIMUM_SIGNAL_SCORE', '信号分数必须在 0 到 100 之间');\n  const signalConfig = signalConfigFor(strategyProfile);\n  validateBacktestExecutionConfig(config);\n  const evaluator = options.evaluator ?? ((context) => defaultEvaluate(context, signalConfig));")
replace_once(engine_path,
    "const ready = !trackingExistingTrade && signal.signalId && (signal.decision === 'LONG_READY' || signal.decision === 'SHORT_READY');",
    "const ready = !trackingExistingTrade && signal.signalId && signal.score >= minimumSignalScore\n      && (signal.decision === 'LONG_READY' || signal.decision === 'SHORT_READY');")
replace_once(engine_path,
    "strategyConfigVersion: 'phase-4.1', executionConfig: config,",
    "strategyConfigVersion: 'phase-4.1', strategyProfile, minimumSignalScore, executionConfig: config,")

replace_once(backtest_path,
    "    const request: BacktestRequest = {\n      symbol, startTime, endTime, appVersion: this.appVersion, gitCommit: this.gitCommit,",
    "    const strategyProfile = body.strategyProfile === 'BALANCED_V1' ? 'BALANCED_V1' : body.strategyProfile === 'CURRENT' || body.strategyProfile === undefined ? 'CURRENT' : null;\n    if (!strategyProfile) throw new MarketServiceError(400, 'INVALID_STRATEGY_PROFILE', 'strategyProfile 仅支持 CURRENT 或 BALANCED_V1');\n    const minimumSignalScore = body.minimumSignalScore === undefined ? 70 : Number(body.minimumSignalScore);\n    if (!Number.isFinite(minimumSignalScore) || minimumSignalScore < 0 || minimumSignalScore > 100) throw new MarketServiceError(400, 'INVALID_MINIMUM_SIGNAL_SCORE', 'minimumSignalScore 必须在 0 到 100 之间');\n    const request: BacktestRequest = {\n      symbol, startTime, endTime, strategyProfile, minimumSignalScore, appVersion: this.appVersion, gitCommit: this.gitCommit,")

# A signal may move from CANDIDATE straight to ACTIVE when price is already in
# the entry zone. Send the normal LONG/SHORT event in that case; ENTRY remains off.
replace_once(notification_path,
"""      this.initialized = true;
      return;""",
"""      this.initialized = true;
      // Recover only recent ACTIVE setups after a restart. The shared READY event
      // key and notification_audit unique constraint prevent duplicate pushes.
      for (const item of snapshot.symbols) {
        const enteredAt = item.signal?.enteredAt;
        if (item.signal?.state === 'ACTIVE' && enteredAt !== null && enteredAt !== undefined
          && snapshot.generatedAt - enteredAt <= 2 * 60 * 60_000) {
          await this.processTransitions(item, {
            dataStatus: item.dataStatus, signalId: null, signalState: null, signalDecision: null,
          });
        }
      }
      return;""")
replace_once(notification_path,
    "const hasReadyEvent = (isNewSignal || stateChanged || decisionChanged) && signal.state === 'READY' && Boolean(readyDirection);",
    "const hasReadyEvent = (isNewSignal || stateChanged || decisionChanged)\n      && (signal.state === 'READY' || signal.state === 'ACTIVE') && Boolean(readyDirection);")

# TP progress is historical state, not a live price label. Once TP2 was reached,
# a later retrace to the TP1 area must not downgrade the lifecycle.
replace_once(signal_engine_path,
    "else if (hit(next.targets.tp1)) next = { ...next, state: 'TP1_HIT' };",
    "else if (next.state === 'ACTIVE' && hit(next.targets.tp1)) next = { ...next, state: 'TP1_HIT' };")

# Recover the highest historically reached TP from monotonic timestamp columns,
# and prevent lower live states from overwriting a higher persisted TP state.
replace_once(repository_path,
"""    const result = await this.pool.query<{ snapshot: SignalSnapshot }>(`
      SELECT snapshot FROM signals""",
"""    const result = await this.pool.query<{ snapshot: SignalSnapshot; tp1_hit_at: Date | null; tp2_hit_at: Date | null; tp3_hit_at: Date | null }>(`
      SELECT snapshot, tp1_hit_at, tp2_hit_at, tp3_hit_at FROM signals""")
replace_once(repository_path,
    "    return result.rows.map((row) => row.snapshot);",
    "    return result.rows.map((row) => ({ ...row.snapshot, state: row.tp3_hit_at ? 'TP3_HIT' : row.tp2_hit_at ? 'TP2_HIT' : row.tp1_hit_at ? 'TP1_HIT' : row.snapshot.state }));")
replace_once(repository_path,
    "        lifecycle = EXCLUDED.lifecycle, state = EXCLUDED.state, snapshot = EXCLUDED.snapshot,",
"""        lifecycle = CASE
          WHEN signals.state='TP2_HIT' AND EXCLUDED.state IN ('ACTIVE','TP1_HIT') THEN signals.lifecycle
          WHEN signals.state='TP1_HIT' AND EXCLUDED.state='ACTIVE' THEN signals.lifecycle
          ELSE EXCLUDED.lifecycle END,
        state = CASE
          WHEN signals.state='TP2_HIT' AND EXCLUDED.state IN ('ACTIVE','TP1_HIT') THEN signals.state
          WHEN signals.state='TP1_HIT' AND EXCLUDED.state='ACTIVE' THEN signals.state
          ELSE EXCLUDED.state END,
        snapshot = CASE
          WHEN signals.state='TP2_HIT' AND EXCLUDED.state IN ('ACTIVE','TP1_HIT') THEN signals.snapshot
          WHEN signals.state='TP1_HIT' AND EXCLUDED.state='ACTIVE' THEN signals.snapshot
          ELSE EXCLUDED.snapshot END,""")

# Add a bounded order-flow boost using Binance aggTrade data already received by
# the service. It is score-only (max 8), adds no gate and emits no new event type.
replace_once(signal_engine_path,
    "  continuationMinimumVolumeRatio: number;\n  expiresAfterMs: number;",
    "  continuationMinimumVolumeRatio: number;\n  flowBoostMaximumScore: number;\n  expiresAfterMs: number;")
replace_once(signal_engine_path,
    "  continuationMinimumVolumeRatio: 0,\n  expiresAfterMs:",
    "  continuationMinimumVolumeRatio: 0,\n  flowBoostMaximumScore: 8,\n  expiresAfterMs:")
replace_once(signal_engine_path,
    "  health: SignalHealth;\n  evaluatedAt: number;",
"""  health: SignalHealth;
  orderFlow?: {
    aggressiveBuyShare: number;
    quoteVolumeAcceleration: number;
    recentTradeCount: number;
  } | null;
  evaluatedAt: number;""")
replace_once(signal_engine_path,
"""  addScore('HEALTH', true, config.scoreWeights.health, '行情、时钟、订阅与历史数据健康');
  const score = Math.round(scoreReasons.reduce((sum, reason) => sum + reason.score, 0) * 100) / 100;""",
"""  addScore('HEALTH', true, config.scoreWeights.health, '行情、时钟、订阅与历史数据健康');
  const flow = input.orderFlow;
  const directionalShare = direction === 'LONG' ? flow?.aggressiveBuyShare ?? 0 : 1 - (flow?.aggressiveBuyShare ?? 1);
  const flowAligned = Boolean(flow && flow.recentTradeCount >= 30
    && flow.quoteVolumeAcceleration >= 1.8 && directionalShare >= 0.65);
  const flowBoost = flowAligned
    ? clamp(4 + (directionalShare - 0.65) * 10 + (flow!.quoteVolumeAcceleration - 1.8), 4, config.flowBoostMaximumScore)
    : 0;
  addScore('FLOW_BOOST', flowAligned, flowBoost,
    `5m 主动${direction === 'LONG' ? '买入' : '卖出'}占比 ${(directionalShare * 100).toFixed(1)}% · 成交额加速 ${flow?.quoteVolumeAcceleration.toFixed(2)}x`);
  const score = Math.min(100, Math.round(scoreReasons.reduce((sum, reason) => sum + reason.score, 0) * 100) / 100);""")

replace_once(market_path,
    "import { evaluateSignal, SignalLifecycleRegistry, type SignalSnapshot } from '@fsm/signal-engine';",
    "import { evaluateSignal, SignalLifecycleRegistry, type SignalInput, type SignalSnapshot } from '@fsm/signal-engine';")
replace_once(market_path,
    "interface Diagnostics {",
"""interface AggressiveFlowBucket {
  bucketStart: number;
  buyQuote: number;
  sellQuote: number;
  tradeCount: number;
}

interface Diagnostics {""")
replace_once(market_path,
    "  private readonly lastCandidatePersistAt = new Map<string, number>();",
    "  private readonly lastCandidatePersistAt = new Map<string, number>();\n  private readonly aggressiveFlow = new Map<string, AggressiveFlowBucket[]>();")
replace_once(market_path,
    "      structure: state.structure,\n      health,\n      evaluatedAt: now,",
    "      structure: state.structure,\n      health,\n      orderFlow: this.orderFlowSnapshot(state.symbol, now),\n      evaluatedAt: now,")
replace_once(market_path,
    "  private publicStreams(symbol: string): string[] {",
"""  private recordAggressiveFlow(symbol: string, time: number, price: number, quantity: number, buyerIsMaker: boolean): void {
    const buckets = this.aggressiveFlow.get(symbol) ?? [];
    const bucketStart = Math.floor(time / 10_000) * 10_000;
    let bucket = buckets.at(-1);
    if (!bucket || bucket.bucketStart !== bucketStart) {
      bucket = { bucketStart, buyQuote: 0, sellQuote: 0, tradeCount: 0 };
      buckets.push(bucket);
    }
    const quoteVolume = price * quantity;
    if (buyerIsMaker) bucket.sellQuote += quoteVolume;
    else bucket.buyQuote += quoteVolume;
    bucket.tradeCount += 1;
    const cutoff = time - 15 * 60_000;
    while (buckets.length > 0 && buckets[0]!.bucketStart < cutoff) buckets.shift();
    this.aggressiveFlow.set(symbol, buckets);
  }

  private orderFlowSnapshot(symbol: string, now: number): SignalInput['orderFlow'] {
    const buckets = this.aggressiveFlow.get(symbol) ?? [];
    const recent = buckets.filter((bucket) => bucket.bucketStart >= now - 5 * 60_000);
    const baseline = buckets.filter((bucket) => bucket.bucketStart >= now - 15 * 60_000 && bucket.bucketStart < now - 5 * 60_000);
    const recentBuyQuote = recent.reduce((sum, bucket) => sum + bucket.buyQuote, 0);
    const recentSellQuote = recent.reduce((sum, bucket) => sum + bucket.sellQuote, 0);
    const recentQuote = recentBuyQuote + recentSellQuote;
    const baselineFiveMinuteQuote = baseline.reduce((sum, bucket) => sum + bucket.buyQuote + bucket.sellQuote, 0) / 2;
    const recentTradeCount = recent.reduce((sum, bucket) => sum + bucket.tradeCount, 0);
    if (recentTradeCount < 10 || !(recentQuote > 0) || !(baselineFiveMinuteQuote > 0)) return null;
    return {
      aggressiveBuyShare: recentBuyQuote / recentQuote,
      quoteVolumeAcceleration: recentQuote / baselineFiveMinuteQuote,
      recentTradeCount,
    };
  }

  private publicStreams(symbol: string): string[] {""")
replace_once(market_path,
    "      state.lastPrice = data.p;\n      state.structure = relocateMarketStructure",
    "      state.lastPrice = data.p;\n      if (numericString(data.q) && typeof data.m === 'boolean') {\n        this.recordAggressiveFlow(symbol, eventTime ?? receivedAt, Number(data.p), Number(data.q), data.m);\n      }\n      state.structure = relocateMarketStructure")
replace_once(market_path,
    "    this.backfillRetryTimers.delete(symbol);\n    this.states.delete(symbol);",
    "    this.backfillRetryTimers.delete(symbol);\n    this.aggressiveFlow.delete(symbol);\n    this.states.delete(symbol);")

print('Quiet notifications, market reliability, monotonic TP recovery, and bounded order-flow scoring applied')
