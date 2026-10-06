# EXPANSIONS — multi-client architecture

benilla began as a faithful World of Warcraft 1.12.1 client.

This fork extends that engine toward multiple WoW client generations without turning the codebase into several clients living beside each other.

The intended architecture is:

```text
                         ┌── Classic 1.12.1
                         │
Benilla shared engine ───┼── WotLK 3.3.5a
                         │
                         └── future profiles when actually implemented
```

not:

```text
benilla-classic
benilla-wotlk
benilla-tbc
...
```

Supported targets initially are:

```text
Classic
    version: 1.12.1
    build:   5875

WotLK
    version: 3.3.5a
    build:   12340
```

Do not implement other expansions speculatively.

A new client generation is added only when there is real work requiring it.

---

## The fundamental rule

The reference client for the active expansion is the specification.

For Classic behaviour, the reference is 1.12.1.

For WotLK behaviour, the reference is 3.3.5a.

Do not assume that something is shared merely because both clients use the same name for it.

Likewise, do not assume something changed merely because the client version changed.

Determine the actual behaviour first.

The objective is:

> share mechanisms where the clients genuinely share mechanisms, and isolate differences where they genuinely differ.

---

# Expansion crate

Expansion-specific knowledge belongs behind a dedicated workspace crate:

```text
crates/benilla-expansions
```

The crate is the authoritative boundary for identifying supported client generations and describing version-specific facts.

The design is inspired by WoWee's expansion data architecture:

```text
Data/expansions/<expansion>/
```

but should be implemented idiomatically for Rust and Benilla.

`benilla-expansions` is not another client implementation.

It must not duplicate protocol parsing, world rendering, asset loading, UI execution, or gameplay systems.

It describes the target environment those systems operate against.

---

# Expansion identity

There must be one canonical expansion/client-version identity used throughout Benilla.

For example:

```rust
pub enum Expansion {
    Classic,
    Wotlk,
}
```

Do not independently represent the same distinction as:

```text
is_wotlk
client_build
expansion_number
protocol_version
has_death_knight
```

in unrelated systems.

Those may be derived facts or capabilities, but there should be one authoritative target identity.

Names are preferable to numeric expansion IDs inside engine code.

Prefer:

```rust
Expansion::Wotlk
```

over:

```rust
expansion == 2
```

---

# Expansion profiles

Each supported target has a profile describing facts about that reference client.

Conceptually:

```text
ExpansionProfile
├── identity
├── version
├── build
├── protocol
├── update fields
├── data layouts
├── format variants
├── UI/Lua capabilities
└── feature capabilities
```

An expansion profile may describe facts such as:

- expansion identity;
- client version;
- client build;
- maximum level;
- available races;
- available classes;
- protocol opcode values;
- authentication differences;
- packet variants;
- update-field layouts;
- movement-info layout;
- DBC schemas;
- MPQ/data discovery differences;
- supported binary-format versions;
- FrameXML behaviour;
- GlueXML behaviour;
- Lua API capabilities;
- client features such as achievements or vehicles.

The exact Rust representation may evolve.

Prefer strongly typed data.

Do not build a giant untyped configuration system merely to avoid writing Rust.

---

# Facts versus behaviour

The expansion crate should primarily contain **facts and selection logic**.

Existing Benilla crates continue to implement **behaviour**.

For example:

```text
benilla-expansions
    tells us that WotLK uses opcode X

benilla-protocol
    knows how that message is encoded and decoded
```

Likewise:

```text
benilla-expansions
    describes a WotLK DBC layout or selects a variant

benilla-formats
    actually parses DBC data
```

And:

```text
benilla-expansions
    says a target supports achievements

benilla-app / benilla-ui
    implements achievement behaviour
```

Do not move entire implementations into `benilla-expansions` just because they differ between versions.

---

# Existing crate ownership remains intact

The existing Benilla architecture remains authoritative.

Expansion support extends those systems; it does not replace them.

## `benilla-protocol`

Owns:

- authentication;
- world-session protocol;
- packet encoding;
- packet decoding;
- wire structures;
- crypto;
- network semantics.

The expansion layer supplies or selects version-specific protocol facts.

Do not implement a second networking stack in `benilla-expansions`.

---

## `benilla-formats` and format crates

Own:

- DBC parsing;
- M2 parsing;
- WMO parsing;
- ADT/WDT/WDL parsing;
- BLP parsing;
- MPQ handling;
- other WoW binary formats.

Expansion support should normally appear as version-aware parsing inside the existing format implementation.

Prefer:

```text
M2 parser
├── shared representation
├── Classic variant
└── WotLK variant
```

rather than:

```text
classic_m2_parser
wotlk_m2_parser
```

unless the formats are genuinely too different to share useful machinery.

---

## `benilla-assets`

Owns translating WoW data into usable Bevy assets.

Do not fork the entire asset pipeline for another expansion.

---

## `benilla-ui`

Owns the UI engine and reusable UI machinery.

Expansion-specific Lua APIs, XML behaviour, events, widget capabilities, and stock-interface expectations should pass through narrow version-aware boundaries.

Do not create separate Classic and WotLK UI engines unless evidence proves that a shared engine is impractical.

---

## `benilla-world`

Owns world representation, rendering, environment, entities, and world behaviour.

Expansion differences in terrain, models, lighting, liquids, doodads, or world data should normally extend the existing mechanisms.

---

## `benilla-app`

Owns integration and client behaviour.

It is acceptable for application behaviour to depend on capabilities exposed by the active expansion profile.

Avoid making `benilla-app` the place where arbitrary build-number checks accumulate.

---

# Keep version decisions narrow

Do not scatter this throughout the project:

```rust
if expansion == Expansion::Wotlk {
    ...
} else {
    ...
}
```

An expansion check is not automatically wrong, but it should happen at the narrowest meaningful seam.

For example, packet dispatch may legitimately select a protocol implementation based on expansion.

Rendering an ordinary character should not repeatedly ask which expansion is running if the relevant parser or asset representation has already handled the difference.

Prefer:

```text
target selected once
       ↓
version-aware subsystem boundary
       ↓
shared internal representation
       ↓
ordinary engine code
```

The farther a version check propagates into unrelated engine code, the more carefully it should be questioned.

---

# Prefer semantic capabilities to build checks

Where behaviour depends on a feature rather than the identity itself, use a meaningful capability.

Prefer concepts such as:

```text
supports_achievements
supports_death_knight
supports_vehicle_ui
supports_equipment_manager
uses_wotlk_movement_info
uses_wotlk_update_fields
```

over:

```rust
if build >= 12340
```

when the actual reason for the decision is a feature.

Build numbers are facts.

Capabilities explain behaviour.

Do not create hundreds of speculative capability flags.

Add them only when real code needs the distinction.

---

# Classic is the baseline

Classic 1.12.1 must remain fully functional while expansion support is introduced.

When converting an existing hard-coded Classic fact into expansion-dependent data:

1. identify the current Classic value;
2. preserve it exactly;
3. represent it in the Classic profile;
4. add the corresponding WotLK value;
5. change the consumer to use the expansion boundary;
6. verify Classic behaviour remains unchanged.

For example, converting an opcode should conceptually be:

```text
before

CMSG_FOO = 0x123

after

Classic:
    CMSG_FOO = 0x123

WotLK:
    CMSG_FOO = 0x456
```

The refactor itself must not alter Classic behaviour.

---

# Do not over-generalize

Do not design abstractions for hypothetical future expansions.

Two implementations that happen to be different do not automatically justify a large framework.

Start with the smallest useful seam.

Bad:

```text
UniversalWowProtocolAbstractionFactory
```

before WotLK can even authenticate.

Better:

```text
Expansion
OpcodeTable
```

followed by additional abstractions as real differences appear.

Generalize from evidence, not anticipation.

---

# Selecting the target

Expansion selection should eventually be explicit and available early enough that all version-dependent systems can use the same target.

There must not be different parts of the client independently guessing which expansion is running.

Possible evidence for target selection includes:

- explicit configuration;
- selected client-data installation;
- known client build metadata;
- a launcher/profile;
- another authoritative mechanism.

The exact user-facing selection mechanism may evolve.

Once selected, the target should be represented consistently throughout the process.

Do not infer the expansion repeatedly from incidental data such as filenames.

---

# Client data

Each expansion uses the player's own appropriate WoW installation.

For example:

```text
Classic target
    → user's 1.12.1 data

WotLK target
    → user's 3.3.5a data
```

The existing Benilla rule remains:

**the WoW installation is external and read-only.**

Never commit:

- MPQ contents;
- models;
- textures;
- sounds;
- DBC contents;
- maps;
- FrameXML;
- GlueXML;
- other Blizzard assets.

Expansion profiles contain structural knowledge about those files, not their copyrighted contents.

---

# Expansion profile data

Appropriate checked-in expansion information includes structural facts such as:

```text
client build numbers
opcode values
update-field indexes
DBC column layouts
binary structure versions
protocol constants
feature availability
known structural flags
```

For example:

```text
WotLK / build 12340

CMSG_PING = ...
SMSG_UPDATE_OBJECT = ...

UNIT_FIELD_HEALTH = ...
PLAYER_XP = ...

Spell.Name = column ...
Map.InternalName = column ...
```

Do not put extracted client data into the expansion crate.

---

# Protocol differences

Protocol knowledge is one of the primary responsibilities of the expansion boundary.

Opcode numbers are expansion-specific facts.

Do not bake WotLK opcode numbers directly into gameplay systems.

Packet layouts may also differ even where packet names appear identical.

For every protocol message added for WotLK:

1. determine the 3.3.5a opcode;
2. determine its 3.3.5a wire format;
3. compare it with the Classic message if one exists;
4. share structures only where they actually match;
5. use version-specific encoding/decoding where they do not;
6. keep gameplay-facing representations shared where practical.

Do not assume:

```text
same opcode name
=
same packet structure
```

Authentication, session crypto, movement packets, object updates, compressed updates, character data, and other protocol machinery must all be investigated individually.

---

# Update fields

Update fields are expansion-specific protocol/data-layout facts.

Do not attempt to use the Classic update-field table for WotLK.

The expansion boundary should eventually provide the appropriate update-field description for the active client.

Gameplay code should refer to semantic fields whenever possible rather than hard-coded numeric offsets.

For example, prefer the equivalent of:

```text
UNIT_FIELD_HEALTH
```

resolved through the target layout rather than:

```text
field[0x18]
```

spread throughout engine code.

---

# DBC differences

DBC is a shared container format, but table schemas change between client generations.

Do not assume a table with the same filename has the same columns.

Expansion-specific schema knowledge belongs behind the expansion/data-layout boundary.

The DBC parser itself remains generic.

Conceptually:

```text
DBC bytes
   ↓
generic DBC reader
   ↓
target schema
   ↓
typed/shared Benilla representation
```

Where a shared typed representation makes sense, normalize the expansion-specific source layout into it.

Where the concepts themselves differ, keep that difference explicit.

---

# M2, WMO, ADT and other formats

Treat binary formats the same way.

First determine whether the file identifies its own format version.

If it does, prefer parsing based on that information.

If interpretation genuinely requires the selected client generation, pass the appropriate context explicitly.

Do not infer format versions from directory names or filenames when stronger evidence exists.

Prefer:

```text
one parser
+
version-aware structures/chunks
```

over copying an entire format implementation for every expansion.

---

# UI, FrameXML and Lua

The stock interface comes from the player's own target-client installation.

Classic should run Classic FrameXML/GlueXML.

WotLK should run WotLK FrameXML/GlueXML.

Do not bundle Blizzard interface files.

Benilla implements the engine verbs that the stock interface requires.

The same rule upstream applies here:

**do not stub APIs merely to make the stock interface load.**

Lua-facing differences may include:

- global functions;
- events;
- widget methods;
- XML elements;
- attributes;
- templates;
- secure UI behaviour;
- GlueXML behaviour;
- API signatures;
- return values;
- constants.

Do not globally expose a WotLK API to Classic merely because the implementation already exists.

The API surface presented to Lua must correspond to the active target.

---

# WowUnreal

WowUnreal is a valuable 3.3.5a implementation reference.

Use it to discover:

- file-format behaviour;
- protocol mechanisms;
- data structures;
- world-loading behaviour;
- rendering requirements;
- WotLK-specific systems;
- relationships between game data.

Do **not** treat its Unreal architecture as the desired Benilla architecture.

Do not translate:

```text
Unreal class
→
equivalent Bevy class
```

mechanically.

Instead:

```text
WowUnreal implementation
        ↓
identify the underlying WoW behaviour
        ↓
verify the behaviour where necessary
        ↓
find the existing Benilla subsystem that owns it
        ↓
determine shared vs version-specific pieces
        ↓
extend Benilla idiomatically
```

A useful mapping is roughly:

```text
WowUnreal data code
    → benilla format/assets crates
      + expansion-specific schemas

WowUnreal network code
    → benilla-protocol
      + expansion-specific protocol facts

WowUnreal world code
    → benilla-world / benilla-assets
      + format differences

WowUnreal UI knowledge
    → benilla-ui / benilla-app
      + expansion-specific Lua/API capabilities
```

Port knowledge and behaviour.

Do not port engine architecture.

---

# WoWee

WoWee is particularly useful as a reference for separating expansion-specific knowledge from shared client code.

Its `Data/expansions` approach is the conceptual inspiration for `benilla-expansions`.

Use WoWee to help identify categories of information that vary by expansion, such as:

- opcodes;
- update fields;
- DBC layouts;
- version metadata.

Do not reproduce its architecture blindly.

Benilla's existing crate boundaries remain authoritative.

---

# Other implementations

Useful references may include:

- WowUnreal;
- WoWee;
- TrinityCore;
- AzerothCore;
- MaNGOS-family projects;
- wowdev documentation;
- packet captures;
- format documentation;
- other open-source implementations.

These are evidence.

They are not automatically the specification.

A server emulator primarily describes what that server expects.

A client implementation describes how that implementation behaves.

The original target client remains the final fidelity reference where behaviour can be established.

---

# Reference hierarchy

For fidelity-defining questions, prefer evidence approximately in this order:

1. behaviour of the actual target client;
2. data supplied with that target client;
3. FrameXML/GlueXML supplied with that target client;
4. packet captures or other direct observations;
5. binary-format evidence;
6. established format/protocol documentation;
7. independent implementations and emulator code.

The ordering is guidance, not an excuse to ignore strong contradictory evidence.

When references disagree, investigate.

Do not choose whichever answer requires less code.

---

# Third-party source and provenance

Benilla's provenance rules continue to apply.

Do not copy code from another project merely because it is publicly visible.

Before substantially copying or adapting third-party source, verify that its license permits incorporation into this project.

If licensing or provenance is uncertain:

```text
use the project as a behavioural/reference source
        ↓
understand the mechanism
        ↓
implement it independently in idiomatic Rust
```

Protocol constants, structure layouts, file-format facts, observed behaviour, and similar interoperability facts should be documented with enough context to make their origin understandable where appropriate.

Never copy original Blizzard client source or disassembled/decompiled client code into the repository.

Reverse engineering may establish behaviour and facts; repository code must remain independently implemented.

---

# Expansion-specific code should fail explicitly

Do not silently fall back to Classic data when WotLK information is missing.

Bad:

```text
WotLK field unknown
    → use Classic field
```

This can produce subtle corruption while appearing to work.

Prefer an explicit unsupported/error path during development.

Missing expansion support should be visible.

---

# Shared representations

Whenever practical, normalize expansion-specific input into shared semantic representations.

For example:

```text
Classic movement packet ─┐
                         ├──> MovementInfo ──> gameplay/world
WotLK movement packet ───┘
```

rather than forcing the entire application to understand both wire representations.

Likewise:

```text
Classic object update ─┐
                       ├──> semantic entity update
WotLK object update ───┘
```

The expansion boundary should contain differences rather than distribute them.

Do not normalize away differences that matter to gameplay or fidelity.

---

# Vertical development

Do not attempt to port all of WotLK before running the client.

Work vertically.

A useful progression is:

```text
1. expansion identity/profile
2. Classic represented through the new boundary
3. WotLK build/profile metadata
4. auth protocol
5. realm list
6. world connection
7. character enumeration
8. character login
9. world entry
10. object updates
11. movement
12. basic world rendering
13. stock UI compatibility
14. gameplay systems
15. WotLK-only systems
```

This is guidance, not a rigid project plan.

The important rule is:

**reach observable working milestones early.**

Do not spend months constructing a universal expansion framework before WotLK can connect to a server.

---

# Refactoring existing Classic code

Adding WotLK will frequently reveal that an existing Classic constant or assumption belongs behind an expansion boundary.

When that happens:

```text
existing Classic implementation
        ↓
capture current behaviour in a test
        ↓
extract only the version-specific fact
        ↓
put Classic value in Classic profile
        ↓
add WotLK value
        ↓
consume through shared boundary
        ↓
prove Classic stayed unchanged
```

Avoid unrelated cleanup while doing this.

Expansion work is already cross-cutting; keep individual changes small.

---

# Testing

Every change to a shared expansion seam should prove both sides where applicable.

At minimum:

```text
Classic
    existing behaviour remains correct

WotLK
    new version-specific behaviour is covered
```

Good candidates for focused tests include:

- expansion selection;
- opcode tables;
- packet layout selection;
- update fields;
- DBC schemas;
- versioned binary structures;
- capabilities;
- Lua API exposure;
- format-version dispatch.

A successful compile is not proof of protocol correctness.

Network work should eventually be exercised against a suitable live server for the target generation.

For WotLK, implementations such as TrinityCore or AzerothCore may be useful integration targets.

Remember:

**server compatibility is necessary, but reference-client fidelity remains the objective.**

All normal Benilla gates from `docs/METHOD.md` still apply.

---

# Comments and documentation

Do not create historical narratives in source comments.

A useful expansion-related comment explains:

```text
what differs
which target differs
what reference fact requires it
```

For example:

```text
// 3.3.5a includes transport time here; 1.12.1 does not.
```

Avoid comments such as:

```text
// Added during the WotLK port after WowUnreal did it differently.
```

Git records history.

Code comments record the mechanism and reference fact.

---

# Anti-patterns

Avoid these patterns.

## Expansion checks everywhere

```rust
if expansion == Expansion::Wotlk
```

appearing through dozens of unrelated gameplay and rendering systems.

Move the distinction closer to the subsystem boundary.

---

## Parallel clients

```text
classic_protocol.rs
classic_world.rs
classic_ui.rs

wotlk_protocol.rs
wotlk_world.rs
wotlk_ui.rs
```

with largely duplicated implementations.

Share mechanisms first.

Split only what genuinely differs.

---

## Build-number programming

```rust
if build >= 12340
```

when the code actually means:

```text
this client uses the WotLK movement layout
```

Represent the reason for the branch.

---

## Configuring behaviour

A huge JSON/TOML/YAML profile attempting to describe complex protocol or engine behaviour.

Configuration should describe facts.

Rust should implement behaviour.

---

## Premature universality

Building abstractions for Vanilla, TBC, WotLK, Cataclysm, MoP, Retail, and hypothetical future clients while only Classic and WotLK are being implemented.

Support the clients we actually have.

---

## Classic fallback

Using Classic constants because WotLK values are not implemented yet.

Fail visibly instead.

---

## Reference-project architecture leakage

Introducing Unreal-style architecture because WowUnreal implements a mechanism that way.

Understand why it works and integrate the mechanism into Benilla's architecture.

---

# Definition of a good expansion seam

A good expansion boundary has these properties:

- Classic behaviour remains unchanged.
- WotLK behaviour can differ explicitly.
- One authoritative target is selected.
- Version-specific facts have one obvious home.
- Existing Benilla crates retain ownership of their domains.
- Shared engine code does not need to know unnecessary version details.
- Unsupported behaviour fails clearly.
- Tests cover the version distinction.
- Adding another expansion later would require supplying its genuine differences rather than copying the whole client.

The target architecture is:

```text
                         Expansion
                             │
                    ExpansionProfile
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
      protocol           data/formats        UI/API
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                     shared Benilla engine
```

Expansion support is successful when the engine remains recognizably one Benilla codebase, while each target behaves like its own reference client.