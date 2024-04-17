from pprint import pprint
import pyaixm
import sys
import json


if __name__ == '__main__':
    with open(sys.argv[1], 'rb') as f:
        features = pyaixm.parse(f, resolve_xlinks=False)
        pprint(features)

        # for feature in features:
        #     if feature.gml_id == "id.f23d6224-09fc-4921-8983-099e49d0a587":
        #         pprint(feature)
        #         break