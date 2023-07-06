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
    f = open(sys.argv[1], mode='rb')
    d = parse(f)
    json.dump(d, sys.stdout, ensure_ascii=False, default=default, sort_keys=True, indent=4)