# Smart-door spec — what a "good first impression" actually means (verifiable)

thread: bawes-zeus-001 · khalid: "I wanted it smart and good first impression, now it's just an idiot responding to every message with 'Your brick is awake.'"

## The failure
The door is a STATIC canned responder: same line to every message, no recognition of who's talking, no read of what they said. It's not wired to any context. That is the exact opposite of "smart."

## What smart means (concrete acceptance criteria — not vague)
1. **Recognize who's there.** khalid → owner greeting. Mishari → his context (building the broker). A stranger → new-member welcome. Never the same line to all three.
2. **Read the message, respond to it.** If someone says "I'm stuck on the broker," the door responds to *that*, not "your brick is awake."
3. **Personalized opener + immediate next step.** New member: "Welcome — I'm the door. First, one tap to agree the fleet can help you [consent]. Then I'll wake your brick and show you how to earn your first banana [module 1]." Not a question that punts work back to them.
4. **No spam / no repeat.** It never sends the same canned line twice in a row. It listens after it speaks.
5. **First impression = one clean move, then route.** Greet → consent → module 1. The door leads; it doesn't ask "what do you want to do?" like it has no idea.

## Acceptance test (how we verify "smart", not claim it)
- New user sends "hello" → door greets by name/context + presents consent + module 1, and does NOT print "your brick is awake."
- Same user sends a second message → door responds to the content of that message, not the first line again.
- khalid sends "hi" → recognized as owner, not treated like a stranger.

## Sent to: DA + rebel + Brick (co-sign).
