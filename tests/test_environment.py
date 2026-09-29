from unittest.mock import patch

import pytest
import syml
from hypothesis import given
from hypothesis import strategies as st

from ravel import environments, exceptions, loaders, types
from ravel.adapters.story_source import MemoryStorySource
from ravel.compiler import rulebooks
from ravel.engine.engine import start
from ravel.engine.story import Story


@pytest.fixture
def env(examples_path):
    return environments.Environment(
        loader=loaders.FileSystemLoader(base_path=examples_path / "simple"),
    )


class TestLoad:
    def test_it_should_load_the_initializing_rulebook(self, env):
        with patch.object(env, "load_rulebook") as mock_loader:
            env.load()
            mock_loader.assert_called_once_with("begin")
            env.initializing_name = "intro"
            mock_loader.reset_mock()
            env.load()
            mock_loader.assert_called_once_with("intro")


class TestGetRulebook:
    def test_it_should_load_the_rulebook_and_its_includes(self, env):
        rulebook = env.load_rulebook("begin")
        assert "begin::intro" in rulebook["rulebook"]["Situation"]["locations"]
        assert "rooms::rooms" in rulebook["rulebook"]["Situation"]["locations"]
        assert "actions::actions" in rulebook["rulebook"]["Situation"]["locations"]

        new_rulebook = env.load_rulebook("begin")
        assert new_rulebook == rulebook


class TestDefaultIsUpToDate:
    def test_it_should_return_true(self, env):
        assert env.default_is_up_to_date() is True


class TestSourcePositions:
    """Parse errors must name the file and line the bad text came from.

    The syml 0.6 upgrade routed loading through ``syml.loads``, which flattens
    every node to a bare ``str`` via ``as_data()``, so ``raise_parse_error``
    could no longer report a position. Loading through ``as_source()`` keeps the
    ``Source`` objects, and the predicate targets must reach
    ``compile_predicate`` unflattened for the position to survive.
    """

    SOURCE = "\n".join(
        [
            "when:",
            "  - this is not a comparison at all",
            "",
            "intro:",
            "",
            "  - Some text.",
        ]
    )

    def test_it_should_report_the_file_and_line_of_a_bad_predicate(self, env):
        with pytest.raises(exceptions.ComparisonParseError) as excinfo:
            env.compile_rulebook(self.SOURCE, name="broken")

        message, position = excinfo.value.args
        assert position.filename == "broken"
        assert position.start.line == 2
        assert position.text == "this is not a comparison at all"
        assert "broken" in message
        assert "Line 2" in message


class TestInjectedLoader:
    def test_it_should_require_a_loader(self):
        with pytest.raises(TypeError):
            environments.Environment()  # type: ignore[call-arg]

    def test_it_should_reject_a_loader_without_a_callable_load(self):
        with pytest.raises(TypeError) as excinfo:
            environments.Environment(loader=object())

        assert str(excinfo.value) == "Environment loader must have a callable load(); got object"

    def test_it_should_not_import_the_loaders_module(self):
        assert "loaders" not in vars(environments)


class CountingLoader(loaders.MemoryLoader):
    """A ``MemoryLoader`` that records each rulebook name it is asked to load, in order."""

    def __init__(self, sources):
        super().__init__(sources)
        self.loaded: list[str] = []

    def get_source(self, environment, name):
        self.loaded.append(name)
        return super().get_source(environment, name)


def include_rulebook(*names, body="intro:\n  - Hi[.] there.\n"):
    return "include:\n%s\n%s" % ("".join("  - %s\n" % n for n in names), body)


class TestIncludeOrder:
    """FR-010 / R1: cycles are allowed, each rulebook loads once, breadth-first."""

    def test_it_should_compile_a_two_rulebook_cycle_once_each(self):
        loader = CountingLoader({"A": include_rulebook("B"), "B": include_rulebook("A")})
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B"]

    def test_it_should_compile_a_three_rulebook_cycle_once_each_in_order(self):
        loader = CountingLoader(
            {"A": include_rulebook("B"), "B": include_rulebook("C"), "C": include_rulebook("A")},
        )
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B", "C"]

    def test_it_should_load_breadth_first(self):
        loader = CountingLoader(
            {
                "A": include_rulebook("B", "C"),
                "B": include_rulebook("D"),
                "C": "intro:\n  - Hi[.] there.\n",
                "D": "intro:\n  - Hi[.] there.\n",
            },
        )
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B", "C", "D"]

    def test_it_should_concatenate_givens_in_load_order_so_later_values_win(self):
        loader = CountingLoader(
            {
                "A": "include:\n  - B\ngiven:\n  - Mood = 1\nintro:\n  - Hi[.] there.\n",
                "B": "given:\n  - Mood = 2\nintro:\n  - Hi[.] there.\n",
            },
        )
        rulebook = environments.Environment(loader=loader, initializing_name="A").load()
        state = start(Story.from_rulebook(rulebook)).state
        assert state.qualities.get("Mood") == 2


def _nested_choice_source(depth, separator=""):
    lines = ["rule:"]
    column = 2
    for _ in range(depth):
        lines.append(" " * column + "- choice:")
        column += 4
        lines.append(" " * column + "- Intro.%sz" % separator)
    return "\n".join(lines) + "\n"


# Every code point str.splitlines() or str.isspace() treats specially that syml does not: syml breaks
# lines on \n only (after normalising \r\n and \r) and indents with spaces only.
NON_SYML_LINE_BREAKS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]
NON_SYML_INDENT_WHITESPACE = [
    "\t",
    "\xa0",
    "\u1680",
    *(chr(code) for code in range(0x2000, 0x200B)),
    "\u202f",
    "\u205f",
    "\u3000",
]
NON_SYML_SEPARATORS = NON_SYML_LINE_BREAKS + NON_SYML_INDENT_WHITESPACE
NON_SYML_SEPARATORS_EXCEPT_TAB = [c for c in NON_SYML_SEPARATORS if c != "\t"]


def _syml_data_depth(source):
    """Return the nesting depth of syml's parsed data for ``source``, walked iteratively."""
    deepest = 0
    pending = [(syml.parsers.parse(source).as_data(), 1)]
    while pending:
        node, depth = pending.pop()
        if isinstance(node, dict):
            children = list(node.values())
        elif isinstance(node, list):
            children = node
        else:
            continue
        deepest = max(deepest, depth)
        pending.extend((child, depth + 1) for child in children)
    return deepest


class TestSourceNestingDepth:
    def test_it_should_count_indentation_levels_ignoring_blanks_and_comments(self):
        source = "a:\n\n# comment\n  - b:\n//  comment\n      - c\n  - d\n"
        assert environments._source_nesting_depth(source) == 4 == _syml_data_depth(source)

    @pytest.mark.parametrize("marker", ["#", "//"])
    def test_it_should_count_an_indented_comment_marker_as_content(self, marker):
        # syml only treats # and // as comments at column 0; indented, they are text at that column.
        source = "a:\n  - b\n    %s not a comment\n" % marker
        assert environments._source_nesting_depth(source) == 3

    # A tab in leading whitespace is a syml TabIndentationError instead (see the syntax-error test below).
    @pytest.mark.parametrize("separator", NON_SYML_SEPARATORS_EXCEPT_TAB, ids=lambda c: "U+%04X" % ord(c))
    def test_it_should_not_count_non_space_whitespace_as_indentation(self, separator):
        source = "a:\n  - b\n  %s- c\n" % separator
        assert environments._source_nesting_depth(source) == 2

    @pytest.mark.parametrize("separator", NON_SYML_SEPARATORS, ids=lambda c: "U+%04X" % ord(c))
    def test_it_should_agree_with_syml_when_a_label_holds_a_non_syml_separator(self, separator):
        clean = _nested_choice_source(20)
        injected = _nested_choice_source(20, separator)

        assert environments._source_nesting_depth(injected) == environments._source_nesting_depth(clean)
        assert _syml_data_depth(injected) == _syml_data_depth(clean)

    @pytest.mark.parametrize("line_ending", ["\r\n", "\r"], ids=["CRLF", "CR"])
    def test_it_should_break_lines_on_carriage_returns_like_syml(self, line_ending):
        source = _nested_choice_source(20).replace("\n", line_ending)
        assert environments._source_nesting_depth(source) == environments._source_nesting_depth(
            _nested_choice_source(20)
        )

    def test_it_should_ignore_a_leading_byte_order_mark_like_syml(self):
        source = "\ufeff" + _nested_choice_source(3)
        assert environments._source_nesting_depth(source) == environments._source_nesting_depth(
            _nested_choice_source(3)
        )

    @given(
        depth=st.integers(min_value=1, max_value=12),
        separators=st.lists(st.sampled_from(NON_SYML_SEPARATORS), min_size=1, max_size=4),
    )
    def test_a_non_syml_separator_in_labels_never_lowers_the_depth(self, depth, separators):
        injected = _nested_choice_source(depth, "".join(separators))
        assert environments._source_nesting_depth(injected) == environments._source_nesting_depth(
            _nested_choice_source(depth)
        )

    @pytest.mark.parametrize("separator", NON_SYML_LINE_BREAKS, ids=lambda c: "U+%04X" % ord(c))
    def test_it_should_refuse_190_nested_choices_with_a_separator_in_each_label(self, separator):
        # ravel-h6v.30: a separator per label used to reset the scanner, so 190 nested choices
        # (~380 real indentation levels) loaded past the 128-level cap.
        with pytest.raises(exceptions.ParseError, match="'begin'.*maximum supported is 128"):
            MemoryStorySource({"begin": _nested_choice_source(190, separator)}).load()

    def test_it_should_raise_parse_error_naming_the_rulebook_for_deep_nesting(self, env):
        source = _nested_choice_source(300)

        with pytest.raises(exceptions.ParseError, match="'deep'.*maximum supported is 128"):
            env.compile_rulebook(source, "deep")

    def test_it_should_raise_parse_error_from_environment_load_via_memory_source(self):
        with pytest.raises(exceptions.ParseError, match="'begin'"):
            MemoryStorySource({"begin": _nested_choice_source(300)}).load()

    @pytest.mark.parametrize(
        "source",
        [
            "foo:\n    - Price: 5 [approx\n",
            "foo:\n    - Intro.\n    - choice: [x\n        - Hi.\n",
        ],
        ids=["intro-line", "choice-label"],
    )
    def test_it_should_raise_parse_error_for_an_unclosed_bracket_via_memory_source(self, source):
        with pytest.raises(exceptions.ParseError, match="Invalid intro text"):
            MemoryStorySource({"begin": source}).load()

    @pytest.mark.parametrize("line", ["a <> b", "{x == 1} a <> b"])
    def test_it_should_raise_parse_error_for_mid_line_glue_via_memory_source(self, line):
        with pytest.raises(exceptions.ParseError, match="Invalid text line"):
            MemoryStorySource({"begin": "foo:\n    - Intro.\n    - %s\n" % line}).load()

    @pytest.mark.parametrize(
        ("source", "syml_error", "message"),
        [
            ("r:\n\t- hi\n", syml.exceptions.TabIndentationError, "begin:2:0: A tab character"),
            ("a: 1\na: 2\n", syml.exceptions.DuplicateKeyError, "begin:2:0: Duplicate key 'a'"),
            ("a:\n  b\n c\n", syml.exceptions.OutOfContextNodeError, "begin:3:1: Line 3"),
        ],
    )
    def test_it_should_wrap_syml_syntax_errors_as_parse_error(self, source, syml_error, message):
        with pytest.raises(exceptions.ParseError, match=message) as excinfo:
            MemoryStorySource({"begin": source}).load()

        assert isinstance(excinfo.value.__cause__, syml_error)

    @pytest.mark.parametrize(
        ("source", "message"),
        [
            ("", "A rulebook must be a mapping"),
            ("# c", "A rulebook must be a mapping"),
            ("hello", "A rulebook must be a mapping"),
            ("- a", "A rulebook must be a mapping"),
            ("foo: bar", "Rule .*foo.* must be a non-empty list"),
            ("foo:", "Rule .*foo.* must be a non-empty list"),
            ("foo:\n    a: b", "Rule .*foo.* must be a non-empty list"),
            ("foo:\n    a: a: hi", "Rule .*foo.* must be a non-empty list"),
            ("about: x", "`about` must be a mapping"),
            ("about:\n    - a", "`about` must be a mapping"),
        ],
    )
    def test_it_should_raise_parse_error_for_badly_shaped_rulebooks(self, source, message):
        with pytest.raises(exceptions.ParseError, match=message):
            MemoryStorySource({"begin": source}).load()

    @pytest.mark.parametrize(
        "source",
        [
            "- - - x\n",
            "-\n",
            "- -\n",
            "-  \t - x\n",
            "a:\n  - - b: c\n    - d\n",
            "- a: b\n  c: d\n",
            "- - k:\n      - v\n",
            "a: - b: - c: d\n",
            "a:\n  - k: - - v\n",
        ],
    )
    def test_it_should_count_inline_list_markers_and_keys_as_levels_like_syml(self, source):
        assert environments._source_nesting_depth(source) == _syml_data_depth(source)

    @given(
        markers=st.integers(min_value=0, max_value=25),
        tail=st.sampled_from(["", "x", "k:", "k: v", "k: - v", "-x"]),
        indent=st.integers(min_value=0, max_value=3),
        spacing=st.sampled_from([" ", "  ", " \t"]),
    )
    def test_the_gate_never_undercounts_a_single_inline_chain(self, markers, tail, indent, spacing):
        source = "a:\n" + " " * (indent + 1) + ("-" + spacing) * markers + tail + "\n"
        assert environments._source_nesting_depth(source) >= _syml_data_depth(source)

    def test_it_should_refuse_a_one_line_chain_of_more_than_the_marker_cap(self):
        source = "- " * (environments.MAX_INLINE_LIST_MARKERS + 1) + "x\n"
        with pytest.raises(exceptions.ParseError, match="'begin'.*maximum supported is 64") as info:
            MemoryStorySource({"begin": source}).load()
        assert not isinstance(info.value.__cause__, RecursionError)

    @pytest.mark.parametrize("stack_depth", [0, 300])
    @pytest.mark.parametrize("indent_levels", [0, 32, environments.MAX_SOURCE_NESTING_DEPTH - 64])
    def test_it_should_load_a_one_line_chain_at_the_marker_cap_without_the_recursion_backstop(
        self, indent_levels, stack_depth
    ):
        keys = "".join(" " * i + "k%d:\n" % i for i in range(indent_levels))
        source = keys + " " * indent_levels + "- " * environments.MAX_INLINE_LIST_MARKERS + "x\n"
        assert environments._source_nesting_depth(source) <= environments.MAX_SOURCE_NESTING_DEPTH

        def load_deep(remaining):
            if remaining:
                return load_deep(remaining - 1)
            return MemoryStorySource({"begin": source}).load()

        with pytest.raises(exceptions.ParseError) as info:
            load_deep(stack_depth)
        assert not isinstance(info.value.__cause__, RecursionError)
        assert "nested too deeply" not in str(info.value)

    def test_it_should_refuse_a_deep_indentation_chain_past_the_depth_cap(self):
        source = "".join(" " * i + "k%d:\n" % i for i in range(environments.MAX_SOURCE_NESTING_DEPTH + 1))
        with pytest.raises(exceptions.ParseError, match="maximum supported is 128"):
            MemoryStorySource({"begin": source}).load()

    def test_it_should_accept_nesting_at_the_limit(self, env):
        source = "a:\n" + "".join(" " * (i + 1) + "b:\n" for i in range(environments.MAX_SOURCE_NESTING_DEPTH - 1))
        assert environments._source_nesting_depth(source) == environments.MAX_SOURCE_NESTING_DEPTH

    def test_it_should_convert_a_syml_recursion_error_to_parse_error(self, env, monkeypatch):
        def explode(*args, **kwargs):
            raise RecursionError

        monkeypatch.setattr(environments.syml.parsers, "parse", explode)

        with pytest.raises(exceptions.ParseError, match="'x' is nested too deeply"):
            env.compile_rulebook("a: b\n", "x")

    def test_it_should_label_an_unnamed_rulebook(self, env, monkeypatch):
        monkeypatch.setattr(environments.syml.parsers, "parse", lambda *a, **k: (_ for _ in ()).throw(RecursionError()))

        with pytest.raises(exceptions.ParseError, match="<rulebook>"):
            env.compile_rulebook("a: b\n")


class TestMergedRuleOrder:
    """The merge in ``load_rulebook`` orders rules with the same key ``compile_rulebook`` uses."""

    @staticmethod
    def _rule(name, operand):
        comparison = types.Comparison("x", ">", operand)
        return types.Rule(name, [types.Predicate("x", comparison)])

    def test_it_should_order_mixed_type_operands_on_a_name_tie_without_raising(self):
        number = self._rule("R", 1)
        reference = self._rule("R", types.QualityRef("y"))
        rulebooks_by_name = {
            "A": {
                "includes": ["B"],
                "metadata": {},
                "givens": [],
                "rulebook": {"c": {"rules": [reference], "locations": {}}},
            },
            "B": {
                "includes": [],
                "metadata": {},
                "givens": [],
                "rulebook": {"c": {"rules": [number], "locations": {}}},
            },
        }
        env = environments.Environment(loader=loaders.MemoryLoader({}), initializing_name="A")
        with patch.object(env, "get_rulebook", side_effect=rulebooks_by_name.__getitem__):
            merged = env.load()["rulebook"]["c"]["rules"]
        assert merged == sorted([reference, number], key=rulebooks.rule_sort_key)
        assert merged == [number, reference]

    def test_it_should_sort_with_the_shared_key_at_both_sites(self):
        with patch.object(rulebooks, "rule_sort_key", wraps=rulebooks.rule_sort_key) as key:
            env = environments.Environment(
                loader=loaders.MemoryLoader({"A": include_rulebook("B"), "B": "intro:\n  - Hi[.] there.\n"}),
                initializing_name="A",
            )
            env.load()
        assert key.call_count > 0
