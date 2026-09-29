# Ravel Language Specification

**Version**: 0.2
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

Imports other rulebook files into the current rulebook. Included files are merged into one rulebook.

```yaml
include:
  - foyer          # Loads foyer.ravel
  - cloakroom      # Loads cloakroom.ravel
  - bar-dark
  - bar-light
```

- File extension (`.ravel`) is implied
- Includes are loaded breadth-first from the entry rulebook, and each rulebook loads once
- Circular includes are allowed: a rulebook that is already loaded is not loaded again
- Include order does not order rules. Matching rules are ranked by score, then by location name,
  descending (see 11.4); no include takes precedence over another

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
- Multiple rulebooks can contribute `given` values; they apply in load order, so later-loaded values win
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
- In an expression, an identifier or a `[Bracketed Name]` is a quality reference, and a quoted token is always a string. Quoted names remain valid as subjects (the left-hand quality of a comparison or operation).
- In an expression, a name with punctuation must be bracketed: `[Has-Key]`. `Has-Key` is `Has` minus `Key`.
- `value`, `min` and `max` are reserved inside expressions only. There are no reserved words in subject position.

```
Has-Key = 5 ; X = [Has-Key] → 5
```

### 4.2 Quality Values

Qualities can hold:

| Type | Examples |
|------|----------|
| Integer | `0`, `1`, `42`, `-5` |
| Float | `3.14`, `0.5`, `-2.7` |
| String | `"Intro"`, `"Foyer"`, `'hello'`, `""` |

A leading `-` is part of a number literal, never a separate operator: `-5` is the integer negative
five. The empty string `""` is a valid string literal.

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

`value` is `0` for a subject that has never been set, and it works in comparisons as well as
operations (`Score > value`).

```
X = 10 ; X += value * 2 → 30
```

---

## 5. Expressions

### 5.1 Arithmetic Expressions

Expressions support standard arithmetic with two precedence tiers. Operators in the same tier are
left-associative: they evaluate left to right.

| Operator | Meaning | Precedence | Associativity |
|----------|---------|------------|---------------|
| `+` | Addition | Low | Left |
| `-` | Subtraction | Low | Left |
| `*` | Multiplication | High | Left |
| `/` | Division | High | Left |
| `//` | Floor Division | High | Left |
| `%` | Modulo | High | Left |
| `()` | Grouping | Highest | n/a |

`* / // %` share one tier and bind tighter than `+ -`, which share the other. Whitespace is optional
around arithmetic operators.

Strings take part only in `+` (concatenation) and `=`. Any other operator with a string operand
(`"ab" * 3`, `"%5d" % 7`, `Name *= 2`) is an evaluation error: false in a condition, an error in an
effect. There is no string repetition or `%`-formatting.

**Examples:**
```
5 + 3           → 8
10 - 4 * 2      → 2  (multiplication first)
10 - 4 - 2        → 4
8 / 4 / 2         → 1.0
2 + 3 * 4         → 14
(10 - 4) * 2    → 12 (parentheses override)
10 -4           → 6  (subtraction, not a negative literal)
10 - -4         → 14
7 // 2          → 3  (floor division)
7 % 3           → 1  (modulo)
```

### 5.2 Expression Terms

Expressions can include:

- **Literals**: `42`, `3.14`, `"string"` (a quoted token is always a string)
- **Quality references**: `Score`, `[Wearing Cloak]`, `[Health]` (identifiers and bracketed names)
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

Whitespace is required around the comparator; it is optional around arithmetic operators in the expression.

**Examples:**
```yaml
when:
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

A condition that cannot be evaluated (for example `X > 10 / Y` with `Y` unset, or `X > Name` with `Name` a string) is false. So `X > E` and `X <= E` can both be false, and a story whose conditions all fail reaches a dead end.

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

Whitespace is required around the setter; it is optional around arithmetic operators in the expression.

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
  - Debt += 1 max -5         # Bounds may be negative
```

**Syntax:**
```
Quality operator Expression min N
Quality operator Expression max N
```

Each operation takes at most one constraint. The bound `N` is a number literal and may be negative. The
constraint applies to the result of `=` as well as the compound operators, and in `given` as well as in
`effect`. A string result is an error, and the clamped value takes the bound's kind (integer or float).

```
X = 5 ; X -= 10 min 0   → 0
X = 5 ; X += 10 max 8   → 8
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

**Detection rule.** The first list item is a concept line if a `when:` item follows it, or if it exactly
names a registered concept (for example a bare `Situation`). Otherwise it is the rule's intro text and the
rule is a `Situation`. Trade-off: a one-word intro line that equals a registered concept name is read as
the concept, not as text.

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

A rule's first line uses intro syntax only (no `{cond}` or `<>`).

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
                        # Tail: "You enter the bar"

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

The `<>` marker at the end of text indicates it should "glue" to the next text element (no line break). `<>` is only allowed at the end of a line; a `<>` anywhere else in the line (for example `a <> b`) is a parse error:

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
        - Gold -= 5
        - Location = "Bar"
```

**Choice Text**: The bracketed text `[...]` appears as the selectable option.

**Post-Choice Text**: Text after the bracket is displayed when the choice is selected.

**Effects**: Quality modifications that occur when this choice is selected.

The bracketed line must be the choice's first item. The items after the bracketed line run in the
order written; a `text:` line may carry a `{...}` condition, and one placed after an `effect:` sees
that effect.

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

### 9.4 End Directive

`- end: <outcome>` halts the story immediately, at any stack depth, with the given outcome label:

```yaml
look-at-message:
  - when:
      - Bar >= 2
      - Fumbled = 0
  - There seems to be some sort of message …
  - **You have won**
  - end: won
```

**Outcome**: free inline text, stripped of surrounding whitespace, carried verbatim. A bare
`- end:` (no value) halts with outcome `""`. `end` takes an inline value only — a block value
(e.g. a nested list) is a `ParseError`.

`end` is legal anywhere a directive is, including inside a `choice:` body. Directives after `end`
still compile normally; they are simply never executed (no warning is raised for this).

## 10. Complete Syntax Reference

### 10.1 Grammar Summary (PEG Notation)

```peg
# Qualities
quality         = bracketed_quality / quoted_quality / simple_quality
simple_quality  = ~'[^\s]+'
quoted_quality  = ~'"[^"]+"'
bracketed_quality = ~'\[[^\]]+\]'

# Values
term            = number / string / qvalue / quality_ref
quality_ref     = bracketed_quality / identifier
identifier      = ~'(?!(?:value|min|max)\b)[^\W\d]\w*'
qvalue          = ~'value\b'
number          = float / integer
integer         = ~'-?[0-9]+'
float           = ~'-?[0-9]+\.[0-9]*'
string          = '"' ~'[^"]*' '"' / "'" ~"[^']*" "'"

# Expressions
expression      = additive
additive          = multiplicative (ws? additive_op ws? multiplicative)*
multiplicative    = primary (ws? multiplicative_op ws? primary)*
additive_op       = '+' / '-'
multiplicative_op = '*' / '//' / '/' / '%'
primary           = term / ('(' ws? expression ws? ')')

# Comparisons
comparison      = quality comparator expression
comparator      = '>=' / '>' / '<=' / '<' / '!=' / '==' / '='

# Operations
operation       = quality setter expression constraint?
setter          = '+=' / '-=' / '*=' / '//=' / '/=' / '%=' / '='
constraint      = ('min' / 'max') ws number

# Text
intro_text      = head ('[' suffix ']' tail)?
conditional_text = '{' comparison '}' text glue?
glue            = '<>'
```

### 10.2 YAML Structure

Directives — `text`, `choice`, `effect`, `end` — appear in order after the optional `when:` block:

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
  - end: outcome              # Halts the story immediately with the given outcome label
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
4. **End**: Halt immediately with the given outcome label — clear the stack, discard any offered
   choices, and stop. This can happen at any stack depth (including inside a `choice:` body); no
   further directives run and no menu is offered afterward. See `- end:` in §9.4.

When a choice is selected, its sub-situation executes, then control returns to the parent situation (if more directives remain) or to the Query Phase.

### 11.3 State Stack

The engine maintains a stack of `(location, ip)` frames, one per active situation:

```
┌───────────────────────────┐
│ Frame(bar, ip)             │ ← Current (choosing within Bar)
├───────────────────────────┤
│ Frame(foyer, ip)           │ ← Paused (Foyer's own directives resume when Bar pops)
└───────────────────────────┘
```

An empty stack means no situation is active — the engine falls back to **query mode** (§11.1
Query Phase), finding every top-level situation whose predicates currently pass. This allows
nested situations (choices within choices) with proper return semantics.

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

given:
  - Location = "Intro"
  - "Wearing Cloak" = 1

when:
  - Location = "Intro"

intro:

  - Hurrying through the rainswept November night[…], you're glad to see the bright
    lights of the Opera House. It's surprising that there aren't more people about
    but, hey, what do you expect in a cheap demo game…?

  - {"Wearing Cloak" == 0}The rain drenches you. Boy, you sure do wish you'd
    worn your opera cloak.

  - choice:

      - [Press onward!]You press onward, until you reach the double doors and let
        yourself in.

      - effect:
          - Location = "Foyer"
```

### foyer.ravel
```yaml
include:
  - cloakroom
  - bar-dark
  - bar-light

when:
  - Location = "Foyer"


foyer:

  - You stand in a spacious hall[.], with glittering chandeliers overhead,
    splendidly decorated in red and gold. The hall, that is. The hall is
    splendidly decorated.

  - {"Wearing Cloak" >= 1}Your cloak drips readily on the thick red carpet.


outside:

  - [Outside, the rain pours down, and lightning flashes.]You look out at the
    drenching rain. Lightning flashes, thunder rolls. Better stay inside.


cloakroom:

  - [A cloak room lies just off the main hall.]
  - {"Wearing Cloak" >= 1}Dripping from the rain, you enter the cloak room.
  - {"Wearing Cloak" == 0}You enter the cloak room.

  - effect:
      - Location = "Cloakroom"


bar:

  - [A little further down the hall, a neon sign advertises the bar.]
  - {"Wearing Cloak" >= 1}Dripping from the rain, you wander over to the bar.
  - {"Wearing Cloak" == 0}You wander over to the bar.

  - effect:
      - Location = "Bar"
```

### cloakroom.ravel
```yaml
include:
  - foyer

given:
  - Cloakroom = 0

when:
  - Location = "Cloakroom"

look:

  - [The cloak room is small.]The walls of this small room were clearly once
    lined with hooks, though now only one remains.

  - {"Wearing Cloak" == 0}Your velvet cloak hangs from that single hook,
    dripping on the carpet.

  - effect: Cloakroom += 1


the-hook:

  - when:
      - Cloakroom >= 2
      - "Wearing Cloak" = 1

  - There's a brass hook on the wall.[] Useful for hanging things on it.

  - {"Wearing Cloak" == 0}Your velvet cloak hangs from that single hook,
    dripping on the carpet.

  - effect: Cloakroom += 1


hang-up-cloak:

  - when:
      - Cloakroom >= 3
      - "Wearing Cloak" >= 1

  - [Hang up your cloak.]You hang the dripping velvet cloak on the small brass
    hook.

  - effect: "Wearing Cloak" = 0


put-on-cloak:

  - when:
      - Cloakroom >= 2
      - "Wearing Cloak" == 0

  - [Put on your cloak.]You take the dripping velvet cloak from the small brass
    hook and put it on.

  - effect: "Wearing Cloak" = 1


look-at-cloak:

  - when:
      - "Wearing Cloak" == 0

  - Your cloak hangs from a brass hook.[] A handsome cloak, of velvet trimmed
    with satin, and slightly spattered with raindrops. Its blackness is so deep
    that it almost seems to suck light from the room.



leave:

  - [The warm glow of the Foyer beckons you out.]You leave the cloakroom.

  - effect:
      - Location = "Foyer"
```

### bar-dark.ravel
```yaml
include:
  - foyer

given:
  - Fumbled = 0
  - Bar = 0

when:
  - Location = "Bar"
  - "Wearing Cloak" >= 1


look-in-dark:

  - It is pitch dark[…], and you can't see a thing. It would be easy to trip
    over something.

  - effect: Bar += 1


fumble-around:

  - when:
      - Bar >= 2

  - [Fumble around for a light switch.]You fumble around in the dark, but to no avail.

  - effect: Fumbled = 1


leave:

  - [The bright opulence of the Foyer beckons you.]You leave the darkened Bar.

  - effect:
      - Location = "Foyer"
```

### bar-light.ravel
```yaml
include:
  - foyer

given:
  - Fumbled = 0
  - Bar = 0

when:
  - Location = "Bar"
  - "Wearing Cloak" = 0


look:

  - The bar, much rougher than you'd have guessed after the opulence of
    the foyer, is completely empty. Sawdust covers the floor.

  - effect: Bar += 1


look-at-message:
  - when:
      - Bar >= 2
      - Fumbled = 0

  - There seems to be some sort of message scrawled in the sawdust on the
    floor.[] The message, neatly marked in the sawdust, reads…

  - **You have won**

  - end: won


look-at-scrambled-message:
  - when:
      - Bar >= 2
      - Fumbled >= 1

  - There seems to have been some sort of message scrawled in the sawdust on
    the floor.[] Unfortunately, some fool has scrambled it up, probably by
    fumbling around in the dark. You can still make out a few letters…

  - **Y… …ve …n**

  - end: lost


leave:

  - [The opulence of the Foyer beckons you.]You leave the Bar.

  - effect:
      - Location = "Foyer"
```


## 13. Appendices

### A. Reserved Words

The following are reserved inside expressions only (no reserved words in subject position):
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

### E. Limits

The engine refuses hostile or runaway input at fixed caps. Each cap fails with a typed error rather than
exhausting memory or the interpreter stack.

| Limit | Value | Error |
|-------|-------|-------|
| Operands in one expression chain (`a + b + c ...`) | 100 | `ParseError` at compile time |
| Text length of one expression (checked before parsing; the prose of a text line is exempt, but its `{…}` predicate prefix is not: the prefix is read only from the line's first 65,538 characters, the cap plus its two braces, so a line that starts with `{` and closes no predicate inside that window is refused, and a shorter such line is plain prose) | 65,536 characters | `ParseError` at compile time |
| Parenthesis nesting in one expression | 20 | `ParseError` at compile time |
| Total expression tree depth | 200 | `ParseError` at compile time |
| Digits in an integer literal | 4300 (Python's `sys.get_int_max_str_digits()` default) | `ParseError` at compile time |
| Indentation nesting in one rulebook source (checked before parsing, on the lines syml lexes: split on `\n` after normalising `\r\n` and `\r`, indented by spaces only, `#`/`//` comments skipped at column 0 only; each inline `-` list marker and an inline key after one counts as a level, so `- - - x` is three) | 128 levels | `ParseError` at load time |
| Choice block nesting (guards rulebook data that bypassed the text loader; a text rulebook hits the 128-level indentation cap first) | 200 | `ParseError` at compile time |
| String length (a quality's value, and the result of any `+` or `+=`) | 65,536 characters | `EvaluationError` |
| Integer quality range | -2^63 to 2^63 - 1 | `InvalidQualityValueError` on store |
| Save file size (applies on save and on load) | 1 MiB | `SaveTooLargeError` on save (nothing is written); `SaveCorruptError` on load |
| Rulebook source size (one `.ravel` file or in-memory source; a file is read at most this many bytes plus one) | 1 MiB (1,048,576 bytes; `MAX_RULEBOOK_BYTES`) | `RulebookTooLargeError` (a `ParseError`) at load time |

The string cap is checked on the combined length before two strings are concatenated, so the oversize
result is never built. An `EvaluationError` in a `when:` predicate makes that predicate false; in an
`effect:` or `given:` it surfaces as the engine's `InvalidOperationError`. A string longer than the cap is
also unstorable, so `InvalidQualityValueError` guards storage as a second check.

---

## 14. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.2 | 2026-09-28 | Applied rulings R1–R8; added precedence and whitespace rules; fixed rule-ordering documentation; resynchronized §12 Cloak listing with examples/cloak files. |
| 0.1 | 2025 | Initial specification draft |

---

*This specification was derived from analysis of the Ravel implementation codebase. It represents the language as implemented, not necessarily as originally designed.*
