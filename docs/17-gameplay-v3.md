# CodeHehe V3 — Typing Challenge

## Gameplay rule

`TYPING_CHALLENGE` is a one-charge attack Skill that costs one Energy and lasts
for at most 20 seconds. The target can continue reading code, but the Python
editor, Run, Submit, and Skill use are locked until the exact prompt is typed
or the challenge expires.
The official client renders the challenge as a sticky popup immediately above
the active problem's Python editor and moves it when the player changes tabs.

Prompts are server-selected ASCII strings from the Match's frozen rules
snapshot. Matching is exact, including spaces and letter case. The official
client disables paste into the challenge input. The current prompt catalog is
kept unchanged for V3.1.

## Lifecycle

- Typing does not stack with another active Typing challenge on the same target.
- Mirror, Blur, and Typing can coexist.
- Completion cancels the associated timed effect; expiry is derived from server
  time and does not require a cleanup write.
- Refresh restores the active prompt from Match State.
- A submission received before Typing was activated can still finish and score.
- Typing does not add a time penalty when the prompt is not completed.

## Security and privacy

Energy, inventory, target, action lock, expiry, and completion are validated by
the backend. Match State exposes the prompt only to the challenged player.
Client-side DevTools resistance remains outside the project scope.
