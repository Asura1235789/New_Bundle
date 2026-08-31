from pathlib import Path

# Keep rolling 24h percentage move in market snapshots for display/analysis,
# but DO NOT create standalone MARKET_MOVE push notifications.
# Trade-signal notifications (LONG_READY / SHORT_READY / ENTRY / TP / STOP)
# are intentionally left untouched.
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
if new in text:
    pass
elif old in text:
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
else:
    raise SystemExit('24h snapshot patch target not found')

print('24h market move percentage retained; standalone MARKET_MOVE push alerts disabled')
