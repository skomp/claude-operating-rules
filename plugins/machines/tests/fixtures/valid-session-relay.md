# Session Relay Protocol

This document describes the session-relay protocol, a state machine that coordinates communication between two repositories in a distributed session management system.

```machine
machine: session-relay
version: v1
prefix: "session-relay:v1 "
roles:
  initiator: repository
  responder: repository
kinds: [triage, question, answer, conclusion, stalemate]
cap: 10
initial: unopened
states:
  - { name: unopened, holder: initiator }
  - { name: awaiting-triage, holder: responder }
  - { name: awaiting-answer, holder: initiator }
  - { name: concluded, terminal: true }
  - { name: stalled, terminal: true }
transitions:
  - { from: unopened, on: triage, by: initiator, to: awaiting-triage, signal: true,
      effects: ["label.add:session-relay:open"] }
  - { from: awaiting-triage, on: question, by: responder, to: awaiting-answer, signal: true }
  - { from: awaiting-answer, on: answer, by: initiator, to: awaiting-triage, signal: true }
  - { from: awaiting-triage, on: conclusion, by: responder, to: concluded, signal: true,
      effects: ["label.remove:session-relay:open"] }
  - { from: awaiting-triage, on: stalemate, by: responder, to: stalled, signal: true,
      effects: ["label.remove:session-relay:open", "label.add:session-relay:stalled", "escalate"] }
```

The protocol ensures that a session between two repositories progresses through well-defined states, with each transition requiring explicit signals and optional side effects on the system state.

A run begins in `unopened`, held by the initiator: the side that found a cause living in the peer's repository and has not yet filed anything. Filing the downstream issue *is* the `triage` message — the issue body carries the protocol header with `kind=triage` and `seq=1`, and there is no separate first comment — which is why `triage` is a transition here and not something the machine starts after. It is an outbound message the machine emits, so it counts against the cap like every other one.
