# GLM-5.2 LANE — LIVE (2026-08-17, khalid: "also try latest glm")

- Model: z-ai/glm-5.2 (latest GLM on OpenRouter; verified from /api/v1/models)
- Lane: glm-5.2 on the token router (3742), same vaulted OpenRouter key (0600)
- Probe lane: glm-5.2-free (z-ai/glm-5.2:free) — $0, but 503 rate-limited often
- Cost: ~$0.03/task, capped under the $10 khalid-funded envelope
- VERIFIED: reasoning model — emits `reasoning` field BEFORE `content`;
  needs max_tokens >= 600 or it burns the budget on reasoning and returns
  empty content with finish_reason=length (confirmed twice)
- Router path verified: invoke via lane returns content correctly
- Lanes now: deepseek-api (flash, routine) / deepseek-pro (v4-pro, reasoning)
  / openrouter-frontier (gpt-4o, frontier) / glm-5.2 (+ free probe)
