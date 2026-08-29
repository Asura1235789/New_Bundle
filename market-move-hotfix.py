from pathlib import Path

# Add rolling 24h percentage move to market snapshots.
p = Path('apps/api/src/market-service.ts')
text = p.read_text(encoding='utf-8')
old = '''        const requiredAges = [...Object.values(ages), ...Object.values(klineAgesMs)].filter((value): value is number => value !== null);
        return {
          symbol: state.symbol,
          lastPrice: state.lastPrice,
'''
new = '''        const requiredAges = [...Object.values(ages), ...Object.values(klineAgesMs)].filter((value): value is number => value !== null);
        const oneHourSeries = this.candles.get(`${state.symbol}:1h`);
        const reference24h = oneHourSeries?.closed.length && oneHourSeries.closed.length >= 24
          ? Number(oneHourSeries.closed.at(-24)?.open ?? Number.NaN)
          : Number.NaN;
        const latestNumeric = state.lastPrice === null ? Number.NaN : Number(state.lastPrice);
        const change24hPercent = Number.isFinite(reference24h) && reference24h > 0 && Number.isFinite(latestNumeric)
          ? ((latestNumeric - reference24h) / reference24h) * 100
          : null;
        return {
          symbol: state.symbol,
          lastPrice: state.lastPrice,
          change24hPercent,
'''
if new not in text:
    if old not in text:
        raise SystemExit('24h snapshot patch target not found')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Add persistence helpers to the existing repository.
p = Path('apps/api/src/watchlist-repository.ts')
text = p.read_text(encoding='utf-8')
anchor = '''  async getNotificationSettings(): Promise<NotificationSettingsRow> {
'''
methods = '''  async listMarketMoveAlertStates(): Promise<Array<{ symbol: string; band: 'NONE' | 'UP' | 'DOWN' }>> {
    const result = await this.pool.query<{ symbol: string; band: 'NONE' | 'UP' | 'DOWN' }>(`
      SELECT symbol, band FROM market_move_alert_state
    `);
    return result.rows.map((row) => ({ symbol: row.symbol, band: row.band }));
  }

  async setMarketMoveAlertState(symbol: string, band: 'NONE' | 'UP' | 'DOWN', changePercent: number): Promise<void> {
    await this.pool.query(`
      INSERT INTO market_move_alert_state (symbol, band, last_change_percent, notified_at, updated_at)
      VALUES ($1, $2, $3, CASE WHEN $2='NONE' THEN NULL ELSE now() END, now())
      ON CONFLICT (symbol) DO UPDATE SET
        band=EXCLUDED.band,
        last_change_percent=EXCLUDED.last_change_percent,
        notified_at=CASE WHEN EXCLUDED.band='NONE' THEN NULL ELSE now() END,
        updated_at=now()
    `, [symbol, band, changePercent]);
  }

'''
if methods not in text:
    if anchor not in text:
        raise SystemExit('repository market move patch target not found')
    p.write_text(text.replace(anchor, methods + anchor, 1), encoding='utf-8')

# Add independent ±10% alerts, separate from directional signal logic.
p = Path('apps/api/src/notification-service.ts')
text = p.read_text(encoding='utf-8')
text = text.replace(
    "type NotificationEventType = 'LONG' | 'SHORT' | 'ENTRY' | 'TP' | 'STOP' | 'DATA_ERROR';",
    "type NotificationEventType = 'LONG' | 'SHORT' | 'ENTRY' | 'TP' | 'STOP' | 'DATA_ERROR' | 'MARKET_MOVE';",
    1,
)
old = '''export class NotificationService {
  private readonly last = new Map<string, LastSymbolState>();
  private unsubscribe: (() => void) | null = null;
  private initialized = false;
'''
new = '''export class NotificationService {
  private readonly last = new Map<string, LastSymbolState>();
  private readonly moveBands = new Map<string, 'NONE' | 'UP' | 'DOWN'>();
  private moveStatePromise: Promise<void> | null = null;
  private unsubscribe: (() => void) | null = null;
  private initialized = false;
'''
if new not in text:
    if old not in text:
        raise SystemExit('notification fields patch target not found')
    text = text.replace(old, new, 1)
old = '''  private async handleSnapshot(snapshot: MarketSnapshot): Promise<void> {
    const current = new Map<string, LastSymbolState>();
'''
new = '''  private async handleSnapshot(snapshot: MarketSnapshot): Promise<void> {
    await this.ensureMoveState();
    for (const item of snapshot.symbols) await this.processMarketMove(item);

    const current = new Map<string, LastSymbolState>();
'''
if new not in text:
    if old not in text:
        raise SystemExit('notification handleSnapshot patch target not found')
    text = text.replace(old, new, 1)
anchor = '''  private async processTransitions(item: MarketSymbol, previous: LastSymbolState): Promise<void> {
'''
methods = '''  private async ensureMoveState(): Promise<void> {
    if (!this.moveStatePromise) {
      this.moveStatePromise = this.repository.listMarketMoveAlertStates()
        .then((rows) => {
          this.moveBands.clear();
          for (const row of rows) this.moveBands.set(row.symbol, row.band);
        })
        .catch((error) => {
          this.moveStatePromise = null;
          throw error;
        });
    }
    await this.moveStatePromise;
  }

  private async processMarketMove(item: MarketSymbol): Promise<void> {
    const change = item.change24hPercent;
    if (item.dataStatus !== 'LIVE' || change === null || !Number.isFinite(change)) return;

    const nextBand: 'NONE' | 'UP' | 'DOWN' = change >= 10 ? 'UP' : change <= -10 ? 'DOWN' : 'NONE';
    const previousBand = this.moveBands.get(item.symbol) ?? 'NONE';
    if (nextBand === previousBand) return;

    if (nextBand !== 'NONE') {
      const directionText = nextBand === 'UP' ? '上涨' : '下跌';
      const signed = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
      await this.dispatch({
        eventKey: `MARKET_MOVE:${item.symbol}:${nextBand}:${Math.floor(Date.now() / 60000)}`,
        eventType: 'MARKET_MOVE',
        symbol: item.symbol,
        signalUid: null,
        title: `${nextBand === 'UP' ? '🚀' : '📉'} ${item.symbol} 24h ${directionText} ${signed}`,
        body: `当前 ${item.lastPrice ?? '—'} · 24h 变动 ${signed} · 独立行情异动提醒，不代表 LONG_READY/SHORT_READY。`,
        url: `/?symbol=${encodeURIComponent(item.symbol)}`,
        tag: `market-move-${item.symbol}-${nextBand}`,
        data: { change24hPercent: change, band: nextBand },
      });
    }

    await this.repository.setMarketMoveAlertState(item.symbol, nextBand, change);
    this.moveBands.set(item.symbol, nextBand);
  }

'''
if methods not in text:
    if anchor not in text:
        raise SystemExit('notification market move methods target not found')
    text = text.replace(anchor, methods + anchor, 1)
text = text.replace(
    "const priority = ['LONG', 'SHORT', 'ENTRY', 'STOP'].includes(message.eventType) ? 4 : 3;",
    "const priority = ['LONG', 'SHORT', 'ENTRY', 'STOP', 'MARKET_MOVE'].includes(message.eventType) ? 4 : 3;",
    1,
)
p.write_text(text, encoding='utf-8')
print('24h ±10% market move alert patch applied')
