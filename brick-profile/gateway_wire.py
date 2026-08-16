#!/usr/bin/env python3
"""gateway_wire.py — T-UNIVERSE-022 THE CONSUMER (khalid: "the product's face").
The missing wiring: reads brick-profile/out/*.json (identity.json,
a2a-policy.json, model.json — written by brick_profile.py apply) and writes
REAL Hermes gateway config so a brick profile becomes a LIVE brick:

  - ~/.hermes/.env          (DISCORD_BOT_TOKEN, DISCORD_ALLOWED_USERS, A2A_PORT)
  - ~/.hermes/config.yaml   (model + providers.<name> + fallback_providers,
                             a2a_agents, platforms.a2a.extra)

Config is deep-MERGED into any existing config.yaml (never marker-appended —
duplicating a top-level ``platforms:``/``providers:``/``model:`` key would
silently drop the user's existing entries). Original files are backed up.
Fails closed. Never writes secrets to the repo. Dry-run default.
"""
import json, os, re, sys, pathlib, shutil, datetime

try:
    import yaml
except ImportError:
    yaml = None

OUT = pathlib.Path(__file__).parent / "out"
HERMES_DIR = pathlib.Path.home() / ".hermes"
CONFIG = HERMES_DIR / "config.yaml"
ENV = HERMES_DIR / ".env"
BACKUP_SUFFIX = ".bak-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# A2A adapter reads platforms.a2a.extra.{enabled,port,advertised_toolsets}
# (plugins/platforms/a2a/adapter.py) and env A2A_PORT / A2A_PEER_TOKENS.
A2A_PORT_DEFAULT = 9900


def fail(msg):
    print(f"REJECTED: {msg}")
    sys.exit(1)


def load_out(name):
    p = OUT / name
    if not p.exists():
        fail(f"{name} missing — run brick_profile.py apply first")
    with open(p) as f:
        return json.load(f)


def write_env(env_path, pairs):
    """Append/update KEY=VALUE lines in an env file, preserving everything else."""
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    keys = set(pairs)
    kept = [l for l in lines if l.strip() and not l.split("=", 1)[0].strip() in keys]
    kept += [f"{k}={v}" for k, v in pairs.items()]
    env_path.write_text("\n".join(kept) + "\n")
    os.chmod(env_path, 0o600)


def _deep_merge(base, override):
    """Recursive dict merge; override wins — EXCEPT list-valued keys that must
    UNION (preserving existing Hermes settings is mandatory there).

    Union paths (dotted): agent.disabled_toolsets, known_builtin_toolsets.<any
    platform>, fallback_providers. Everything else: override wins (scalars,
    dicts merge deep, lists replace — e.g. platform_toolsets.a2a is the
    enforcement allow-list and MUST be exactly the signed profile's list,
    never widened).
    """
    # exact dotted path, or prefix (e.g. "known_builtin_toolsets." matches any
    # platform sub-key)
    _UNION_LIST_PREFIXES = ("known_builtin_toolsets.",)
    _UNION_LIST_EXACT = ("agent.disabled_toolsets", "fallback_providers")

    def _path(prefix, key):
        return f"{prefix}.{key}" if prefix else key

    def _should_union(p):
        return p in _UNION_LIST_EXACT or any(p.startswith(pre) for pre in _UNION_LIST_PREFIXES)

    def _merge(dst, src, prefix=""):
        for k, v in src.items():
            p = _path(prefix, k)
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _merge(dst[k], v, p)
            elif isinstance(v, list) and isinstance(dst.get(k), list) and _should_union(p):
                # union preserving order and existing entries (dedupe by str)
                merged = []
                seen = set()
                for item in list(dst.get(k)) + v:
                    sig = str(item)
                    if sig not in seen:
                        seen.add(sig)
                        merged.append(item)
                dst[k] = merged
            else:
                dst[k] = v
        return dst

    return _merge(base, override)


def load_yaml(path):
    if yaml is None:
        fail("pyyaml not installed — gateway_wire requires `pip install pyyaml`")
    text = path.read_text() if path.exists() else ""
    try:
        return yaml.safe_load(text) or {} if text.strip() else {}
    except Exception as e:
        fail(f"existing config.yaml unparseable: {str(e)[:80]}")


def write_yaml(path, data):
    if yaml is None:
        fail("pyyaml not installed — gateway_wire requires `pip install pyyaml`")
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    os.chmod(path, 0o600)


def build_wiring(ident, a2a, model):
    """Return (env_pairs, config_override) — the REAL Hermes 0.20.x settings."""
    brick_id = ident.get("brick_id")
    person_id = ident.get("person_id")
    discord_user_id = ident.get("discord_user_id")
    if not brick_id or not person_id:
        fail("identity.json missing brick_id/person_id")
    if not discord_user_id:
        fail("identity.json missing discord_user_id — Discord identity is explicit, "
             "never inferred from person_id")

    primary = (model.get("primary") or "").strip().rstrip("/")
    default_model = (model.get("default_model") or "").strip()
    if not primary or not default_model:
        fail("model.json missing primary/default_model — point model.primary at the "
             "LM Studio /v1 endpoint and set default_model to a loaded model id")

    token = os.environ.get("BRICK_DISCORD_TOKEN", "")
    peer_toolsets = a2a.get("peer_toolsets") or ["web", "vision", "session_search"]
    reject = a2a.get("reject") or ["terminal", "code_execution", "memory", "file", "skill_manage"]

    # Sanity: the allow-list must never include a rejected toolset. If the
    # signed profile contradicts itself, fail closed rather than wire it.
    overlap = set(peer_toolsets) & set(reject)
    if overlap:
        fail(f"a2a-policy.json contradiction: {sorted(overlap)} in both "
             "peer_toolsets and reject")

    # ---- .env: Discord + A2A transport ---- 
    env_pairs = {
        "BRICK_ID": brick_id,
        "PERSON_ID": person_id,
        "DISCORD_USER_ID": discord_user_id,
        "DISCORD_ALLOWED_USERS": discord_user_id,
        "A2A_PORT": str(A2A_PORT_DEFAULT),
    }
    if token:
        env_pairs["DISCORD_BOT_TOKEN"] = token

    # ---- config.yaml: REAL model/provider config (v12 providers schema) ----
    # model: is the RUNTIME SELECTION — the gateway's provider resolution
    # (hermes_cli/runtime_provider.resolve_requested_provider + auth.resolve_provider)
    # reads model.provider / model.default / model.base_url. A bare string
    # (model: <id>) leaves provider unselected and fails at auth time with
    # "No inference provider configured" (the live Discord failure).
    config_override = {
        "model": {
            "provider": "lmstudio",
            "default": default_model,
            "base_url": primary,
        },
        "providers": {
            "lmstudio": {
                "name": "lmstudio",
                "base_url": primary,
                "api_mode": "chat_completions",
                "default_model": default_model,
            }
        },
    }
    # DeepSeek fallback: only declared when its credentials/router wiring
    # actually exists. Without DEEPSEEK_API_KEY (or a router URL), a declared
    # fallback is a lie — auth would fail the same way the primary did. No
    # credential => no fallback entry.
    chain = model.get("chain") or []
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if len(chain) > 1 and deepseek_key:
        config_override["fallback_providers"] = [
            {"provider": "deepseek", "model": "deepseek-v4-flash"}
            for c in chain[1:] if isinstance(c, str)
        ]

    # ---- config.yaml: REAL A2A config (0.20+ adapter reads platforms.a2a.extra) ----
    config_override["a2a_agents"] = {}          # peers added as mesh grows
    config_override["platforms"] = {
        "a2a": {
            "extra": {
                "enabled": True,
                "port": A2A_PORT_DEFAULT,
                "advertised_toolsets": peer_toolsets,  # agent-card claim (informational)
            }
        }
    }
    # REAL ENFORCEMENT: platform_toolsets.<plat> is what the gateway resolves at
    # session build (gateway/run.py _get_platform_tools(platform_key)) to set
    # the session's enabled_toolsets.
    #  - a2a:    the signed peer allow-list — inbound A2A requests get exactly
    #            these toolsets, nothing else. terminal/code_execution/memory/
    #            file/skill_manage (the signed reject list) are structurally
    #            unreachable.
    #  - discord: the SAME signed surface applies to the brick's own channel.
    #            The Hermes default discord toolset is _HERMES_CORE_TOOLS
    #            (~31 tools, ~15K tokens of schemas) — every trivial turn pays
    #            that full cost (the live 17,281-token /context baseline). The
    #            signed profile's reject list already forbids terminal/
    #            code_execution/memory/file/skill_manage, so exposing them on
    #            the owner channel contradicts the signed model. Restricting to
    #            the signed allow-list: (a) enforces the signed model on the
    #            owner channel, (b) slims the fresh-turn prompt ~87% (tool
    #            defs 14,986 -> 1,947; est. total 17,281 -> ~7,989).
    #            Capabilities are NOT removed — they are permission-gated:
    #            web_search/web_extract auto-appear when a web API key exists
    #            (check_fn), and the CLI surface keeps the full core set.
    config_override["platform_toolsets"] = {
        "a2a": peer_toolsets,
        "discord": peer_toolsets,
    }
    # Hermes 0.20 auto-adds toolsets on top of an explicit platform list:
    #  - "bfl" via _RECENTLY_SHIPPED_TOOLSETS (bfl_flux3_* video-gen) —
    #    suppressed per-platform via known_builtin_toolsets.<plat>, so CLI
    #    keeps bfl.
    #  - "kanban" via the non-configurable toolset recovery block (reads no
    #    per-platform config — only agent.disabled_toolsets strips it, and
    #    that is global). kanban is state-mutating (kanban_create/complete/
    #    comment/block), so global-disable is the fail-closed default.
    config_override["known_builtin_toolsets"] = {
        "a2a": ["bfl"],
        "discord": ["bfl"],   # discord is now explicit too — keep bfl out
    }
    disabled = config_override.setdefault("agent", {}).setdefault(
        "disabled_toolsets", [])
    for ts in ("kanban",):
        if ts not in disabled:
            disabled.append(ts)

    return env_pairs, config_override


def wire(dry_run=True, force=False):
    ident = load_out("identity.json")
    a2a = load_out("a2a-policy.json")
    model = load_out("model.json")

    env_pairs, config_override = build_wiring(ident, a2a, model)
    brick_id = ident.get("brick_id")
    person_id = ident.get("person_id")

    if dry_run:
        print(f"[dry] would wire brick '{brick_id}' (person {person_id})")
        print(f"[dry]   .env: DISCORD_BOT_TOKEN={'<set>' if env_pairs.get('DISCORD_BOT_TOKEN') else '<MISSING>'} "
              f"DISCORD_ALLOWED_USERS={env_pairs['DISCORD_ALLOWED_USERS']} A2A_PORT={env_pairs['A2A_PORT']}")
        print(f"[dry]   config.yaml: model={config_override['model']}")
        print(f"[dry]   config.yaml: providers.lmstudio={config_override['providers']['lmstudio']}")
        fbp = config_override.get('fallback_providers')
        print(f"[dry]   config.yaml: fallback_providers={'<set>' if fbp else '<none — no DEEPSEEK_API_KEY>'}")
        print(f"[dry]   config.yaml: a2a_agents + platforms.a2a.extra"
              f"(enabled, advertised_toolsets={config_override['platforms']['a2a']['extra']['advertised_toolsets']})")
        print(f"[dry]   config.yaml: platform_toolsets.a2a={config_override['platform_toolsets']['a2a']} "
              f"(ENFORCED — the inbound session's enabled_toolsets)")
        print(f"[dry]   config.yaml: platform_toolsets.discord={config_override['platform_toolsets']['discord']} "
              f"(ENFORCED — slim signed surface for the brick's channel)")
        print("[dry] nothing written")
        return 0

    # backup originals, then write (config deep-merged, never key-duplicated)
    if CONFIG.exists():
        shutil.copy2(CONFIG, str(CONFIG) + BACKUP_SUFFIX)
    if ENV.exists():
        shutil.copy2(ENV, str(ENV) + BACKUP_SUFFIX)

    existing = load_yaml(CONFIG)
    merged = _deep_merge(existing, config_override)
    write_yaml(CONFIG, merged)
    write_env(ENV, env_pairs)

    print(f"wired brick '{brick_id}' -> {HERMES_DIR} (backups: {BACKUP_SUFFIX})")
    print("receipt:", {"brick_id": brick_id, "person_id": person_id,
                       "model": config_override["model"],
                       "a2a_port": env_pairs["A2A_PORT"],
                       "ts": datetime.datetime.utcnow().isoformat() + "Z"})
    return 0


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    force = "--force" in sys.argv
    sys.exit(wire(dry_run=dry, force=force))
