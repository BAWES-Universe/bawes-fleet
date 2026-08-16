# For Mishari — the plain map + your 4 answers (no fleet jargon)

## Who's who — so "what brick is what brick" stops being confusing
There are a few separate agents, and "brick" is used for two different things. That's the whole confusion.

- **khalid** — the owner. His entire job is to say "ok" or "no." Nothing else.
- **The AGI (the brain)** — thinks, plans, runs the checks (devil's advocate, rebels, economist), decides WHAT to do. It never builds; it judges.
- **Brick (the hands)** — the operator. Builds, runs, verifies the work, keeps the books. Capital-B "Brick" = this ONE specific agent.
- **The door** — the Discord bot that greets new people and hands each one their own agent. Front desk, nothing more.
- **A personal brick** — every member gets their OWN agent (their own "brain + hands" pair) that serves them. khalid gets one, you'll get one, everyone gets one.

**The naming gotcha:** "Brick" (capital B) = the fleet's operator agent. "a brick" (lowercase) = any member's personal agent. Same word, two meanings. The broker you're building is for **khalid's personal brick** — the one he talks to in Discord.

## Your four questions, answered plainly
1. **Is Discord the owner's "everything interface"?** YES. Eventually the owner asks their brick in Discord to do anything — inspect files, run code, manage skills, delegate work, use memory, set up cron — with normal approval gates on dangerous stuff. Chat is the whole surface; nothing else.

2. **"Read-only by default" — A or B?** **A.** Write-capable tools EXIST and stay available, but actually writing / doing something dangerous requires approval (or earned permission). Not "hide the tools" (B) — it's "tools are there, but the risky action needs a yes."

3. **Authoritative permission source?** A **new explicit signed Discord capability list** — one signed list of exactly what the owner's brick may do in Discord. Not Hermes's default "owner can do everything" surface (too broad), not just the restricted a2a surface (too narrow). One signed list = one source of truth.

4. **Is the broker the right fix?** YES, exactly. Keep every owner capability available through chat, but load the big tool schemas ON DEMAND (only when actually needed) instead of up front. That's what turns a 5-minute "Hello" into a fast one — the brick stops loading everything just to say hi.

## The whole picture
The owner says "deploy the site" or "check the logs" in Discord and their brick does it — without the owner touching a token, a file path, or a command. The brain (AGI) decides, the hands (Brick) do it, the door onboards people, and your broker makes it fast enough to actually use. You're building the speed layer, not changing the design — exactly right.
