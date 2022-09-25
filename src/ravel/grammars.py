import textwrap

base_expression_grammar = textwrap.dedent(
    r"""
    quality               = bracketed_quality / quoted_quality / simple_quality
    quoted_quality        = ~'"[^"]+"'
    simple_quality        = ~'[^\s]+'
    bracketed_quality     = ~'\[[^\]]+\]'

    expression            = additive
    additive              = (multiplicative ws? (add / subtract) ws? additive)
                            / multiplicative
    multiplicative        = (divisive ws? multiply ws? multiplicative)
                            / divisive
    divisive              = (primary ws? (floor_div / divide / modulus) ws? divisive)
                            / primary
    primary               = value / (open_paren ws? additive ws? close_paren)


    open_paren            = "("
    close_paren           = ")"

    add                   = "+"
    subtract              = "-"
    multiply              = "*"
    floor_div             = "//"
    divide                = "/"
    modulus               = "%"

    setter                = set_add / set_subtract / set_multiply / set_floor_div / set_divide / set_modulus / set
    set                   = "="
    set_add               = add set
    set_subtract          = subtract set
    set_multiply          = multiply set
    set_floor_div         = floor_div set
    set_divide            = divide set
    set_modulus           = modulus set

    constraint            = (max / min) ws number
    max                   = "max"
    min                   = "min"

    comparator            = gte / gt / lte / lt / ne / eq
    gte                   = ">="
    gt                    = ">"
    lte                   = "<="
    lt                    = "<"
    ne                    = "!="
    eq                    = "==" / "="

    ws                    = ~"\s+"
    end                   = ~"\s*$"

    value                 = number / string / qvalue / bracketed_quality

    qvalue                = "value"

    number                = float / integer
    float                 = ~"\d+\.\d*"
    integer               = ~"\d+"

    string                = ('"""
    + '"""'
    + r"""' ~'([^"])+' '"""
    + '"""'
    + r"""')
                            / ("'''" ~"([^'])+" "'''")
                            / ("```" ~"([^`])+" "```")
                            / ('"' ~'([^"])+' '"')
                            / ("'" ~"([^'])+" "'")
                            / ("`" ~"([^`])+" "`")
"""
)


operation_grammar = (
    textwrap.dedent(
        """
    operation = ws? quality ws setter ws (expression (ws constraint)?) ws?
    """
    )
    + base_expression_grammar
)


comparison_grammar = (
    textwrap.dedent(
        """
    comparison = ws? quality ws comparator ws expression ws?
    """
    )
    + base_expression_grammar
)


intro_text_grammar = textwrap.dedent(
    r"""
    intro       = head (suffix tail)?

    head        = ~"[^\[]*"
    suffix      = "[" ~"[^\]]*" "]"
    tail        = ~".*"
"""
)


plain_text_grammar = (
    textwrap.dedent(
        r"""
    line        = cmp_prefix? text glue?

    text        = ~"(?:(?!<>).)*"
    glue        = "<>"
    eol         = "\n" / ~"$"

    cmp_prefix  = "{" comparison "}"
"""
    )
    + comparison_grammar
)
