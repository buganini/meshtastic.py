import sys
if sys.argv[1:2] == ["--textual"]:
    from PUI.textual import *
else:
    from PUI.PySide6 import *
