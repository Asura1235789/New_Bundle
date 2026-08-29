#!/bin/sh
set -eu

if [ "${FSM_ROLE:-web}" = "api" ]; then
  exec env API_HOST=0.0.0.0 API_PORT="${PORT}" npm run start -w @fsm/api
else
  exec env HOST=0.0.0.0 PORT="${PORT}" npm run start
fi
