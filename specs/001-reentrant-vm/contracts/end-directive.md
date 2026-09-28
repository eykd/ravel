# Contract: `end` directive — grammar, compile, execute

## Syntax (LANGUAGE spec §9, §10.2)

```yaml
look-at-message:
  - when:
      - Bar >= 2
      - Fumbled = 0
  - There seems to be some sort of message …[] The message … reads…
  - **You have won**
  - end: won
```

- `- end: <outcome>` — outcome is free inline text, stripped of surrounding whitespace, carried
  verbatim. `- end:` (no value) → outcome `""` (syml 1.0 gives an absent value as `""`, item 1).
- Legal anywhere a directive is, including inside a `choice:` body. Not legal as a situation's
  first item (that slot is always the intro text, as today).
- No PEG grammar change: `end` is a mapping key dispatched in `compile_directive`, like `choice`,
  `text`, `effect`. `end` matches syml 1.0's key rule and collides with no reserved word
  (LANGUAGE §13.A).

## Compiled type (`ravel/types.py`)

```python
@attr.s(slots=True)
class End:
    outcome: str = attr.ib()
```

## Compile (`ravel/compiler/directives.py`)

```python
elif get_text(key) == "end":
    return [compile_end(environment, concept, parent_rule, directive)]

def compile_end(environment, concept, parent_rule, directive) -> tuple[types.End, dict[str, types.Situation]]:
    if not is_text(directive):
        raise exceptions.ParseError("end takes an inline outcome label, not a block: %r" % directive)
    return types.End(get_text(directive).strip()), {}
```

| Source | Compiled |
|---|---|
| `- end: won` | `End("won")` |
| `- end:   lost  ` | `End("lost")` |
| `- end:` | `End("")` |
| `- end:` followed by an indented list | `ParseError("end takes an inline outcome label, not a block: …")` |

Choice-block bracketing is unaffected: an `End` after `Choice`s closes the block with `GetChoice`
exactly as any other non-choice directive does. Directives after `End` compile normally and are
never executed (no warning, PD-10).

## Execute (engine)

On `End(outcome)` at any stack depth: stack → `()`, offered → `()`, outcome →
`Outcome(outcome, dead_end=False)`, status → `HALTED`, emit `Halted(outcome, False)`, return. No
`SituationExited` outputs, no further directives, no menu (FR-018).

## Cloak edits (FR-019)

- `examples/cloak/bar-light.ravel` `look-at-message`: append `- end: won` after `**You have won**`.
- `look-at-scrambled-message`: append `- end: lost` after `**Y… …ve …n**`.

## Identity

*(Historical: `fingerprint()`/`IR_VERSION` are dead code as of the 2026-09-28 save-format
revision — see § Save validation below — so this no longer matters to anything. Kept as a record:
`End` was an attrs instance, so `fingerprint()` covered it automatically without an `IR_VERSION`
bump.)*

## Save validation

**2026-09-28 revision — this section describes something now removed.** `Story.end_labels` and
the "halted save accepted only if its label is a known `End` label" check are gone: saves no
longer carry a story identity, and loading is never refused for story drift (data-model.md §
Story, save-format.md, engine-api.md § `resume`). A halted save's `outcome.label` is still shape-
checked (must be a `str`) at decode time, but not checked against any story's compiled labels.
`contracts/cli.md`'s `Halted` rendering row now escapes control characters in the label instead,
to close the gap this reopens for a hand-edited save. `Story.end_labels`/`_collect_end_labels`
become dead code, removed alongside `identity`/`fingerprint()`/`IR_VERSION` in the US4 Green leaf.
`End.outcome` is still an exact `str` (`get_text(...).strip()`), unaffected otherwise.
