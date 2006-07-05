from array import array
from dis import *
from new import code
from types import CodeType

__all__ = [
    'Code', 'Const', 'Return', 'Global', 'Local', 'Call', 'const_value',
    'NotAConstant', 'Label', 'fold_args', 'nodetype', 'Node'
]

opcode = {}
for op in range(256):
    name=opname[op]
    if name.startswith('<'): continue
    if name.endswith('+0'): opcode[name[:-2]]=op
    opcode[name]=op

globals().update(opcode) # opcodes are now importable at will

# Flags from code.h
CO_OPTIMIZED              = 0x0001      # use LOAD/STORE_FAST instead of _NAME
CO_NEWLOCALS              = 0x0002      # only cleared for module/exec code
CO_VARARGS                = 0x0004
CO_VARKEYWORDS            = 0x0008
CO_NESTED                 = 0x0010      # ???
CO_GENERATOR              = 0x0020
CO_NOFREE                 = 0x0040      # set if no free or cell vars
CO_GENERATOR_ALLOWED      = 0x1000      # unused
CO_FUTURE_DIVISION        = 0x2000
CO_FUTURE_ABSOLUTE_IMPORT = 0x4000      # Python 2.5+ only
CO_FUTURE_WITH_STATEMENT  = 0x8000      # Python 2.5+ only

__all__.extend([k for k in globals().keys() if k.startswith('CO_')])








class Const(object):
    """Wrapper to ensure constants are hashable even if mutable"""

    __slots__ = 'value', 'hash', 'hashable'
    def __init__(self, value):
        self.value = value
        try:
            self.hash = hash(value)
        except TypeError:
            self.hash = hash(id(value))
            self.hashable = False
        else:
            self.hashable = True

    def __repr__(self):
        return "Const(%s)" % repr(self.value)

    def __hash__(self):
        return self.hash

    def __eq__(self, other):
        if type(other) is not Const:
            return False
        if self.hashable:
            return self.value == other.value
        else:
            return self.value is other.value

    def __ne__(self, other):
        return not self==other

    def __call__(self, code):
        code.LOAD_CONST(self.value)








class Node(tuple):
    """Base class for AST nodes"""
    __slots__ = []


def nodetype(*mixins, **kw):

    def callback(frame, name, func, old_locals):
        def __new__(cls, *args, **kw):
            result = func(*args, **kw)
            if type(result) is tuple:
                return tuple.__new__(cls, (cls,)+result)
            else:
                return result

        def __repr__(self):
            return name+tuple.__repr__(self[1:])

        def __call__(self, code):
            return func(*(self[1:]+(code,)))

        import inspect
        args = inspect.getargspec(func)[0]

        d = dict(
            __new__ = __new__, __repr__ = __repr__, __doc__=func.__doc__,
            __module__ = func.__module__, __args__ = args, __slots__ = [],
            __call__ = __call__
        )
        for p,a in enumerate(args[:-1]):    # skip 'code' argument
            if isinstance(a,str):
                d[a] = property(lambda self, p=p+1: self[p])

        d.update(kw)
        return type(name, mixins+(Node,), d)

    from peak.util.decorators import decorate_assignment
    return decorate_assignment(callback)



nodetype()
def Global(name, code=None):
    if code is None:
        return name,
    code.LOAD_GLOBAL(name)

nodetype()
def Local(name, code=None):
    if code is None:
        return name,
    if name in code.co_cellvars or name in code.co_freevars:
        return code.LOAD_DEREF(name)
    elif code.co_flags & CO_OPTIMIZED:
        return code.LOAD_FAST(name)
    else:
        return code.LOAD_NAME(name)

nodetype()
def Return(value=None, code=None):
    if code is None:
        return value,
    return code(value, Code.RETURN_VALUE)



















nodetype()
def Call(func, args=(),kwargs=(), star=None,dstar=None, fold=True, code=None):
    if code is None:
        data = (
            func, tuple(args), tuple(kwargs), star or (), dstar or (), fold
        )
        if fold and (args or kwargs or star or dstar):
            return fold_args(Call, *data)
        else:
            return data

    code(func, *args)
    for k,v in kwargs:
        code(k,v)

    argc = len(args)
    kwargc = len(kwargs)

    if star:
        if dstar:
            code(star, dstar)
            return code.CALL_FUNCTION_VAR_KW(argc, kwargc)
        else:
            code(star)
            return code.CALL_FUNCTION_VAR(argc, kwargc)
    else:
        if dstar:
            code(dstar)
            return code.CALL_FUNCTION_KW(argc, kwargc)
        else:
            return code.CALL_FUNCTION(argc, kwargc)










class Label(object):
    """A forward-referenceable location in a ``Code`` object"""

    __slots__ = 'backpatches', 'resolution'

    def __init__(self):
        self.backpatches = []
        self.resolution = None

    def SETUP_EXCEPT(self, code):
        code.SETUP_EXCEPT(); self.backpatches.append(code.blocks[-1][-1])

    def SETUP_FINALLY(self, code):
        code.SETUP_FINALLY(); self.backpatches.append(code.blocks[-1][-1])

    def SETUP_LOOP(self, code):
        code.SETUP_LOOP(); self.backpatches.append(code.blocks[-1][-1])

    def POP_BLOCK(self, code):
        self.backpatches[0] = code.POP_BLOCK()

    for op in hasjrel+hasjabs:
        if opname[op] not in locals():
            def do_jump(self, code, op=op):
                method = getattr(code, opname[op])
                if self.resolution is None:
                    return self.backpatches.append(method())
                else:
                    return method(self.resolution)
            locals()[opname[op]] = do_jump
    del do_jump

    def __call__(self, code):
        if self.resolution is not None:
            raise AssertionError("Label previously defined")
        self.resolution = resolution = len(code.co_code)
        for p in self.backpatches:
            if p: p()



class Code(object):
    co_argcount = 0
    co_stacksize = 0
    co_flags = CO_OPTIMIZED | CO_NEWLOCALS      # typical usage
    co_filename = '<generated code>'
    co_name = '<lambda>'
    co_firstlineno = 0
    co_freevars = ()
    co_cellvars = ()
    _last_lineofs = 0
    _ss = 0

    def __init__(self):
        self.co_code = array('B')
        self.co_consts = [None]
        self.co_names = []
        self.co_varnames = []
        self.co_lnotab = array('B')
        self.emit = self.co_code.append
        self.blocks = []
        self.stack_history = []

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











    def LOAD_CONST(self, const):
        self.stackchange((0,1))
        pos = 0
        hashable = True
        try:
            hash(const)
        except TypeError:
            hashable = False
        while 1:
            try:
                arg = self.co_consts.index(const, pos)
                it = self.co_consts[arg]
            except ValueError:
                arg = len(self.co_consts)
                self.co_consts.append(const)
                break
            else:
                if type(it) is type(const) and (hashable or it is const):
                    break
            pos = arg+1
            continue
        return self.emit_arg(LOAD_CONST, arg)

    def CALL_FUNCTION(self, argc=0, kwargc=0, op=CALL_FUNCTION, extra=0):
        self.stackchange((1+argc+2*kwargc+extra,1))
        emit = self.emit
        emit(op); emit(argc); emit(kwargc)

    def CALL_FUNCTION_VAR(self, argc=0, kwargc=0):
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_VAR, 1)    # 1 for *args

    def CALL_FUNCTION_KW(self, argc=0, kwargc=0):
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_KW, 1)     # 1 for **kw

    def CALL_FUNCTION_VAR_KW(self, argc=0, kwargc=0):
        self.CALL_FUNCTION(argc,kwargc,CALL_FUNCTION_VAR_KW, 2) # 2 *args,**kw

    def BUILD_TUPLE(self, count):
        self.stackchange((count,1))
        self.emit_arg(BUILD_TUPLE,count)

    def BUILD_LIST(self, count):
        self.stackchange((count,1))
        self.emit_arg(BUILD_LIST,count)

    def UNPACK_SEQUENCE(self, count):
        self.stackchange((1,count))
        self.emit_arg(UNPACK_SEQUENCE,count)

    def RETURN_VALUE(self):
        self.stackchange((1,0))
        self.emit(RETURN_VALUE)
        self.stack_unknown()

    def BUILD_SLICE(self, count):
        assert count in (2,3), "Invalid number of arguments for BUILD_SLICE"
        self.stackchange((count,1))
        self.emit_arg(BUILD_SLICE,count)

    def DUP_TOPX(self, count):
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

    def here(self):
        return len(self.co_code)




    def set_stack_size(self, size):
        if size<0:
            raise AssertionError("Stack underflow")
        if size>self.co_stacksize:
            self.co_stacksize = size
        bytes = len(self.co_code) - len(self.stack_history) + 1
        if bytes>0:
            self.stack_history.extend([self._ss]*bytes)
        self._ss = size

    def get_stack_size(self):
        return self._ss

    stack_size = property(get_stack_size, set_stack_size)

    def stackchange(self, (inputs,outputs)):
        if self._ss is None:
            raise AssertionError("Unknown stack size at this location")
        self.stack_size -= inputs   # check underflow
        self.stack_size += outputs  # update maximum height

    def stack_unknown(self):
        self._ss = None


















    def branch_stack(self, location, expected):
        if location >= len(self.stack_history):
            if location > len(self.co_code):
                raise AssertionError("Forward-looking stack prediction!",
                    location, len(self.co_code)
                )
            actual = self.stack_size
            if actual is None:
                self.stack_size = actual = expected
                self.stack_history[location] = actual
        else:
            actual = self.stack_history[location]
            if actual is None:
                self.stack_history[location] = actual = expected

        if actual != expected:
            raise AssertionError(
                "Stack level mismatch: actual=%s expected=%s"
                % (actual, expected)
            )





















    def jump(self, op, arg=None):

        def backpatch(offset):
            target = offset
            if op not in hasjabs:
                target = target - posn
                assert target>=0, "Relative jumps can't go backwards"
            self.co_code[posn-2] = target & 255
            self.co_code[posn-1] = (target>>8) & 255
            self.branch_stack(offset, old_level)

        def lbl(code=None):
            backpatch(self.here())

        old_level = self.stack_size
        self.emit_arg(op,0)
        posn = self.here()

        if op in (JUMP_FORWARD, JUMP_ABSOLUTE, CONTINUE_LOOP):
            self.stack_unknown()

        if arg is not None:
            backpatch(arg)
        else:
            return lbl
















    def setup_block(self, op):
        jmp = self.jump(op)
        self.blocks.append((op,self.stack_size,jmp))
        return jmp

    def SETUP_EXCEPT(self):
        ss = self.stack_size
        self.stack_size = ss+3  # simulate the level at "except:" time
        self.setup_block(SETUP_EXCEPT)
        self.stack_size = ss    # restore the current level

    def SETUP_FINALLY(self):
        ss = self.stack_size
        self.stack_size = ss+3  # allow for exceptions
        self.stack_size = ss+1  # simulate the level after the None is pushed
        self.setup_block(SETUP_FINALLY)
        self.stack_size = ss    # restore original level

    def SETUP_LOOP(self):
        self.setup_block(SETUP_LOOP)


    def POP_BLOCK(self):
        if not self.blocks:
            raise AssertionError("Not currently in a block")

        why, level, fwd = self.blocks.pop()
        self.emit(POP_BLOCK)

        if why!=SETUP_LOOP:
            if why==SETUP_FINALLY:
                self.LOAD_CONST(None)
                fwd()
            else:
                else_ = self.JUMP_FORWARD()
                fwd()
                return else_
        else:
            return fwd


    def assert_loop(self):
        for why,level,fwd in self.blocks:
            if why==SETUP_LOOP:
                return
        raise AssertionError("Not inside a loop")

    def BREAK_LOOP(self):
        self.assert_loop(); self.emit(BREAK_LOOP)
        self.stack_unknown()

    def CONTINUE_LOOP(self, label):
        self.assert_loop()
        if self.blocks[-1][0]==SETUP_LOOP:
            op = JUMP_ABSOLUTE  # more efficient if not in a nested block
        else:
            op = CONTINUE_LOOP
        return self.jump(op, label)

    def __call__(self, *args):
        last = None
        for ob in args:
            if callable(ob):
                last = ob(self)
            else:
                try:
                    f = generate_types[type(ob)]
                except KeyError:
                    raise TypeError("Can't generate", ob)
                else:
                    last = f(self, ob)
        return last

    def return_(self, ob=None):
        return self(ob, Code.RETURN_VALUE)

    def from_function(cls, function, copy_lineno=False):
        code = cls.from_code(function.func_code, copy_lineno)
        return code

    from_function = classmethod(from_function)

    def from_code(cls, code, copy_lineno=False):
        self = cls()
        if copy_lineno:
            self.set_lineno(code.co_firstlineno)

        import inspect
        args, var, kw = inspect.getargs(code)
        self.co_varnames.extend(args)
        if var:
            self.co_varnames.append(var)
            self.co_flags |= CO_VARARGS
        if kw:
            self.co_varnames.append(kw)
            self.co_flags |= CO_VARKEYWORDS

        def tuple_arg(args):
            self.UNPACK_SEQUENCE(len(args))
            for arg in args:
                if isinstance(arg, list):
                    tuple_arg(arg)
                else:
                    self.STORE_FAST(arg)

        for narg, arg in enumerate(args):
            if isinstance(arg,list):
                dummy_name = '.'+str(narg)
                self.co_varnames[narg] = dummy_name
                self.LOAD_FAST(dummy_name)
                tuple_arg(arg)

        self.co_argcount = code.co_argcount
        self.co_name     = code.co_name
        self.co_freevars = code.co_freevars
        return self

    from_code = classmethod(from_code)





    def code(self):
        if self.blocks:
            raise AssertionError("%d unclosed block(s)" % len(self.blocks))

        flags = self.co_flags & ~CO_NOFREE

        if not self.co_freevars and not self.co_cellvars:
            flags |= CO_NOFREE

        return code(
            self.co_argcount, len(self.co_varnames),
            self.co_stacksize, flags, self.co_code.tostring(),
            tuple(self.co_consts), tuple(self.co_names),
            tuple(self.co_varnames),
            self.co_filename, self.co_name, self.co_firstlineno,
            self.co_lnotab.tostring(), self.co_freevars, self.co_cellvars
        )


for op in hasfree:
    if not hasattr(Code, opname[op]):
        def do_free(self, varname, op=op):
            self.stackchange(stack_effects[op])
            try:
                arg = list(self.co_cellvars+self.co_freevars).index(varname)
            except ValueError:
                raise NameError("Undefined free or cell var", varname)
            self.emit_arg(op, arg)
        setattr(Code, opname[op], do_free)












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
            if op in (LOAD_NAME, STORE_NAME, DELETE_NAME):
                # Can't use optimized local vars, so reset flags
                self.co_flags &= ~CO_OPTIMIZED
        setattr(Code, opname[op], do_name)

for op in haslocal:
    if not hasattr(Code, opname[op]):
        def do_local(self, varname, op=op):
            if not self.co_flags & CO_OPTIMIZED:
                raise AssertionError(
                    "co_flags must include CO_OPTIMIZED to use fast locals"
                )
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




def gen_map(code, ob):
    code.BUILD_MAP(0)
    for k,v in ob.items():
        code.DUP_TOP()
        code(k, v)
        code.ROT_THREE()
        code.STORE_SUBSCR()

def gen_tuple(code, ob):
    code(*ob)
    return code.BUILD_TUPLE(len(ob))

def gen_list(code, ob):
    code(*ob)
    return code.BUILD_LIST(len(ob))

generate_types = {
    int:        Code.LOAD_CONST,
    long:       Code.LOAD_CONST,
    bool:       Code.LOAD_CONST,
    CodeType:   Code.LOAD_CONST,
    str:        Code.LOAD_CONST,
    unicode:    Code.LOAD_CONST,
    complex:    Code.LOAD_CONST,
    float:      Code.LOAD_CONST,
    type(None): Code.LOAD_CONST,
    tuple:      gen_tuple,
    list:       gen_list,
    dict:       gen_map,
}











class NotAConstant(Exception):
    """The supplied value is not a constant expression tree"""


def const_value(value):
    """Return the constant value -- if any -- of an expression tree

    Raises NotAConstant if the value or any child of the value are
    not constants.
    """
    t = type(value)
    if t is Const:
        value = value.value
    elif t is tuple:
        t = tuple(map(const_value,value))
        if t==value:
            return value
        return t
    elif generate_types.get(t) != Code.LOAD_CONST:
        raise NotAConstant(value)
    return value


def fold_args(f, *args):
    """Return a folded ``Const`` or an argument tuple"""

    try:
        map(const_value, args)
    except NotAConstant:
        return args
    else:
        c = Code()
        f(*args+(c,))
        c.RETURN_VALUE()
        return Const(eval(c.code()))






class _se:
    """Quick way of defining static stack effects of opcodes"""
    POP_TOP   = END_FINALLY = 1,0
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
    JUMP_IF_TRUE = JUMP_IF_FALSE = 1,1

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





















