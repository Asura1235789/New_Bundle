from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Patch target not found in {path}: {old[:120]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# 1) API config: add an ntfy-compatible Android fallback channel.
config = Path('apps/api/src/config.ts')
replace_once(
    config,
    """  push: {\n    enabled: boolean;\n    vapidPublicKey: string | null;\n    vapidPrivateKey: string | null;\n    vapidSubject: string;\n    ttlSeconds: number;\n  };\n  binance: {\n""",
    """  push: {\n    enabled: boolean;\n    vapidPublicKey: string | null;\n    vapidPrivateKey: string | null;\n    vapidSubject: string;\n    ttlSeconds: number;\n  };\n  ntfy: {\n    enabled: boolean;\n    baseUrl: string | null;\n    topic: string | null;\n  };\n  binance: {\n""",
)
replace_once(
    config,
    """    push: {\n      enabled: Boolean(env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY),\n      vapidPublicKey: env.VAPID_PUBLIC_KEY || null,\n      vapidPrivateKey: env.VAPID_PRIVATE_KEY || null,\n      vapidSubject: env.VAPID_SUBJECT || 'mailto:local@example.invalid',\n      ttlSeconds: integer('PUSH_TTL_SECONDS', env.PUSH_TTL_SECONDS, 120, 10),\n    },\n    binance: {\n""",
    """    push: {\n      enabled: Boolean(env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY),\n      vapidPublicKey: env.VAPID_PUBLIC_KEY || null,\n      vapidPrivateKey: env.VAPID_PRIVATE_KEY || null,\n      vapidSubject: env.VAPID_SUBJECT || 'mailto:local@example.invalid',\n      ttlSeconds: integer('PUSH_TTL_SECONDS', env.PUSH_TTL_SECONDS, 120, 10),\n    },\n    ntfy: {\n      enabled: Boolean(env.NTFY_BASE_URL && env.NTFY_TOPIC),\n      baseUrl: env.NTFY_BASE_URL ? env.NTFY_BASE_URL.replace(/\\/+$/, '') : null,\n      topic: env.NTFY_TOPIC || null,\n    },\n    binance: {\n""",
)

# 2) Notification service: send each push-worthy transition to both Web Push and ntfy.
svc = Path('apps/api/src/notification-service.ts')
replace_once(
    svc,
    """  status(): { enabled: boolean; configured: boolean; publicKey: string | null } {\n    return {\n      enabled: this.config.push.enabled,\n      configured: Boolean(this.config.push.vapidPublicKey && this.config.push.vapidPrivateKey),\n      publicKey: this.config.push.vapidPublicKey,\n    };\n  }\n""",
    """  status(): { enabled: boolean; configured: boolean; publicKey: string | null; ntfyConfigured: boolean } {\n    return {\n      enabled: this.config.push.enabled || this.config.ntfy.enabled,\n      configured: Boolean(this.config.push.vapidPublicKey && this.config.push.vapidPrivateKey),\n      publicKey: this.config.push.vapidPublicKey,\n      ntfyConfigured: this.config.ntfy.enabled,\n    };\n  }\n""",
)
replace_once(
    svc,
    """  private async dispatch(message: NotificationMessage, ignoreSettings = false): Promise<{ sent: number; failed: number; revoked: number }> {\n    if (!this.config.push.enabled || !this.config.push.vapidPublicKey || !this.config.push.vapidPrivateKey) {\n      return { sent: 0, failed: 0, revoked: 0 };\n    }\n    const subscriptions = await this.repository.listPushSubscriptions();\n    const counts = { sent: 0, failed: 0, revoked: 0 };\n    for (const subscription of subscriptions) {\n      await this.sendToSubscription(subscription, message, counts, ignoreSettings);\n    }\n    return counts;\n  }\n\n  private async sendToSubscription(\n""",
    """  private async dispatch(message: NotificationMessage, ignoreSettings = false): Promise<{ sent: number; failed: number; revoked: number }> {\n    const webPushConfigured = Boolean(\n      this.config.push.enabled && this.config.push.vapidPublicKey && this.config.push.vapidPrivateKey,\n    );\n    const counts = { sent: 0, failed: 0, revoked: 0 };\n\n    if (this.config.ntfy.enabled && this.config.ntfy.baseUrl && this.config.ntfy.topic) {\n      try {\n        await this.sendToNtfy(message);\n        counts.sent += 1;\n      } catch (error) {\n        counts.failed += 1;\n        console.error(JSON.stringify({\n          level: 'error',\n          message: 'Honor/ntfy fallback delivery failed',\n          symbol: message.symbol,\n          eventKey: message.eventKey,\n          error: error instanceof Error ? error.message : String(error),\n        }));\n      }\n    }\n\n    if (webPushConfigured) {\n      const subscriptions = await this.repository.listPushSubscriptions();\n      for (const subscription of subscriptions) {\n        await this.sendToSubscription(subscription, message, counts, ignoreSettings);\n      }\n    }\n    return counts;\n  }\n\n  private async sendToNtfy(message: NotificationMessage): Promise<void> {\n    const baseUrl = this.config.ntfy.baseUrl!;\n    const topic = this.config.ntfy.topic!;\n    const click = new URL(message.url, this.config.webOrigin).toString();\n    const priority = ['LONG', 'SHORT', 'ENTRY', 'STOP'].includes(message.eventType) ? 4 : 3;\n    const tags = message.eventType === 'LONG'\n      ? ['chart_with_upwards_trend']\n      : message.eventType === 'SHORT'\n        ? ['chart_with_downwards_trend']\n        : message.eventType === 'TP'\n          ? ['white_check_mark']\n          : message.eventType === 'STOP'\n            ? ['no_entry']\n            : ['bell'];\n    const response = await fetch(baseUrl, {\n      method: 'POST',\n      headers: { 'content-type': 'application/json' },\n      body: JSON.stringify({\n        topic,\n        title: message.title,\n        message: message.body,\n        priority,\n        tags,\n        click,\n      }),\n      signal: AbortSignal.timeout(10_000),\n    });\n    if (!response.ok) {\n      const body = await response.text().catch(() => '');\n      throw new Error(`ntfy HTTP ${response.status}: ${body.slice(0, 300)}`);\n    }\n  }\n\n  private async sendToSubscription(\n""",
)

# 3) Frontend: unsupported browsers still load server status and can test the Honor fallback.
ui = Path('app/notification-center.tsx')
replace_once(
    ui,
    """  subscriptionCount: number;\n}\n""",
    """  subscriptionCount: number;\n  ntfyConfigured?: boolean;\n}\n""",
)
replace_once(
    ui,
    """  const refresh = useCallback(async () => {\n    if (!supported) {\n      setPermission('unsupported');\n      return;\n    }\n    setPermission(Notification.permission);\n    const [nextStatus, nextSettings] = await Promise.all([\n      api<NotificationStatus>('/notifications/status'),\n      api<NotificationSettings>('/notifications/settings'),\n    ]);\n    setStatus(nextStatus);\n    setSettings(nextSettings);\n    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });\n    await navigator.serviceWorker.ready;\n    setSubscribed(Boolean(await registration.pushManager.getSubscription()));\n  }, [supported]);\n""",
    """  const refresh = useCallback(async () => {\n    const [nextStatus, nextSettings] = await Promise.all([\n      api<NotificationStatus>('/notifications/status'),\n      api<NotificationSettings>('/notifications/settings'),\n    ]);\n    setStatus(nextStatus);\n    setSettings(nextSettings);\n    if (!supported) {\n      setPermission('unsupported');\n      setSubscribed(false);\n      return;\n    }\n    setPermission(Notification.permission);\n    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });\n    await navigator.serviceWorker.ready;\n    setSubscribed(Boolean(await registration.pushManager.getSubscription()));\n  }, [supported]);\n""",
)
replace_once(
    ui,
    """    if (!supported) {\n      setMessage('当前浏览器不支持 Web Push。');\n      return;\n    }\n""",
    """    if (!supported) {\n      setMessage(status?.ntfyConfigured\n        ? '荣耀浏览器不支持标准 Web Push；服务器已启用荣耀备用推送通道，请使用 ntfy Android 客户端接收。'\n        : '当前浏览器不支持 Web Push。');\n      return;\n    }\n""",
)
replace_once(
    ui,
    """        <span className={`rounded-lg border px-2 py-1 font-mono text-[10px] ${subscribed ? 'border-emerald-400/25 text-emerald-300' : 'border-white/10 text-[#8993a2]'}`}>\n          {subscribed ? 'PUSH ON' : 'PUSH OFF'}\n        </span>\n""",
    """        <span className={`rounded-lg border px-2 py-1 font-mono text-[10px] ${(subscribed || status?.ntfyConfigured) ? 'border-emerald-400/25 text-emerald-300' : 'border-white/10 text-[#8993a2]'}`}>\n          {subscribed ? 'WEB PUSH ON' : status?.ntfyConfigured ? 'HONOR PUSH ON' : 'PUSH OFF'}\n        </span>\n""",
)
replace_once(
    ui,
    """          {subscribed ? (\n            <button type=\"button\" disabled={busy} onClick={() => void disablePush()} className=\"rounded-lg border border-white/10 px-3 py-2 text-xs disabled:opacity-50\">关闭本设备推送</button>\n          ) : (\n            <button type=\"button\" disabled={busy || !status?.configured} onClick={() => void enablePush()} className=\"rounded-lg bg-cyan-300 px-3 py-2 text-xs font-semibold text-black disabled:opacity-40\">开启通知</button>\n          )}\n          <button type=\"button\" disabled={busy || !subscribed} onClick={() => void sendTest()} className=\"rounded-lg border border-white/10 px-3 py-2 text-xs disabled:opacity-40\">发送测试</button>\n""",
    """          {subscribed ? (\n            <button type=\"button\" disabled={busy} onClick={() => void disablePush()} className=\"rounded-lg border border-white/10 px-3 py-2 text-xs disabled:opacity-50\">关闭本设备推送</button>\n          ) : supported ? (\n            <button type=\"button\" disabled={busy || !status?.configured} onClick={() => void enablePush()} className=\"rounded-lg bg-cyan-300 px-3 py-2 text-xs font-semibold text-black disabled:opacity-40\">开启浏览器通知</button>\n          ) : (\n            <span className=\"rounded-lg border border-emerald-400/20 px-3 py-2 text-xs text-emerald-300\">荣耀备用通道</span>\n          )}\n          <button type=\"button\" disabled={busy || (!subscribed && !status?.ntfyConfigured)} onClick={() => void sendTest()} className=\"rounded-lg border border-white/10 px-3 py-2 text-xs disabled:opacity-40\">发送测试</button>\n""",
)
replace_once(
    ui,
    """      {status && !status.configured && (\n        <p className=\"mt-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100\">VAPID 尚未配置。使用新版 start-local.cmd 首次启动会自动生成本地密钥。</p>\n      )}\n\n      {settings && (\n""",
    """      {status && !status.configured && !status.ntfyConfigured && (\n        <p className=\"mt-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100\">VAPID 尚未配置。使用新版 start-local.cmd 首次启动会自动生成本地密钥。</p>\n      )}\n      {permission === 'unsupported' && status?.ntfyConfigured && (\n        <p className=\"mt-3 rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3 text-xs text-emerald-100\">\n          荣耀兼容推送已启用：LONG/SHORT READY、进入 Entry、TP、止损/失效会同步发送到 Android ntfy 客户端，不依赖荣耀浏览器的 Web Push。\n        </p>\n      )}\n\n      {settings && (\n""",
)
print('Honor/ntfy fallback patch applied')
