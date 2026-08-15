# brick-image — the AGI containerizes itself (khalid directive 2026-08-15)
# One image: worker + router client + brain lane. Runs on ANY Vast GPU or human device.
# Self-sustaining: the death warrant + budget gate make it kill itself when it
# stops earning; the ledger is git-native so state rides in, state rides out.
FROM python:3.11-slim

LABEL brick.bawes="brick-image-v1" brick.owner="bawes"

# runtime deps only — no build toolchain in the image (small = cheap)
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /brick

# the spawn package = the brick's organs
COPY spawn-package/ /brick/spawn-package/
COPY orchestrator/ /brick/orchestrator/

# entrypoint: boot identity -> model chain -> worker -> death warrant
COPY docker/entrypoint.sh /brick/entrypoint.sh
RUN chmod +x /brick/entrypoint.sh

# health + worker port; A2A mesh port
EXPOSE 3737 3738

ENV BRICK_ID=brick-worker \
    WORKER_PORT=3737 \
    STATE_FILE=/work/worker-state.json \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["/brick/entrypoint.sh"]
