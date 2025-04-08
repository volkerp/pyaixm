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
class GmlObject:
    id_registry = {}
    gml_id: str = None

    def parse(self, elm):
        self.gml_id = elm.get(GML + 'id')
        GmlObject.id_registry[self.gml_id] = self
   

@dataclass
class Feature(GmlObject):
    identifier_registry = {}
    identifier: str = None
    parent: 'Feature' = None

    def parse(self, elm):
        super().parse(elm)

        if (identi_elm := elm.find(GML + 'identifier')) is not None:
            self.identifier = identi_elm.text
            Feature.identifier_registry[self.identifier] = self

    def dict(self):
        d = {}
        for field in fields(self):
            if field.name in {'parent', 'id_registry', 'identifier_registry'}:
                continue

            value = getattr(self, field.name)
            d[field.name] = value

        return d

    def to_json(self):
        return { self.__class__.__name__: self.dict() }


@dataclass
class GMLCircleByCenterPoint:
    pos: str = None

    def parse(self, elm):
        pos = elm.find(GML + 'pos').text
        print('Parse CircleByCenterPoint')



@dataclass
class GMLArcByCenterPoint:
    pos: str = None
    radius: float = None
    radius_uom: str = None
    startAngle: float = None
    endAngle: float = None

    def _parse_poslist(s: str):
        return [float(v) for  v in s.strip().split()] 

    @classmethod
    def parse(cls, elm):
        o = cls()
        o.pos = cls._parse_poslist(elm.find(GML + 'pos').text)
        o.radius = float(elm.find(GML + 'radius').text)
        o.radius_uom = elm.find(GML + 'radius').get('uom')
        if elm.find(GML + 'startAngle') is not None:
            o.startAngle = float(elm.find(GML + 'startAngle').text)
        if elm.find(GML + 'endAngle') is not None:
            o.endAngle = float(elm.find(GML + 'endAngle').text)

        return o


@dataclass
class GMLGeodesicString:
    pos: typing.List

    def _parse_poslist(s: str):
        return [float(v) for  v in s.strip().split()] 

    @classmethod
    def parse(cls, elm):
        p = []
        for pl in elm.iter('{*}posList'):
            p += cls._parse_poslist(pl.text)
        for pos in elm.iter('{*}pos'):
            p += cls._parse_poslist(pos.text)

        return cls(pos=p)

    def dict(self):
        return { 'pos': self.pos }
    
    def to_json(self):
        return { 'GMLGeodesicString': self.dict() }


@dataclass
class GMLPatch:
    patches: typing.List
    exterior_ring: typing.List = None
    gmlid: str = None
    parent: 'Feature' = None
    registry = []

    def _parse_poslist(s: str):
        return [float(v) for  v in s.split()]

    @classmethod
    def parse(cls, elm, parent = None):
        patches = []

        #elm_segments = next(elm.iter('{*}segments'))
        for seg in elm.iter('{*}segments'):
            for sub_seg in seg:
                if sub_seg.tag == GML + 'GeodesicString' or sub_seg.tag == GML + 'LineStringSegment':
                    patches.append(GMLGeodesicString.parse(sub_seg))
                elif sub_seg.tag == GML + 'ArcByCenterPoint':
                    patches.append(GMLArcByCenterPoint.parse(sub_seg))
 #           for pl in seg.iter('{*}posList'):
 #               p += cls._parse_poslist(pl.text)
 #           for pos in seg.iter('{*}pos'):
 #               p += cls._parse_poslist(pos.text)

        p = cls(patches, parent=parent)
        cls.registry.append(p)
        return p

    def dict(self):
        return { 'patches': self.patches,
                'gmlid': self.gmlid }

    to_json = dict


class XLink:
    xlink_registry = {}
    target: Feature = None
    title: str = None

    def __init__(self, elm):
        self.href = elm.get('{http://www.w3.org/1999/xlink}href')
        self.title = elm.get('{http://www.w3.org/1999/xlink}title')
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
                # local reference
                feature = GmlObject.id_registry.get(xlink.href[1:])
            elif xlink.href.startswith('urn:uuid:'):
                # universal resource name (URN) pointing to a UUID
                feature = Feature.identifier_registry.get(xlink.href[9:])
            else:
                # external reference and natural keys are not supported
                feature = None

            if feature is None:
                warnings.warn(f"can't resolve xlink:href: {xlink.href}")
            else:
                xlink.target = feature

    def __repr__(self) -> str:
        return f"XLink(href: {self.href} target: {'resolved' if self.target else 'unresolved'})"

    def to_json(self) -> dict:
        return { 'XLink': { 'href': self.href, 'target': self.target.__class__.__name__, 'title': self.title } }


class Nil:
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
                elif field.type == 'GMLPatch':
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


    new_class = make_dataclass(classname, class_fields, bases=(Feature, ), namespace={'parse': _parse})

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

    feature_types['GMLPatch'] = GMLPatch
    feature_types['CircleByCenterPoint'] = GMLCircleByCenterPoint

    for feature_name in schema.keys():
        # construct dataclass from schema
        feature_class = construct_dataclass(schema, feature_name)
        feature_types[feature_name] = feature_class


if __name__ == '__main__':
    print("Automaticaly constructed feature types (DataClasses) from aixm_schema")
    pprint(feature_types)
