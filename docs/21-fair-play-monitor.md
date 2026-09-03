# Fair Play Monitor v1

Fair Play Monitor records limited, privacy-safe signals while a player is in a
running match. It is an operations aid and deterrent, not proof of cheating.
It never changes the winner, score, submissions, skills, or AI review.

## Signals and thresholds

- Absence shorter than 1 second is ignored.
- Absence from 1 to under 3 seconds is kept as an informational audit event.
- Absence of at least 3 seconds adds one strike and shows a short notice when
  the player returns.
- A player state is flagged at two strikes or 10 recorded seconds away.
- A connection gap of at least 30 seconds creates a separate flag without a
  strike.
- Paste records only the event count and pasted character count. Clipboard
  content is never sent or stored.

Every new room receives an immutable policy snapshot. Matches created before
the feature migration stay unmonitored and are not backfilled.

## Privacy and limitations

Players do not receive their flag state or their opponent's monitoring data.
Only authorized administrators can inspect aggregate states and audit events.
The Result, Match History, Match State, and AI prompts do not include Fair Play
data.

Browser lifecycle signals are best-effort. They cannot prove that a player used
AI, opened DevTools, used a phone, or consulted another device. Browser or
network termination may also prevent a final page event from reaching the
server; a later heartbeat can only identify sufficiently long connection gaps.
Do not use a flag as the sole basis for sanctions.

The implementation intentionally does not block F12, DevTools, right-click,
keyboard shortcuts, clipboard use, or force fullscreen.

## Operations

The Battle client sends a small batch to the private integrity endpoint and
retries accepted event IDs idempotently. Failures never block the editor,
submission, or skill actions.

The operations dashboard shows the number of distinct flagged matches in the
configured alert window and links administrators to read-only Django Admin
records. Configure thresholds with the `MATCH_INTEGRITY_*` variables and the
dashboard window with `OPERATIONS_INTEGRITY_ALERT_WINDOW_SECONDS`.
