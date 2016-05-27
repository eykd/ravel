class ParseError(ValueError): pass


class OutOfContextNodeError(ParseError): pass


class ComparisonParseError(ParseError): pass


class OperationParseError(ParseError): pass
