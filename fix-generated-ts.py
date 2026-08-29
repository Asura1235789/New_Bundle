from pathlib import Path

p = Path('apps/api/src/watchlist-repository.ts')
text = p.read_text(encoding='utf-8')
text = text.replace('\\\\d', '\\d')
text = text.replace('\\\\.', '\\.')
text = text.replace('\\\\/', '\\/')
p.write_text(text, encoding='utf-8')

market = Path('apps/api/src/market-service.ts')
market_text = market.read_text(encoding='utf-8')
old = """  if (!/^[A-Z0-9]{3,30}$/.test(symbol)) {
    throw new MarketServiceError(400, 'INVALID_SYMBOL_FORMAT', 'Symbol 只能包含 3-30 位英文字母或数字');
  }
"""
new = r"""  if (!/^[\p{L}\p{N}]{3,30}$/u.test(symbol)) {
    throw new MarketServiceError(400, 'INVALID_SYMBOL_FORMAT', 'Symbol 只能包含 3-30 位字母或数字（支持 Binance 非 ASCII Symbol）');
  }
"""
if old not in market_text and new not in market_text:
    raise SystemExit('normalizeSymbol validation target not found')
if old in market_text:
    market_text = market_text.replace(old, new)
    market.write_text(market_text, encoding='utf-8')

print('Generated TypeScript regex escaping and Unicode symbol support fixed')
