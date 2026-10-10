# Roadmap

These are contribution priorities, not delivery promises.

| Priority | Work | Acceptance evidence |
| --- | --- | --- |
| P0 | Bounded detection/retry of stalled Blender workers | Simulated stall preserves inputs and previous delivery; matching verified clips resume; retries stop at a fixed limit |
| P0 | Stronger movement/acting QA | Synthetic positive and negative motion fixtures; avoid claiming full animation approval from three images |
| P1 | Better face expressions, eye direction and hand/prop contact | Character identity remains stable and actions are demonstrated across multiple synthetic stories |
| P1 | More registered actions, props and locations | Schema, compiler and renderer agree; unknown capabilities still fail validation |
| P1 | Multilingual cast role detection | Hindi/English fixtures route correctly, retain exact source order and do not invent actors |
| P1 | Clear progress, phase timing and render diagnostics | Genuine current-phase state, no invented ETA or stale "running" after failure |
| P2 | Provider abstraction with explicit capability negotiation | Mock and live opt-in tests; no silent model/provider substitution |
| P2 | Render benchmarks and cache efficiency | Reproducible synthetic cases with hardware, timings and unchanged output checks |
| P2 | Wider OS/Blender support | Explicit version matrix, platform-specific credential design and passing integration checks |

The first release prioritizes working Windows behavior and honest capability boundaries.
See the open issues for scoped work and ownership.
