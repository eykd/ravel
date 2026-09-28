# Gherkin Spec Writing Guide

## Format Syntax

### File Structure

```gherkin
Feature: Scoring matching situations
  A rulebook can contain several situations whose predicates all match the
  current qualities; the most specific match should win.

  Scenario: The more specific situation is chosen
    Given a rulebook with two matching situations of different specificity
    When the situations are queried against the current qualities
    Then the more specific situation is chosen

  Scenario: A tie falls back to declaration order
    Given a rulebook with two equally specific matching situations
    When the situations are queried against the current qualities
    Then the first-declared situation is chosen
```

### Rules

- **`Feature:`** — one line naming the user story, followed by an indented narrative of a sentence or two (who wants this, why it matters)
- **`Scenario:`** — one line describing a single, independently-runnable case
- **Steps**: `Given`, `When`, `Then`, continued with `And`/`But` — capitalized, one per line, no trailing period required
- **Blank lines**: allowed between scenarios, ignored by the parser
- **`Scenario Outline:` + `Examples:`**: parameterize one scenario shape over a table of rows — use when the same Given/When/Then structure repeats with only the values changing
- **One feature file per user story**: `US<NN>-<kebab-case-title>.feature`

### Multi-Scenario Files

A single feature file can contain multiple scenarios. Each scenario binds to one pytest-bdd test function at collection time. Use multiple scenarios to cover variations of the same user story: the happy path, edge cases, and error cases as separate, independent scenarios.

## Domain Language Discipline

Specs must use the vocabulary of **`.ravel` rulebooks and what compiling/running them produces**, never the vocabulary of the compiler's or VM's implementation.

### Ravel Domain Vocabulary

| Say this                                                   | NOT this                                                |
| ------------------------------------------------------------ | ---------------------------------------------------------- |
| a rulebook containing a situation with a predicate           | a `When` clause compiled to a `compile_predicate` call      |
| the rulebook is compiled                                     | `compile_rulebook` is called                                |
| the situation with the most specific predicates is chosen    | `query_predicates` scores by `len(rule.predicates)`         |
| the situations are presented in rule order                   | the `Rule` list preserves declaration order                 |
| a situation displays a directive's text                      | a `Text` value's `handle_text` dispatch runs                |
| compilation fails with an out-of-context error naming the directive | `OutOfContextNodeError` is raised by the concept handler |
| the choice leads to a new situation                          | a `GetChoice`/`BeginChoices` pair transitions VM state       |

### Good/Bad Examples

**1. Describing preconditions**

Good:

```gherkin
Given a rulebook with two matching situations of different specificity
```

Bad:

```gherkin
Given a compiled Rule with two predicates in its predicates tuple
```

**2. Describing the action**

Good:

```gherkin
When the situations are queried against the current qualities
```

Bad:

```gherkin
When query_predicates iterates the ruleset comparing qkeys
```

**3. Describing outcomes**

Good:

```gherkin
Then the more specific situation is chosen
Then the second choice leads to the cloakroom situation
```

Bad:

```gherkin
Then query() returns the Rule with predicates=(Comparison(...),)
Then the VirtualMachine's state stack has two States
```

**4. Describing errors**

Good:

```gherkin
Given a rulebook whose situation uses an unknown directive
When it is compiled
Then compilation fails with an out-of-context error naming the directive
```

Bad:

```gherkin
When compile_directive is called
Then OutOfContextNodeError is raised with the raw directive dict
```

**5. Multi-step setup with Scenario Outline**

Good:

```gherkin
Scenario Outline: A simple predicate compiles and matches
  Given a rulebook whose situation predicate is "<predicate>"
  When it is queried against qualities "<qualities>"
  Then the situation "<matches>"

  Examples:
    | predicate        | qualities      | matches      |
    | Fumbled == 1      | Fumbled: 1     | matches      |
    | Fumbled == 1      | Fumbled: 0     | does not match |
```

Bad:

```gherkin
Given a rule is compiled via compile_predicate({"Fumbled": "== 1"})
Then the Comparison evaluates to True
```

## Spec Review Checklist

Before committing a spec file, verify:

1. **File name** matches `specs/acceptance-specs/US<NN>-<kebab-case-title>.feature`
2. **`Feature:`** line has a short narrative underneath it
3. **Keywords** are `Given`/`When`/`Then`/`And`/`But`, capitalized, at the start of the line
4. **No implementation language** — no class/function/module names, no compiler or VM internals vocabulary, no exception class names in step text
5. **Scenarios are independent** — each can run alone, in any order
6. **Outcomes are observable** — describe what compiling/querying/running the rulebook produces or raises, not internal `Rule`/VM-state shape
7. **Error cases are covered** — include at least one scenario for a malformed rulebook
8. **`Scenario Outline`** is used instead of copy-pasted near-duplicate scenarios whenever only the values differ
