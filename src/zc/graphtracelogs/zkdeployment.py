import hashlib
import os
import zc.metarecipe

class Recipe(zc.metarecipe.Recipe):

    def __init__(self, buildout, name, options):
        super(Recipe, self).__init__(buildout, name, options)
        assert name.endswith('.0'), name # There can be only one.
        self['deployment'] = dict(
            recipe = 'zc.recipe.deployment',
            name=name,
            user='zope',
            )
        with open(os.path.join(os.path.dirname(__file__),
                               'zkdeployment.template')) as f:
            template = f.read()
        self.parse(template)
