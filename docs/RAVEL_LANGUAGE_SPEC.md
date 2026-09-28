# Ravel Language Specification

**Version**: 0.1 (Draft)
**Status**: Working specification derived from implementation analysis

---

## 1. Introduction

Ravel is a YAML-based domain-specific language for authoring **Quality-Based Narratives (QBN)**—an interactive fiction paradigm pioneered by Failbetter Games (Fallen London, Sunless Sea). The language draws inspiration from Inkle's Ink language while targeting the storylet/quality model rather than linear branching narratives.

### 1.1 Design Goals

From the project README:

- Provide a flexible engine for authoring, testing, and running QBNs
- Provide a simple, text-based authoring format that is easy to work with, yet doesn't require special tools
- Export QBNs to a portable format that can be read from any environment
- Provide a simple reference implementation of a VM that can perform a Ravel-based QBN

**Language Design Principles:**

- **Declarative authoring**: Stories are defined as collections of situations with predicate-based activation
- **Quality-driven flow**: Story progression is controlled by testing and modifying qualities (variables)
- **Modular composition**: Stories can be split across multiple files with include directives
- **Human-readable**: YAML syntax allows non-programmers to author content
- **Extensible concepts**: Support for custom narrative concepts beyond built-in Situations

### 1.2 Core Paradigm

Unlike traditional branching narratives with explicit goto/jump statements, Ravel uses a **predicate-matching** model:

1. The runtime maintains a set of **qualities** (named variables)
2. **Situations** (storylets) define predicates that must be satisfied for activation
3. Each turn, all matching situations are presented as available choices
4. Player selection triggers situation display and quality modifications
5. Modified qualities change which situations match on subsequent turns

---

## 2. File Format

### 2.1 File Extension and Encoding

- Extension: `.ravel`
- Encoding: UTF-8
- Format: YAML/SYML (YAML with multiline string improvements)

### 2.2 Rulebook Structure

A Ravel file (rulebook) consists of two sections:

1. **Preamble**: Optional metadata and configuration directives
2. **Rules**: Named situation definitions

```yaml
# ========== PREAMBLE ==========
include:
  - other_rulebook
  - another_rulebook

given:
  - Quality = initial_value
  - "Another Quality" = 5

when:
  - GlobalCondition >= 1

about:
  author: "Author Name"
  version: "1.0"

# ========== RULES ==========
rule-name:
  - Situation                    # Concept declaration
  - when:                        # Rule-specific predicates
    - Quality > threshold
  - Intro text here              # Directives begin
  - More content...
```

### 2.3 Entry Point

By convention, the entry rulebook is named `begin.ravel`. The runtime loads this file first, following any `include` directives to build the complete rulebook.

---

## 3. Preamble Directives

### 3.1 `include`

Imports other rulebook files into the current rulebook. Included files are merged, with rules from later includes taking precedence for same-named locations.

```yaml
include:
  - foyer          # Loads foyer.ravel
  - cloakroom      # Loads cloakroom.ravel
  - bar-dark
  - bar-light
```

- File extension (`.ravel`) is implied
- Include order matters for rule ordering
- Circular includes are not permitted

### 3.2 `given`

Initializes qualities at story start. Each entry is an operation that sets an initial value.

```yaml
given:
  - Location = "Intro"
  - "Wearing Cloak" = 1
  - Health = 100
  - Visited = 0
```

- Qualities not in `given` default to `0` when first tested
- Multiple rulebooks can contribute `given` values (later values override)
- String values must be quoted

### 3.3 `when`

Defines predicates that apply to ALL rules in this file. File-level `when` conditions are combined with rule-level conditions using AND logic.

```yaml
when:
  - Location = "Cloakroom"
  - "Game Started" >= 1
```

This is useful for grouping related situations in a file—e.g., all cloakroom situations share `Location = "Cloakroom"`.

### 3.4 `about`

Metadata key-value pairs. Not used by the runtime but available for tooling and documentation.

```yaml
about:
  author: "Interactive Fiction Author"
  title: "Cloak of Darkness"
  version: "1.0"
  ifid: "UUID-HERE"
```

---

## 4. Quality System

Qualities are the core state mechanism in Ravel. They are named variables that store numeric or string values.

### 4.1 Quality Names

Three naming formats are supported:

| Format | Syntax | Example |
|--------|--------|---------|
| Simple | `Name` | `Location`, `Health`, `Score` |
| Quoted | `"Name With Spaces"` | `"Wearing Cloak"`, `"Man of Honor"` |
| Bracketed | `[Name With Spaces]` | `[Wearing Cloak]`, `[Score]` |

**Rules:**
- Simple names cannot contain whitespace
- Quoted names use double quotes
- Bracketed names use square brackets
- Names are case-sensitive
- No reserved words

### 4.2 Quality Values

Qualities can hold:

| Type | Examples |
|------|----------|
| Integer | `0`, `1`, `42`, `-5` |
| Float | `3.14`, `0.5`, `-2.7` |
| String | `"Intro"`, `"Foyer"`, `'hello'` |

**String Quoting Styles:**

Six quoting styles are supported for string literals:

| Style | Example |
|-------|---------|
| Double quotes | `"hello"` |
| Single quotes | `'hello'` |
| Backticks | `` `hello` `` |
| Triple double | `"""hello"""` |
| Triple single | `'''hello'''` |
| Triple backtick | `` ```hello``` `` |

**Note:** When a quality is tested but has never been set, it defaults to `0`.

### 4.3 The `value` Keyword

In expressions, the special keyword `value` refers to the quality's current value:

```yaml
effect:
  - Score += value * 2      # Double the current Score
  - Health -= value / 10    # Reduce Health by 10% of itself
```

---

## 5. Expressions

### 5.1 Arithmetic Expressions

Expressions support standard arithmetic with proper precedence:

| Operator | Meaning | Precedence |
|----------|---------|------------|
| `+` | Addition | Low |
| `-` | Subtraction | Low |
| `*` | Multiplication | Medium |
| `/` | Division | Medium |
| `//` | Floor Division | Medium |
| `%` | Modulo | Medium |
| `()` | Grouping | Highest |

**Examples:**
```
5 + 3           → 8
10 - 4 * 2      → 2  (multiplication first)
(10 - 4) * 2    → 12 (parentheses override)
7 // 2          → 3  (floor division)
7 % 3           → 1  (modulo)
```

### 5.2 Expression Terms

Expressions can include:

- **Literals**: `42`, `3.14`, `"string"`
- **Quality references**: `Score`, `"Wearing Cloak"`, `[Health]`
- **The value keyword**: `value`
- **Nested expressions**: `(Score + 5) * 2`

---

## 6. Comparisons and Predicates

### 6.1 Comparison Operators

| Operator | Meaning |
|----------|---------|
| `=` | Equal to |
| `==` | Equal to (synonym) |
| `!=` | Not equal to |
| `>` | Greater than |
| `>=` | Greater than or equal |
| `<` | Less than |
| `<=` | Less than or equal |

### 6.2 Comparison Syntax

```
Quality comparator Expression
```

**Examples:**
```yaml
- Location = "Foyer"
- "Wearing Cloak" >= 1
- Health > 0
- Score <= 100
- Visited != 0
```

### 6.3 Predicates in Rules

Predicates determine when a rule/situation is available:

```yaml
look-around:
  - when:
    - Location = "Foyer"
    - Visited >= 1
  - You look around the familiar foyer.
```

**Evaluation:**
- All predicates in a rule must be TRUE for the rule to match (AND logic)
- Missing qualities are treated as `0`
- More predicates = higher specificity score (used for ordering)

---

## 7. Operations and Effects

### 7.1 Assignment Operators

| Operator | Meaning |
|----------|---------|
| `=` | Set to value |
| `+=` | Add to current value |
| `-=` | Subtract from current value |
| `*=` | Multiply current value |
| `/=` | Divide current value |
| `//=` | Floor divide current value |
| `%=` | Modulo current value |

### 7.2 Operation Syntax

```
Quality operator Expression [constraint]
```

**Examples:**
```yaml
effect:
  - Location = "Bar"
  - Health -= 10
  - Score += 50
  - "Wearing Cloak" = 0
```

### 7.3 Constraints

Operations can include min/max constraints to bound the result:

```yaml
effect:
  - Health -= 10 min 0       # Cannot go below 0
  - Score += 100 max 1000    # Cannot exceed 1000
  - Reputation += 5 min 0    # Clamp at 0
```

**Syntax:**
```
Quality operator Expression min N
Quality operator Expression max N
```

---

## 8. Rules and Situations

### 8.1 Rule Structure

A rule is a named entry in the rulebook with associated predicates and content:

```yaml
rule-name:
  - Concept                  # Optional: defaults to "Situation"
  - when:                    # Optional: rule-specific predicates
    - predicate1
    - predicate2
  - directive1               # Content begins here
  - directive2
  - ...
```

### 8.2 Concepts

The first list item can declare a concept type. Currently supported:

| Concept | Purpose |
|---------|---------|
| `Situation` | Standard narrative situation (default) |

Custom concepts can be registered via the compiler's handler system.

### 8.3 Location Names

Each rule compiles to a **location** in the rulebook. Locations are hierarchical, using `::` as separator:

```
rulebook-name::rule-name
rulebook-name::rule-name::choice-name
```

**Example:**
```
begin::intro
begin::intro::press-onward
foyer::look-around
```

---

## 9. Directives

Directives are the content within a situation. They appear after the `when:` block (if present) or directly after the concept declaration.

### 9.1 Text Directives

#### Plain Text

Simple narrative text:

```yaml
- You stand in a spacious hall, splendidly decorated in red and gold.
- The rain pours down outside.
```

#### Intro Text (Bracket Syntax)

The first text element in a situation uses special bracket syntax for variant forms:

```
Text before[suffix]Text after
```

This produces two forms:
- **Intro form**: `Text before` + `suffix` (shown in choice lists)
- **Tail form**: `Text before` + `Text after` (shown when situation displays)

**Examples:**
```yaml
- You enter the bar[.]  # Intro: "You enter the bar."
                        # Tail: "You enter the bar."

- The room is dark[!], almost pitch black.
                        # Intro: "The room is dark!"
                        # Tail: "The room is dark, almost pitch black."

- [The foyer stretches before you.]
                        # Intro: "The foyer stretches before you."
                        # Tail: "" (empty)
```

#### Conditional Text

Text with a predicate prefix—only displayed if condition is true:

```yaml
- {"Wearing Cloak" >= 1}Your cloak drips readily on the carpet.
- {Health < 50}You feel weak and tired.
- {Visited == 0}This is your first time here.
```

**Syntax:**
```
{comparison}Text content
```

#### Sticky Text (Glue)

The `<>` marker at the end of text indicates it should "glue" to the next text element (no line break):

```yaml
- You see a door<>
- {Open >= 1} (open)
- {Open == 0} (closed)
- .
```

### 9.2 Choice Directives

Choices present options to the player within a situation:

```yaml
- choice:
  - [Go to the bar]You head toward the neon sign advertising the bar.
  - effect:
    - Location = "Bar"
```

**Structure:**
```yaml
- choice:
  - [Choice Text]Description after choosing
  - text: (optional additional text)
  - effect:
    - operation1
    - operation2
```

**Choice Text**: The bracketed text `[...]` appears as the selectable option.

**Post-Choice Text**: Text after the bracket is displayed when the choice is selected.

**Effects**: Quality modifications that occur when this choice is selected.

#### Multiple Choices

Multiple `choice:` blocks in sequence create a choice menu:

```yaml
- choice:
  - [Head north]You walk northward.
  - effect:
    - Location = "North"

- choice:
  - [Head south]You turn and walk south.
  - effect:
    - Location = "South"

- choice:
  - [Stay here]You decide to remain.
```

### 9.3 Effect Directives

Standalone effects outside of choices:

```yaml
- effect:
  - Visited += 1
  - "Has Seen Intro" = 1

- effect: Score += 10    # Single-line form
```

---

## 10. Complete Syntax Reference

### 10.1 Grammar Summary (PEG Notation)

```peg
# Qualities
quality         = bracketed_quality / quoted_quality / simple_quality
simple_quality  = ~'[^\s]+'
quoted_quality  = ~'"[^"]+"'
bracketed_quality = ~'\[[^\]]+\]'

# Values
value           = number / string / quality_ref / "value"
number          = float / integer
integer         = ~'-?[0-9]+'
float           = ~'-?[0-9]+\.[0-9]+'
string          = '"' ~'[^"]*' '"' / "'" ~"[^']*" "'"

# Expressions
expression      = additive
additive        = multiplicative (('+' / '-') multiplicative)*
multiplicative  = primary (('*' / '/' / '//' / '%') primary)*
primary         = value / '(' expression ')'

# Comparisons
comparison      = quality comparator expression
comparator      = '>=' / '>' / '<=' / '<' / '!=' / '==' / '='

# Operations
operation       = quality setter expression constraint?
setter          = '+=' / '-=' / '*=' / '//=' / '/=' / '%=' / '='
constraint      = ('min' / 'max') number

# Text
intro_text      = head ('[' suffix ']' tail)?
conditional_text = '{' comparison '}' text glue?
glue            = '<>'
```

### 10.2 YAML Structure

```yaml
# Preamble (all optional)
include: [rulebook_name, ...]
given: [operation, ...]
when: [comparison, ...]
about: {key: value, ...}

# Rules
rule-name:
  - Concept                    # Optional, defaults to Situation
  - when:                      # Optional predicates
    - comparison
    - comparison
  - text directive             # First text uses intro syntax
  - {comparison}conditional text
  - choice:
    - [choice text]result text
    - effect:
      - operation
  - effect:
    - operation
```

---

## 11. Execution Model

### 11.1 Turn Structure

1. **Query Phase**: Find all situations whose predicates match current qualities
2. **Display Phase**: Show available situations as choices (using intro text)
3. **Input Phase**: Wait for player selection
4. **Execute Phase**: Display selected situation's directives in order
5. **Loop**: Return to Query Phase

### 11.2 Situation Execution

Within a situation, directives execute sequentially:

1. **Text**: Display (if predicate passes)
2. **Choice Block**: Collect choices, display menu, wait for selection
3. **Effect**: Modify qualities

When a choice is selected, its sub-situation executes, then control returns to the parent situation (if more directives remain) or to the Query Phase.

### 11.3 State Stack

The runtime maintains a stack of execution states:

```
┌─────────────────────────┐
│ DisplaySituation(bar)   │ ← Current
├─────────────────────────┤
│ DisplaySituation(foyer) │ ← Paused
├─────────────────────────┤
│ DisplayPossibleSits     │ ← Base
└─────────────────────────┘
```

This allows nested situations (choices within choices) with proper return semantics.

### 11.4 Rule Matching and Scoring

When multiple situations match:

1. All predicates for each rule are tested
2. Rules with failing predicates are excluded
3. Remaining rules are scored by predicate count (more = higher priority)
4. All matching rules are presented as available choices

**Example:**
```yaml
# Score: 1 (one predicate)
generic-look:
  - when:
    - Location = "Bar"
  - The bar is dimly lit.

# Score: 2 (two predicates)
dark-bar-look:
  - when:
    - Location = "Bar"
    - "Has Light" = 0
  - The bar is pitch black. You cannot see a thing.
```

If `Location = "Bar"` and `"Has Light" = 0`, both rules match, but `dark-bar-look` scores higher and appears first.

---

## 12. Example: Cloak of Darkness

The classic IF demonstration game, implemented in Ravel:

### begin.ravel
```yaml
include:
  - foyer
  - cloakroom
  - bar-dark
  - bar-light

given:
  - Location = "Intro"
  - "Wearing Cloak" = 1
  - Fumbled = 0

when:
  - Location = "Intro"

intro:
  - Hurrying through the rainswept November night[…], you're glad to see
    the bright lights of the Opera House.

  - {"Wearing Cloak" == 0}The rain drenches you. Boy, you sure do wish
    you'd worn your opera cloak.

  - choice:
    - [Press onward!]You press onward to the entrance.
    - effect:
      - Location = "Foyer"
```

### foyer.ravel
```yaml
when:
  - Location = "Foyer"

foyer:
  - You are standing in a spacious hall[.], splendidly decorated in red
    and gold, with glittering chandeliers overhead.

  - choice:
    - [Go to the cloakroom]You head toward the small room off the hall.
    - effect:
      - Location = "Cloakroom"

  - choice:
    - [Go to the bar]The neon sign beckons.
    - effect:
      - Location = "Bar"
```

### cloakroom.ravel
```yaml
when:
  - Location = "Cloakroom"

look:
  - [The cloakroom is small.]The walls are lined with hooks.
  - {"Wearing Cloak" == 0}Your velvet cloak hangs on a brass hook.

hang-up-cloak:
  - when:
    - "Wearing Cloak" >= 1
  - [Hang up your cloak.]You hang your cloak on the hook.
  - effect:
    - "Wearing Cloak" = 0

return-to-foyer:
  - [Return to the foyer]You step back into the main hall.
  - effect:
    - Location = "Foyer"
```

---

## 13. Appendices

### A. Reserved Words

The following are reserved in expression contexts:
- `value` - Current quality value
- `min` - Constraint keyword
- `max` - Constraint keyword

### B. File Organization Best Practices

```
story/
├── begin.ravel          # Entry point with intro
├── locations/
│   ├── foyer.ravel      # Foyer situations
│   ├── bar.ravel        # Bar situations
│   └── garden.ravel     # Garden situations
├── characters/
│   ├── alice.ravel      # Alice interactions
│   └── bob.ravel        # Bob interactions
└── events/
    ├── weather.ravel    # Weather events
    └── time.ravel       # Time-based events
```

### C. Quality Naming Conventions

| Pattern | Use Case | Example |
|---------|----------|---------|
| `Location` | Current location | `Location = "Foyer"` |
| `Has X` | Boolean possession | `"Has Key" = 1` |
| `X Count` | Numeric counter | `"Visit Count" += 1` |
| `Is X` | Boolean state | `"Is Tired" = 1` |
| `X Level` | Scaled value | `"Trust Level" >= 50` |

### D. Comparison with Ink

| Feature | Ink | Ravel |
|---------|-----|-------|
| File format | Custom syntax | YAML |
| Flow control | Knots/stitches with diverts | Predicate matching |
| Variables | Global variables | Qualities |
| Conditionals | Inline `{ }` blocks | Predicate prefixes |
| Choices | `* [text]` or `+ [text]` | `choice:` blocks |
| State model | Sequential with jumps | Quality-based matching |
| Use case | Linear branching | Quality-based narratives |

---

## 14. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2025 | Initial specification draft |

---

*This specification was derived from analysis of the Ravel implementation codebase. It represents the language as implemented, not necessarily as originally designed.*
