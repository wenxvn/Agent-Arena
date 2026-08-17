#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_root/.env"

if [[ ! -f "$env_file" ]]; then
  echo "Missing .env. Copy .env.example and set the API key."
  exit 1
fi

set -a
source "$env_file"
set +a

api_key="${OPENAI_API_KEY:-${DASHSCOPE_API_KEY:-}}"

if [[ -z "$api_key" || -z "${OPENAI_BASE_URL:-}" || -z "${OPENAI_MODEL:-}" ]]; then
  echo "OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL must be set."
  exit 1
fi

response="$(curl --silent --show-error --fail-with-body \
  --request POST "$OPENAI_BASE_URL/chat/completions" \
  --header "Authorization: Bearer $api_key" \
  --header "Content-Type: application/json" \
  --data "{\"model\":\"$OPENAI_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with: Agent Arena model configuration verified.\"}],\"temperature\":0,\"max_tokens\":32}")"

if command -v jq >/dev/null 2>&1; then
  jq --raw-output '"Model: \(.model)\nResponse: \(.choices[0].message.content)"' <<<"$response"
else
  echo "Model request succeeded. Install jq to print the response summary."
fi
