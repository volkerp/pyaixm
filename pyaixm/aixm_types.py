from dataclasses import dataclass, field, fields, make_dataclass
import os
import typing
from pprint import pprint
import warnings
import yaml


AIXM = "{http://www.aixm.aero/schema/5.1.1}"
GML = "{http://www.opengis.net/gml/3.2}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"


@dataclass
class Feature:
    gmlid: str = None
    gmlidentifier: str = None
    id_registry = {}

    def parse(self, elm):
        self.gmlid = elm.get(GML + 'id')
        Feature.id_registry[self.gmlid] = self

        if (identi_elm := elm.find(GML + 'identifier')) is not None:
            self.gmlidentifier = identi_elm.text
            Feature.id_registry[self.gmlidentifier] = self


@dataclass
class PolygonPatch:
    """ One of GM_Polygon, GM_Surface """
    patches: typing.List

    @classmethod
    def parse(cls, elm):
        patches = []
        for pl in elm.iter('{*}posList'):
            patches.append(pl.text)
        return cls(patches)


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


class Nil():
    def __init__(self, nil_reason = None):
        self.nil_reason = nil_reason

    @classmethod
    def parse(cls, elm):
        if elm.get(XSI + 'nil'):
            return cls(elm.get('nilReason'))
        else:
            return None

    def __repr__(self) -> str:
        return f'Nil(reason: {self.nil_reason})'


def construct_dataclass(schema: dict, classname: str):

    # this method defined here is placed in the to be contructed class
    @classmethod
    def _parse(cls, featureElm):
        c = cls()
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
                else:
                    # field type is complex (not str)
                    # recurse
                    attribute += [feature_type.parse(elm2) for elm2 in elm.iter('{*}' + field.type)]

                if len(attribute) == 0:
                    c.__setattr__(field.name, None)
                elif len(attribute) == 1:
                    c.__setattr__(field.name, attribute[0])
                else:
                    c.__setattr__(field.name, attribute)
        return c


    class_fields = list()
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

    feature_types['PolygonPatch'] = PolygonPatch

    for feature_name in schema.keys():
        # construct dataclass from schema
        feature_class = construct_dataclass(schema, feature_name)
        feature_types[feature_name] = feature_class


if __name__ == '__main__':
    print("Automaticaly constructed feature types (DataClasses) from aixm_schema")
    pprint(feature_types)
