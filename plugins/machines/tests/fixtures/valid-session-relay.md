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
initial: awaiting-triage
states:
  - { name: awaiting-triage, holder: responder }
  - { name: awaiting-answer, holder: initiator }
  - { name: concluded, terminal: true }
  - { name: stalled, terminal: true }
transitions:
  - { from: awaiting-triage, on: question, by: responder, to: awaiting-answer, signal: true }
  - { from: awaiting-answer, on: answer, by: initiator, to: awaiting-triage, signal: true }
  - { from: awaiting-triage, on: conclusion, by: responder, to: concluded, signal: true,
      effects: ["label.remove:session-relay:open"] }
  - { from: awaiting-triage, on: stalemate, by: responder, to: stalled, signal: true,
      effects: ["label.remove:session-relay:open", "label.add:session-relay:stalled", "escalate"] }
```

The protocol ensures that a session between two repositories progresses through well-defined states, with each transition requiring explicit signals and optional side effects on the system state.
