#!/bin/sh
set -eu

if [ -z "${API_BASE_URL:-}" ]; then
  echo "API_BASE_URL is not set; keeping the default config.json" >&2
  exit 0
fi

case "$API_BASE_URL" in
  http://*|https://*) ;;
  *) echo "API_BASE_URL must start with http:// or https://" >&2; exit 1 ;;
esac

printf '{ "apiBaseUrl": "%s" }\n' "$API_BASE_URL" > "${HTML_DIR:-/usr/share/nginx/html}/config.json"
