#!/usr/bin/env bash
# Kaggle CLI wrapper: the pip-installed kaggle.exe exits 1 silently on this
# machine (Python 3.14 console-script issue), but the CLI works via
# `python -c "from kaggle.cli import main; main()"`.
# Usage: ./kaggle_cli.sh competitions list -s kaggriculture
python -c "
import sys
from kaggle.cli import main
sys.argv = ['kaggle'] + sys.argv[1:]
main()
" "$@" 2>&1 | grep -v "outdated.*upgrade"
