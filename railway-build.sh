#!/bin/sh
set -eu

for f in runtime-parts/part*.b64; do
  base64 -d "$f"
done | tar -xzf -

mkdir -p .openai
printf '%s\n' '{"project_id":"appgprj_6a913eeb9ab881918392b50db9c4fd10","d1":null,"r2":null}' > .openai/hosting.json

python3 honor-push-hotfix.py

if [ "${FSM_ROLE:-web}" = "api" ]; then
  python3 deploy-patch.py
  python3 sql-proxy-serialize-hotfix.py
  python3 runtime-hotfix.py
  python3 candidate-persistence-throttle-hotfix.py
  python3 market-move-hotfix.py
  python3 suppress-preentry-invalidated-hotfix.py
  python3 trend-continuation-hotfix.py
  python3 fix-generated-ts.py
  npm install --include=dev
  npm run build:api
  test -f apps/api/dist/server.js
else
  npm install --include=dev
  npm run build
fi
