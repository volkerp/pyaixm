from dataclasses import fields
from lxml import etree
import sys
from pprint import pprint
import typing

from . import aixm_types


def replace_xlinks(features: list):
    "Replaces XLink references on all features with the referenced object"
    for feature in features:
        if isinstance(feature, aixm_types.Feature):
            for field in fields(feature):
                attr = getattr(feature, field.name)
                if isinstance(attr, aixm_types.XLink):
                    if attr.target is not None:
                        setattr(feature, field.name, attr.target)


def parse(f: typing.IO, resolve_xlinks = False) -> list:
    context = etree.iterparse(f)
    l = []
    for action, elem in context:
        if action == 'end' and elem.tag in ['{http://www.aixm.aero/schema/5.1.1/message}hasMember', '{http://www.aixm.aero/schema/5.1/message}hasMember']:
            feature = aixm_types.parse_feature(elem[0])  # first child of 'hasMember' is aixm feature
            l.append(feature)

    aixm_types.XLink.resolve()

    if resolve_xlinks:
        replace_xlinks(l)

    return l


if __name__ == '__main__':
    f = open(sys.argv[1], mode='rb')
    d = aixm_types.parse(f)
    pprint(d)