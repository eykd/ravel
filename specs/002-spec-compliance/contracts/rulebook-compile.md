# Contract: Rulebook compilation — concept detection, include cycles, `text:` in choices (FR-009 – FR-011)

**Surface**: `ravel.compiler.rulebooks.compile_rulebook`, `ravel.compiler.concepts.is_registered`
(new), `ravel.environments.Environment.load_rulebook` (unchanged code, newly pinned).

## Concept detection (FR-009, R6, PD-09)

```python
# ravel/compiler/concepts.py
def is_registered(concept: str) -> bool:
    """Whether a handler is registered for ``concept`` (``@concepts.handler``)."""
```

`compile_rulebook` decides each rule's concept, predicates and baggage in this order:

| # | Condition | Concept | Rule predicates | Baggage |
|---|---|---|---|---|
| 1 | `data[0]` is a `when:` mapping | `Situation` | `data[0]["when"]` | `data[1:]` |
| 2 | `data[1]` is a `when:` mapping | `get_text(data[0])` | `data[1]["when"]` | `data[2:]` |
| 3 | `data[0]` is text and `is_registered(get_text(data[0]).strip())` | that name | none | `data[1:]` |
| 4 | otherwise | `Situation` | none | `data[:]` |

Examples (`Environment(loader=MemoryLoader({...})).load()`):

```yaml
# begin.ravel
declared:
  - Situation
  - You are here[.], somewhere.
```

→ `rulebook["Situation"]["rules"] == [Rule("begin::declared", [])]`, and
`locations["begin::declared"].intro == Text("You are here.")`. Before the fix, `Situation` was the
intro text and `You are here[.], somewhere.` a plain-text directive.

```yaml
# begin.ravel
lonely:
  - Hello
  - There you are.
```

→ `Hello` isn't a registered concept, so it's intro text: `locations["begin::lonely"].intro ==
Text("Hello")`, concept `Situation`.

A registered concept followed by nothing (`- Situation` alone) raises `MissingBaggageError`, as an
empty baggage does today.

## Include cycles (FR-010, R1)

Unchanged code. Contract pinned by tests:

- `A` includes `B`, `B` includes `A`: loading `A` compiles `A` then `B`, once each, and returns.
- `A → B → C → A`: compiles `A`, `B`, `C` once each, in that order.
- Breadth-first: `A` includes `[B, C]`, `B` includes `[D]` → compile order `A, B, C, D`.

"Compiled once" is observed with a counting loader (a `MemoryLoader` subclass whose `load`
records names) on a fresh `Environment`.

## `text:` inside `choice:` (FR-011, PD-10)

```yaml
# begin.ravel
intro:
  - Hello[.] there.
  - choice:
      - [Go]You go.
      - text: Extra words.
      - effect: X += 1
```

`start` → offers `begin::intro` ("Hello."). `choose(begin::intro)` → `SituationEntered`,
`TextShown("Hello there.")`, `ChoicesOffered(("begin::intro::go", "Go"))`. `choose(begin::intro::go)`
→ `SituationEntered("begin::intro::go")`, `TextShown("You go.")`, `TextShown("Extra words.")`,
`QualityChanged("X", None, 1)`, `SituationExited` ×2, then the next menu. The menu label stays `Go`.
(Verified by probe against the shipped engine, 2026-09-28.)

**Rejected order (RT-5).** The bracketed `[Label]…` line must be the choice's first item:

```yaml
intro:
  - Hello[.] there.
  - choice:
      - text: Extra words.
      - [Go]You go.
```

→ compiling raises `ravel.exceptions.ParseError` ("No text found, instead: …") whose message
carries the `Source` position of the `text:` key. Existing behavior, pinned by a test; §9.2 v0.2
states the ordering rule.
