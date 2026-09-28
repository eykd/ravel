# Ravel Narrative VM Specification

**Version**: 0.1 (Draft)
**Status**: Design specification for Ravel narrative engine

---

## 1. Introduction

This document specifies a Virtual Machine (VM) for executing compiled Ravel rulebooks. The architecture cleanly separates:

1. **Compilation Target**: Serializable Intermediate Representation (IR)
2. **Execution Context**: Stateless VM with reconstructible state
3. **Presentation Context**: Event subscribers (out of scope)

### 1.1 Design Goals

- **Portable**: Serializable IR for distribution and caching
- **Reconstructible**: Capture and restore VM state at any point
- **Decoupled**: Event-driven architecture for UI flexibility
- **Flexible**: Support realtime, HATEOAS, and hybrid execution modes

### 1.2 Execution Model

The VM implements a **pushdown automaton**:

1. A **stack of frames** tracks active situation execution
2. Each frame executes a **flow-chart state machine** (instruction sequence)
3. When the stack is empty, the VM **queries** for applicable top-level situations
4. Player choices **manipulate the stack** (push, pop, replace, clear)
5. All operations **emit events** for external subscribers

---

## 2. Domain Model

### 2.1 Value Objects (Immutable)

#### QualityValue

A quality value is one of:
- **Integer**: `0`, `42`, `-5`
- **Float**: `3.14`, `0.5`
- **String**: `"Foyer"`, `"Wearing Cloak"`

```
QualityValue = int | float | str
```

Default value for unset qualities: `0` (integer)

#### QualityName

A validated quality identifier supporting three formats:
- **Simple**: `Location`, `Health`, `Score`
- **Quoted**: `"Wearing Cloak"`, `"Man of Honor"`
- **Bracketed**: `[Wearing Cloak]`, `[Score]`

Canonical form strips quotes/brackets and preserves original casing.

#### LocationId

A unique situation identifier as a tuple of path segments:

```
LocationId = tuple[str, ...]

Examples:
  ("begin", "intro")                    → "begin::intro"
  ("begin", "intro", "press-onward")    → "begin::intro::press-onward"
  ("foyer", "cloakroom", "hang-cloak")  → "foyer::cloakroom::hang-cloak"
```

#### Expression

An arithmetic expression tree:

```
Expression =
  | Literal(value: QualityValue)
  | QualityRef(quality: QualityName)
  | ValueRef()                              # Current quality value
  | BinaryOp(op: Operator, left: Expression, right: Expression)

Operator = "+" | "-" | "*" | "/" | "//" | "%"
```

Evaluation: `evaluate(expression, qualities, current_value) → QualityValue`

#### Comparator

```
Comparator = "=" | "==" | "!=" | ">" | ">=" | "<" | "<="
```

Note: `=` and `==` are equivalent for comparisons.

#### Constraint

A bound applied after quality operations:

```
Constraint =
  | Min(bound: QualityValue)
  | Max(bound: QualityValue)
```

Application:
- `Min(0)`: Result cannot go below 0
- `Max(100)`: Result cannot exceed 100

---

### 2.2 Entities

#### Predicate

A condition testing quality state:

```
Predicate = {
  quality: QualityName,
  comparator: Comparator,
  expression: Expression
}
```

Evaluation: `evaluate(predicate, qualities) → bool`

#### Instruction

An atomic VM operation:

```
Instruction = {
  opcode: InstructionOpcode,
  operands: dict[str, Any]
}
```

See Section 4 for the complete instruction set.

#### SituationDef

A compiled situation definition:

```
SituationDef = {
  location: LocationId,
  predicates: list[Predicate],
  intro_text: str,
  tail_text: str,
  instructions: list[Instruction]
}
```

Properties:
- `predicate_score`: Number of predicates (for ranking)
- `matches(qualities)`: True if all predicates pass

---

### 2.3 Aggregates

#### Rulebook (Aggregate Root)

The compiled story—an immutable artifact:

```
Rulebook = {
  version: str,
  metadata: dict[str, str],
  initial_qualities: list[(QualityName, Expression)],
  situations: dict[LocationId, SituationDef],
  situation_index: dict[str, list[LocationId]]    # concept → locations
}
```

Operations:
- `get_situation(location) → SituationDef`
- `query_situations(concept, qualities) → list[SituationDef]`

#### StackFrame

Execution context for an active situation:

```
StackFrame = {
  location: LocationId,
  instruction_pointer: int,              # Default: 0
  local_state: dict[str, Any]            # Frame-local variables
}
```

Operations:
- `advance(delta=1) → StackFrame`: New frame with IP += delta
- `with_local(key, value) → StackFrame`: New frame with updated local

#### QualityLayer

An immutable quality state layer:

```
QualityLayer = {
  layer_id: str,
  qualities: dict[QualityName, QualityValue]
}
```

#### QualityState (Aggregate Root)

Layered quality storage with precedence resolution:

```
QualityState = {
  layers: list[QualityLayer]    # Ordered by precedence (first = highest)
}
```

**Layer Types**:

| Layer | Scope | Persistence | Default Write |
|-------|-------|-------------|---------------|
| `location` | Active frame | Frame-scoped | No |
| `session` | Current playthrough | Ephemeral | Yes |
| `player` | Player profile | Persistent | No |
| `global` | World constants | Read-only | No |

**Resolution Order**: `location → session → player → global → 0`

Operations:
- `get(quality) → QualityValue`: Resolve through layers
- `set(layer_id, quality, value) → QualityState`: New state with update
- `get_layer(layer_id) → QualityLayer`

#### VMState (Aggregate Root)

Complete VM state—fully serializable:

```
VMState = {
  stack: list[StackFrame],
  qualities: QualityState,
  pending_events: list[VMEvent],
  status: VMStatus,
  waiting_context: dict | None
}

VMStatus = "running" | "waiting_input" | "halted"
```

Properties:
- `current_frame`: Top of stack or None

Operations:
- `push_frame(frame) → VMState`
- `pop_frame() → VMState`
- `replace_frame(frame) → VMState`
- `with_qualities(qualities) → VMState`
- `with_status(status) → VMState`
- `emit_event(event) → VMState`
- `clear_events() → VMState`

---

## 3. Quality State Layering

### 3.1 Layer Semantics

**Global Layer** (`global`):
- World constants, story flags shared across all players
- Read-only at runtime (set during rulebook compilation)
- Example: `MaxHealth = 100`, `StoryVersion = 2`

**Player Layer** (`player`):
- Persistent player profile data
- Survives across sessions
- Example: `Achievements`, `Unlocks`, `TotalPlaytime`

**Session Layer** (`session`):
- Current playthrough state
- Ephemeral—lost when session ends
- Default target for quality writes
- Example: `Location`, `Health`, `Inventory`

**Location Layer** (`location`):
- Frame-local variables
- Scoped to the active situation
- Automatically cleared when frame pops
- Example: `VisitCount`, `LocalFlags`

### 3.2 Write Targeting

By default, quality operations write to the `session` layer. Future Ravel syntax may support explicit layer targeting:

```yaml
effect:
  - Location = "Bar"                # session (default)
  - @player.Achievement = 1         # player layer
  - @location.Visited += 1          # location layer
```

### 3.3 Resolution Example

```
qualities:
  global:   {MaxHealth: 100}
  player:   {Achievement: 1}
  session:  {Health: 75, Location: "Foyer"}
  location: {Visited: 2}

get("Health")      → 75       (from session)
get("MaxHealth")   → 100      (from global)
get("Achievement") → 1        (from player)
get("Visited")     → 2        (from location)
get("Unknown")     → 0        (default)
```

---

## 4. Instruction Set

### 4.1 Instruction Format

```
Instruction = {
  opcode: str,
  operands: dict[str, Any]
}
```

### 4.2 Stack Operations

| Opcode | Operands | Description |
|--------|----------|-------------|
| `PUSH` | `{location: LocationId}` | Push new frame onto stack |
| `POP` | `{}` | Pop current frame from stack |
| `REPLACE` | `{location: LocationId}` | Pop then push (tail call) |
| `CLEAR` | `{}` | Clear stack until empty |

**Semantics**:

```
PUSH(location):
  frame = StackFrame(location, ip=0, local_state={})
  state = state.push_frame(frame)
  emit StackPushed(location, len(state.stack))
  emit SituationEntered(location)

POP:
  old_frame = state.current_frame
  state = state.pop_frame()
  emit StackPopped(old_frame.location, len(state.stack))
  emit SituationExited(old_frame.location)

REPLACE(location):
  execute POP
  execute PUSH(location)

CLEAR:
  while state.stack is not empty:
    execute POP
```

### 4.3 Display Operations

| Opcode | Operands | Description |
|--------|----------|-------------|
| `DISPLAY_TEXT` | `{text: str, sticky: bool, predicate: Predicate?}` | Display narrative text |
| `DISPLAY_INTRO` | `{location: LocationId}` | Display situation intro text |
| `BEGIN_CHOICES` | `{}` | Signal start of choice block |
| `DISPLAY_CHOICE` | `{index: int, location: LocationId, text: str}` | Display choice option |
| `END_CHOICES` | `{}` | Signal end of choice block |

**Semantics**:

```
DISPLAY_TEXT(text, sticky, predicate):
  if predicate is None or predicate.evaluate(state.qualities):
    emit TextDisplayed(text, sticky)
  advance IP

DISPLAY_INTRO(location):
  situation = rulebook.get_situation(location)
  emit TextDisplayed(situation.intro_text, sticky=False)
  advance IP

BEGIN_CHOICES:
  emit ChoicesBegin()
  advance IP

DISPLAY_CHOICE(index, location, text):
  emit ChoiceDisplayed(index, location, text)
  advance IP

END_CHOICES:
  emit ChoicesEnd()
  advance IP
```

### 4.4 Quality Operations

| Opcode | Operands | Description |
|--------|----------|-------------|
| `SET_QUALITY` | `{layer: str, quality: QualityName, expression: Expression, constraint: Constraint?}` | Set quality to value |
| `INC_QUALITY` | `{layer: str, quality: QualityName, expression: Expression, constraint: Constraint?}` | Add to quality |
| `DEC_QUALITY` | `{layer: str, quality: QualityName, expression: Expression, constraint: Constraint?}` | Subtract from quality |

**Semantics**:

```
SET_QUALITY(layer, quality, expression, constraint):
  current = state.qualities.get(quality)
  value = expression.evaluate(state.qualities, current)
  if constraint:
    value = constraint.apply(value)
  state = state.with_qualities(state.qualities.set(layer, quality, value))
  emit QualityChanged(quality, layer, current, value)
  advance IP

INC_QUALITY(layer, quality, expression, constraint):
  current = state.qualities.get(quality)
  delta = expression.evaluate(state.qualities, current)
  value = current + delta
  if constraint:
    value = constraint.apply(value)
  state = state.with_qualities(state.qualities.set(layer, quality, value))
  emit QualityChanged(quality, layer, current, value)
  advance IP

DEC_QUALITY(layer, quality, expression, constraint):
  # Same as INC_QUALITY with subtraction
  current = state.qualities.get(quality)
  delta = expression.evaluate(state.qualities, current)
  value = current - delta
  if constraint:
    value = constraint.apply(value)
  state = state.with_qualities(state.qualities.set(layer, quality, value))
  emit QualityChanged(quality, layer, current, value)
  advance IP
```

### 4.5 Control Flow Operations

| Opcode | Operands | Description |
|--------|----------|-------------|
| `BRANCH_IF` | `{predicate: Predicate, offset: int}` | Conditional relative jump |
| `JUMP` | `{offset: int}` | Unconditional relative jump |
| `YIELD` | `{kind: str, context: dict}` | Pause, wait for input |
| `HALT` | `{reason: str?}` | Terminate VM |
| `NOP` | `{}` | No operation |

**Semantics**:

```
BRANCH_IF(predicate, offset):
  if predicate.evaluate(state.qualities):
    advance IP by offset
  else:
    advance IP by 1

JUMP(offset):
  advance IP by offset

YIELD(kind, context):
  state = state.with_status("waiting_input")
  state = state.with_waiting_context({kind: kind, **context})
  emit WaitingForInput(kind, context)
  # Do NOT advance IP - resume continues from here

HALT(reason):
  state = state.with_status("halted")
  emit VMHalted(reason)

NOP:
  advance IP
```

### 4.6 Query Operations

| Opcode | Operands | Description |
|--------|----------|-------------|
| `QUERY_SITUATIONS` | `{concept: str}` | Find matching situations |
| `CHECK_PREDICATE` | `{predicate: Predicate, jump_if_false: int}` | Test and branch |

**Semantics**:

```
QUERY_SITUATIONS(concept):
  matches = rulebook.query_situations(concept, state.qualities)
  sorted_matches = sort by predicate_score descending
  frame = frame.with_local("query_results", sorted_matches)
  advance IP

CHECK_PREDICATE(predicate, jump_if_false):
  if not predicate.evaluate(state.qualities):
    advance IP by jump_if_false
  else:
    advance IP by 1
```

---

## 5. Event Schema

### 5.1 Event Base

```
VMEvent = {
  timestamp: float,     # Unix timestamp
  sequence: int         # Monotonic sequence number
}
```

### 5.2 Quality Events

```
QualityChanged = VMEvent & {
  type: "quality_changed",
  quality: QualityName,
  layer: str,
  old_value: QualityValue,
  new_value: QualityValue
}
```

### 5.3 Display Events

```
TextDisplayed = VMEvent & {
  type: "text_displayed",
  text: str,
  sticky: bool
}

ChoicesBegin = VMEvent & {
  type: "choices_begin"
}

ChoiceDisplayed = VMEvent & {
  type: "choice_displayed",
  index: int,
  location: LocationId,
  text: str
}

ChoicesEnd = VMEvent & {
  type: "choices_end"
}
```

### 5.4 Situation Events

```
SituationEntered = VMEvent & {
  type: "situation_entered",
  location: LocationId
}

SituationExited = VMEvent & {
  type: "situation_exited",
  location: LocationId
}
```

### 5.5 Control Events

```
WaitingForInput = VMEvent & {
  type: "waiting_for_input",
  kind: "choice" | "text" | "confirm",
  context: dict
}

VMHalted = VMEvent & {
  type: "vm_halted",
  reason: str | None
}
```

### 5.6 Stack Events

```
StackPushed = VMEvent & {
  type: "stack_pushed",
  location: LocationId,
  depth: int
}

StackPopped = VMEvent & {
  type: "stack_popped",
  location: LocationId,
  depth: int
}
```

---

## 6. Serialization Format

### 6.1 Design Principles

- **Portable**: JSON primary, MessagePack for performance
- **Versioned**: Schema version for forward compatibility
- **Human-readable**: JSON for debugging and tooling

### 6.2 Rulebook Schema (JSON)

```json
{
  "$schema": "https://ravel-lang.org/schemas/rulebook/v1",
  "version": "1.0.0",
  "metadata": {
    "title": "Cloak of Darkness",
    "author": "Roger Firth",
    "ifid": "UUID-HERE"
  },
  "initialQualities": [
    {
      "quality": "Location",
      "expression": {"kind": "literal", "value": "Intro"}
    },
    {
      "quality": "Wearing Cloak",
      "expression": {"kind": "literal", "value": 1}
    }
  ],
  "situations": {
    "begin::intro": {
      "predicates": [
        {
          "quality": "Location",
          "comparator": "=",
          "expression": {"kind": "literal", "value": "Intro"}
        }
      ],
      "introText": "Hurrying through the rainswept November night...",
      "tailText": "Hurrying through the rainswept November night, you're glad to see the bright lights of the Opera House.",
      "instructions": [
        {
          "opcode": "DISPLAY_TEXT",
          "operands": {
            "text": "Hurrying through the rainswept November night, you're glad to see the bright lights of the Opera House.",
            "sticky": false,
            "predicate": null
          }
        },
        {"opcode": "BEGIN_CHOICES", "operands": {}},
        {
          "opcode": "DISPLAY_CHOICE",
          "operands": {
            "index": 0,
            "location": "begin::intro::press-onward",
            "text": "Press onward!"
          }
        },
        {"opcode": "END_CHOICES", "operands": {}},
        {"opcode": "YIELD", "operands": {"kind": "choice", "context": {}}}
      ]
    },
    "begin::intro::press-onward": {
      "predicates": [],
      "introText": "Press onward!",
      "tailText": "You press onward to the entrance.",
      "instructions": [
        {
          "opcode": "DISPLAY_TEXT",
          "operands": {
            "text": "You press onward to the entrance.",
            "sticky": false,
            "predicate": null
          }
        },
        {
          "opcode": "SET_QUALITY",
          "operands": {
            "layer": "session",
            "quality": "Location",
            "expression": {"kind": "literal", "value": "Foyer"},
            "constraint": null
          }
        }
      ]
    }
  },
  "situationIndex": {
    "Situation": ["begin::intro", "foyer::foyer", "foyer::cloakroom"]
  }
}
```

### 6.3 VMState Schema (JSON)

```json
{
  "$schema": "https://ravel-lang.org/schemas/vmstate/v1",
  "version": "1.0.0",
  "rulebookId": "cloak-of-darkness",
  "stack": [
    {
      "location": "begin::intro",
      "instructionPointer": 5,
      "localState": {}
    }
  ],
  "qualities": {
    "global": {},
    "player": {},
    "session": {
      "Location": "Intro",
      "Wearing Cloak": 1
    },
    "location": {}
  },
  "pendingEvents": [],
  "status": "waiting_input",
  "waitingContext": {
    "kind": "choice",
    "choices": ["begin::intro::press-onward"]
  }
}
```

### 6.4 Expression Schema

```json
// Literal
{"kind": "literal", "value": 42}
{"kind": "literal", "value": "Foyer"}

// Quality reference
{"kind": "quality_ref", "quality": "Health"}

// Current value reference
{"kind": "value_ref"}

// Binary operation
{
  "kind": "binary_op",
  "operator": "+",
  "left": {"kind": "quality_ref", "quality": "Score"},
  "right": {"kind": "literal", "value": 10}
}
```

### 6.5 Predicate Schema

```json
{
  "quality": "Location",
  "comparator": "=",
  "expression": {"kind": "literal", "value": "Foyer"}
}
```

### 6.6 Constraint Schema

```json
{"kind": "min", "bound": 0}
{"kind": "max", "bound": 100}
```

---

## 7. VM Execution

### 7.1 Executor Interface

```python
class VMExecutor:
    """Stateless VM executor - all state passed explicitly."""

    def __init__(self, rulebook: Rulebook): ...

    def step(self, state: VMState) -> VMState:
        """Execute one instruction, return new state."""

    def run_until_yield(self, state: VMState) -> VMState:
        """Execute until YIELD or HALT."""

    def resume(self, state: VMState, input_data: dict) -> VMState:
        """Resume from YIELD with player input."""
```

### 7.2 Step Execution

```
step(state):
  if state.status != "running":
    return state

  frame = state.current_frame
  if frame is None:
    return enter_query_mode(state)

  situation = rulebook.get_situation(frame.location)
  if frame.instruction_pointer >= len(situation.instructions):
    return execute_implicit_pop(state)

  instruction = situation.instructions[frame.instruction_pointer]
  return execute_instruction(state, instruction)
```

### 7.3 Query Mode

When the stack is empty, the VM enters query mode:

```
enter_query_mode(state):
  matches = rulebook.query_situations("Situation", state.qualities)
  sorted_matches = sort by predicate_score descending

  emit ChoicesBegin()
  for i, situation in enumerate(sorted_matches):
    emit ChoiceDisplayed(i, situation.location, situation.intro_text)
  emit ChoicesEnd()

  state = state.with_status("waiting_input")
  state = state.with_waiting_context({
    kind: "choice",
    choices: [s.location for s in sorted_matches]
  })
  emit WaitingForInput("choice", state.waiting_context)
  return state
```

### 7.4 Resume from Input

```
resume(state, input_data):
  if state.status != "waiting_input":
    raise VMError("Not waiting for input")

  kind = state.waiting_context["kind"]

  if kind == "choice":
    location = LocationId.parse(input_data["choice"])
    state = state.with_status("running")
    state = state.push_frame(StackFrame(location))
    emit SituationEntered(location)

    # Display tail text
    situation = rulebook.get_situation(location)
    emit TextDisplayed(situation.tail_text, sticky=False)

  return run_until_yield(state)
```

### 7.5 Execution Modes

#### Realtime Mode (In-Memory)

```python
executor = VMExecutor(rulebook)
state = VMState.initial(rulebook)

while True:
    state = executor.run_until_yield(state)

    for event in state.pending_events:
        ui.handle_event(event)
    state = state.clear_events()

    if state.status == "halted":
        break

    user_input = ui.get_input(state.waiting_context)
    state = executor.resume(state, user_input)
```

#### HATEOAS Mode (Stateless Server)

```python
@app.post("/game/{game_id}/action")
async def game_action(game_id: str, input_data: dict):
    state = await storage.load_state(game_id)
    rulebook = await storage.load_rulebook(state.rulebook_id)

    executor = VMExecutor(rulebook)
    state = executor.resume(state, input_data)

    await storage.save_state(game_id, state)

    return {
        "events": [e.to_dict() for e in state.pending_events],
        "status": state.status,
        "waiting": state.waiting_context,
    }
```

#### Hybrid Mode

```python
class HybridRunner:
    def __init__(self, rulebook, checkpoint_interval=10):
        self.executor = VMExecutor(rulebook)
        self.checkpoint_interval = checkpoint_interval
        self.steps = 0

    async def step(self, state, input_data=None):
        if input_data:
            state = self.executor.resume(state, input_data)
        else:
            state = self.executor.run_until_yield(state)

        self.steps += 1
        if self.steps >= self.checkpoint_interval:
            await self.checkpoint_to_server(state)
            self.steps = 0

        return state
```

---

## 8. Compilation Target

### 8.1 Compilation Pipeline

```
.ravel files → Parser (SYML) → Analyzer → Codegen → Rulebook (IR)
```

### 8.2 Situation Compilation

Source (`begin.ravel`):
```yaml
intro:
  - Hurrying through the rainswept November night[…], you're glad to see
    the bright lights of the Opera House.
  - {"Wearing Cloak" == 0}The rain drenches you.
  - choice:
    - [Press onward!]You press onward to the entrance.
    - effect:
      - Location = "Foyer"
```

Compiled instructions:
```
SituationDef("begin::intro"):
  predicates: [Location = "Intro"]
  intro_text: "Hurrying through the rainswept November night..."
  tail_text: "Hurrying through the rainswept November night, you're glad to see the bright lights of the Opera House."
  instructions:
    [0] DISPLAY_TEXT(text="Hurrying through...", sticky=false, predicate=null)
    [1] DISPLAY_TEXT(text="The rain drenches you.", sticky=false,
                     predicate={quality="Wearing Cloak", comparator="=", value=0})
    [2] BEGIN_CHOICES
    [3] DISPLAY_CHOICE(index=0, location="begin::intro::press-onward", text="Press onward!")
    [4] END_CHOICES
    [5] YIELD(kind="choice")

SituationDef("begin::intro::press-onward"):
  predicates: []
  intro_text: "Press onward!"
  tail_text: "You press onward to the entrance."
  instructions:
    [0] DISPLAY_TEXT(text="You press onward to the entrance.", sticky=false)
    [1] SET_QUALITY(layer="session", quality="Location", value="Foyer")
```

---

## 9. Application Ports

### 9.1 Port Interfaces

```python
class VMExecutorPort(Protocol):
    def step(self, state: VMState) -> VMState: ...
    def run_until_yield(self, state: VMState) -> VMState: ...
    def resume(self, state: VMState, input_data: dict) -> VMState: ...


class StateRepositoryPort(Protocol):
    async def load(self, state_id: str) -> VMState: ...
    async def save(self, state_id: str, state: VMState) -> None: ...
    async def delete(self, state_id: str) -> None: ...


class RulebookRepositoryPort(Protocol):
    async def load(self, rulebook_id: str) -> Rulebook: ...
    async def save(self, rulebook_id: str, rulebook: Rulebook) -> None: ...


class EventPublisherPort(Protocol):
    def publish(self, event: VMEvent) -> None: ...
    def subscribe(self, handler: Callable[[VMEvent], None]) -> Subscription: ...
```

---

## 10. Acceptance Tests

### 10.1 Value Object Tests

#### AT-VO-1: QualityValue Arithmetic
```
GIVEN QualityValue(10) and QualityValue(5)
WHEN added together
THEN result is QualityValue(15)

GIVEN QualityValue(10) and QualityValue(3)
WHEN subtracted
THEN result is QualityValue(7)

GIVEN QualityValue("hello") and QualityValue(5)
WHEN added together
THEN TypeError is raised
```

#### AT-VO-2: QualityName Parsing
```
GIVEN raw string "Location"
WHEN parsed as QualityName
THEN canonical name is "Location"

GIVEN raw string '"Wearing Cloak"'
WHEN parsed as QualityName
THEN canonical name is "Wearing Cloak"

GIVEN raw string "[Score]"
WHEN parsed as QualityName
THEN canonical name is "Score"
```

#### AT-VO-3: LocationId Operations
```
GIVEN LocationId(("begin", "intro"))
WHEN qualified_name is accessed
THEN result is "begin::intro"

GIVEN LocationId(("begin", "intro"))
WHEN child("press-onward") is called
THEN result is LocationId(("begin", "intro", "press-onward"))
```

#### AT-VO-4: Expression Evaluation
```
GIVEN Expression(Literal(5))
WHEN evaluated with qualities={}, current_value=0
THEN result is 5

GIVEN Expression(QualityRef("Health"))
WHEN evaluated with qualities={"Health": 75}, current_value=0
THEN result is 75

GIVEN Expression(BinaryOp("+", QualityRef("Score"), Literal(10)))
WHEN evaluated with qualities={"Score": 50}, current_value=0
THEN result is 60

GIVEN Expression(ValueRef())
WHEN evaluated with qualities={}, current_value=42
THEN result is 42
```

#### AT-VO-5: Constraint Application
```
GIVEN Constraint(Min(0)) and value -5
WHEN constraint is applied
THEN result is 0

GIVEN Constraint(Max(100)) and value 150
WHEN constraint is applied
THEN result is 100

GIVEN Constraint(Min(0)) and value 50
WHEN constraint is applied
THEN result is 50 (unchanged)
```

### 10.2 Predicate Tests

#### AT-PR-1: Predicate Evaluation
```
GIVEN Predicate(quality="Location", comparator="=", expression=Literal("Foyer"))
WHEN evaluated with qualities={"Location": "Foyer"}
THEN result is true

GIVEN Predicate(quality="Health", comparator=">", expression=Literal(50))
WHEN evaluated with qualities={"Health": 75}
THEN result is true

GIVEN Predicate(quality="Health", comparator=">", expression=Literal(50))
WHEN evaluated with qualities={"Health": 25}
THEN result is false

GIVEN Predicate(quality="Unknown", comparator="=", expression=Literal(0))
WHEN evaluated with qualities={}
THEN result is true (unset qualities default to 0)
```

### 10.3 Stack Operation Tests

#### AT-SO-1: PUSH Instruction
```
GIVEN VMState with empty stack
WHEN PUSH("begin::intro") is executed
THEN stack has one frame with location="begin::intro", ip=0
AND SituationEntered event is emitted
AND StackPushed event is emitted with depth=1
```

#### AT-SO-2: POP Instruction
```
GIVEN VMState with stack=[Frame("begin::intro")]
WHEN POP is executed
THEN stack is empty
AND SituationExited event is emitted
AND StackPopped event is emitted with depth=0
```

#### AT-SO-3: REPLACE Instruction
```
GIVEN VMState with stack=[Frame("begin::intro")]
WHEN REPLACE("foyer::look") is executed
THEN stack has one frame with location="foyer::look", ip=0
AND SituationExited event for "begin::intro" is emitted
AND SituationEntered event for "foyer::look" is emitted
```

#### AT-SO-4: CLEAR Instruction
```
GIVEN VMState with stack=[Frame("a"), Frame("b"), Frame("c")]
WHEN CLEAR is executed
THEN stack is empty
AND three SituationExited events are emitted (c, b, a order)
```

### 10.4 Display Operation Tests

#### AT-DO-1: DISPLAY_TEXT without Predicate
```
GIVEN DISPLAY_TEXT(text="Hello world", sticky=false, predicate=null)
WHEN executed
THEN TextDisplayed event is emitted with text="Hello world", sticky=false
AND instruction pointer advances by 1
```

#### AT-DO-2: DISPLAY_TEXT with Passing Predicate
```
GIVEN DISPLAY_TEXT(text="You have the key", predicate={quality="HasKey", comparator=">=", value=1})
AND qualities={"HasKey": 1}
WHEN executed
THEN TextDisplayed event is emitted
AND instruction pointer advances by 1
```

#### AT-DO-3: DISPLAY_TEXT with Failing Predicate
```
GIVEN DISPLAY_TEXT(text="You have the key", predicate={quality="HasKey", comparator=">=", value=1})
AND qualities={"HasKey": 0}
WHEN executed
THEN no TextDisplayed event is emitted
AND instruction pointer advances by 1
```

#### AT-DO-4: Choice Block Sequence
```
GIVEN instructions:
  [0] BEGIN_CHOICES
  [1] DISPLAY_CHOICE(0, "choice-a", "Go left")
  [2] DISPLAY_CHOICE(1, "choice-b", "Go right")
  [3] END_CHOICES
WHEN executed in sequence
THEN events are emitted in order:
  ChoicesBegin
  ChoiceDisplayed(0, "choice-a", "Go left")
  ChoiceDisplayed(1, "choice-b", "Go right")
  ChoicesEnd
```

### 10.5 Quality Operation Tests

#### AT-QO-1: SET_QUALITY
```
GIVEN SET_QUALITY(layer="session", quality="Location", expression=Literal("Bar"))
AND qualities.session={"Location": "Foyer"}
WHEN executed
THEN qualities.session={"Location": "Bar"}
AND QualityChanged event is emitted with old="Foyer", new="Bar"
```

#### AT-QO-2: INC_QUALITY
```
GIVEN INC_QUALITY(layer="session", quality="Score", expression=Literal(10))
AND qualities.session={"Score": 50}
WHEN executed
THEN qualities.session={"Score": 60}
AND QualityChanged event is emitted with old=50, new=60
```

#### AT-QO-3: DEC_QUALITY with Constraint
```
GIVEN DEC_QUALITY(layer="session", quality="Health", expression=Literal(30), constraint=Min(0))
AND qualities.session={"Health": 20}
WHEN executed
THEN qualities.session={"Health": 0} (constrained from -10)
AND QualityChanged event is emitted with old=20, new=0
```

#### AT-QO-4: Quality Layer Targeting
```
GIVEN SET_QUALITY(layer="player", quality="Achievement", expression=Literal(1))
AND qualities.player={}
WHEN executed
THEN qualities.player={"Achievement": 1}
AND qualities.session is unchanged
```

### 10.6 Control Flow Tests

#### AT-CF-1: BRANCH_IF with True Condition
```
GIVEN BRANCH_IF(predicate={quality="Flag", comparator="=", value=1}, offset=3)
AND qualities={"Flag": 1}
AND current IP=5
WHEN executed
THEN IP becomes 8 (5 + 3)
```

#### AT-CF-2: BRANCH_IF with False Condition
```
GIVEN BRANCH_IF(predicate={quality="Flag", comparator="=", value=1}, offset=3)
AND qualities={"Flag": 0}
AND current IP=5
WHEN executed
THEN IP becomes 6 (5 + 1)
```

#### AT-CF-3: YIELD
```
GIVEN YIELD(kind="choice", context={choices: ["a", "b"]})
AND status="running"
WHEN executed
THEN status becomes "waiting_input"
AND waiting_context is {kind: "choice", choices: ["a", "b"]}
AND WaitingForInput event is emitted
AND IP does NOT advance
```

#### AT-CF-4: HALT
```
GIVEN HALT(reason="game over")
AND status="running"
WHEN executed
THEN status becomes "halted"
AND VMHalted event is emitted with reason="game over"
```

### 10.7 Query Tests

#### AT-QR-1: QUERY_SITUATIONS
```
GIVEN rulebook with situations:
  - "a" with predicates [Location="X"]
  - "b" with predicates [Location="X", Flag>=1]
  - "c" with predicates [Location="Y"]
AND qualities={"Location": "X", "Flag": 1}
WHEN QUERY_SITUATIONS("Situation") is executed
THEN local_state["query_results"] contains ["b", "a"] (b first due to higher score)
AND "c" is not included (predicate fails)
```

#### AT-QR-2: CHECK_PREDICATE True
```
GIVEN CHECK_PREDICATE(predicate={quality="HasKey", comparator=">=", value=1}, jump_if_false=5)
AND qualities={"HasKey": 1}
AND IP=10
WHEN executed
THEN IP becomes 11
```

#### AT-QR-3: CHECK_PREDICATE False
```
GIVEN CHECK_PREDICATE(predicate={quality="HasKey", comparator=">=", value=1}, jump_if_false=5)
AND qualities={"HasKey": 0}
AND IP=10
WHEN executed
THEN IP becomes 15 (10 + 5)
```

### 10.8 Execution Flow Tests

#### AT-EF-1: Empty Stack Enters Query Mode
```
GIVEN VMState with empty stack and status="running"
WHEN step() is called
THEN VM enters query mode
AND matching situations are displayed as choices
AND status becomes "waiting_input"
```

#### AT-EF-2: Resume from Choice
```
GIVEN VMState with status="waiting_input"
AND waiting_context={kind: "choice", choices: ["begin::intro"]}
WHEN resume(state, {choice: "begin::intro"}) is called
THEN stack contains Frame("begin::intro")
AND SituationEntered event is emitted
AND status becomes "running"
AND execution continues until next YIELD
```

#### AT-EF-3: End of Situation Pops Frame
```
GIVEN VMState with stack=[Frame("a", ip=5)]
AND situation "a" has 5 instructions (indices 0-4)
WHEN step() is called with ip=5 (past end)
THEN frame is popped
AND SituationExited event is emitted
```

#### AT-EF-4: run_until_yield Executes Multiple Steps
```
GIVEN VMState at start of situation with 3 instructions then YIELD
WHEN run_until_yield() is called
THEN all 3 instructions execute
AND YIELD is executed
AND status is "waiting_input"
```

### 10.9 Serialization Tests

#### AT-SR-1: Rulebook Round-Trip
```
GIVEN a compiled Rulebook
WHEN serialized to JSON
AND deserialized back
THEN resulting Rulebook is equivalent to original
AND all situations, predicates, instructions are preserved
```

#### AT-SR-2: VMState Round-Trip
```
GIVEN a VMState with:
  - stack with 2 frames
  - qualities in multiple layers
  - status="waiting_input"
  - waiting_context with choices
WHEN serialized to JSON
AND deserialized back
THEN resulting VMState is equivalent to original
AND execution can continue correctly
```

#### AT-SR-3: Expression Serialization
```
GIVEN Expression(BinaryOp("+", QualityRef("A"), BinaryOp("*", Literal(2), ValueRef())))
WHEN serialized to JSON
AND deserialized back
THEN expression evaluates identically to original
```

### 10.10 Quality Layer Tests

#### AT-QL-1: Layer Resolution Order
```
GIVEN QualityState with:
  - global: {"A": 1}
  - player: {"A": 2}
  - session: {"A": 3}
  - location: {"A": 4}
WHEN get("A") is called
THEN result is 4 (location layer wins)
```

#### AT-QL-2: Layer Resolution Fallthrough
```
GIVEN QualityState with:
  - global: {"A": 1}
  - player: {}
  - session: {}
  - location: {}
WHEN get("A") is called
THEN result is 1 (falls through to global)
```

#### AT-QL-3: Layer Write Isolation
```
GIVEN QualityState with session={"A": 1}, player={}
WHEN set("session", "A", 5) is called
THEN session={"A": 5}
AND player={} (unchanged)
```

### 10.11 Integration Tests

#### AT-INT-1: Cloak of Darkness Intro
```
GIVEN compiled Cloak of Darkness rulebook
AND fresh VMState
WHEN executed until first YIELD
THEN events include:
  - ChoicesBegin
  - ChoiceDisplayed for "begin::intro"
  - ChoicesEnd
  - WaitingForInput(kind="choice")
AND qualities include Location="Intro", "Wearing Cloak"=1
```

#### AT-INT-2: Cloak of Darkness Choice Navigation
```
GIVEN VMState after intro display
WHEN resume with choice="begin::intro"
AND resume with choice="begin::intro::press-onward"
THEN qualities include Location="Foyer"
AND next YIELD shows foyer situations
```

#### AT-INT-3: State Persistence Across Execution
```
GIVEN VMState mid-execution
WHEN serialized
AND server restarted
AND deserialized
AND execution resumed
THEN narrative continues correctly
AND no events are lost or duplicated
```

#### AT-INT-4: Predicate Conditional Text
```
GIVEN situation with conditional text:
  - DISPLAY_TEXT("You have the cloak", predicate={"Wearing Cloak" >= 1})
AND qualities={"Wearing Cloak": 0}
WHEN situation executes
THEN conditional text is NOT displayed

WHEN qualities changed to {"Wearing Cloak": 1}
AND situation re-executes
THEN conditional text IS displayed
```

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **Frame** | Stack entry for active situation execution |
| **Instruction** | Atomic VM operation |
| **Layer** | Quality state scope (global/session/player/location) |
| **Location** | Unique situation identifier (`rulebook::situation::choice`) |
| **Predicate** | Condition testing quality state |
| **Quality** | Named variable in narrative state |
| **Rulebook** | Compiled story (situations + metadata) |
| **Situation** | Narrative unit with predicates, text, and instructions |
| **Yield** | VM pause waiting for external input |

---

## 12. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2025 | Initial specification draft |

---

*This specification defines the Ravel Narrative VM, designed for Clean Architecture and Domain-Driven Design principles.*
