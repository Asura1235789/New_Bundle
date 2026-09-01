from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Patch target not found in {path}')
    target.write_text(text.replace(old, new), encoding='utf-8')


replace(
    'packages/signal-engine/src/index.ts',
    '''    const previous = this.signals.get(signal.signalId);
    if (previous && ['INVALIDATED', 'EXPIRED', 'TP3_HIT'].includes(previous.state)) return previous;
    let next: SignalSnapshot = previous ? {
      ...signal,
      createdAt: previous.createdAt,
      state: LIVE_TRADE_STATES.has(previous.state) ? previous.state : signal.state,
      enteredAt: previous.enteredAt,
      entryPrice: previous.entryPrice,
    } : signal;
    const hit = (target: Target | null) => target !== null && (next.bias === 'LONG' ? price >= target.price : price <= target.price);
    const invalidationCrossed = next.invalidation !== null
      && ((next.bias === 'LONG' && price <= next.invalidation) || (next.bias === 'SHORT' && price >= next.invalidation));
    const wasLiveTrade = previous ? LIVE_TRADE_STATES.has(previous.state) : false;
''',
    '''    const previous = this.signals.get(signal.signalId);
    if (previous && ['INVALIDATED', 'EXPIRED', 'TP3_HIT'].includes(previous.state)) return previous;
    const wasLiveTrade = previous ? LIVE_TRADE_STATES.has(previous.state) : false;
    // Once a trade is active its direction, entry plan, stop and targets are immutable.
    // Re-evaluation may discover a new market setup, but it must not silently rewrite
    // the risk contract of a position that the user is already tracking.
    let next: SignalSnapshot = previous
      ? wasLiveTrade
        ? structuredClone(previous)
        : {
            ...signal,
            createdAt: previous.createdAt,
            enteredAt: previous.enteredAt,
            entryPrice: previous.entryPrice,
          }
      : signal;
    const hit = (target: Target | null) => target !== null && (next.bias === 'LONG' ? price >= target.price : price <= target.price);
    const invalidationCrossed = next.invalidation !== null
      && ((next.bias === 'LONG' && price <= next.invalidation) || (next.bias === 'SHORT' && price >= next.invalidation));
''',
)

replace(
    'packages/signal-engine/src/index.ts',
    '''  deleteSymbol(symbol: string): void {
''',
    '''  activeForSymbol(symbol: string): SignalSnapshot | null {
    const active = [...this.signals.values()]
      .filter((signal) => signal.symbol === symbol && LIVE_TRADE_STATES.has(signal.state))
      .sort((left, right) => (left.enteredAt ?? left.createdAt) - (right.enteredAt ?? right.createdAt))[0];
    return active ? structuredClone(active) : null;
  }

  deleteSymbol(symbol: string): void {
''',
)

replace(
    'apps/api/src/market-service.ts',
    '''    const previous = state.signal;
    const evaluated = evaluateSignal({
      symbol: state.symbol,
      price: Number(state.lastPrice),
      bestBid: state.bestBid === null ? null : Number(state.bestBid),
      bestAsk: state.bestAsk === null ? null : Number(state.bestAsk),
      candles: Object.fromEntries(INTERVALS.map((interval) => [interval, this.candles.get(`${state.symbol}:${interval}`)?.closed ?? []])),
      indicators: state.indicators,
      structure: state.structure,
      health,
      evaluatedAt: now,
    });
''',
    '''    const previous = state.signal;
    const activeTrade = this.signalLifecycle.activeForSymbol(state.symbol);
    // A live trade has priority over new candidates for the same symbol. This keeps
    // the original signal visible and advancing even after a new 15m candle creates
    // a different candidate signalId.
    const evaluated = activeTrade ?? evaluateSignal({
      symbol: state.symbol,
      price: Number(state.lastPrice),
      bestBid: state.bestBid === null ? null : Number(state.bestBid),
      bestAsk: state.bestAsk === null ? null : Number(state.bestAsk),
      candles: Object.fromEntries(INTERVALS.map((interval) => [interval, this.candles.get(`${state.symbol}:${interval}`)?.closed ?? []])),
      indicators: state.indicators,
      structure: state.structure,
      health,
      evaluatedAt: now,
    });
''',
)

replace(
    'apps/api/src/market-service.ts',
    '''      void this.repository.saveSignal(state.signal).catch((error: unknown) => {
        log('error', 'Signal persistence failed', { symbol: state.symbol, signalId: state.signal?.signalId, error: error instanceof Error ? error.message : String(error) });
      });
    }
  }

  private publicStreams''',
    '''      void this.repository.saveSignal(state.signal).catch((error: unknown) => {
        log('error', 'Signal persistence failed', { symbol: state.symbol, signalId: state.signal?.signalId, error: error instanceof Error ? error.message : String(error) });
      });
    }
    if (lifecycleChanged && ['ACTIVE', 'TP1_HIT', 'TP2_HIT', 'TP3_HIT', 'INVALIDATED'].includes(state.signal.state)) {
      // Lifecycle notifications must not wait for the throttled UI broadcast. A fast
      // follow-up market event may already replace a terminal signal with a candidate.
      this.emitNow();
    }
  }

  private publicStreams''',
)

replace(
    'apps/api/src/notification-service.ts',
    '''  private initialized = false;
''',
    '''  private initialized = false;
  private processing: Promise<void> = Promise.resolve();
''',
)

replace(
    'apps/api/src/notification-service.ts',
    '''    this.unsubscribe = this.market.subscribe((snapshot) => {
      void this.handleSnapshot(snapshot).catch((error: unknown) => {
        console.error(JSON.stringify({
          level: 'error', message: 'Notification snapshot processing failed',
          error: error instanceof Error ? error.message : String(error),
        }));
      });
    });
''',
    '''    this.unsubscribe = this.market.subscribe((snapshot) => {
      // Preserve lifecycle event order when immediate transition snapshots and the
      // regular UI broadcast arrive close together.
      this.processing = this.processing.then(() => this.handleSnapshot(snapshot)).catch((error: unknown) => {
        console.error(JSON.stringify({
          level: 'error', message: 'Notification snapshot processing failed',
          error: error instanceof Error ? error.message : String(error),
        }));
      });
    });
''',
)

replace(
    'packages/backtest-engine/src/index.ts',
    '''}

export function datasetFingerprint(dataset: HistoricalDataset): string {
''',
    '''}

export function validateBacktestExecutionConfig(config: BacktestExecutionConfig): void {
  if (config.fillModel !== 'PREFERRED_OR_CONSERVATIVE_EDGE') {
    throw new BacktestValidationError('INVALID_FILL_MODEL', '不支持的回测成交模型');
  }
  if (!['STOP_FIRST', 'TARGET_FIRST', 'MARK_AMBIGUOUS'].includes(config.sameBarConflictPolicy)) {
    throw new BacktestValidationError('INVALID_CONFLICT_POLICY', '不支持的同 K 线冲突策略');
  }
  if (config.exitModel !== 'FULL_EXIT_TP1') {
    throw new BacktestValidationError('INVALID_EXIT_MODEL', '不支持的回测退出模型');
  }
  if (!['STOP_IF_TOUCHED_IGNORE_TARGETS', 'MARK_AMBIGUOUS'].includes(config.entryBarPolicy)) {
    throw new BacktestValidationError('INVALID_ENTRY_BAR_POLICY', '不支持的入场 K 线策略');
  }
  for (const [name, value] of [['makerFee', config.makerFee], ['takerFee', config.takerFee]] as const) {
    if (!Number.isFinite(value) || value < 0 || value > 0.01) {
      throw new BacktestValidationError('INVALID_EXECUTION_FEE', `${name} 必须在 0 到 0.01 之间`);
    }
  }
  if (!Number.isFinite(config.slippageBps) || config.slippageBps < 0 || config.slippageBps > 500) {
    throw new BacktestValidationError('INVALID_SLIPPAGE', 'slippageBps 必须在 0 到 500 之间');
  }
}

export function datasetFingerprint(dataset: HistoricalDataset): string {
''',
)

replace(
    'packages/backtest-engine/src/index.ts',
    '''  const config: BacktestExecutionConfig = { ...DEFAULT_EXECUTION_CONFIG, ...request.executionConfig, fundingIncluded: false };
  const evaluator = options.evaluator ?? defaultEvaluate;
''',
    '''  const config: BacktestExecutionConfig = { ...DEFAULT_EXECUTION_CONFIG, ...request.executionConfig, fundingIncluded: false };
  validateBacktestExecutionConfig(config);
  const evaluator = options.evaluator ?? defaultEvaluate;
''',
)

replace(
    'packages/backtest-engine/src/index.ts',
    '''    const signal = evaluator({ symbol: dataset.symbol, now, price, visibleCandles: visibleForEvaluation });
    const ready = signal.signalId && (signal.decision === 'LONG_READY' || signal.decision === 'SHORT_READY');
    if (ready && !readySignalIds.has(signal.signalId!) && !completedIds.has(signal.signalId!)) {
''',
    '''    const signal = evaluator({ symbol: dataset.symbol, now, price, visibleCandles: visibleForEvaluation });
    const trackingExistingTrade = active.size > 0 || targetTracking.size > 0;
    const ready = !trackingExistingTrade && signal.signalId && (signal.decision === 'LONG_READY' || signal.decision === 'SHORT_READY');
    for (const pendingSignalId of [...pending.keys()]) {
      if (ready && pendingSignalId === signal.signalId) continue;
      pending.delete(pendingSignalId);
      noFill += 1;
    }
    if (ready && !readySignalIds.has(signal.signalId!) && !completedIds.has(signal.signalId!)) {
''',
)

signal_test = r'''import assert from 'node:assert/strict';
import test from 'node:test';
import { SignalLifecycleRegistry, type SignalSnapshot } from '../src/index.ts';

function readySignal(signalId = 'sig_original'): SignalSnapshot {
  return {
    symbol: 'BTCUSDT', decision: 'LONG_READY', state: 'READY', bias: 'LONG', setupType: 'SUPPORT_REJECTION',
    score: 80, completionScore: 100, scoreReasons: [], completedConditions: [], missingConditions: [],
    hardGates: {
      dataHealthy: true, historyReady: true, supportResistanceHistoryReady: true, clockHealthy: true,
      subscriptionsHealthy: true, notExtremeVolatility: true, closedCandleConfirmation: true,
      minimumRiskReward: true, zoneStrengthHealthy: true,
    },
    volatility: 'NORMAL',
    timeframeContext: { oneHourBias: 'LONG', fifteenMinuteSetup: 'SUPPORT_REJECTION', fiveMinuteTiming: 'CONFIRMED' },
    entryZone: { lower: 94, upper: 96, preferredEntry: 95, reason: 'test' },
    invalidation: 90,
    stop: { price: 90, reason: 'test', distancePercent: 5, distanceATR: 1 },
    targets: { tp1: { price: 105, expectedRR: 2, reason: 'test' }, tp2: null, tp3: null },
    riskReward: { risk: 5, tp1: 2, tp2: null, tp3: null, minimumPassed: true, idealTp2Passed: false },
    signalId, createdAt: 0, confirmedAt: 0, expiresAt: 3_600_000, enteredAt: null, entryPrice: null,
  };
}

test('active trade keeps its original stop and targets after strategy re-evaluation', () => {
  const registry = new SignalLifecycleRegistry();
  const original = readySignal();
  assert.equal(registry.upsert(original, 95, 1).state, 'ACTIVE');
  const recalculated: SignalSnapshot = {
    ...original, decision: 'WAIT', state: 'CANDIDATE', invalidation: 92,
    stop: { ...original.stop!, price: 92 },
    targets: { tp1: { price: 103, expectedRR: 2, reason: 'changed' }, tp2: null, tp3: null },
  };
  const stillActive = registry.upsert(recalculated, 91.5, 2);
  assert.equal(stillActive.state, 'ACTIVE');
  assert.equal(stillActive.stop?.price, 90);
  assert.equal(stillActive.targets.tp1?.price, 105);
  const stopped = registry.upsert(recalculated, 89.9, 3);
  assert.equal(stopped.state, 'INVALIDATED');
  assert.equal(stopped.stop?.price, 90);
});

test('active trade remains discoverable when a new candidate has a different signalId', () => {
  const registry = new SignalLifecycleRegistry();
  registry.upsert(readySignal('sig_old'), 95, 1);
  registry.upsert({ ...readySignal('sig_new'), state: 'CANDIDATE', decision: 'WAIT' }, 100, 2);
  const active = registry.activeForSymbol('BTCUSDT');
  assert.equal(active?.signalId, 'sig_old');
  assert.equal(active?.state, 'ACTIVE');
});
'''

backtest_test = r'''import assert from 'node:assert/strict';
import test from 'node:test';
import type { Candle, CandleInterval } from '@fsm/shared';
import type { SignalSnapshot } from '@fsm/signal-engine';
import {
  BacktestValidationError,
  DEFAULT_EXECUTION_CONFIG,
  runBacktest,
  validateBacktestExecutionConfig,
  type HistoricalDataset,
} from '../src/index.ts';

function candle(interval: CandleInterval, openTime: number, low = 99, high = 101): Candle {
  const step = { '1m': 60_000, '5m': 300_000, '15m': 900_000, '1h': 3_600_000 }[interval];
  return {
    symbol: 'BTCUSDT', interval, openTime, closeTime: openTime + step - 1,
    open: '100', high: String(high), low: String(low), close: '100',
    baseVolume: '1', quoteVolume: '100', tradeCount: 1, isClosed: true,
  };
}

function readySignal(now: number): SignalSnapshot {
  return {
    symbol: 'BTCUSDT', decision: 'LONG_READY', state: 'READY', bias: 'LONG', setupType: 'SUPPORT_REJECTION',
    score: 80, completionScore: 100, scoreReasons: [], completedConditions: [], missingConditions: [],
    hardGates: {
      dataHealthy: true, historyReady: true, supportResistanceHistoryReady: true, clockHealthy: true,
      subscriptionsHealthy: true, notExtremeVolatility: true, closedCandleConfirmation: true,
      minimumRiskReward: true, zoneStrengthHealthy: true,
    },
    volatility: 'NORMAL',
    timeframeContext: { oneHourBias: 'LONG', fifteenMinuteSetup: 'SUPPORT_REJECTION', fiveMinuteTiming: 'CONFIRMED' },
    entryZone: { lower: 89, upper: 91, preferredEntry: 90, reason: 'test' },
    invalidation: 80, stop: { price: 80, reason: 'test', distancePercent: 10, distanceATR: 1 },
    targets: { tp1: { price: 110, expectedRR: 2, reason: 'test' }, tp2: null, tp3: null },
    riskReward: { risk: 10, tp1: 2, tp2: null, tp3: null, minimumPassed: true, idealTp2Passed: false },
    signalId: 'sig_pending', createdAt: now, confirmedAt: now, expiresAt: now + 3_600_000,
    enteredAt: null, entryPrice: null,
  };
}

test('accepts the default execution assumptions', () => {
  assert.doesNotThrow(() => validateBacktestExecutionConfig(DEFAULT_EXECUTION_CONFIG));
});

test('rejects negative fees that would inflate net returns', () => {
  assert.throws(
    () => validateBacktestExecutionConfig({ ...DEFAULT_EXECUTION_CONFIG, takerFee: -0.001 }),
    (error: unknown) => error instanceof BacktestValidationError && error.code === 'INVALID_EXECUTION_FEE',
  );
});

test('rejects negative or excessive slippage', () => {
  assert.throws(
    () => validateBacktestExecutionConfig({ ...DEFAULT_EXECUTION_CONFIG, slippageBps: -1 }),
    (error: unknown) => error instanceof BacktestValidationError && error.code === 'INVALID_SLIPPAGE',
  );
  assert.throws(
    () => validateBacktestExecutionConfig({ ...DEFAULT_EXECUTION_CONFIG, slippageBps: 501 }),
    (error: unknown) => error instanceof BacktestValidationError && error.code === 'INVALID_SLIPPAGE',
  );
});

test('cancels a pending entry when the live evaluator no longer returns READY', () => {
  const dataset: HistoricalDataset = {
    symbol: 'BTCUSDT', requestedStartTime: 0, requestedEndTime: 179_999, warmupStartTime: 0,
    source: 'Binance 官方 USDⓈ-M Futures REST',
    candles: {
      '1m': [candle('1m', 0), candle('1m', 60_000), candle('1m', 120_000, 89, 101)],
      '5m': [candle('5m', 0)], '15m': [candle('15m', 0)], '1h': [candle('1h', 0)],
    },
  };
  const result = runBacktest(dataset, {
    symbol: 'BTCUSDT', startTime: 0, endTime: 179_999,
  }, {
    evaluator: ({ now }) => now === 59_999
      ? readySignal(now)
      : { ...readySignal(59_999), decision: 'WAIT', state: 'CANDIDATE' },
  });
  assert.equal(result.trades.length, 0);
  assert.equal(result.metrics.noFill, 1);
});
'''

signal_test_path = Path('packages/signal-engine/test/lifecycle.test.ts')
signal_test_path.parent.mkdir(parents=True, exist_ok=True)
signal_test_path.write_text(signal_test, encoding='utf-8')

backtest_test_path = Path('packages/backtest-engine/test/execution-config.test.ts')
backtest_test_path.parent.mkdir(parents=True, exist_ok=True)
backtest_test_path.write_text(backtest_test, encoding='utf-8')

print('Signal lifecycle integrity patch applied')
