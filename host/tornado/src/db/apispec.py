from boto.dynamodb2.fields import HashKey, RangeKey, GlobalKeysOnlyIndex, GlobalAllIndex
from boto.dynamodb2.types import STRING
from boto.dynamodb2.exceptions import ItemNotFound

import datetime
import pytz

from db.db_base import JBoxDB


class JBoxAPISpec(JBoxDB):
    NAME = 'jbox_apispec'

    SCHEMA = [
        HashKey('api_name', data_type=STRING)
    ]

    INDEXES = [
        GlobalKeysOnlyIndex('publisher-index', parts=[
            HashKey('publisher', data_type=STRING)
        ])
    ]

    TABLE = None

    def __init__(self, api_name, cmd=None, endpt_in=None, endpt_out=None, image_name=None, methods=None,
                 publisher=None, timeout_secs=None, create=False):
        if self.table() is None:
            return

        self.item = None
        if create:
            dt = datetime.datetime.now(pytz.utc)
            data = {
                'api_name': api_name,
                'cmd': cmd,
                'endpt_in': endpt_in,
                'endpt_out': endpt_out,
                'methods': methods,
                'publisher': publisher,
                'create_time': JBoxAPISpec.datetime_to_epoch_secs(dt)
            }
            if image_name is not None:
                data['image_name'] = image_name
            if timeout_secs is not None:
                data['timeout_secs'] = timeout_secs
            self.create(data)

        self.item = self.table().get_item(api_name=api_name)
        self.is_new = create

    def get_api_name(self):
        return self.get_attrib('api_name', None)

    def get_endpoint_in(self):
        return int(self.get_attrib('endpt_in', None))

    def get_endpoint_out(self):
        return int(self.get_attrib('endpt_out', None))

    def get_timeout_secs(self):
        return int(self.get_attrib('timeout_secs', 30))

    def get_methods(self):
        return self.get_attrib('methods', '').split(',')

    def get_publisher(self):
        return self.get_attrib('publisher', None)

    def get_image_name(self):
        return self.get_attrib('image_name', 'juliabox/juliaboxapi:latest')

    def get_cmd(self):
        return self.get_attrib('cmd', None)

    def get_create_time(self):
        return int(self.get_attrib('create_time', None))

    def set_cmd(self, cmd):
        self.set_attrib('cmd', cmd)

    def set_methods(self, methods):
        self.set_attrib('methods', ','.join(methods))

    def set_timeout_secs(self, timeout_secs):
        self.set_attrib('timeout_secs', timeout_secs)

    def set_endpoint_in(self, endpt_in):
        self.set_attrib('endpt_in', endpt_in)

    def set_endpoint_out(self, endpt_out):
        self.set_attrib('endpt_out', endpt_out)

    def set_publisher(self, publisher):
        self.set_attrib('publisher', publisher)

    def set_image_name(self, image_name):
        self.set_attrib('image_name', image_name)

    def as_json(self):
        return {
            'api_name': self.get_api_name(),
            'cmd': self.get_cmd(),
            'endpt_in': self.get_endpoint_in(),
            'endpt_out': self.get_endpoint_out(),
            'image_name': self.get_image_name(),
            'methods': self.get_methods(),
            'publisher': self.get_publisher(),
            'timeout_secs': self.get_timeout_secs(),
            'create_time': self.get_create_time()
        }

    @staticmethod
    def get_api_info(publisher, api_name):
        if publisher is None and api_name is None:
            raise
        ret = []
        if publisher is None:
            ret.append(JBoxAPISpec(api_name).as_json())
        else:
            if api_name is None:
                api_name = ' '
            records = JBoxAPISpec.table().query_2(publisher__eq=publisher, api_name__ge=api_name,
                                                  index='publisher-api_name-index')
            for api in records:
                ret.append(JBoxAPISpec(api['api_name']).as_json())
        return ret

    @staticmethod
    def set_api_info(api_name, cmd=None, endpt_in=None, endpt_out=None, image_name=None, methods=None,
                     publisher=None, timeout_secs=None):
        try:
            api = JBoxAPISpec(api_name)
            if cmd is not None:
                api.set_cmd(cmd)
            # TODO: use conditional put to get unique port numbers from an entry in dynconfig
            if endpt_in is not None:
                api.set_endpoint_in(endpt_in)
            if endpt_out is not None:
                api.set_endpoint_out(endpt_out)
            if image_name is not None:
                api.set_image_name(image_name)
            if publisher is not None:
                api.set_publisher(publisher)
            if timeout_secs is not None:
                api.set_timeout_secs(timeout_secs)
            api.save()
        except ItemNotFound:
            JBoxAPISpec(api_name, cmd=cmd, endpt_in=endpt_in, endpt_out=endpt_out, image_name=image_name,
                        methods=methods, publisher=publisher, timeout_secs=timeout_secs, create=True)