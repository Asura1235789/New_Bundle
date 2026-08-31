from pathlib import Path

p = Path('apps/api/src/notification-service.ts')
text = p.read_text(encoding='utf-8')

old = "    const hasStopEvent = stateChanged && signal.state === 'INVALIDATED';"
new = "    const hasStopEvent = stateChanged && signal.state === 'INVALIDATED' && ['ACTIVE', 'TP1_HIT', 'TP2_HIT'].includes(previous.signalState ?? '');"
if new not in text:
    if old not in text:
        raise SystemExit('pre-entry invalidation throttle target not found')
    text = text.replace(old, new, 1)

old = "    if (stateChanged && signal.state === 'INVALIDATED' && settings.notifyStop) {"
new = "    if (stateChanged && signal.state === 'INVALIDATED' && ['ACTIVE', 'TP1_HIT', 'TP2_HIT'].includes(previous.signalState ?? '') && settings.notifyStop) {"
if new not in text:
    if old not in text:
        raise SystemExit('pre-entry invalidation dispatch target not found')
    text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
print('Pre-entry INVALIDATED push alerts disabled; real post-entry stop alerts preserved')
