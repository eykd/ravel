# -*- coding: utf-8 -*-
import re
from unittest import TestCase
from unittest.mock import Mock
import textwrap

import ensure

from ravel import yamlish as ish
from ravel.types import Pos

ensure.unittest_case.maxDiff = None

ensure = ensure.ensure


class GetLineTests(TestCase):
    def setUp(self):
        self.text = textwrap.dedent("""

        foo
            bar
                baz blah blargh
        boo
        """)

    def test_it_should_get_the_line(self):
        (ensure(ish.get_line)
         .called_with(self.text, 5)
         .equals("        baz blah blargh\n"))

    def test_it_should_get_a_blank_str_for_bad_line(self):
        (ensure(ish.get_line)
         .called_with(self.text, 99)
         .equals(""))


class GetCoordsOfStrIndexTests(TestCase):
    def setUp(self):
        self.text = textwrap.dedent("""

        foo
            bar
                baz blah blargh
        boo
        """)

    def test_returns_line_and_column_at_start_of_line(self):
        match = re.search('foo', self.text)
        start = match.start()
        (ensure(ish.get_coords_of_str_index)
         .called_with(self.text, start)
         .equals(Pos(start, 3, 0)))

    def test_returns_line_and_column_of_indented_text(self):
        match = re.search('bar', self.text)
        start = match.start()
        (ensure(ish.get_coords_of_str_index)
         .called_with(self.text, start)
         .equals(Pos(start, 4, 4)))

    def test_returns_line_and_column_of_midline_text(self):
        match = re.search('blah', self.text)
        start = match.start()
        (ensure(ish.get_coords_of_str_index)
         .called_with(self.text, start)
         .equals(Pos(start, 5, 12)))

    def test_returns_last_line_and_first_column_of_bad_index(self):
        (ensure(ish.get_coords_of_str_index)
         .called_with(self.text, len(self.text) + 5)
         .equals(Pos(len(self.text), 6, 0)))


class RootTests(TestCase):
    def setUp(self):
        self.root = ish.Root(Mock())

    def test_it_should_add_a_list(self):
        new_node = ish.List(Mock(), level=4)
        result = self.root.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.root.value).is_(new_node)
        ensure(new_node.parent).is_(self.root)

    def test_it_should_add_a_list_item_and_create_an_intervening_list(self):
        new_node = ish.ListItem(Mock(), 'foo', level=4)
        result = self.root.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.root.value).is_an(ish.List)

        ensure(result.parent).is_(self.root.value)
        ensure(self.root.value.parent).is_(self.root)

    def test_it_should_add_a_keyvalue_and_create_an_intervening_mapping(self):
        new_node = ish.KeyValue(Mock(), 'foo', value='bar', level=4)
        result = self.root.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.root.value).is_an(ish.Mapping)

        ensure(result.parent).is_(self.root.value)
        ensure(self.root.value.parent).is_(self.root)


class ListTests(TestCase):
    def setUp(self):
        self.root = ish.Root(Mock())
        self.node = self.root.add_node(ish.List(Mock()))
        self.node.level = 4

    def test_it_should_add_a_list_item_at_a_higher_level(self):
        new_node = ish.ListItem(Mock(), value='foo', level=8)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(result.parent).is_(self.node)
        ensure(self.node.children).contains(new_node)

    def test_it_should_not_add_a_list_item_at_a_lower_level(self):
        pnode = Mock(
            full_text = '    - bar\n   - foo',
            text = '- foo',
            start = 16,
        )
        new_node = ish.ListItem(pnode, value='foo', level=3)
        (ensure(self.node.incorporate_node)
         .called_with(new_node)
         .raises(ish.OutOfContextNodeError)
         )

    def test_it_should_not_add_a_keyvalue_item_at_a_higher_level(self):
        pnode = Mock(
            full_text = '    - bar\n     foo: baz',
            text = 'foo: baz',
            start = 18,
        )
        new_node = ish.KeyValue(pnode, key='foo', value='bar', level=8)
        (ensure(self.node.incorporate_node)
         .called_with(new_node)
         .raises(ish.OutOfContextNodeError)
         )


class MappingTests(TestCase):
    def setUp(self):
        self.root = ish.Root(Mock())
        self.node = self.root.add_node(ish.Mapping(Mock()))
        self.node.level = 4

    def test_it_should_add_a_keyvalue_at_a_higher_level(self):
        new_node = ish.KeyValue(Mock(), 'foo', value='bar', level=8)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(result.parent).is_(self.node)
        ensure(self.node.children).contains(new_node)

    def test_it_should_not_add_a_keyvalue_at_a_lower_level(self):
        pnode = Mock(
            full_text = '    foo: bar\n   bar: baz',
            text = 'bar: baz',
            start = 14,
        )
        new_node = ish.KeyValue(pnode, 'foo', value='bar', level=3)
        (ensure(self.node.incorporate_node)
         .called_with(new_node)
         .raises(ish.OutOfContextNodeError)
         )

    def test_it_should_not_add_a_listitem_at_a_higher_level(self):
        pnode = Mock(
            full_text = '    foo: bar\n       - baz',
            text = '- baz',
            start = 18,
        )
        new_node = ish.ListItem(pnode, value='foo', level=8)
        (ensure(self.node.incorporate_node)
         .called_with(new_node)
         .raises(ish.OutOfContextNodeError)
         )


class ListItemTests(TestCase):
    def setUp(self):
        self.root = ish.Root(Mock())
        self.level = 4
        self.node = self.root.incorporate_node(ish.ListItem(Mock(), level=self.level))

    def test_it_should_add_a_list_at_a_higher_level(self):
        new_node = ish.List(Mock(), level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_(new_node)
        ensure(new_node.parent).is_(self.node)

    def test_it_should_add_a_list_item_at_a_higher_level_and_create_an_intervening_list(self):
        new_node = ish.ListItem(Mock(), 'foo', level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_an(ish.List)
        ensure(self.node.value.level).equals(new_node.level)

        ensure(result.parent).is_(self.node.value)
        ensure(self.node.value.parent).is_(self.node)

    def test_it_should_cooperatively_add_a_list_item_at_the_same_level_to_the_parent_list(self):
        new_node = ish.ListItem(Mock(), 'foo', level=self.level)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_none()
        ensure(self.node.parent.children).has_length(2)
        ensure(self.node.parent.children[-1]).is_(new_node)

        ensure(new_node.parent).is_(self.node.parent)

    def test_it_should_add_a_keyvalue_at_a_higher_level_and_create_an_intervening_mapping(self):
        new_node = ish.KeyValue(Mock(), 'foo', value='bar', level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_an(ish.Mapping)
        ensure(self.node.value.level).equals(new_node.level)

        ensure(result.parent).is_(self.node.value)
        ensure(self.node.value.parent).is_(self.node)

    def test_it_should_add_a_keyvalue_with_no_level_and_create_an_intervening_mapping(self):
        new_node = ish.KeyValue(Mock(), 'foo', value='bar', level=None)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_an(ish.Mapping)
        ensure(self.node.value.level).equals(new_node.level)

        ensure(result.parent).is_(self.node.value)
        ensure(self.node.value.parent).is_(self.node)

    def test_it_should_add_a_leafnode(self):
        new_node = ish.LeafNode(Mock(), value='foo')
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_(new_node)
        ensure(new_node.parent).is_(self.node)


class KeyValueTests(TestCase):
    def setUp(self):
        self.root = ish.Root(Mock())
        self.level = 4
        self.node = self.root.incorporate_node(
            ish.KeyValue(Mock(), 'foo', level=self.level)
        )

    def test_it_should_add_a_list_at_a_higher_level(self):
        new_node = ish.List(Mock(), level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_(new_node)
        ensure(new_node.parent).is_(self.node)

    def test_it_should_add_a_list_item_at_a_higher_level_and_create_an_intervening_list(self):
        new_node = ish.ListItem(Mock(), 'foo', level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_an(ish.List)
        ensure(self.node.value.level).equals(new_node.level)

        ensure(result.parent).is_(self.node.value)
        ensure(self.node.value.parent).is_(self.node)

    def test_it_should_cooperatively_add_a_keyvalue_at_the_same_level_to_the_parent_mapping(self):
        new_node = ish.KeyValue(Mock(), 'bar', level=self.level)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_none()
        ensure(self.node.parent.children).has_length(2)
        ensure(self.node.parent.children[-1]).is_(new_node)

        ensure(new_node.parent).is_(self.node.parent)

    def test_it_should_add_a_keyvalue_at_a_higher_level_and_create_an_intervening_mapping(self):
        new_node = ish.KeyValue(Mock(), 'foo', value='bar', level=self.level + 4)
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_an(ish.Mapping)
        ensure(self.node.value.level).equals(new_node.level)

        ensure(result.parent).is_(self.node.value)
        ensure(self.node.value.parent).is_(self.node)

    def test_it_should_add_a_leafnode(self):
        new_node = ish.LeafNode(Mock(), value='foo')
        result = self.node.incorporate_node(new_node)
        ensure(result).is_(new_node)
        ensure(self.node.value).is_(new_node)
        ensure(new_node.parent).is_(self.node)


class YamlParserTests(TestCase):
    def setUp(self):
        self.parser = ish.YamlParser()

    def test_it_should_parse_a_simple_list(self):
        text = textwrap.dedent("""
            - foo
            - bar
            - baz
        """)
        result = self.parser.parse(text)
        ensure(result.as_data()).equals([
            ish.get_text_source(text, 'foo'),
            ish.get_text_source(text, 'bar'),
            ish.get_text_source(text, 'baz'),
        ])

    def test_it_should_parse_a_simple_mapping(self):
        text = textwrap.dedent("""
            foo: bar
            baz: boo
        """)
        result = self.parser.parse(text)
        ensure(result.as_data()).equals({
            ish.get_text_source(text, 'foo'): ish.get_text_source(text, 'bar'),
            ish.get_text_source(text, 'baz'): ish.get_text_source(text, 'boo')
        })

    def test_it_should_parse_a_nested_mapping_with_list(self):
        text = textwrap.dedent("""
            foo:
              - bar
              - baz
            blah: boo
        """)
        result = self.parser.parse(text)
        ensure(result.as_data()).equals({
            ish.get_text_source(text, 'foo'): [
                ish.get_text_source(text, 'bar'),
                ish.get_text_source(text, 'baz'),
            ],
            ish.get_text_source(text, 'blah'): ish.get_text_source(text, 'boo')
        })

    def test_it_should_parse_a_nested_list_with_mapping(self):
        text = textwrap.dedent("""
            - foo:
              - bar
              - baz
            - blah: boo
        """)
        result = self.parser.parse(text)
        ensure(result.as_data()).equals([
            {
                ish.get_text_source(text, 'foo'): [
                    ish.get_text_source(text, 'bar'),
                    ish.get_text_source(text, 'baz'),
                ],
            },
            {
                ish.get_text_source(text, 'blah'): ish.get_text_source(text, 'boo')
            }
        ])

    def test_it_should_parse_comments_and_blanks(self):
        text = textwrap.dedent("""
        # A comment
        - foo:

          - bar
          # Something else entirely
          - baz

        - blah: boo # not a comment!

        """)
        result = self.parser.parse(text)
        ensure(result.as_data()).equals([
            {
                ish.get_text_source(text, 'foo'): [
                    ish.get_text_source(text, 'bar'),
                    ish.get_text_source(text, 'baz'),
                ],
            },
            {
                ish.get_text_source(text, 'blah'): ish.get_text_source(text, 'boo # not a comment!')
            }
        ])

    def test_it_fails_parsing_weird_indentations(self):
        bad_yamlish = textwrap.dedent("""
          - foo:
              - bar
         - baz
        - blah
        """)
        (ensure(self.parser.parse)
         .called_with(bad_yamlish)
         .raises(ish.OutOfContextNodeError)
         )
