from pathlib import Path

# 1) Make watchlist additions return immediately while historical candles load in background.
p = Path('apps/api/src/market-service.ts')
text = p.read_text(encoding='utf-8')
old = '''  async addSymbol(input: unknown): Promise<WatchlistEntry> {
    const symbol = normalizeSymbol(input);
    const verified = await this.verifySymbol(symbol);
    const entry = await this.repository.add(verified);
    this.entries.set(symbol, entry);
    await this.activateSymbol(symbol, true);
    this.emitNow();
    return entry;
  }
'''
new = '''  async addSymbol(input: unknown): Promise<WatchlistEntry> {
    const symbol = normalizeSymbol(input);
    const existing = this.entries.get(symbol);
    if (existing?.state === 'ACTIVE') return existing;

    const verified = await this.verifySymbol(symbol);
    const entry = await this.repository.add(verified);
    this.entries.set(symbol, entry);

    let state = this.states.get(symbol);
    if (!state) {
      state = blankState(symbol);
      this.states.set(symbol, state);
    }
    state.repairing = true;
    state.dataStatus = 'RECOVERING';
    state.staleReason = '正在后台从 Binance REST 补齐历史 K 线';
    this.emitNow();

    void this.activateSymbol(symbol, true)
      .then(() => this.emitNow())
      .catch((error: unknown) => {
        const current = this.states.get(symbol);
        if (current) {
          current.repairing = false;
          current.dataStatus = 'DATA STALE';
          current.staleReason = `历史数据初始化失败：${error instanceof Error ? error.message : String(error)}`;
        }
        log('error', 'Symbol activation failed', {
          symbol,
          error: error instanceof Error ? error.message : String(error),
        });
        this.emitNow();
      });

    return entry;
  }
'''
if new in text:
    print('Runtime hotfix already applied: watchlist add')
elif old in text:
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('Runtime hotfix applied: watchlist add now returns immediately')
else:
    raise SystemExit('Runtime hotfix target not found in market-service.ts')

# 2) Do not hit PostgreSQL notification settings for every CANDIDATE signal-id change.
#    Only query settings when there is an actual push-worthy transition.
p = Path('apps/api/src/notification-service.ts')
text = p.read_text(encoding='utf-8')
old = '''    const settings = await this.repository.getNotificationSettings();
    const readyDirection = signal.decision === 'LONG_READY' ? 'LONG' : signal.decision === 'SHORT_READY' ? 'SHORT' : null;
    if ((isNewSignal || stateChanged || decisionChanged) && signal.state === 'READY' && readyDirection) {
'''
new = '''    const readyDirection = signal.decision === 'LONG_READY' ? 'LONG' : signal.decision === 'SHORT_READY' ? 'SHORT' : null;
    const hasReadyEvent = (isNewSignal || stateChanged || decisionChanged) && signal.state === 'READY' && Boolean(readyDirection);
    const hasEntryEvent = stateChanged && signal.state === 'ACTIVE';
    const hasTpEvent = stateChanged && ['TP1_HIT', 'TP2_HIT', 'TP3_HIT'].includes(signal.state);
    const hasStopEvent = stateChanged && signal.state === 'INVALIDATED';
    if (!hasReadyEvent && !hasEntryEvent && !hasTpEvent && !hasStopEvent) return;

    const settings = await this.repository.getNotificationSettings();
    if (hasReadyEvent && readyDirection) {
'''
if new in text:
    print('Runtime hotfix already applied: notification transition throttle')
elif old in text:
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('Runtime hotfix applied: notification DB reads limited to push-worthy transitions')
else:
    raise SystemExit('Runtime hotfix target not found in notification-service.ts')
