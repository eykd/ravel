# Contract: CLI UX (`ravel.cli`) — adapter

Entry point unchanged: `ravel = "ravel.cli:main"`.

```text
ravel [--verbose] [--debug] run DIRECTORY [--load FILE]
```

```python
@click.group()
@click.option("--verbose", is_flag=True)   # unchanged: logging INFO + narration
@click.option("--debug", is_flag=True)     # unchanged: logging DEBUG + pdb post-mortem
def main(ctx_obj..., verbose: bool, debug: bool) -> None: ...

@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--load", "load_file", type=click.STRING, default=None)
def run(config: Config, directory: str, load_file: str | None) -> None: ...

class ConsoleUI:
    def __init__(self, session: GameSession, *, verbose: bool = False,
                 read_line: Callable[[str], str] = input,
                 echo: Callable[[str], None] = click.echo) -> None: ...
    def render(self, outputs: Sequence[Output]) -> None: ...
    def loop(self) -> None: ...          # returns on halt or quit
```

## Startup

- Compile the story once via `FileSystemStorySource(directory)`.
- No `--load`: `session.new_game()`, render.
- `--load FILE`: `session.load(FILE)`, render. On `LoadRefusedError`: print
  `Error: <message>` to stderr, exit code **1** (FR-028, US5-AS5).

## Rendering

| Output | Printed |
|---|---|
| `TextShown` | wrapped paragraph (`textwrap.fill`), blank line after. `sticky` ignored (glue deferred) |
| `ChoicesOffered` | `1: <label>` … numbered in order; the CLI keeps `offered` for number→location mapping |
| `QualityChanged` | verbose only: `## <name> was <old>, now <new>` |
| `SituationEntered` / `SituationExited` | verbose only: `## Entering <location>` / `## Exiting <location>` |
| `Halted(outcome, dead_end=False)` | `*** The End (outcome: <outcome>) ***` (`*** The End ***` when outcome is `""`); exit 0 |
| `Halted(dead_end=True)` | `*** The story has nowhere left to go. ***`; exit 0 |

## Prompt: `What'll it be? `

| Input (trimmed, case-insensitive command word) | Action |
|---|---|
| `N` (1 ≤ N ≤ menu size) | `session.choose(menu[N-1].location)`, print separator, render |
| other number | `That's not an option.`; re-prompt |
| `save` / `save FILE` | `session.save(FILE or "ravel-save.json")` → `Saved to <path>.`; same menu stays; OSError → `Could not save: <msg>` |
| `load` / `load FILE` | `session.load(...)` → render the re-presented menu (or halt → end line, exit 0). `LoadRefusedError` → `Could not load: <msg>`; current game continues |
| `s` | print qualities, one `name = value` per line, sorted |
| `help` / `?` | list the commands above |
| `q` | exit 0 |
| EOF / Ctrl-C | print newline, exit 0 |
| anything else | `I'm sorry, what?`; re-prompt |

The menu is never asked twice at startup (D1): the UI renders exactly the outputs the session
returns, once.

## Errors

- Unexpected exception anywhere in `run`: log it; `--debug` → `pdb.post_mortem()`; exit 1
  (`handle_exception`, kept).
- `ravel.exceptions.*` compile errors at startup take the same path.

## Example transcript (US6-AS4, abbreviated)

```text
$ ravel run examples/cloak
1: Hurrying through the rainswept November night…
What'll it be? 1
...
What'll it be? save
Saved to /tmp/x/ravel-save.json.
What'll it be? q
$ ravel run examples/cloak --load ravel-save.json
1: ...
What'll it be? ...
**You have won**
*** The End (outcome: won) ***
$ echo $?
0
```
