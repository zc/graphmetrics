import hashlib
import os
import pprint
import zc.metarecipe
import zc.zk

class Recipe(zc.metarecipe.Recipe):

    def __init__(self, buildout, name, options):
        super(Recipe, self).__init__(buildout, name, options)
        assert name.endswith('.0'), name # There can be only one.

        zk = zc.zk.ZK('zookeeper:2181')

        zk_options = zk.properties(
            '/' + name.replace(',', '/').rsplit('.', 1)[0])

        with open(os.path.join(os.path.dirname(__file__), 'zkdeployment.cfg')
                  ) as f:
            self.parse(f.read() % dict(
                name = name,
                home = '/home/databases',
                digest = hashlib.sha224(
                    pprint.pformat(dict(zk_options))).hexdigest(),
                url = str(zk_options['url']),
                secret = str(zk_options['secret']),
                zim = str(zk_options['zim']),
                ))
