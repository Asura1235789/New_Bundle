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

# 3) Reduce mobile live-view traffic. 150 ms was unnecessarily aggressive for a phone UI.
p = Path('apps/api/src/config.ts')
text = p.read_text(encoding='utf-8')
old = "uiBroadcastIntervalMs: integer('UI_BROADCAST_INTERVAL_MS', env.UI_BROADCAST_INTERVAL_MS, 150, 100),"
new = "uiBroadcastIntervalMs: integer('UI_BROADCAST_INTERVAL_MS', env.UI_BROADCAST_INTERVAL_MS, 1000, 100),"
if new in text:
    print('Runtime hotfix already applied: UI broadcast interval')
elif old in text:
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('Runtime hotfix applied: UI broadcast interval reduced to 1 Hz')
else:
    raise SystemExit('Runtime hotfix target not found in config.ts')

# 4) Respect SSE backpressure. Slow/backgrounded mobile browsers must not make Node buffer
#    an unbounded number of full market snapshots in memory.
p = Path('apps/api/src/app.ts')
text = p.read_text(encoding='utf-8')
old = '''    if (request.method === 'GET' && url.pathname === '/events') {
      response.writeHead(200, {
        ...corsHeaders(request, config),
        'content-type': 'text/event-stream; charset=utf-8',
        connection: 'keep-alive',
        'x-accel-buffering': 'no',
      });
      response.write(': connected\\n\\n');
      const unsubscribe = market.subscribe((snapshot) => {
        response.write(`data: ${JSON.stringify(snapshot)}\\n\\n`);
      });
      const heartbeat = setInterval(() => response.write(': heartbeat\\n\\n'), 15_000);
      request.on('close', () => {
        clearInterval(heartbeat);
        unsubscribe();
      });
      return;
    }
'''
new = '''    if (request.method === 'GET' && url.pathname === '/events') {
      response.writeHead(200, {
        ...corsHeaders(request, config),
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache',
        connection: 'keep-alive',
        'x-accel-buffering': 'no',
      });
      response.write(': connected\\n\\n');

      let blocked = false;
      let pendingSnapshot: unknown | null = null;
      let closed = false;

      const writeSnapshot = (snapshot: unknown) => {
        if (closed) return;
        const accepted = response.write(`data: ${JSON.stringify(snapshot)}\\n\\n`);
        if (!accepted) blocked = true;
      };

      const unsubscribe = market.subscribe((snapshot) => {
        if (blocked) {
          pendingSnapshot = snapshot;
          return;
        }
        writeSnapshot(snapshot);
      });

      response.on('drain', () => {
        if (closed) return;
        blocked = false;
        const pending = pendingSnapshot;
        pendingSnapshot = null;
        if (pending !== null) writeSnapshot(pending);
      });

      const heartbeat = setInterval(() => {
        if (closed || blocked) return;
        if (!response.write(': heartbeat\\n\\n')) blocked = true;
      }, 15_000);

      const cleanup = () => {
        if (closed) return;
        closed = true;
        pendingSnapshot = null;
        clearInterval(heartbeat);
        unsubscribe();
      };
      request.on('close', cleanup);
      response.on('close', cleanup);
      return;
    }
'''
if new in text:
    print('Runtime hotfix already applied: SSE backpressure')
elif old in text:
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('Runtime hotfix applied: SSE backpressure drops stale snapshots instead of buffering')
else:
    raise SystemExit('Runtime hotfix target not found in app.ts')
