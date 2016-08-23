import sys
from resultsdb import cli

if __name__ == '__main__':
    exit = cli.main()
    if exit:
        sys.exit(exit)
