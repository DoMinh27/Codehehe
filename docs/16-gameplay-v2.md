# CodeHehe V2 — Energy and Skill Battle

## Product rule

Coding score remains the match result authority. Energy and Skills add temporary
pressure but never modify or delete an opponent's source code.

## Energy and rewards

- A player's first Accepted submission for a MatchProblem grants one Energy,
  capped at three.
- The same solve also grants one uniformly random Skill charge.
- Duplicate Accepted submissions do not grant another reward.
- A Skill charge is still granted when Energy is already full.
- The server persists and applies every reward transactionally.

## V2 Skill set

| Code | Cost | Effect |
|---|---:|---|
| `MIRROR_CODE` | 1 | Render every opponent editor right-to-left for 30 seconds. |
| `BLUR_STATEMENT` | 1 | Blur every opponent statement and sample for 30 seconds. |
| `TIME_DRAIN_60` | 2 | Subtract 60 seconds from the opponent's personal clock. |

Mirror and Blur cannot be stacked with another active effect of the same code.
They can coexist with each other. Time Drain is instantaneous and can stack when
the player has enough Energy and charges.

## Personal clocks

Each player has a personal deadline:

```text
max(match.started_at, match.ends_at - player.time_penalty_seconds)
```

After that deadline the player can watch the battle but cannot Run, Submit, or
use a Skill. A Submission accepted by the server before a later Time Drain
remains valid and can still score.

A player becomes terminal after solving every problem or reaching their personal
deadline. The match finishes once both players are terminal and all valid pending
Submissions have completed. Score determines the winner; equal score is a draw.

## Security and privacy

- Django validates match membership, target, clock, Energy, inventory, duplicate
  effects, and idempotency before spending resources.
- Skill definitions are snapshotted at StartMatch.
- Match State exposes only the caller's Energy/inventory.
- Hidden tests, source code, and browser drafts never appear in Skill or State
  responses.
- Browser effects are part of the official client experience; anti-DevTools
  enforcement is outside V2.

## Deferred

Hint is not included in V2. Cleanse, Reflect, and Shield belong to V2.5.
Minigames belong to V3.
