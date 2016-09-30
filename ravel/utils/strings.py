import re

from ..types import Source, Pos


def get_text_source(text, substring, source_text=None, filename=''):
    match = re.search(substring, text)
    return Source(
        filename = '',
        start = get_coords_of_str_index(text, match.start()),
        end = get_coords_of_str_index(text, match.end()),
        text = match.group() if source_text is None else source_text
    )


def get_coords_of_str_index(s, index):
    """Get (line_number, col) of `index` in `string`.

    Based on http://stackoverflow.com/a/24495900
    """
    lines = s.splitlines(True)
    curr_pos = 0
    for linenum, line in enumerate(lines):
        if curr_pos + len(line) > index:
            return Pos(index, linenum + 1, index - curr_pos)
        curr_pos += len(line)
    return Pos(len(s), linenum + 1, 0)


def get_line(s, line_number):
    try:
        return s.splitlines(True)[line_number - 1]
    except IndexError:
        return ''


def get_text(text_or_source):
    if isinstance(text_or_source, Source):
        return text_or_source.text
    else:
        return text_or_source


def strip_outer_whitespace(text):
    """Strip surrounding blank lines in a multiline string.

    This does not affect first-line indentation, or trailing whitespace on the
    last line.
    """
    lines = text.rstrip().splitlines()
    i = 0
    try:
        while not lines[i].strip():
            i += 1
    except IndexError:
        i -= 1
    return '\n'.join(lines[i:])
