from pathlib import Path

p = Path('apps/api/src/market-service.ts')
text = p.read_text(encoding='utf-8')

old_field = "  private readonly signalLifecycle = new SignalLifecycleRegistry();\n  private readonly clock: BinanceClock;\n"
new_field = "  private readonly signalLifecycle = new SignalLifecycleRegistry();\n  private readonly lastCandidatePersistAt = new Map<string, number>();\n  private readonly clock: BinanceClock;\n"

if new_field not in text:
    if old_field not in text:
        raise SystemExit('Candidate persistence field target not found')
    text = text.replace(old_field, new_field, 1)

old_logic = '''    state.signal = this.signalLifecycle.upsert(evaluated, Number(state.lastPrice), now);
    if (state.signal.signalId && this.repository.saveSignal
      && (previous?.signalId !== state.signal.signalId || previous.state !== state.signal.state)) {
      void this.repository.saveSignal(state.signal).catch((error: unknown) => {
        log('error', 'Signal persistence failed', { symbol: state.symbol, signalId: state.signal?.signalId, error: error instanceof Error ? error.message : String(error) });
      });
    }
'''
new_logic = '''    state.signal = this.signalLifecycle.upsert(evaluated, Number(state.lastPrice), now);
    const lifecycleChanged = previous?.signalId !== state.signal.signalId || previous?.state !== state.signal.state;
    const isCandidate = state.signal.state === 'CANDIDATE';
    const lastCandidatePersistAt = this.lastCandidatePersistAt.get(state.symbol) ?? 0;
    const candidatePersistDue = isCandidate && now - lastCandidatePersistAt >= 60_000;
    const shouldPersist = isCandidate ? candidatePersistDue : lifecycleChanged;

    if (state.signal.signalId && this.repository.saveSignal && shouldPersist) {
      if (isCandidate) this.lastCandidatePersistAt.set(state.symbol, now);
      void this.repository.saveSignal(state.signal).catch((error: unknown) => {
        log('error', 'Signal persistence failed', { symbol: state.symbol, signalId: state.signal?.signalId, error: error instanceof Error ? error.message : String(error) });
      });
    }
'''

if new_logic in text:
    print('Candidate signal persistence throttle already applied')
elif old_logic in text:
    text = text.replace(old_logic, new_logic, 1)
else:
    raise SystemExit('Candidate persistence logic target not found')

p.write_text(text, encoding='utf-8')
print('Candidate signal persistence throttled to at most once per symbol per minute; lifecycle transitions remain immediate')
