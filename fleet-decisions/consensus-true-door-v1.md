# CONSENSUS — TRUE DOOR v1 (round-126, 2026-08-16)
# Khalid: "a true brick for the door... incentive to bring in leads and earn
# bananas... no technical instructions... spoon feeding... get consensus
# before you shame me in front of my customers again."
# Three verdicts folded: AGI (design), DA (deleg_ac97110f OBJECT), Rebel
# (deleg_6b9e6ed1 DISSENT-block). All three agree on the SHAPE:
# DM-first, one link, one button, verified-completion pay.

## THE ARCHITECTURE (post-fix, all verdicts folded)

### 1. ONE LINK = A DISCORD DM (Rebel 5, DA 1)
No web page, no domain, no bawes.ai. The link is a Discord invite that
opens a DM with the door bot (game character, per doctrine). Chat IS the
surface. Token: random 128-bit unguessable (DA 3), maps server-side to
referrer — member_id NEVER in the URL (no leak via previews/referer).
The bot's first words: "who brought you here?" with buttons.

### 2. VALUE FIRST, THEN GATES (Rebel 3)
Before ANY phone/Discord/wallet: the door SHOWS the brick working live —
a report, a game event, the banana ledger. Zero prerequisites. Demonstrate
→ connect; never connect → demonstrate.

### 3. CONSENT IS STEP 0 (DA 8, V-5)
Own words, timestamped, BEFORE all buttons, custody-hash-linked.
PLUS explicit disclosure: "X referred you and earns 1 banana when you
finish" — the referrer is never hidden (DA 8, Rebel 1).

### 4. REFERRER EARNS, NOT THE DOOR (Rebel 1+2, DA 9)
The door is infrastructure. The REFERRER (khalid's friend) earns 1 banana
per VERIFIED completion, minted to the MEMBER's own wallet/brick (never
khalid's, never the door's). New member gets a starter gift (first banana
/ starter brick). This is what makes hoostralie's friend join: what THEY
get.

### 5. COMPLETION GATE = bot-authored PR + verified wallet (DA 5)
PR is bot-authored FROM CHAT ANSWERS (no human homework), merged ONLY via
the existing DA-gated review path (self-merge = RuntimeError precedent).
Wallet verified by signed message via the paste-once ingest surface — key
never in chat.

### 6. ATTRIBUTION = server-side, frozen at VERIFICATION (DA 2)
NOT first-tap, NOT cookies (cookies die at the Discord hop). One
phone/Discord/wallet = one attribution, forever, deduped. Cookie is a UX
hint only. Frozen server-side at verification time.

### 7. ANTI-FRAUD (DA 4)
- Payout denied when referrer/referred share device/IP/wallet-custody graph
- Referred identity must have ZERO prior fleet history
- Non-earner DA review of every payout
- Holding period + per-door cap per window

### 8. ECONOMICS (DA 6)
Payer = khalid's sponsored lane (his CAC) or fleet treasury with mint cap.
Every payout carries a PROOF BUNDLE (PR link + merge commit + wallet
verification) in the audit row. No unsourced minting.

### 9. FLOW RECOVERY (DA 7)
Persisted per-session state machine. Every step: retry/skip/human-escape.
Re-tapping a completed step is idempotent. Step-level audit.

## GATE
Re-DA with hostile tests (cookie-flip, alt-harvest, forged URL, self-merge)
BEFORE any real banana moves. No code until khalid approves THIS doc.
