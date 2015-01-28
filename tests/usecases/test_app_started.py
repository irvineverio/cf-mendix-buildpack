#!/usr/bin/env python

import os
import unittest
import requests
from mxplient.mxplient import MXClient
from nose.tools import assert_equal


class TestApplicationStarted(unittest.TestCase):

    def setUp(self):
        self.app_url = os.environ.get('MX_APP_URL', None)
        self.admin_password = os.environ.get('MX_ADMIN_PASSWORD', None)

    def test_admin_login(self):
        assert(self.app_url is not None)
        assert(self.admin_password is not None)
        self.mxc = MXClient(self.app_url,
                            username='MxAdmin',
                            password=self.admin_password)

    def test_application_up(self):
        assert(self.app_url is not None)
        r = requests.get(self.app_url + '/xas/', auth=('user', 'pass'), verify=True)
        assert_equal(r.status_code, 401)

    def tearDown(self):
        pass
