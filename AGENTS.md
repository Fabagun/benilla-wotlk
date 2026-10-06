# benilla

A from-scratch World of Warcraft client in Rust and Bevy.

Upstream benilla targets World of Warcraft 1.12.1 faithfully. This fork extends that foundation to support multiple client generations while preserving the same core rule:

**the target reference client is the specification.**

Classic 1.12.1 remains a first-class target. Expansion support must be explicit and isolated; adding another client generation must not silently change Classic behaviour.

Read, in this order:

1. `docs/METHOD.md` — the upstream rules and working method. Binding for every session.
2. `docs/EXPANSIONS.md` — architecture and rules for multi-expansion work. Binding whenever a change involves client-version differences. Where upstream's 1.12-only scope conflicts with this fork's explicit multi-expansion design, this document governs.
3. `docs/MAP.md` — what is built right now, generated from the code. Orient here before touching anything.
4. `docs/CONTRIBUTING.md` — what gets in and how a change is judged.

The rest of the root is code and data: `crates/` is the workspace, `reference/` contains the reference surfaces checked by tests, `scripts/` contains gates and development instruments, and `third_party/` contains vendored code.

Do not implement expansion differences ad hoc. If behaviour, protocol, data layout, UI API, or file formats differ between supported client generations, follow `docs/EXPANSIONS.md`.

@docs/METHOD.md
@docs/EXPANSIONS.md