##############################################################################
#
# Copyright (c) 2010 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
from zope.testing import setupstack
import logging
import manuel.capture
import manuel.doctest
import manuel.testing
import sys
import unittest


def setUp(test):
    setupstack.setUpDirectory(test)


    def setupLogging():
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(name)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        oldlevel = logging.getLogger().getEffectiveLevel()
        logging.getLogger().setLevel(logging.INFO)

        def restore():
            logging.getLogger().removeHandler(handler)
            logging.getLogger().setLevel(oldlevel)

        setupstack.register(test, restore)

    test.globs['setupLogging'] = setupLogging

def test_suite():
    return unittest.TestSuite((
        manuel.testing.TestSuite(
            manuel.doctest.Manuel() + manuel.capture.Manuel(),
            'collectmetrics.test', 'zkdeployment.test',
            setUp=setUp, tearDown=setupstack.tearDown,
            ),
        ))

