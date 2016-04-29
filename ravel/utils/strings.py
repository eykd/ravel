

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
