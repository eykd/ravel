# Untrusted Input & File Handling Validation

## Purpose

`ravel.environments.Environment.load()` (and `Environment.load_rulebook(name)`)
is where a rulebook name reaches the filesystem: it walks to
`FileSystemLoader.get_source(environment, name)`, which builds
`Path(base_path) / (name + extension)` and opens that path with
`encoding="utf-8"`. Unlike syml's `loads`/`load` (which only ever take
caller-supplied text or an already-open file object), ravel's loader
**builds the filesystem path itself from `name`** — so if `name` is ever
attacker-influenced (e.g. derived from a URL path segment or user input
rather than a fixed set of story files), it is a real path-traversal
surface (`../../etc/passwd` as a rulebook name), not just an advisory
string. Treat `name` as untrusted input requiring validation whenever it
does not come from a fixed, developer-controlled set of story file names.

## Critical Validation Points

### 1. Encoding Validation

#### Why It Matters

`FileSystemLoader.get_source` opens files with `encoding="utf-8"` (no
explicit `errors=` argument, so Python's default `errors="strict"`
applies). If a `.ravel` file is not valid UTF-8, this already raises
loudly. The risk is in code that reads `.ravel` content some *other* way
(e.g. a custom `Loader` subclass, or code that pre-reads file bytes before
handing them to the compiler) and silently swallows or replaces decoding
errors.

#### Implementation

```python
from pathlib import Path

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader


def load_story(base_path: Path, name: str) -> dict:
    """Load a rulebook, failing loudly on encoding problems."""
    environment = Environment(loader=FileSystemLoader(base_path=str(base_path)))
    return environment.load_rulebook(name)
```

```python
# Wrong — a custom loader that reads bytes and decodes with errors="replace"
# hides corruption instead of surfacing it as a decode error.
class LossyLoader(FileSystemLoader):
    def get_source(self, environment, name):
        filepath = Path(self.base_path) / (name + self.extension)
        text = filepath.read_bytes().decode("utf-8", errors="replace")
        return text, self.get_up_to_date_checker(filepath)
```

#### Recommended Defaults

- Always read `.ravel` text as UTF-8 with strict error handling unless
  there is a documented reason to support another encoding
- Never pass `errors="replace"` or `errors="ignore"` for untrusted input —
  silently substituting characters can change which directive a line
  compiles as without raising

### 2. Input Size Validation

#### Why It Matters

Nothing in `FileSystemLoader.get_source` or the compiler bounds how much
text a rulebook file may contain. A caller that loads an untrusted `.ravel`
file (e.g. user-submitted story content), or a custom `Loader` that reads
from an unbounded stream, can be driven to exhaust memory by a single
oversized rulebook.

#### Implementation

```python
MAX_RAVEL_BYTES = 5 * 1024 * 1024  # 5 MiB — tune to the caller's domain


def read_bounded(file_obj: object, max_bytes: int = MAX_RAVEL_BYTES) -> str:
    """Read at most max_bytes+1 to detect (not silently truncate) oversize input."""
    data = file_obj.read(max_bytes + 1)  # type: ignore[attr-defined]
    if len(data) > max_bytes:
        raise ValueError(f"input exceeds {max_bytes} byte limit")
    return data
```

#### Recommended Size Limits

Tune to the deployment, but as a starting point for a story-file format:

- Interactive/CLI use (`ravel run`, local authoring): no hard limit needed,
  but log a warning above ~1 MB
- Service ingesting untrusted rulebook uploads: 1-10 MiB depending on domain
- Batch/CI validation: bound by the repo's own file-size conventions

### 3. Rulebook `name` Handling (Path Traversal)

#### Why It Matters

`FileSystemLoader.get_source` concatenates `name + self.extension` onto
`base_path` with no traversal check. Because ravel resolves the filesystem
path from `name` (unlike syml, where a caller supplies the filename purely
for display), an attacker-influenced `name` is a genuine path-traversal
vector: `"../../../etc/passwd"` (with `extension=""`) or a name containing
`..` segments can escape `base_path`.

#### Implementation

```python
from pathlib import Path

_SAFE_NAME_RE = None  # define per the naming convention this loader uses


def validate_rulebook_name(name: str, base_path: Path, extension: str) -> Path:
    """Resolve name to a path guaranteed to stay under base_path."""
    candidate = (base_path / (name + extension)).resolve()
    if not candidate.is_relative_to(base_path.resolve()):
        raise ValueError(f"invalid rulebook name: {name!r}")
    return candidate
```

#### Recommended Practice

- Never pass a raw, externally-supplied string as `name` to
  `Environment.load()`/`load_rulebook()` — validate against an allowlist of
  known story names, or resolve and check `is_relative_to(base_path)` first
- If a custom `Loader` derives `name` from a URL path segment or form
  input, treat it exactly like any other untrusted filesystem path

### 4. Rulebook Shape Validation (Depth & Include Chains)

Covered in detail in [rate-limiting.md](rate-limiting.md): deeply nested
situations or long `include:` chains are a resource-exhaustion concern, not
a metadata one, but they are validated at the same boundary (during
loading/compiling) as encoding and size.

## Validation Pipeline Pattern

```python
from pathlib import Path

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader


def load_untrusted_story(base_path: Path, name: str) -> dict:
    """Full validation pipeline for an untrusted rulebook name."""
    validate_rulebook_name(name, base_path, ".ravel")
    environment = Environment(loader=FileSystemLoader(base_path=str(base_path)))
    return environment.load_rulebook(name)
```

## Testing Untrusted Input Handling

### Test Encoding Validation

```python
import pytest


def test_it_should_raise_on_invalid_utf8_bytes(tmp_path):
    bad_file = tmp_path / "bad.ravel"
    bad_file.write_bytes(b"key: \xff\xfe not valid utf-8")

    with pytest.raises(UnicodeDecodeError):
        bad_file.read_text(encoding="utf-8")
```

### Test Size Validation

```python
import io


def test_it_should_reject_input_beyond_the_configured_byte_limit():
    oversized = "look: text\n" * 1_000_000

    with pytest.raises(ValueError, match="exceeds"):
        read_bounded(io.StringIO(oversized), max_bytes=1024)
```

### Test Rulebook Name Traversal Rejection

```python
import pytest
from pathlib import Path


def test_it_should_reject_a_traversal_name(tmp_path):
    with pytest.raises(ValueError, match="invalid rulebook name"):
        validate_rulebook_name("../../etc/passwd", tmp_path, ".ravel")
```

## Best Practices Checklist

- [ ] Rulebook files are read with an explicit, strict encoding — never
      silent `errors="replace"`/`errors="ignore"` for untrusted input
- [ ] Input is read with an enforced size cap before being handed to the
      compiler
- [ ] `name` passed to `Environment.load()`/`load_rulebook()` is validated
      against an allowlist or checked to stay under `base_path` whenever it
      is not a fixed, developer-controlled value
- [ ] Nesting depth and include-chain length are bounded per
      [rate-limiting.md](rate-limiting.md)

## Common Vulnerabilities

### Reading Untrusted Input Without a Size Check

```python
text = untrusted_stream.read()  # unbounded — memory-exhaustion risk
```

### Validate Size Before Reading Fully

```python
text = read_bounded(untrusted_stream, max_bytes=MAX_RAVEL_BYTES)
```

### Passing an Untrusted `name` Straight to the Loader

```python
# name came from a URL path segment or request param — using it directly
# reintroduces path traversal, since FileSystemLoader.get_source builds the
# path from it with no traversal check of its own.
environment.load_rulebook(name)
```

### Validate Independently Before Loading

```python
validate_rulebook_name(name, base_path, ".ravel")
environment.load_rulebook(name)
```

## Related Skills

- **security-audit**: Full taxonomy (untrusted input, recursion, ReDoS, file handling)
- **rate-limiting.md**: Resource-exhaustion limits for the same input boundary
