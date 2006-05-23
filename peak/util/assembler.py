from array import array
from dis import *
from new import code

__all__ = ['Code']

opcode = {}

for op in range(256):
    name=opname[op]
    if name.startswith('<'): continue
    if name.endswith('+0'): opcode[name[:-2]]=op
    opcode[name]=op

globals().update(opcode) # opcodes are now importable at will
__all__.extend(opcode.keys())


def additional_tests():
    from protocols.tests import doctest
    return doctest.DocFileSuite(
        'assembler.txt', package='peak.util.assembler',
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE,
    )

















class Code:
    co_argcount = 0
    co_stacksize = 0
    co_flags = 0
    co_filename = '<generated code>'
    co_name = '<lambda>'
    co_firstlineno = 0
    co_freevars = ()
    co_cellvars = ()
    _last_lineofs = 0
    stack_size = 0

    def __init__(self):
        self.co_code = array('B')
        self.co_consts = []
        self.co_names = []
        self.co_varnames = []
        self.co_lnotab = array('B')
        self.emit = self.co_code.append

    def code(self):
        return code(
            self.co_argcount, len(self.co_varnames),
            self.co_stacksize, self.co_flags, self.co_code.tostring(),
            tuple(self.co_consts), tuple(self.co_names),
            tuple(self.co_varnames),
            self.co_filename, self.co_name, self.co_firstlineno,
            self.co_lnotab.tostring(),
            self.co_freevars, self.co_cellvars
        )

    def emit_arg(self, op, arg):
        emit = self.emit
        if arg>0xFFFF:
            emit(EXTENDED_ARG)
            emit((arg>>16)&255)
            emit((arg>>24)&255)
        emit(op)
        emit(arg&255)
        emit((arg>>8)&255)

    def set_lineno(self, lno):
        if not self.co_firstlineno:
            self.co_firstlineno = self._last_line = lno
            return

        append = self.co_lnotab.append
        incr_line = lno - self._last_line
        incr_addr = len(self.co_code) - self._last_lineofs
        if not incr_line:
            return

        assert incr_addr>=0 and incr_line>=0

        while incr_addr>255:
            append(255)
            append(0)
            incr_addr -= 255

        while incr_line>255:
            append(incr_addr)
            append(255)
            incr_line -= 255
            incr_addr = 0

        if incr_addr or incr_line:
            append(incr_addr)
            append(incr_line)

        self._last_line = lno
        self._last_lineofs = len(self.co_code)

    def stackchange(self, (inputs,outputs)):
        assert inputs<=self.stack_size, "Stack underflow"
        if inputs or outputs:
            ss = self.stack_size = self.stack_size + outputs - inputs
            if outputs>inputs and ss>self.co_stacksize:
                self.co_stacksize = ss




    def LOAD_CONST(self, const):
        self.stackchange((0,1))
        try:
            arg = self.co_consts.index(const)
        except ValueError:
            arg = len(self.co_consts)
            self.co_consts.append(const)
        self.emit_arg(LOAD_CONST, arg)


    def CALL_FUNCTION(self, argc=0, kwargc=0, op=CALL_FUNCTION):
        self.stackchange((1+argc+2*kwargc,1))
        emit = self.emit
        emit(op); emit(argc); emit(kwargc)

    def CALL_FUNCTION_VAR(self, argc=0, kwargc=0):
        self.stackchange((1,0))    # extra for *args
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_VAR)

    def CALL_FUNCTION_KW(self, argc=0, kwargc=0):
        self.stackchange((1,0))    # extra for **kw
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_KW)

    def CALL_FUNCTION_VAR_KW(self, argc=0, kwargc=0):
        self.stackchange((2,0))    # extra for *args, **kw
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_VAR_KW)

    def BUILD_TUPLE(self, count):
        self.stackchange((count,1))
        self.emit_arg(BUILD_TUPLE,count)

    def BUILD_LIST(self, count):
        self.stackchange((count,1))
        self.emit_arg(BUILD_LIST,count)

    def UNPACK_SEQUENCE(self, count):
        self.stackchange((1,count))
        self.emit_arg(UNPACK_SEQUENCE,count)



    def BUILD_SLICE(self, count):
        assert count in (2,3), "Invalid number of arguments for BUILD_SLICE"
        self.stackchange((count,1))
        self.emit_arg(BUILD_SLICE,count)

    def DUP_TOPX(self,count):
        self.stackchange((count,count*2))
        self.emit_arg(DUP_TOPX,count)

    def RAISE_VARARGS(self, argc):
        assert 0<=argc<=3, "Invalid number of arguments for RAISE_VARARGS"
        self.stackchange((argc,0))
        self.emit_arg(RAISE_VARARGS,argc)

    def MAKE_FUNCTION(self, ndefaults):
        self.stackchange((1+ndefaults,1))
        self.emit_arg(MAKE_FUNCTION, ndefaults)

    def MAKE_CLOSURE(self, ndefaults, freevars):
        self.stackchange((1+freevars+ndefaults,1))
        self.emit_arg(MAKE_CLOSURE, ndefaults)

    def label(self):
        return len(self.co_code)

    def jump(self, op, arg=None):
        def backpatch(target):
            if op not in hasjabs:
                target = target - posn
                assert target>=0, "Relative jumps can't go backwards"
            self.co_code[posn-2] = target & 255
            self.co_code[posn-1] = (target>>8) & 255
        def lbl():
            backpatch(self.label())
        self.emit_arg(op,0)
        posn = self.label()
        if arg is not None:
            backpatch(arg)
        return lbl


for op in hasname:
    if not hasattr(Code, opname[op]):
        def do_name(self, name, op=op):
            self.stackchange(stack_effects[op])
            try:
                arg = self.co_names.index(name)
            except ValueError:
                arg = len(self.co_names)
                self.co_names.append(name)
            self.emit_arg(op, arg)
        setattr(Code, opname[op], do_name)

for op in haslocal:
    if not hasattr(Code, opname[op]):
        def do_local(self, varname, op=op):
            self.stackchange(stack_effects[op])
            try:
                arg = self.co_varnames.index(varname)
            except ValueError:
                arg = len(self.co_varnames)
                self.co_varnames.append(varname)
            self.emit_arg(op, arg)
        setattr(Code, opname[op], do_local)

for op in hasjrel+hasjabs:
    if not hasattr(Code, opname[op]):
        def do_jump(self, address=None, op=op):
            self.stackchange(stack_effects[op])
            return self.jump(op, address)
        setattr(Code, opname[op], do_jump)











class _se:
    """Quick way of defining static stack effects of opcodes"""
    POP_TOP   = 1,0
    ROT_TWO   = 2,2
    ROT_THREE = 3,3
    ROT_FOUR  = 4,4
    DUP_TOP   = 1,2

    UNARY_POSITIVE = UNARY_NEGATIVE = UNARY_NOT = UNARY_CONVERT = \
        UNARY_INVERT = GET_ITER = LOAD_ATTR = IMPORT_FROM = 1,1

    BINARY_POWER = BINARY_MULTIPLY = BINARY_DIVIDE = BINARY_FLOOR_DIVIDE = \
        BINARY_TRUE_DIVIDE = BINARY_MODULO = BINARY_ADD = BINARY_SUBTRACT = \
        BINARY_SUBSCR = BINARY_LSHIFT = BINARY_RSHIFT = BINARY_AND = \
        BINARY_XOR = BINARY_OR = COMPARE_OP = 2,1

    INPLACE_POWER = INPLACE_MULTIPLY = INPLACE_DIVIDE = \
        INPLACE_FLOOR_DIVIDE = INPLACE_TRUE_DIVIDE = INPLACE_MODULO = \
        INPLACE_ADD = INPLACE_SUBTRACT = INPLACE_LSHIFT = INPLACE_RSHIFT = \
        INPLACE_AND = INPLACE_XOR = INPLACE_OR = 2,1

    SLICE_0, SLICE_1, SLICE_2, SLICE_3 = \
        (1,1),(2,1),(2,1),(3,1)
    STORE_SLICE_0, STORE_SLICE_1, STORE_SLICE_2, STORE_SLICE_3 = \
        (2,0),(3,0),(3,0),(4,0)
    DELETE_SLICE_0, DELETE_SLICE_1, DELETE_SLICE_2, DELETE_SLICE_3 = \
        (1,0),(2,0),(2,0),(3,0)

    STORE_SUBSCR = 3,0
    DELETE_SUBSCR = STORE_ATTR = 2,0
    DELETE_ATTR = STORE_DEREF = 1,0
    PRINT_EXPR = PRINT_ITEM = PRINT_NEWLINE_TO = IMPORT_STAR = 1,0
    RETURN_VALUE = YIELD_VALUE = STORE_NAME = STORE_GLOBAL = STORE_FAST = 1,0
    PRINT_ITEM_TO = LIST_APPEND = 2,0

    LOAD_LOCALS = LOAD_CONST = LOAD_NAME = LOAD_GLOBAL = LOAD_FAST = \
        LOAD_CLOSURE = LOAD_DEREF = IMPORT_NAME = BUILD_MAP = 0,1

    EXEC_STMT = BUILD_CLASS = 3,0


stack_effects = [(0,0)]*256

for name in opcode:
    op = opcode[name]
    name = name.replace('+','_')

    if hasattr(_se,name):
        # update stack effects table from the _se class
        stack_effects[op] = getattr(_se,name)

    if not hasattr(Code,name):
        # Create default method for Code class
        if op>=HAVE_ARGUMENT:
            def do_op(self,arg,op=op,se=stack_effects[op]):
                self.stackchange(se); self.emit_arg(op,arg)
        else:
            def do_op(self,op=op,se=stack_effects[op]):
                self.stackchange(se); self.emit(op)

        setattr(Code, name, do_op)





















