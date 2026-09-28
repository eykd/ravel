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

`End` is an attrs instance, so `fingerprint()` covers it automatically; adding the type does not
bump `IR_VERSION` (no existing save can contain it — there are no saves yet).

## Save validation

`Story.end_labels: frozenset[str]` collects every compiled `End.outcome` (all situations,
including choice bodies). A halted save is accepted only if `outcome.label in story.end_labels`
(or `dead_end` with label `""`), so a save cannot carry arbitrary text for the CLI's end line.
`End.outcome` is an exact `str` (`get_text(...).strip()` already returns `str`; syml 1.0's
`Source` is not a `str` subclass and must never reach a compiled value).
