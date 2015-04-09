import sys
if sys.version<'2.4':
    # Python 2.3 disassembler is broken wrt co_lnotab; use a later version
    import _dis
    sys.modules['dis'] = _dis

if sys.version<'3':
    from peak.util.assembler import NotAConstant
    NotAConstant.__name__ = "peak.util.assembler.NotAConstant"

    
def additional_tests():
    import doctest
    return doctest.DocFileSuite(
        'README.txt',
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE,
    )

