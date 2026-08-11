#!/bin/bash
# BAWES fleet repo — guardrail scan (run in CI + locally)
# 1) secrets  2) no .env  3) no raw data  4) schema + cross-file validation
set -e

echo "=== 1. Secret patterns (public repo!) ==="
if git grep -nE "(BEGIN RSA|BEGIN OPENSSH|ghp_|gho_|ghs_|ntn_[A-Za-z0-9]{20}|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|xox[baprs]-|secret_[A-Za-z0-9]{20}|password[[:space:]]*=[[:space:]]*['\"][^'\"]{6,})" -- . ':!*.md' ':!.gitignore' ':!scripts' 2>/dev/null; then
  echo "FAIL: secret pattern found. This repo is PUBLIC — remove it."
  exit 1
fi

echo "=== 2. No .env tracked ==="
if git ls-files | grep -E "(^|/)\.env($|\.)"; then
  echo "FAIL: .env tracked. Never commit env files."
  exit 1
fi

echo "=== 3. No raw data dumps ==="
if git ls-files | grep -E "\.(csv|sql|jsonl)(\.gz)?$"; then
  echo "FAIL: raw data files blocked — summaries only."
  exit 1
fi

echo "=== 4. Schema + cross-file validation ==="
python3 scripts/validate_schemas.py

echo "✅ clean: no secrets, no env, no raw data, all content valid against schemas"
