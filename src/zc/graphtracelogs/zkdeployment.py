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

        self.parse("""
        [rrd]
        recipe = z3c.recipe.mkdir
        paths = /mnt/ephemeral0/rrds/tracelog
        user = zope
        group = zope
        """)

        self.parse("""
        [collect]
        recipe = zc.zdaemonrecipe
        deployment = deployment
        rrdpath = ${rrd:paths}
        logpath = /mnt/ephemeral0/logs/tracelogs/z4m
        program =
          ${buildout:bin-directory}/collect_tracelogs ${:logpath} ${:rrdpath}
        zdaemon.conf =
           <runner>
              transcript ${deployment:log-directory}/collect-tracelogs.log
           </runner>
        """)

        self.parse("""
        [paste.ini]
        recipe = zc.recipe.deployment:configuration
        deployment = deployment
        s =
        text =
          ${:s}[app:main]
          ${:s}use = egg:bobo
          ${:s}bobo_configure = zc.graphtracelogs.tracelogs:config
          ${:s}bobo_resources = zc.graphtracelogs.tracelogs
          ${:s}
          ${:s}rrd = ${collect:rrdpath}
          ${:s}pool_info =
          ${:s}
          ${:s}filter-with = reload
          ${:s}
          ${:s}logging =
          ${:s}     <logger>
          ${:s}        level INFO
          ${:s}        <logfile>
          ${:s}           PATH STDOUT
          ${:s}           format $(asctime)s $(levelname)s $(name)s $(message)r
          ${:s}        </logfile>
          ${:s}     </logger>
          ${:s}
          ${:s}[filter:reload]
          ${:s}use = egg:bobo#reload
          ${:s}modules = zc.graphtracelogs.metrics
          ${:s}filter-with = zodb
          ${:s}
          ${:s}[filter:zodb]
          ${:s}use = egg:zc.zodbwsgi
          ${:s}#filter-with = debug
          ${:s}configuration =
          ${:s}  <zodb>
          ${:s}     <filestorage>
          ${:s}        path ${collect:rrdpath}/web.fs
          ${:s}     </filestorage>
          ${:s}  </zodb>
          ${:s}
          ${:s}[filter:debug]
          ${:s}use = egg:bobo#debug
          ${:s}
          ${:s}[server:main]
          ${:s}use = egg:Paste#http
          ${:s}host = 0.0.0.0
          ${:s}port = 8081
        """)

        self.parse("""
        [web]
        recipe = zc.zdaemonrecipe
        deployment = deployment
        program = ${buildout:bin-directory}/paster serve ${paste.ini:location}
        zdaemon.conf =
           <runner>
              transcript ${deployment:log-directory}/web.log
           </runner>
        """)

        self.parse("""
        [rc]
        recipe = zc.recipe.rhrc
        deployment = deployment
        parts = web
        chkconfig = 345 99 10
        process-management = true
        """)
