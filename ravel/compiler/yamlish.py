from collections import OrderedDict

from parsimonious import NodeVisitor, Grammar, VisitationError

from ravel.exceptions import OutOfContextNodeError
from ravel import grammars
from ravel.types import Source
from ravel.utils.strings import get_coords_of_str_index, get_line


class YamlNode:
    def __init__(self, pnode, level=None, parent=None, comments=()):
        self.pnode = pnode
        self._level = None
        self.parent = parent
        self.comments = list(comments)
        self.level = level

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, level):
        self._set_level(level)

    def _set_level(self, level):
        self._level = level

    def as_data(self, filename=''):
        raise NotImplementedError()

    def get_tip(self):
        return self

    def can_add_node(self, node):
        return False

    def add_node(self, node):
        raise NotImplementedError()

    def incorporate_node(self, node):
        if self.can_add_node(node):
            return self.add_node(node)
        else:
            if self.parent is not None:
                return self.parent.incorporate_node(node)
            else:
                self.fail_to_incorporate_node(node)

    def fail_to_incorporate_node(self, node):
        pnode = node.pnode
        pos = get_coords_of_str_index(pnode.full_text, pnode.start)
        line = get_line(pnode.full_text, pos.line)
        raise OutOfContextNodeError("Line %s, column %s:\n%s" % (pos.line, pos.column, line))


class ContainerNode(YamlNode):
    def __init__(self, pnode, value=None, **kwargs):
        self.value = value
        super().__init__(pnode, **kwargs)

    def _set_level(self, level):
        self._level = level
        if isinstance(self.value, YamlNode):
            self.value.level = level

    def as_data(self, filename=''):
        if isinstance(self.value, YamlNode):
            return self.value.as_data(filename)
        else:
            return self.value

    def get_tip(self):
        if self.value is not None and isinstance(self.value, YamlNode):
            return self.value.get_tip()
        else:
            return self

    def incorporate_node(self, node):
        if self.can_add_node(node):
            intermediary = None
            if isinstance(node, KeyValue):
                intermediary = Mapping(node.pnode)
            elif isinstance(node, ListItem):
                intermediary = List(node.pnode)

            if intermediary is not None:
                intermediary.level = node.level
                intermediary = self.incorporate_node(intermediary)
                return intermediary.incorporate_node(node)
            else:
                return super().incorporate_node(node)
        else:
            if self.parent is not None:
                return self.parent.incorporate_node(node)
            else:
                self.fail_to_incorporate_node(node)

    def can_add_node(self, node):
        return (
            self.value is None
            and (
                node.level is None
                or node.level > self.level
            )
        )

    def add_node(self, node):
        self.value = node
        node.parent = self
        if node.level is None:
            node.level = self.level
        return node.get_tip()


class ParentNode(YamlNode):
    def __init__(self, pnode, children=(), **kwargs):
        self.children = list(children)
        super().__init__(pnode, **kwargs)

    def _set_level(self, level):
        self._level = level
        for child in self.children:
            if isinstance(child, YamlNode):
                child.level = level

    def get_tip(self):
        if self.children and isinstance(self.children[-1], YamlNode):
            return self.children[-1].get_tip()
        else:
            return self

    def can_add_node(self, node):
        return node.level is None or node.level >= self.level

    def add_node(self, node):
        self.children.append(node)
        node.parent = self
        if node.level is None:
            node.level = self.level
        return node.get_tip()


class Root(ContainerNode):
    def __init__(self, pnode):
        super().__init__(pnode, level=0)

    def can_add_node(self, node):
        return (
            self.value is None
            and (
                node.level is None
                or node.level >= self.level
            )
        )


class Comment(ContainerNode):
    pass


class List(ParentNode):
    def can_add_node(self, node):
        return (
            super().can_add_node(node)
            and
            isinstance(node, ListItem)
        )

    def as_data(self, filename=''):
        return [c.as_data(filename) for c in self.children]


class ListItem(ContainerNode):
    pass


class Mapping(ParentNode):
    def can_add_node(self, node):
        return (
            super().can_add_node(node)
            and
            isinstance(node, KeyValue)
        )

    def as_data(self, filename=''):
        return OrderedDict([
            (c.key.as_data(filename), c.as_data(filename))
            for c in self.children
        ])


class KeyValue(ContainerNode):
    def __init__(self, pnode, key, **kwargs):
        self.key = key
        super().__init__(pnode, **kwargs)


class LeafNode(YamlNode):
    def __init__(self, pnode, value=None, **kwargs):
        self.value = [(pnode, value)] if value is not None else []
        super().__init__(pnode, **kwargs)

    def as_data(self, filename=''):
        start_pnode = self.value[0][0]
        end_pnode = self.value[-1][0]
        start = get_coords_of_str_index(start_pnode.full_text, start_pnode.start)
        end = get_coords_of_str_index(end_pnode.full_text, end_pnode.end)
        return Source(
            filename = filename,
            start = start,
            end = end,
            text = ' '.join([v[1] for v in self.value]),
        )

    def can_add_node(self, node):
        return (
            isinstance(node, LeafNode)
            and (
                node.level is None
                or node.level >= self.level
            )
        )

    def add_node(self, node):
        self.value.extend(node.value)
        return self.get_tip()


class YamlParser(NodeVisitor):
    grammar = Grammar(grammars.yamlish_grammar)

    def reduce_children(self, children):
        children = [c for c in children if c is not None]
        if children:
            return children if len(children) > 1 else children[0]
        else:
            return None

    def visit_blank(self, node, children):
        return None

    def visit_line(self, node, children):
        indent, value, _ = children
        if value is not None:
            value.level = indent
            return value

    def generic_visit(self, node, children):
        return self.reduce_children(children)

    def get_text(self, node, children):
        return LeafNode(node, value=node.text)

    def visit_comment(self, node, children):
        _, text = children
        return Comment(text)

    visit_text = get_text
    visit_key = get_text

    def visit_indent(self, node, children):
        return len(node.text.replace('\t', ' ' * 4).strip('\n'))

    def visit_key_value(self, node, children):
        key, _, _, value = children
        kv = KeyValue(node, key)
        kv.incorporate_node(value)
        return kv

    def visit_section(self, node, children):
        key, _ = children
        return KeyValue(node, key)

    def visit_list_item(self, node, children):
        _, _, value = children
        li = ListItem(node)
        li.incorporate_node(value)
        return li

    def visit_lines(self, node, children):
        root = Root(node)
        current = root
        for child in self.reduce_children(children):
            if isinstance(child, Comment):
                current.comments.append(child)
            else:
                current = current.incorporate_node(child)
        return root

    def parse(self, *args, **kwargs):
        try:
            return super().parse(*args, **kwargs)
        except VisitationError as e:
            # Parsimonious swallows errors inside of `visit_` handlers and
            # wraps them in VisitationError cruft.
            if e.args[0].startswith('OutOfContextNodeError'):
                # Extract the original error message, ignoring the cruft.
                msg = e.args[0].split('\n\n\n')[0].split(':', 1)[1]
                raise OutOfContextNodeError(msg)
            else:
                raise


def parse(source, filename=''):
    return YamlParser().parse(source).as_data(filename)