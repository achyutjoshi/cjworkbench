from django.test import TestCase
from server.utils import *
from server.tests.utils import *
from pandas.util import hash_pandas_object
import pandas as pd
import os

class UtilsTestCase(TestCase):

    def test_sanitize_dataframe(self):
        # Load a test table which has a dict column
        fname = os.path.join(settings.BASE_DIR, 'server/tests/test_data/sfpd.json')
        sfpd_dict = json.load(open(fname))
        sfpd = pd.DataFrame(sfpd_dict)

        sfpd_types = sfpd.apply(pd.api.types.infer_dtype)
        self.assertEqual(sfpd.columns[6], 'location')
        self.assertEqual(sfpd_types[6], 'mixed')

        sanitize_dataframe(sfpd)

        # should have converted mixed types (and other complex types) to string
        sfpd_types = sfpd.apply(pd.api.types.infer_dtype)
        self.assertEqual(sfpd_types[6], 'string')

        hash_pandas_object(sfpd) # will crash on complex types, used by StoredObject
