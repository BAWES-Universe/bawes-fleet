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
import hashlib, json, os, re, sys, pathlib, shutil, datetime

try:
    import yaml
except ImportError:
    yaml = None

OUT = pathlib.Path(__file__).parent / "out"
HERMES_DIR = pathlib.Path.home() / ".hermes"
CONFIG = HERMES_DIR / "config.yaml"
ENV = HERMES_DIR / ".env"
BACKUP_SUFFIX = ".bak-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# Rollback manifest: recorded on the FIRST brokerized apply so that rollback
# restores the exact pre-broker runtime state (config.yaml + .env), never an
# unrelated older backup. install_seam.py --rollback consumes it.
ROLLBACK_MANIFEST = "brick-rollback-state.json"

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
    # REAL ENFORCEMENT: platform_toolsets.a2a is what the gateway resolves at
    # session build (gateway/run.py _get_platform_tools(platform_key)) to set
    # the inbound session's enabled_toolsets. Everything NOT in this list —
    # terminal, code_execution, memory, file, skill_manage, ... — is
    # unreachable by an inbound A2A request, because the session is built
    # with exactly these toolsets and nothing else.
    config_override["platform_toolsets"] = {
        "a2a": peer_toolsets,
    }
    # BROKER SURFACE (Brock latency fix, brick/brock-latency-broker-v3):
    # The owner's discord session exposes ONLY the small progressive-disclosure
    # broker (brick_capability_search/describe/invoke) plus tiny eager tools
    # (clarify, todo). The broker's catalog — the full baseline owner surface —
    # is generated at runtime from catalog_toolsets.json (written below), so
    # every capability stays reachable behind the broker without paying its
    # schema cost on every turn. A2A is untouched: peer_toolsets stays the
    # signed {web, vision, session_search}.
    config_override["platform_toolsets"]["discord"] = [
        "brick_broker", "clarify", "todo",
    ]
    # The broker's own plugin tools are plugin-registered (deferrable) — the
    # native tool_search bridge would otherwise strip them and replace with
    # tool_search/tool_describe/tool_call, defeating the broker. Tool search
    # must stay OFF so the three broker tools are the model-facing surface.
    config_override["tools"] = {
        "tool_search": {"enabled": "off"},
    }
    # Catalog source for the broker: the FULL baseline owner surface the
    # gateway would have resolved for discord WITHOUT the broker override.
    # Written as JSON next to the plugin; the broker reads it at runtime and
    # regenerates real schemas via get_tool_definitions() (check_fn-gated).
    broker_catalog_toolsets = _baseline_discord_toolsets()
    # Hermes 0.20 auto-adds toolsets on top of an explicit platform list:
    #  - "bfl" via _RECENTLY_SHIPPED_TOOLSETS (bfl_flux3_* video-gen) —
    #    suppressed A2A-specifically via known_builtin_toolsets.a2a, so
    #    Discord/CLI keep bfl.
    #  - "kanban" via the non-configurable toolset recovery block (reads no
    #    per-platform config — only agent.disabled_toolsets strips it, and
    #    that is global). kanban is state-mutating (kanban_create/complete/
    #    comment/block), so global-disable is the fail-closed default.
    config_override["known_builtin_toolsets"] = {
        "a2a": ["bfl"],
    }
    disabled = config_override.setdefault("agent", {}).setdefault(
        "disabled_toolsets", [])
    for ts in ("kanban",):
        if ts not in disabled:
            disabled.append(ts)

    return env_pairs, config_override


def _catalog_target():
    """Path of the broker catalog file (next to the plugin, in-repo)."""
    return pathlib.Path(__file__).parent / "brick_broker" / "catalog_toolsets.json"


def _effective_disabled(existing):
    """Global agent.disabled_toolsets + the kanban the wiring ALWAYS adds."""
    disabled = set(existing.get("agent", {}).get("disabled_toolsets") or [])
    disabled.add("kanban")
    return {str(d) for d in disabled}


def _config_is_brokerized(existing):
    """True when the current config already routes discord through the broker."""
    pt = (existing.get("platform_toolsets") or {}).get("discord") or []
    return "brick_broker" in [str(x) for x in pt]


def _read_captured_catalog():
    """Load + validate the previously captured catalog file.

    Returns (toolsets_list, captured_disabled_set) or fails closed.
    """
    target = _catalog_target()
    if not target.exists():
        fail(f"config is brokerized but {target.name} is MISSING — the underlying "
             "owner surface cannot be re-derived from the broker surface. Restore the "
             "catalog file or remove the broker surface, then re-apply.")
    try:
        data = json.loads(target.read_text())
    except Exception as e:
        fail(f"catalog file unreadable ({e}) — restore it or remove the broker "
             "surface and re-apply.")
    toolsets = data.get("toolsets")
    if not isinstance(toolsets, list) or not toolsets:
        fail(f"catalog file {target.name} is empty/corrupt — restore it or remove "
             "the broker surface and re-apply.")
    captured_disabled = data.get("captured_disabled_toolsets")
    if not isinstance(captured_disabled, list):
        fail(f"catalog file {target.name} has no captured_disabled_toolsets "
             "metadata — it was not written by gateway_wire (or is a stale "
             "default). Re-apply from a non-brokerized config to capture.")
    # The captured catalog must look like a REAL owner surface, never the
    # small broker/eager set — guards against a collapsed capture being
    # reused. Anchor: terminal is always enabled for an owner; the broker
    # surface (brick_broker + clarify + todo) is tiny and never contains it.
    present = {str(t) for t in toolsets}
    if "brick_broker" in present:
        fail(f"captured catalog contains the broker itself ({target.name}) — "
             "corrupt capture. Remove the broker surface and re-apply.")
    if "terminal" not in present or len(present) < 5:
        fail(f"captured catalog is collapsed/incomplete ({len(present)} toolsets, "
             "missing terminal) — it does not represent the owner surface. "
             "Remove the broker surface and re-apply to recapture.")
    return [str(t) for t in toolsets], set(captured_disabled)


def _baseline_discord_toolsets():
    """Return the FULL baseline discord toolset list the gateway would resolve
    WITHOUT the broker override (the owner's real effective surface).

    IDEMPOTENT capture (Finding 1):
      * FIRST apply (config not brokerized): derive from the real pre-broker
        config and store the result in catalog_toolsets.json WITH the
        captured disabled_toolsets snapshot.
      * SUBSEQUENT applies (config already brokerized): do NOT re-derive from
        the broker surface — reuse + validate the previously captured catalog.
        If the owner changed global disabled_toolsets since capture, FAIL
        CLOSED (never silently collapse the catalog).
    Never includes brick_broker.
    """
    try:
        existing = load_yaml(CONFIG) or {}
    except Exception:
        existing = {}
    if _config_is_brokerized(existing):
        toolsets, _captured_disabled = _read_captured_catalog()
        # Deliberate handling of owner/global disabled-toolset changes: a
        # captured catalog was derived under a specific disabled set; reusing
        # it under a DIFFERENT set would silently keep stale capabilities.
        current_disabled = _effective_disabled(existing)
        if current_disabled != _captured_disabled:
            fail(
                "agent.disabled_toolsets changed since the broker catalog was "
                f"captured (captured={sorted(_captured_disabled)}, now="
                f"{sorted(current_disabled)}). Refusing to reuse a stale catalog. "
                "Remove the broker surface from platform_toolsets.discord, "
                "re-apply to recapture, then re-add it — or revert the "
                "disabled_toolsets change."
            )
        return toolsets
    try:
        from hermes_cli.tools_config import _get_platform_tools
        toolsets = _get_platform_tools(existing, "discord")
    except Exception:
        toolsets = set()
    toolsets = {str(ts) for ts in toolsets}
    toolsets -= _effective_disabled(existing)
    toolsets.discard("brick_broker")
    return sorted(toolsets)


def _write_broker_catalog(broker_catalog_toolsets):
    """Write catalog_toolsets.json next to the brick_broker plugin so the
    broker's catalog is generated from Brock's real effective surface.

    Path: brick-profile/brick_broker/catalog_toolsets.json (in-repo, next to
    the plugin). The plugin reads it relative to its own __file__.

    The file ALSO records the disabled_toolsets snapshot the capture was
    derived under, so a later re-apply can detect (and fail closed on) an
    owner/global disabled-toolset change instead of silently reusing a stale
    catalog.
    """
    plugin_dir = pathlib.Path(__file__).parent / "brick_broker"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    target = plugin_dir / "catalog_toolsets.json"
    if target.exists():
        shutil.copy2(target, str(target) + BACKUP_SUFFIX)
    try:
        existing = load_yaml(CONFIG) or {}
    except Exception:
        existing = {}
    captured_disabled = sorted(_effective_disabled(existing))
    target.write_text(json.dumps({
        "toolsets": broker_catalog_toolsets,
        "captured_disabled_toolsets": captured_disabled,
        "captured_ts": datetime.datetime.utcnow().isoformat() + "Z",
    }, indent=2) + "\n")
    return target


# ---------------------------------------------------------------------------
# Rollback manifest (Finding 2): record the EXACT pre-broker runtime state so
# install_seam.py --rollback can restore config.yaml + .env transactionally.
# ---------------------------------------------------------------------------
def _manifest_path():
    return HERMES_DIR / ROLLBACK_MANIFEST


def _write_manifest(config_backup, env_backup, config_pre_sha, env_pre_sha,
                    config_post_sha=None, env_post_sha=None):
    """Record the pre-broker runtime state + the backups that hold it.

    config_post_sha256 / env_post_sha256 capture the state wiring WROTE, so
    rollback can detect (and refuse to clobber) user edits made after apply.
    """
    manifest = {
        "installed_by": "gateway_wire.py",
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "config_backup": str(config_backup),
        "env_backup": str(env_backup),
        "config_pre_sha256": config_pre_sha,
        "env_pre_sha256": env_pre_sha,
        "config_post_sha256": config_post_sha,
        "env_post_sha256": env_post_sha,
    }
    mp = _manifest_path()
    if mp.exists():
        shutil.copy2(mp, str(mp) + BACKUP_SUFFIX)
    mp.write_text(json.dumps(manifest, indent=2) + "\n")
    return mp


def _read_manifest():
    mp = _manifest_path()
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text())
    except Exception:
        return None


def _sha256_file(p):
    h = hashlib.sha256()
    if p.exists():
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()


def wire(dry_run=True, force=False):
    ident = load_out("identity.json")
    a2a = load_out("a2a-policy.json")
    model = load_out("model.json")

    env_pairs, config_override = build_wiring(ident, a2a, model)
    broker_catalog_toolsets = _baseline_discord_toolsets()
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
              f"(BROKER surface — model sees only the broker + clarify/todo)")
        print(f"[dry]   config.yaml: tools.tool_search.enabled=off "
              f"(keeps broker tools model-facing; native bridge stays off)")
        print(f"[dry]   brick-profile/brick_broker/catalog_toolsets.json: {len(broker_catalog_toolsets)} baseline "
              f"toolsets ({broker_catalog_toolsets})")
        print("[dry] nothing written")
        return 0

    # ---- backup + rollback manifest (Finding 2: transactional rollback) ----
    # FIRST brokerized apply: back up the pre-broker runtime state (config.yaml
    # + .env) and record the exact backup identities + pre-shas in a manifest.
    # RE-APPLY: never overwrite those backups with the brokerized state — the
    # manifest's backups ARE the pre-first-apply state rollback must restore.
    manifest = _read_manifest()
    if manifest is None:
        config_pre_sha = _sha256_file(CONFIG)
        env_pre_sha = _sha256_file(ENV)
        config_backup = None
        env_backup = None
        if CONFIG.exists():
            config_backup = str(CONFIG) + BACKUP_SUFFIX
            shutil.copy2(CONFIG, config_backup)
        if ENV.exists():
            env_backup = str(ENV) + BACKUP_SUFFIX
            shutil.copy2(ENV, env_backup)
    else:
        print(f"re-apply: reusing rollback manifest (ts={manifest.get('ts')}) — "
              "pre-broker backups preserved, nothing re-backed-up")
        config_backup = manifest.get("config_backup")
        env_backup = manifest.get("env_backup")
        for b in (config_backup, env_backup):
            if b and not pathlib.Path(b).exists():
                fail(f"recorded rollback backup missing: {b} — restore it or "
                     "remove the manifest, then re-apply (rollback would be "
                     "impossible otherwise)")

    existing = load_yaml(CONFIG)
    merged = _deep_merge(existing, config_override)
    write_yaml(CONFIG, merged)
    write_env(ENV, env_pairs)
    # Catalog written only on the FIRST apply (capture). Re-applies reuse the
    # validated captured catalog — never rewrite it (captured_ts would churn
    # and a collapsed capture could be re-derived from the broker surface).
    if manifest is None:
        catalog_target = _write_broker_catalog(broker_catalog_toolsets)
    else:
        catalog_target = _catalog_target()
        if not catalog_target.exists():
            fail("re-apply: captured catalog missing and config is brokerized — "
                 "restore the catalog or remove the broker surface, then re-apply.")

    # Record the manifest AFTER writing, so it can pin the post-wiring shas
    # (what rollback refuses to clobber) alongside the pre-broker backups.
    if manifest is None:
        _write_manifest(config_backup, env_backup, config_pre_sha, env_pre_sha,
                        config_post_sha=_sha256_file(CONFIG),
                        env_post_sha=_sha256_file(ENV))

    print(f"wired brick '{brick_id}' -> {HERMES_DIR} (backups: {BACKUP_SUFFIX})")
    print(f"broker catalog: {catalog_target} ({len(broker_catalog_toolsets)} baseline toolsets)")
    print(f"rollback manifest: {_manifest_path()}")
    print("receipt:", {"brick_id": brick_id, "person_id": person_id,
                       "model": config_override["model"],
                       "a2a_port": env_pairs["A2A_PORT"],
                       "ts": datetime.datetime.utcnow().isoformat() + "Z"})
    return 0


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    force = "--force" in sys.argv
    sys.exit(wire(dry_run=dry, force=force))
