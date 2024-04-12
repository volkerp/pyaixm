from dataclasses import dataclass, asdict, field, fields, make_dataclass
import json
import os
import typing
from pprint import pprint
import warnings
import yaml
import pdb


AIXM = "{http://www.aixm.aero/schema/5.1.1}"
GML = "{http://www.opengis.net/gml/3.2}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"


@dataclass
class Feature:
    gmlid: str = None
    gmlidentifier: str = None
    parent: 'Feature' = None
    id_registry = {}

    def parse(self, elm):
        self.gmlid = elm.get(GML + 'id')
        Feature.id_registry[self.gmlid] = self

        if (identi_elm := elm.find(GML + 'identifier')) is not None:
            self.gmlidentifier = identi_elm.text
            Feature.id_registry[self.gmlidentifier] = self

    def dict(self):
        d = {}
        for field in fields(self):
            if field.name in {'parent', 'id_registry'}:
                continue

            value = getattr(self, field.name)
            d[field.name] = value

        return d

    def to_json(self):
        return { self.__class__.__name__: self.dict() }


@dataclass
class GMLPatches:
    patches: typing.List
    gmlid: str = None
    parent: 'Feature' = None
    registry = []

    def _parse_poslist(s: str):
        return [float(v) for  v in s.split()]

    @classmethod
    def parse(cls, elm, parent = None):
        patches = []
        for seg in elm.iter('{*}segments'):
            p = []
            for pl in seg.iter('{*}posList'):
                p += cls._parse_poslist(pl.text)
            for pos in seg.iter('{*}pos'):
                p += cls._parse_poslist(pos.text)
            patches.append(p)

        p = cls(patches, parent=parent)
        cls.registry.append(p)
        return p

    def dict(self):
        return { 'patches': self.patches,
                'gmlid': self.gmlid }

    to_json = dict


class XLink():
    xlink_registry = {}
    target: Feature = None

    def __init__(self, elm):
        self.href = elm.get('{http://www.w3.org/1999/xlink}href')
        if not self.href:
            raise ValueError('Invalid xlink:href')
        XLink.xlink_registry[self.href] = self

    @classmethod
    def parse(cls, elm):
        href = elm.get('{http://www.w3.org/1999/xlink}href')
        if href in cls.xlink_registry:           # already XLink with this href?
            return cls.xlink_registry[href]      # yes, return

        try:
            return cls(elm)
        except ValueError:
            return None

    @classmethod
    def resolve(cls):
        for href, xlink in cls.xlink_registry.items():
            if xlink.href.startswith('#'):
                feature = Feature.id_registry.get(xlink.href[1:])
            elif xlink.href.startswith('urn:uuid:'):
                feature = Feature.id_registry.get(xlink.href[9:])
            else:
                feature = None

            if feature is None:
                warnings.warn(f"can't resolve xlink:href: {xlink.href}")
            else:
                xlink.target = feature

    def __repr__(self) -> str:
        return f"XLink(href: {self.href} target: {'resolved' if self.target else 'unresolved'})"

    def to_json(self) -> dict:
        return { 'XLink': { 'href': self.href, 'target': self.target.__class__.__name__} }


class Nil():
    def __init__(self, nil_reason = None):
        self.nil_reason = nil_reason

    @classmethod
    def parse(cls, elm):
        if elm.get(XSI + 'nil'):
            return cls(elm.get('nilReason'))
        else:
            return None

    def to_json(self):
        return { 'Nil': self.nil_reason }

    def __repr__(self) -> str:
        return f'Nil(reason: {self.nil_reason})'


def construct_dataclass(schema: dict, classname: str):

    # this method defined here is placed in the to be contructed class
    @classmethod
    def _parse(cls, featureElm, parent = None):
        c = cls(parent=parent)
        super(cls, c).parse(featureElm)

        # handle the fields defined in schema
        for field in fields(c):
            if not field.metadata.get('extract'):
                continue              # field not marked as extract => skip

            attribute = []
            for elm in featureElm.iter('{*}' + field.metadata['tag']):
                feature_type = feature_types.get(field.type, str)

                xlink = XLink.parse(elm)
                nil = Nil.parse(elm)

                if xlink is not None:
                    attribute.append(xlink)
                elif nil is not None:
                    attribute.append(nil)
                elif feature_type == str:
                    if elm.text is not None and len(elm.text.strip()) > 0:
                        attribute.append(elm.text.strip())
                elif field.type == 'GMLPatches':
                    """ todo: generic solution"""
                    attribute += [feature_type.parse(elm2, parent=c) for elm2 in elm.iter('{*}PolygonPatch')]
                else:
                    # field type is complex (not str)
                    # recurse
                    attribute += [feature_type.parse(elm2, parent=c) for elm2 in elm.iter('{*}' + field.type)]

                if len(attribute) == 0:
                    c.__setattr__(field.name, None)
                elif len(attribute) == 1:
                    c.__setattr__(field.name, attribute[0])
                else:
                    c.__setattr__(field.name, attribute)
        return c


    class_fields = list()
    class_fields.append(('feature_name', str, field(default=classname)))
    for tag, typename in schema[classname].items():
        metadata = {'extract': True, 'tag': tag}
        fieldname = tag.replace('-', '')  # remove invalid chars from field name

        class_fields.append(
            (fieldname, typename, field(default=None, metadata=metadata))
        )

    new_class = make_dataclass(classname, class_fields, bases=(Feature,), namespace={'parse': _parse})

    return new_class


def parse_feature(feature):
    feature_name = feature.tag.split('}', 1)[1]

    if feature_name in feature_types:
        feature = feature_types[feature_name].parse(feature)
        return feature


##
## init
##

# maps name of feature 'AirportHeliport' => dataclass
feature_types = {}

schemafile = os.path.join(os.path.dirname(__file__), 'aixm_schema.yaml')
with open(schemafile) as j:
    schema = yaml.safe_load(j)

    feature_types['GMLPatches'] = GMLPatches

    for feature_name in schema.keys():
        # construct dataclass from schema
        feature_class = construct_dataclass(schema, feature_name)
        feature_types[feature_name] = feature_class


if __name__ == '__main__':
    print("Automaticaly constructed feature types (DataClasses) from aixm_schema")
    pprint(feature_types)
