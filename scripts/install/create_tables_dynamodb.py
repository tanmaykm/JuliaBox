#! /usr/bin/env python

from boto.dynamodb2.table import Table
from db import JBoxUserV2, JBoxInvite, JBoxDiskState, JBoxAccountingV2, JBoxDynConfig, \
    JBoxSessionProps, JBoxCourseHomework, JBoxAPISpec


def table_exists(name):
    t = Table(name)
    try:
        t.describe()
        return True
    except:
        return False

for cls in [JBoxUserV2, JBoxInvite, JBoxDiskState, JBoxAccountingV2, JBoxDynConfig,
            JBoxSessionProps, JBoxCourseHomework, JBoxAPISpec]:
    print("Creating %s..." % (cls.NAME,))
    if table_exists(cls.NAME):
        print("\texists already!")
    else:
        # TODO: throughput should be picked up from an external configuration
        tput = 1
        if cls.INDEXES is not None:
            tput += len(cls.INDEXES)
        Table.create(cls.NAME, schema=cls.SCHEMA, indexes=cls.INDEXES, throughput={
            'read': tput,
            'write': tput
        })
        print("\tcreated.")
