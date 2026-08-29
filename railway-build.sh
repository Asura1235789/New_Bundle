#!/bin/sh
set -eu

for f in runtime-parts/part*.b64; do
  base64 -d "$f"
done | tar -xzf -

mkdir -p .openai
printf '%s\n' '{"project_id":"appgprj_6a913eeb9ab881918392b50db9c4fd10","d1":null,"r2":null}' > .openai/hosting.json

if [ "${FSM_ROLE:-web}" = "api" ]; then
  python3 deploy-patch.py
  python3 fix-generated-ts.py
  npm install --include=dev
  npm run build:api
  test -f apps/api/dist/server.js
else
  npm install --include=dev
  npm run build
fi
