#!/usr/bin/env python3
import signal
import sys

from novelbot.cli import main

if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # `bot.py ... | head` should end quietly
sys.exit(main())
