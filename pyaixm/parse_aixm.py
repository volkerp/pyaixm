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
            replace_xlinks_r(feature)


def replace_xlinks_r(feature: aixm_types.Feature, path: list = []):
    new_path = path
    for field in fields(feature):
        if field.name == "parent":
            continue
        attr = getattr(feature, field.name)
        if isinstance(attr, list):
            for a in attr:
                if isinstance(a, aixm_types.Feature):
                   replace_xlinks_r(a, path=new_path + [a.gmlid])
        if isinstance(attr, aixm_types.Feature):
            if attr.gmlid in path:
                continue
            new_path.append(attr.gmlid)
            replace_xlinks_r(feature, path=new_path)
        if isinstance(attr, aixm_types.XLink):
            if attr.target is not None:
                setattr(feature, field.name, attr.target)


def parse(f: typing.IO | list[typing.IO], resolve_xlinks = False) -> list:
    l = []
    if isinstance(f, list):
        for g in f:
            context = etree.iterparse(g)
            for action, elem in context:
                if action == 'end' and elem.tag in ['{http://www.aixm.aero/schema/5.1.1/message}hasMember', '{http://www.aixm.aero/schema/5.1/message}hasMember']:
                    feature = aixm_types.parse_feature(elem[0])  # first child of 'hasMember' is aixm feature
                    l.append(feature)

    else:
        context = etree.iterparse(f)
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