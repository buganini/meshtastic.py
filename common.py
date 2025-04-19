import sys
if sys.argv[1:2] == ["--textual"]:
    from PUI.textual import *
else:
    from PUI.PySide6 import *

def bool_from_str(s):
    return s.lower()[0] in "yt1" if s else False
