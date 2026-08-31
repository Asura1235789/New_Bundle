from pathlib import Path

p = Path('packages/signal-engine/src/index.ts')
text = p.read_text(encoding='utf-8')

old_score = """  const score = Math.round(scoreReasons.reduce((sum, reason) => sum + reason.score, 0) * 100) / 100;\n  const completionScore = Math.round(completedConditions.length / (completedConditions.length + missingConditions.length) * 100);\n"""
new_score = """  const score = Math.round(scoreReasons.reduce((sum, reason) => sum + reason.score, 0) * 100) / 100;\n  // High-conviction continuation path: do not let one slightly-late confirmation make us miss an already-established trend.\n  // This is intentionally narrow: aligned 1h trend + confirmed 15m structure + 5m timing + good RR + >=1 ATR room + score >=70.\n  // It never bypasses health/extreme-volatility/zone-strength/RR/space gates.\n  const strongTrendContinuation = oneHourBias === direction\n    && confirmed\n    && fiveMinuteTiming\n    && zoneStrengthHealthy\n    && riskReward?.minimumPassed === true\n    && (opposingDistanceAtr ?? 0) >= Math.max(config.opposingZoneTooCloseAtr, 1.0)\n    && score >= 70;\n  const completionScore = Math.round(completedConditions.length / (completedConditions.length + missingConditions.length) * 100);\n"""
if new_score not in text:
    if old_score not in text:
        raise SystemExit('score insertion target not found')
    text = text.replace(old_score, new_score, 1)

old_required = """  const hardGatesPassed = Object.values(hardGates).every(Boolean);\n  const requiredConditionsPassed = zoneStrengthHealthy && confirmed && (volumeRatio ?? 0) >= config.minimumClosedVolumeRatio && !severeTrendConflict && (opposingDistanceAtr ?? 0) >= config.opposingZoneTooCloseAtr;\n  const ready = hardGatesPassed && requiredConditionsPassed;\n"""
new_required = """  const hardGatesPassed = Object.values(hardGates).every(Boolean);\n  // Normal path still requires closed-candle volume. The continuation path may waive only that one lagging gate\n  // when the broader trend/structure/execution/RR/space evidence is already strong.\n  const volumeConfirmedOrContinuation = (volumeRatio ?? 0) >= config.minimumClosedVolumeRatio || strongTrendContinuation;\n  const requiredConditionsPassed = zoneStrengthHealthy && confirmed && volumeConfirmedOrContinuation && !severeTrendConflict && (opposingDistanceAtr ?? 0) >= config.opposingZoneTooCloseAtr;\n  const ready = hardGatesPassed && requiredConditionsPassed;\n"""
if new_required not in text:
    if old_required not in text:
        raise SystemExit('required-conditions target not found')
    text = text.replace(old_required, new_required, 1)

# Deliberately keep fake-breakout, structural invalidation, low-volume, health and volatility blockers intact.
p.write_text(text, encoding='utf-8')
print('Strong trend continuation READY path applied')
