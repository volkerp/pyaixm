from pprint import pprint
import pyaixm
import sys


if __name__ == '__main__':
    with open(sys.argv[1], 'rb') as f:
        features = pyaixm.parse(f, resolve_xlinks=False)
        pprint(features)

