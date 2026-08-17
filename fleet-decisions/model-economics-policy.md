# MODEL ECONOMICS POLICY (round-133 correction, khalid 2026-08-17)
# "Why you putting glm in universe. It should mostly be deepseek flash,
# glm is for agi to utilize slowly for brainstorming"

## THE LANE ECONOMICS
| Lane | Model | Cost | Use |
|---|---|---|---|
| deepseek-api | deepseek-v4-flash | $0.002/task | **UNIVERSE WORKHORSE — default for everything** (bots, world, member-facing) |
| deepseek-pro | deepseek-v4-pro | $0.02/task | Heavy reasoning when flash isn't enough |
| glm-5.2 | z-ai/glm-5.2 | ~$0.03/task | **AGI ONLY — slow brainstorming, evolution proposals** — never the universe default |
| openrouter-frontier | gpt-4o | ~$0.05/task | Reserved — only what no other lane can do |

## RULES
1. The universe (bots, world, admin, member surface) runs on **deepseek flash** — $0.002.
2. **GLM-5.2 is the AGI's brainstorming lane** — the AGI self-loop, evolution proposals,
   "what should we build next" thinking. Slow, deliberate, rare.
3. The AGI self-loop reasons on GLM-5.2 (already wired). It should NOT be the
   provider registered for universe bots.
4. When admin registers an AI provider for the universe bot-server: use deepseek
   flash (the router lane), NOT glm.
5. deepseek-pro for intermediate reasoning; gpt-4o only for what others can't do.
