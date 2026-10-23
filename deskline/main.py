import sys
import traceback

from deskline.config import log

def _hook(exc_type, exc, tb) -> None:
    log("".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _hook

from deskline.app import main

if __name__ == "__main__":
    main()
