#!/bin/sh
set -eu

missing_vars=""

for var_name in DISCORD_BOT_TOKEN DISCORD_CHANNEL_ID DISCORD_GUILD_ID; do
    eval "var_value=\${$var_name:-}"
    if [ -z "$var_value" ]; then
        missing_vars="$missing_vars $var_name"
    fi
done

if [ -n "$missing_vars" ]; then
    echo "Discord bot is optional; skipping startup because required env vars are missing:$missing_vars"
    exit 0
fi

exec python -m trader_bot.main
