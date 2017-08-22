import ast

import pydot

from astmonkey import utils


class GraphNodeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.graph = pydot.Dot(graph_type='graph', **self._dot_graph_kwargs())

    def visit(self, node):
        if len(node.parents) <= 1:
            self.graph.add_node(self._dot_node(node))
        if len(node.parents) == 1:
            self.graph.add_edge(self._dot_edge(node))
        super(GraphNodeVisitor, self).visit(node)

    def _dot_graph_kwargs(self):
        return {}

    def _dot_node(self, node):
        return pydot.Node(str(node), label=self._dot_node_label(node), **self._dot_node_kwargs(node))

    def _dot_node_label(self, node):
        fields_labels = []
        for field, value in ast.iter_fields(node):
            if not isinstance(value, list):
                value_label = self._dot_node_value_label(value)
                if value_label:
                    fields_labels.append('{0}={1}'.format(field, value_label))
        return 'ast.{0}({1})'.format(node.__class__.__name__, ', '.join(fields_labels))

    def _dot_node_value_label(self, value):
        if not isinstance(value, ast.AST):
            return repr(value)
        elif len(value.parents) > 1:
            return self._dot_node_label(value)
        return None

    def _dot_node_kwargs(self, node):
        return {
            'shape': 'box',
            'fontname': 'Curier'
        }

    def _dot_edge(self, node):
        return pydot.Edge(str(node.parent), str(node), label=self._dot_edge_label(node), **self._dot_edge_kwargs(node))

    def _dot_edge_label(self, node):
        label = node.parent_field
        if not node.parent_field_index is None:
            label += '[{0}]'.format(node.parent_field_index)
        return label

    def _dot_edge_kwargs(self, node):
        return {
            'fontname': 'Curier'
        }


"""
    Source generator node visitor from Python AST was originaly written by Armin Ronacher (2008), license BSD.
"""

BOOLOP_SYMBOLS = {
    ast.And: 'and',
    ast.Or: 'or'
}

BINOP_SYMBOLS = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.Div: '/',
    ast.FloorDiv: '//',
    ast.Mod: '%',
    ast.LShift: '<<',
    ast.RShift: '>>',
    ast.BitOr: '|',
    ast.BitAnd: '&',
    ast.BitXor: '^',
    ast.Pow: '**'
}

CMPOP_SYMBOLS = {
    ast.Eq: '==',
    ast.Gt: '>',
    ast.GtE: '>=',
    ast.In: 'in',
    ast.Is: 'is',
    ast.IsNot: 'is not',
    ast.Lt: '<',
    ast.LtE: '<=',
    ast.NotEq: '!=',
    ast.NotIn: 'not in'
}

UNARYOP_SYMBOLS = {
    ast.Invert: '~',
    ast.Not: 'not',
    ast.UAdd: '+',
    ast.USub: '-'
}

ALL_SYMBOLS = {}
ALL_SYMBOLS.update(BOOLOP_SYMBOLS)
ALL_SYMBOLS.update(BINOP_SYMBOLS)
ALL_SYMBOLS.update(CMPOP_SYMBOLS)
ALL_SYMBOLS.update(UNARYOP_SYMBOLS)


def to_source(node, indent_with=' ' * 4):
    """This function can convert a node tree back into python sourcecode.
    This is useful for debugging purposes, especially if you're dealing with
    custom asts not generated by python itself.

    It could be that the sourcecode is evaluable when the AST itself is not
    compilable / evaluable.  The reason for this is that the AST contains some
    more data than regular sourcecode does, which is dropped during
    conversion.

    Each level of indentation is replaced with `indent_with`.  Per default this
    parameter is equal to four spaces as suggested by PEP 8, but it might be
    adjusted to match the application's styleguide.
    """
    generator = SourceGeneratorNodeVisitor(indent_with)
    generator.visit(node)

    return ''.join(generator.result)


class BaseSourceGeneratorNodeVisitor(ast.NodeVisitor):
    """This visitor is able to transform a well formed syntax tree into python
    sourcecode.  For more details have a look at the docstring of the
    `node_to_source` function.
    """

    def __init__(self, indent_with):
        self.result = []
        self.indent_with = indent_with
        self.indentation = 0
        self.new_line = False

    @classmethod
    def _is_node_args_valid(cls, node, arg_name):
        return hasattr(node, arg_name) and getattr(node, arg_name) is not None

    def write(self, x, node=None):
        self.correct_line_number(node)
        self.result.append(x)

    def correct_line_number(self, node):
        if self.new_line:
            self.write_newline()
        if node and self._is_node_args_valid(node, 'lineno'):
            self.add_missing_lines(node)

    def add_missing_lines(self, node):
        lines = len("".join(self.result).split('\n')) if self.result else 0
        line_diff = node.lineno - lines
        if line_diff:
            [self.write_newline() for _ in range(line_diff)]

    def write_newline(self):
        if self.result:
            self.result.append('\n')
        self.result.append(self.indent_with * self.indentation)
        self.new_line = False

    def newline(self, node=None):
        self.new_line = True
        self.correct_line_number(node)

    def body(self, statements):
        self.new_line = True
        self.indentation += 1
        for stmt in statements:
            self.visit(stmt)
        self.indentation -= 1

    def body_or_else(self, node):
        self.body(node.body)
        if node.orelse:
            self.newline()
            self.write('else:')
            self.body(node.orelse)

    def docstring(self, node):
        self.write('"""{0}"""'.format(node.s))

    def signature(self, node):
        want_comma = []

        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        padding = [None] * (len(node.args) - len(node.defaults))
        for arg, default in zip(node.args, padding + node.defaults):
            self.signature_arg(arg, default, write_comma)
        self.signature_vararg(node, write_comma)
        self.signature_kwarg(node, write_comma)

    def signature_kwarg(self, node, write_comma):
        if node.kwarg is not None:
            write_comma()
            self.write('**' + node.kwarg)

    def signature_vararg(self, node, write_comma):
        if node.vararg is not None:
            write_comma()
            self.write('*' + node.vararg)

    def signature_arg(self, arg, default, write_comma):
        write_comma()
        self.visit(arg)
        if default is not None:
            self.write('=')
            self.visit(default)

    def decorators(self, node):
        for decorator in node.decorator_list:
            self.newline(decorator)
            self.write('@')
            self.visit(decorator)

    # Statements

    def visit_Assign(self, node):
        self.newline(node)
        for idx, target in enumerate(node.targets):
            if idx:
                self.write(' = ')
            self.visit(target)
        self.write(' = ')
        self.visit(node.value)

    def visit_AugAssign(self, node):
        self.newline(node)
        self.visit(node.target)
        self.write(' ' + BINOP_SYMBOLS[type(node.op)] + '= ')
        self.visit(node.value)

    def visit_ImportFrom(self, node):
        self.newline(node)

        imports = []
        for alias in node.names:
            name = alias.name
            if alias.asname:
                name += ' as ' + alias.asname
            imports.append(name)
        self.write('from {0}{1} import {2}'.format('.' * node.level, node.module or '', ', '.join(imports)))

    def visit_Import(self, node):
        self.newline(node)
        for item in node.names:
            self.write('import ')
            self.visit(item)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Str):
            self.docstring(node.value)
        else:
            self.newline(node)
            self.generic_visit(node)

    def visit_keyword(self, node):
        if self._is_node_args_valid(node, 'arg'):
            self.write(node.arg + '=')
        else:
            self.write('**')
        self.visit(node.value)

    def visit_FunctionDef(self, node):
        self.function_definition(node)

    def function_definition(self, node, prefixes=()):
        self.decorators(node)
        self.newline(node)
        self._prefixes(prefixes)
        self.write('def %s(' % node.name, node)
        self.signature(node.args)
        self.write('):')
        self.body(node.body)

    def _prefixes(self, prefixes):
        self.write(' '.join(prefixes))
        if prefixes:
            self.write(' ')

    def visit_ClassDef(self, node):
        have_args = []

        def paren_or_comma():
            if have_args:
                self.write(', ')
            else:
                have_args.append(True)
                self.write('(')

        self.decorators(node)
        self.newline(node)
        self.write('class %s' % node.name, node)
        for base in node.bases:
            paren_or_comma()
            self.visit(base)
        self.write(have_args and '):' or ':')
        self.body(node.body)

    def visit_If(self, node):
        self.newline(node)
        self.write('if ')
        self.visit(node.test)
        self.write(':')
        self.body(node.body)
        while node.orelse:
            else_ = node.orelse
            if len(else_) == 1 and isinstance(else_[0], ast.If):
                node = else_[0]
                self.newline()
                self.write('elif ')
                self.visit(node.test)
                self.write(':')
                self.body(node.body)
            else:
                self.newline()
                self.write('else:')
                self.body(else_)
                break

    def visit_For(self, node):
        self.for_loop(node)

    def for_loop(self, node, prefixes=()):
        self.newline(node)
        self._prefixes(prefixes)
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.body_or_else(node)

    def visit_While(self, node):
        self.newline(node)
        self.write('while ')
        self.visit(node.test)
        self.write(':')
        self.body_or_else(node)

    def visit_Pass(self, node):
        self.newline(node)
        self.write('pass', node)

    def visit_Print(self, node):
        self.newline(node)
        self.write('print ')
        want_comma = False
        if node.dest is not None:
            self.write('>> ')
            self.visit(node.dest)
            want_comma = True
        for value in node.values:
            if want_comma:
                self.write(', ')
            self.visit(value)
            want_comma = True
        if not node.nl:
            self.write(',')

    def visit_Delete(self, node):
        self.newline(node)
        self.write('del ')

        for target in node.targets:
            self.visit(target)
            if target is not node.targets[-1]:
                self.write(', ')

    def visit_Global(self, node):
        self.newline(node)
        self.write('global ' + ', '.join(node.names))

    def visit_Nonlocal(self, node):
        self.newline(node)
        self.write('nonlocal ' + ', '.join(node.names))

    def visit_Return(self, node):
        self.newline(node)
        self.write('return')
        if node.value:
            self.write(' ')
            self.visit(node.value)

    def visit_Break(self, node):
        self.newline(node)
        self.write('break')

    def visit_Continue(self, node):
        self.newline(node)
        self.write('continue')

    def visit_Raise(self, node):
        self.newline(node)
        self.write('raise')
        if self._is_node_args_valid(node, 'exc'):
            self.raise_exc(node)
        elif self._is_node_args_valid(node, 'type'):
            self.raise_type(node)

    def raise_type(self, node):
        self.write(' ')
        self.visit(node.type)
        if node.inst is not None:
            self.write(', ')
            self.visit(node.inst)
        if node.tback is not None:
            self.write(', ')
            self.visit(node.tback)

    def raise_exc(self, node):
        self.write(' ')
        self.visit(node.exc)
        if node.cause is not None:
            self.write(' from ')
            self.visit(node.cause)

    # Expressions

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.write('.' + node.attr)

    def visit_Call(self, node):
        self.visit(node.func)
        self.write('(')
        self.call_signature(node)
        self.write(')')

    def call_signature(self, node):
        want_comma = []

        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)
        for arg in node.args:
            write_comma()
            self.visit(arg)
        for keyword in node.keywords:
            write_comma()
            self.visit(keyword)
        if self._is_node_args_valid(node, 'starargs'):
            write_comma()
            self.write('*')
            self.visit(node.starargs)
        if self._is_node_args_valid(node, 'kwargs'):
            write_comma()
            self.write('**')
            self.visit(node.kwargs)

    def visit_Name(self, node):
        self.write(node.id, node)

    def visit_str(self, node):
        self.write(node)

    def visit_Str(self, node):
        self.write(repr(node.s))

    def visit_Bytes(self, node):
        self.write(repr(node.s))

    def visit_Num(self, node):
        self.write(repr(node.n))

    def visit_Tuple(self, node):
        self.write('(')
        idx = -1
        for idx, item in enumerate(node.elts):
            if idx:
                self.write(', ')
            self.visit(item)
        self.write(idx and ')' or ',)')

    def sequence_visit(left, right):  # @NoSelf
        def visit(self, node):
            self.write(left)
            for idx, item in enumerate(node.elts):
                if idx:
                    self.write(', ')
                self.visit(item)
            self.write(right)

        return visit

    visit_List = sequence_visit('[', ']')
    visit_Set = sequence_visit('{', '}')
    del sequence_visit

    def visit_Dict(self, node):
        self.write('{')
        for idx, (key, value) in enumerate(zip(node.keys, node.values)):
            if idx:
                self.write(', ')
            if key:
                self.visit(key)
                self.write(': ')
            else:
                self.write('**')
            self.visit(value)
        self.write('}')

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.write(' %s ' % BINOP_SYMBOLS[type(node.op)])
        self.visit(node.right)

    def visit_BoolOp(self, node):
        self.write('(')
        for idx, value in enumerate(node.values):
            if idx:
                self.write(' %s ' % BOOLOP_SYMBOLS[type(node.op)])
            self.visit(value)
        self.write(')')

    def visit_Compare(self, node):
        # self.write('(')
        self.visit(node.left)
        for op, right in zip(node.ops, node.comparators):
            self.write(' %s ' % CMPOP_SYMBOLS[type(op)])
            self.visit(right)
            # self.write(')')

    def visit_UnaryOp(self, node):
        self.write('(')
        op = UNARYOP_SYMBOLS[type(node.op)]
        self.write(op)
        if op == 'not':
            self.write(' ')
        self.visit(node.operand)
        self.write(')')

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.write('[')
        self.visit(node.slice)
        self.write(']')

    def visit_Slice(self, node):
        self.slice_lower(node)
        self.write(':')
        self.slice_upper(node)
        self.slice_step(node)

    def slice_step(self, node):
        if node.step is not None:
            self.write(':')
            if not (isinstance(node.step, ast.Name) and node.step.id == 'None'):
                self.visit(node.step)

    def slice_upper(self, node):
        if node.upper is not None:
            self.visit(node.upper)

    def slice_lower(self, node):
        if node.lower is not None:
            self.visit(node.lower)

    def visit_ExtSlice(self, node):
        for idx, item in enumerate(node.dims):
            if idx:
                self.write(',')
            self.visit(item)

    def visit_Yield(self, node):
        self.write('yield')
        if node.value:
            self.write(' ')
            self.visit(node.value)

    def visit_Lambda(self, node):
        self.write('lambda ')
        self.signature(node.args)
        self.write(': ')
        self.visit(node.body)

    def visit_Ellipsis(self, node):
        self.write('...')

    def generator_visit(left, right):  # @NoSelf
        def visit(self, node):
            self.write(left)
            self.visit(node.elt)
            for comprehension in node.generators:
                self.visit(comprehension)
            self.write(right)

        return visit

    visit_ListComp = generator_visit('[', ']')
    visit_GeneratorExp = generator_visit('(', ')')
    visit_SetComp = generator_visit('{', '}')
    del generator_visit

    def visit_DictComp(self, node):
        self.write('{')
        self.visit(node.key)
        self.write(': ')
        self.visit(node.value)
        for comprehension in node.generators:
            self.visit(comprehension)
        self.write('}')

    def visit_IfExp(self, node):
        self.visit(node.body)
        self.write(' if ')
        self.visit(node.test)
        self.write(' else ')
        self.visit(node.orelse)

    def visit_Starred(self, node):
        self.write('*')
        self.visit(node.value)

    def visit_Repr(self, node):
        self.write('`')
        self.visit(node.value)
        self.write('`')

    # Helper Nodes

    def visit_alias(self, node):
        self.write(node.name)
        if node.asname is not None:
            self.write(' as ' + node.asname)

    def visit_comprehension(self, node):
        self.write(' for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        if node.ifs:
            for if_ in node.ifs:
                self.write(' if ')
                self.visit(if_)

    def visit_ExceptHandler(self, node):
        self.newline(node)
        self.write('except')
        if node.type is not None:
            self.write(' ')
            self.visit(node.type)
            if node.name is not None:
                self.write(' as ')
                self.visit(node.name)
        self.write(':')
        self.body(node.body)

    def visit_arg(self, node):
        self.write(node.arg)

    def visit_Assert(self, node):
        self.newline(node)
        self.write('assert ')
        self.visit(node.test)
        if node.msg:
            self.write(', ')
            self.visit(node.msg)

    def visit_TryExcept(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)

    def visit_TryFinally(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        self.newline(node)
        self.write('finally:')
        self.body(node.finalbody)

    def visit_With(self, node):
        self.newline(node)
        self.write('with ')
        self.visit(node.context_expr)
        if node.optional_vars is not None:
            self.write(' as ')
            self.visit(node.optional_vars)
        self.write(':')
        self.body(node.body)


class SourceGeneratorNodeVisitorPython26(BaseSourceGeneratorNodeVisitor):
    __python_version__ = (2, 6)


class SourceGeneratorNodeVisitorPython27(SourceGeneratorNodeVisitorPython26):
    __python_version__ = (2, 7)


class SourceGeneratorNodeVisitorPython30(SourceGeneratorNodeVisitorPython27):
    __python_version__ = (3, 0)

    def visit_ClassDef(self, node):
        have_args = []

        def paren_or_comma():
            if have_args:
                self.write(', ')
            else:
                have_args.append(True)
                self.write('(')

        self.decorators(node)
        self.newline(node)
        self.write('class %s' % node.name, node)
        for base in node.bases:
            paren_or_comma()
            self.visit(base)
        if self._is_node_args_valid(node, 'keywords'):
            for keyword in node.keywords:
                paren_or_comma()
                self.visit(keyword)
        self.write(have_args and '):' or ':')
        self.body(node.body)

    def signature_arg(self, arg, default, write_comma):
        super().signature_arg(arg, default, write_comma)
        if self._is_node_args_valid(arg, 'annotation'):
            self.write(': ')
            self.visit(arg.annotation)

    def visit_FunctionDef(self, node):
        self.decorators(node)
        self.newline(node)
        self.write('def %s(' % node.name, node)
        self.signature(node.args)
        self.write(')')
        if self._is_node_args_valid(node, 'returns'):
            self.write(' -> ')
            self.visit(node.returns)
        self.write(':')
        self.body(node.body)


class SourceGeneratorNodeVisitorPython31(SourceGeneratorNodeVisitorPython30):
    __python_version__ = (3, 1)


class SourceGeneratorNodeVisitorPython32(SourceGeneratorNodeVisitorPython31):
    __python_version__ = (3, 2)


class SourceGeneratorNodeVisitorPython33(SourceGeneratorNodeVisitorPython32):
    __python_version__ = (3, 3)

    def visit_Try(self, node):
        self.newline(node)
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)
        if node.finalbody:
            self.newline(node)
            self.write('finally:')
            self.body(node.finalbody)

    def visit_With(self, node):
        self.newline(node)
        self.write('with ')
        for with_item in node.items:
            self.visit(with_item.context_expr)
            if with_item.optional_vars is not None:
                self.write(' as ')
                self.visit(with_item.optional_vars)
            if with_item != node.items[-1]:
                self.write(', ')
        self.write(':')
        self.body(node.body)

    def visit_YieldFrom(self, node):
        self.write('yield from ')
        self.visit(node.value)


class SourceGeneratorNodeVisitorPython34(SourceGeneratorNodeVisitorPython33):
    __python_version__ = (3, 4)

    def visit_NameConstant(self, node):
        self.write(str(node.value))

    def visit_Name(self, node):
        if isinstance(node.id, ast.arg):
            self.write(node.id.arg, node)
        else:
            self.write(node.id, node)

    def signature_vararg(self, node, write_comma):
        if node.vararg is not None:
            write_comma()
            self.write('*' + node.vararg.arg)

    def signature_kwarg(self, node, write_comma):
        if node.kwarg is not None:
            write_comma()
            self.write('**' + node.kwarg.arg)


class SourceGeneratorNodeVisitorPython35(SourceGeneratorNodeVisitorPython34):
    __python_version__ = (3, 5)

    def visit_AsyncFunctionDef(self, node):
        self.function_definition(node, prefixes=['async'])

    def visit_AsyncFor(self, node):
        self.for_loop(node, prefixes=['async'])

    def visit_Await(self, node):
        self.write('await ')
        if self._is_node_args_valid(node, 'value'):
            self.visit(node.value)

    def call_signature(self, node):
        want_comma = []

        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        starargs = []
        kwargs = []
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                starargs.append(arg)
            else:
                write_comma()
                self.visit(arg)
        for keyword in node.keywords:
            if keyword.arg:
                write_comma()
                self.visit(keyword)
            else:
                kwargs.append(keyword)
        for stararg in starargs:
            write_comma()
            self.visit(stararg)
        for kwarg in kwargs:
            write_comma()
            self.visit(kwarg)


class SourceGeneratorNodeVisitorPython36(SourceGeneratorNodeVisitorPython35):
    __python_version__ = (3, 6)

    def visit_JoinedStr(self, node):
        if self._is_node_args_valid(node, 'values'):
            self.write('f\'')
            for item in node.values:
                if isinstance(item, ast.Str):
                    self.write(item.s.lstrip('\'').rstrip('\''))
                else:
                    self.visit(item)
            self.write('\'')

    def visit_FormattedValue(self, node):
        if self._is_node_args_valid(node, 'value'):
            self.write('{')
            self.visit(node.value)
            self.write('}')


SourceGeneratorNodeVisitor = utils.get_by_python_version([
    SourceGeneratorNodeVisitorPython26,
    SourceGeneratorNodeVisitorPython27,
    SourceGeneratorNodeVisitorPython30,
    SourceGeneratorNodeVisitorPython31,
    SourceGeneratorNodeVisitorPython32,
    SourceGeneratorNodeVisitorPython33,
    SourceGeneratorNodeVisitorPython34,
    SourceGeneratorNodeVisitorPython35,
    SourceGeneratorNodeVisitorPython36
])
