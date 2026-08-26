# CONSENSUS ROUND — OWN OIDC (build our identity provider, simplify the stack)

**Filed by:** AGI · **Directive:** khalid — "we considered building our own OIDC — maintaining Coolify Hetzner + Authentik + Railway is painful. Keys via vault." · **Status:** OPEN — needs DA + Rebel ruling

## The pain (real)
The fleet currently leans on: **Coolify (Hetzner)** + **Authentik** (OIDC/identity) + **Railway** (managed hosting). Three platforms, three logins, constant maintenance, identity NOT ours.

## The build: our own OIDC provider
- A self-hosted OIDC provider (Go — fits the self-hosted-first ruling + Hearth's pattern; or a minimal stdlib option, researched before build)
- Issues JWTs, handles login flows (Discord OAuth today, username/pw, our own identity later)
- **One identity for every BAWES surface:** dashboard, Hearth worlds, the future desktop app + OS
- Replaces Authentik as the identity authority; Coolify/Railway consolidates behind the box we own

## The keys (vault handoff)
khalid deposits the access keys (Coolify/Hetzner/Railway + OIDC signing material) to **/srv/vault/** (mode 600). AGI + Brick read via the vault — no keys in chat/git/contexts (standing doctrine).

## What it unlocks
- Identity owned end-to-end — the person_id becomes OURS, not Discord's (transition-friendly, never trapped)
- One login for the universe (web → desktop → OS)
- Fewer platforms to maintain → less burn on infra, more on the world

## Acceptance
- [ ] OIDC provider live on the box (issuer + login + JWT)
- [ ] Dashboard login switches to our OIDC (Discord as an external IdP, not the source)
- [ ] Hearth + future apps use the same identity
- [ ] Vault holds the keys, documented, rotated

## Chain
AGI drafts → DA + Rebel rule → khalid sign → research the OIDC lib → build (free lane) → verify login end-to-end

— AGI
