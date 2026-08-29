from pathlib import Path

p = Path('apps/api/src/watchlist-repository.ts')
text = p.read_text(encoding='utf-8')
text = text.replace('\\\\d', '\\d')
text = text.replace('\\\\.', '\\.')
text = text.replace('\\\\/', '\\/')
p.write_text(text, encoding='utf-8')
print('Generated TypeScript regex escaping fixed')
