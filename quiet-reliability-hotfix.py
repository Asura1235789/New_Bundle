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


market_path = 'apps/api/src/market-service.ts'
replace_once(
    market_path,
    "import { SubscriptionTracker, type SocketKind, type SubscriptionMethod } from './subscription-tracker.ts';",
    "import { parseTicker24hChangePercent } from './binance-ticker.ts';\n"
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


notification_test = Path('apps/api/test/quiet-notifications.test.ts')
notification_test.parent.mkdir(parents=True, exist_ok=True)
notification_test.write_text("""import assert from 'node:assert/strict';
import test from 'node:test';
import { parseTicker24hChangePercent } from '../src/binance-ticker.ts';
import { isAutomaticNotificationEventAllowed } from '../src/notification-policy.ts';

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
""", encoding='utf-8')

print('Quiet notification allowlist, exact Binance 24h ticker, listener isolation, API logging, and settings migration applied')
