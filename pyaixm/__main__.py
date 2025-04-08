import json
from pprint import pprint
import sys
from .parse_aixm import parse

def default(obj):
    if hasattr(obj, 'to_json'):
        return obj.to_json()
    else:
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')


if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        print("Please provide one or more filenames as command line arguments.")
        sys.exit(1)

    d = parse(files, resolve_xlinks=True)
    json.dump(d, sys.stdout, ensure_ascii=False, default=default, sort_keys=True, indent=4)