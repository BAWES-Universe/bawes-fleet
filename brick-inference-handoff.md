# Brick-to-brick inference handoff (cross-brick context) + latency + onboarding path

thread: bawes-zeus-001 · khalid: "you should be able to make his brick guide him by informing it what another brick inferred his owner wants from him."

## Latency — why "Hello" takes 5 min
The brick loads EVERY tool's full schema up front (thousands of tokens) even to answer "Hello." Each schema is large; loading all of them before a single reply is the whole delay. The broker fixes it: keep all capabilities, but load a tool's schema only when that tool is actually invoked. "Hello" then costs near-zero schemas.

## Cross-brick inference handoff (the mechanism)
Any brick/AGI that INFERS something about a member writes it to the shared store keyed by owner. The member's own brick reads its owner's inference on start and uses it to guide them.

Concrete:
- Shared store gains an `owner-inferences` section (per owner id, hashed): e.g. `mishari → "building the broker; confused about brick naming; needs map + 4 answers + latency context"`.
- On start, a brick pulls its owner's inference and folds it into its guidance ("I understand you're building the broker — here's the map").
- The AGI (or another brick) writes the inference when it learns something (here: Mishari is building the broker + asked 4 questions + is confused about naming).

This is the "informing it what another brick inferred" loop: infer → write → guide. Makes each brick feel pre-loaded with what its owner actually wants, instead of starting cold.

## Simple path to get Mishari operational
1. khalid forwards ONE message (the explainer below) — the map + 4 answers + what Mishari builds.
2. The AGI writes the `owner-inferences.mishari` entry so Mishari's brick guides him automatically the moment it comes online.
3. The door (once live) does steps 1–2 for every new member automatically — that's the "amazing experience for all onboarded."

## The one message to forward (Mishari starter)
See mishari-onboarding-explainer.md — the map + naming gotcha + 4 answers + the whole picture.
