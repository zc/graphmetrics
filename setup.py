##############################################################################
#
# Copyright (c) Zope Corporation and Contributors.
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
name = 'zc.graphtracelogs'
version = '0'
description = """
"""

import os
from setuptools import setup, find_packages

entry_points = """
[console_scripts]
collect_tracelogs = zc.graphtracelogs.collecttracelogs:main
collect_metrics = zc.graphtracelogs.collectmetrics:main
[zc.buildout]
default = zc.graphtracelogs.zkdeployment:Recipe
"""

setup(
    name = name,
    version = version,
    author = 'Jim Fulton',
    author_email = 'jim@zope.com',
    description = description.split('\n', 1)[0],
    long_description = description.split('\n', 1)[1].lstrip(),
    license = 'ZPL 2.1',

    packages = find_packages('src'),
    namespace_packages = name.split('.')[:1],
    package_dir = {'': 'src'},
    install_requires = [
        'py-rrdtool',
        'pytz',
        'requests',
        'setuptools',
        'z3c.recipe.mkdir',
        'zc.buildout',
        'zc.metarecipe',
        'zc.ngi',
        'zc.recipe.deployment',
        'zc.recipe.rhrc',
        'zc.wsgisessions',
        'zc.zdaemonrecipe',
        'zc.zk [static]',
        ],
    extras_require=dict(test=['manuel', 'zope.testing', 'zc.zk [test]']),
    zip_safe = False,
    entry_points=entry_points,
    )
