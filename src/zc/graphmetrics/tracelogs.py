import BTrees.OOBTree
import bobo
import boboserver
import collections
import datetime
import hashlib
import hmac
import json
import logging
import os
import persistent.mapping
import pool
import pprint
import pytz
import re
import rrdtool
import socket
import sys
import tempfile
import time
import urllib
import urllib2

import zope.component

import zc.graphmetrics.auth

from zc.graphmetrics.auth import who

dojoroot = 'http://ajax.googleapis.com/ajax/libs/dojo/1.8.3'

inst_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match
numbered_instance = re.compile('instance(\d+)$').match
portly_instance = re.compile('-(\d\d\d+)').search
unportly_instance = re.compile('([-a-z]+)\d*').match

def config(config):
    global rrd_dir, get_pools
    rrd_dir = config['rrd']
    if 'pool_info' in config:
        if config['pool_info']:
            pool_addr = config['pool_info'].split(':')
            pool_addr = pool_addr[0], int(pool_addr[1])
            get_pools = lambda : pool.get_pools(pool_addr)
        else:
            get_pools = lambda : []
    else:
        get_pools = pool.get_pools

    if 'logging' in config:
        if not getattr(logging, 'been_configured', False):
            import ZConfig
            ZConfig.configureLoggers(config['logging'].replace('$(', '%('))
            logging.been_configured = True

hex2 = lambda v: ('0'+hex(v)[2:])[-2:]

styles = []
for thickness in 1, 2:
    for dash in False, True:
        for color in ("000000", "0000ff", "ff0000", "dda0dd",
                      "800080", "7fff00", "6495ed", "ffff00"):
            styles.append((thickness, dash, color))

nstyles = len(styles)




@bobo.resource('/', check=zc.graphmetrics.auth.checker)
def home(request):
    return bobo.redirect('%s/default/' % who(request))

BIG = 1<<31

static = boboserver.static(
    '/static', os.path.join(os.path.dirname(__file__), 'static'))

def rrdname(instance):
    instance += '.rrd'
    assert inst_rrd(instance)
    return instance

@bobo.query("/shorten")
def shorten(url):
    hash = hmac.new("tads591'Mekong", url, hashlib.sha1).hexdigest()
    f = urllib2.urlopen("http://zo.pe/shorten?url=%s&hash=%s" %
                        (urllib.quote(url), hash))
    r = json.loads(f.read())['url']
    f.close()
    return r

@bobo.subroute('/:user/:name', scan=True)
class App:

    def __init__(self, request, user, name):
        self.request = request
        self.user = user
        self.name = name

        root = request.environ['zodb.connection']

    @bobo.query('')
    def base(self):
        return bobo.redirect(self.request.url+'/')

    @bobo.query('/', check=zc.graphmetrics.auth.checker)
    def index(self):
        return index_html % ("%s/%s" % (self.user, self.name))

    @bobo.query('/web.js', content_type="text/javascript")
    def js(self):
        return open(os.path.join(os.path.dirname(__file__), 'tracelogs.js')
                    ).read()

    def get_definitions(self, user=None):
        if user is None:
            user = self.user

        root = self.request.environ['zodb.connection'].root()
        try:
            definitions = root['definitions']
        except KeyError:
            definitions = root['definitions'] = BTrees.OOBTree.BTree()
        try:
            return definitions[user]
        except KeyError:
            definitions[user] = r = BTrees.OOBTree.BTree()
            return r

    definitions = property(get_definitions)

    @bobo.query(content_type='application/json',
                check=zc.graphmetrics.auth.checker)
    def load(self):
        defs = self.definitions.get(self.name)
        if defs is None:
            result = dict(charts=[])
        else:
            charts = sorted(defs['charts'].iteritems())
            result = dict(
                charts=[i[1] for i in charts],
                imgids=[i[0] for i in charts],
                )
        return json.dumps(result)

    @bobo.query(content_type='application/json',
                check=zc.graphmetrics.auth.checker)
    def get_instances(self):
        customers = {}
        by_addr = {}
        pools = {}
        for inst in sorted(
            (f[:-4] for f in os.listdir(rrd_dir) if inst_rrd(f)),
            key=(lambda name:
                 os.stat(os.path.join(rrd_dir, name+'.rrd')).st_mtime
                 ),
            ):
            addr, customer, inst_name = inst.split('__')
            host = addr
            try:
                addr = socket.gethostbyname(host)
            except:
                logging.exception("Couldn't look up host %s" % host)
                addr = host

            port = None
            m = portly_instance(inst_name)
            if m:
                port = int(m.group(1))
                by_addr["%s:%s" % (addr, port)] = inst

                if customer not in customers:
                    customers[customer] = {}
                instance_type = inst_name.rsplit('-', 1)[0]+'-instances'
                if instance_type not in customers[customer]:
                    customers[customer][instance_type] = []
                customers[customer][instance_type].append((inst, inst))
            else:
                m = unportly_instance(inst_name)
                if m:
                    if customer not in customers:
                        customers[customer] = {}
                    instance_type = m.group(1)+'-workers'
                    if instance_type not in customers[customer]:
                        customers[customer][instance_type] = []
                    customers[customer][instance_type].append((inst, inst))

            hosts = customers.get(customer)
            if hosts is None:
                hosts = customers[customer] = {}

            instances = hosts.get(host)
            if instances is None:
                instances = hosts[host] = []
            instances.append((inst_name, inst))

        for customer, pools in customers.items():
            for label, instances in pools.items():
                if label.endswith('-instances') or label.endswith('-workers'):
                    instances.sort()
                    if len(instances) > 1:
                        all = (("%s-%s," % (customer, label)) +
                               (','.join(i[0] for i in instances)))
                        compare_rpm = (
                            (',rpm,%s-%s-rpm,' % (customer, label))
                            + (','.join(i[0] for i in instances)))
                        compare_max_rpm = (
                            (',spr,%s-%s-max-rpm,' % (customer, label))
                            + (','.join(i[0] for i in instances)))
                        max_headroom = (
                            (',mh,%s-%s-max-headroom,' % (customer, label))
                            + (','.join(i[0] for i in instances)))
                        instances[0:0] = [
                            ('all', all),
                            ('compare rpm', compare_rpm),
                            ('compare max rpm', compare_max_rpm),
                            ('max headroon', max_headroom),
                            ]

        for info, addrs in get_pools():
            customer = info['customer'].lower()
            label = "%(pooltype)s-%(desc)s" % info
            instances = sorted([by_addr[addr] for addr in addrs
                                if addr in by_addr])
            if len(instances) > 1:
                all = ("%s-%s," % (customer, label)) + (','.join(instances))
                compare_rpm = (
                    (',rpm,%s-%s-rpm,' % (customer, label))
                    + (','.join(instances)))
                compare_max_rpm = (
                    (',spr,%s-%s-max-rpm,' % (customer, label))
                    + (','.join(instances)))
                max_headroom = (
                    (',mh,%s-%s-max-headroom,' % (customer, label))
                    + (','.join(instances)))
                instances = [(inst, inst)
                             for inst in sorted(instances)]
                instances[0:0] = [
                    ('all', all),
                    ('compare rpm', compare_rpm),
                    ('compare max rpm', compare_max_rpm),
                    ('max headroon', max_headroom),
                    ]
                cpools = customers.get(customer)
                if cpools is None:
                    cpools = customers[customer] = {}
                cpools[label] = instances

        return json.dumps(dict(
            customers=sorted((customer, sorted(customers[customer].items()))
                             for customer in customers),
            saved=list(self.get_definitions(who(self.request))),
            ))

    @bobo.query('/show.png', content_type='image/png',
                check=zc.graphmetrics.auth.checker)
    def show(self, imgid, instance, generation=0,
             start=None, end=None, start_time=None, end_time=None,
             width=900, height=None, step=None,
             log=None, trail=None, upper_limit=None, lower_limit=None,
             ):
        params = dict(i for i in dict(
            instance = instance,
            start = start, start_time = start_time,
            end = end, end_time = end_time,
            height = height,
            step = step,
            log = log,
            trail=trail,
            upper_limit = upper_limit,
            lower_limit = lower_limit,
            generation = generation,
            ).iteritems() if i[1])

        if start_time:
            if not start:
                start = str(datetime.date.today())
            start += start_time

        if end_time:
            if not end:
                end = str(datetime.date.today())
            end += end_time

        log = log == 'y'

        lines = []
        compare = mh = pool = False
        if ',' in instance:
            pool = True
            instances = instance.split(',')
            if not instances[0]:
                instances.pop(0)
                compare = instances.pop(0)
                if compare == 'mh':
                    compare = ''
                    mh=True
            title = instances.pop(0).replace('-', ' ')
            ninstances = len(instances)
            n=0
            for instance in instances:
                rrd_path = os.path.join(rrd_dir, rrdname(instance))
                if not os.path.exists(rrd_path):
                    logging.error("Can't find %r", rrd_path)
                    continue
                if compare:
                    thickness, dash, color = styles[n % nstyles]
                    legend = instance[:-4]
                    legend = "%s-%s" % (
                        ''.join(legend.split('.')[0:2]).replace('app', ''),
                        legend.split('__')[-1])
                    if dash:
                        legend = '- ' + legend
                    lines.extend([
                        rrdtool.Def("v%s" % n, rrd_path, data_source=compare,
                                    cf=rrdtool.AverageCF),
                        "LINE%s:v%s#%s:%s%s" % (
                            thickness, n, color, legend,
                            ':dashes' if dash else ''),
                        ])
                else:
                    lines.extend([
                        rrdtool.Def("rpm%s" % n, rrd_path, data_source="rpm",
                                    cf=rrdtool.AverageCF),
                        rrdtool.Def("epm%s" % n,
                                    rrd_path, data_source="epm",
                                    cf=rrdtool.AverageCF),
                        rrdtool.Def("bl%s" % n,
                                    rrd_path, data_source="bl",
                                    cf=rrdtool.AverageCF),
                        ])
                    if 1 or log or mh:
                        lines.append(
                            rrdtool.Def("spr%s" % n, rrd_path,
                                        data_source="spr",
                                        cf=rrdtool.AverageCF),
                            )
                lines.append(
                    rrdtool.Def("start%s" % n, rrd_path,
                                data_source="start",
                                cf=rrdtool.AverageCF)
                    )
                n += 1

            if not compare:
                lines.extend([
                    "CDEF:rpm=rpm0,UN,0,rpm0,IF,%s" % (
                        ','.join("rpm%s,UN,0,rpm%s,IF,+" % (i, i)
                                 for i in range(1, n))),
                    "CDEF:epm=epm0,UN,0,epm0,IF,%s" % (
                        ','.join("epm%s,UN,0,epm%s,IF,+" % (i, i)
                                 for i in range(1, n))),
                    "CDEF:bl=bl0,UN,0,bl0,IF,%s" % (
                        ','.join("bl%s,UN,0,bl%s,IF,+" % (i, i)
                                 for i in range(1, n))),
                    ])
                if 1 or log or mh:
                    lines.append(
                        "CDEF:spr=spr0,UN,0,spr0,IF,%s" % (
                            ','.join("spr%s,UN,0,spr%s,IF,+" % (i, i)
                                     for i in range(1, n))),
                        )
                if mh:
                    lines.append(
                        'CDEF:mh=spr,rpm,-,spr,/,100,*'
                        )
            lines.append("CDEF:start=%s,%s,AVG" % (
                ','.join("start%s" % i for i in range(0, n)),
                n))
        else:
            title = instance.replace('__', ' ')
            rrd_path = os.path.join(rrd_dir, rrdname(instance))
            assert os.path.exists(rrd_path)
            lines.extend([
                rrdtool.Def("rpm", rrd_path, data_source="rpm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("epm", rrd_path, data_source="epm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("bl", rrd_path, data_source="bl",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("start", rrd_path, data_source="start",
                            cf=rrdtool.AverageCF),
                ])
            if 1 or log:
                lines.append(
                    rrdtool.Def("spr", rrd_path, data_source="spr",
                                cf=rrdtool.AverageCF),
                    )

        fd, img_path = tempfile.mkstemp('.png')
        g = rrdtool.RoundRobinGraph(img_path)

        options = dict(
            width=int(width)-70,
            height=height and int(height) or 200,
            title=title,
            )
        if upper_limit:
            options['upper_limit'] = int(upper_limit)
            options['rigid'] = None
        if lower_limit:
            options['lower_limit'] = int(lower_limit)
            options['rigid'] = None

        if trail:
            options['start'] = int(time.time()/60*60-int(trail)*3600)
        else:
            if start:
                options['start'] = parsedt(start)
            if end:
                options['end'] = parsedt(end)

        if step:
            options['step'] = int(step)*60

        if not compare:
            if mh:
                lines.extend([
                    rrdtool.LINE1("mh", rrggbb="00ff00", legend="max-headroom"),
                    rrdtool.LINE1("epm", rrggbb="ff0000", legend="epm"),
                    rrdtool.LINE1("bl", rrggbb="e082e6", legend="waiting"),
                    ])
            else:
                lines.extend([
                    rrdtool.LINE1("rpm", rrggbb="00ff00", legend="rpm"),
                    rrdtool.LINE1("epm", rrggbb="ff0000", legend="epm"),
                    rrdtool.LINE1("bl", rrggbb="e082e6", legend="waiting"),
                    ])

                if 1 or log:
                    lines.append(
                        rrdtool.LINE1("spr", rrggbb="93f9fb", legend="max rpm"),
                        )
        if log:
            options['logarithmic'] = None
        lines.append('TICK:start#00000055:1:start')
        #lines.append('-Y')

        g.graph(*lines, **options)

        updated = ''
        if self.user == who(self.request):
            defs = self.definitions.get(self.name)
            if defs is None:
                defs = persistent.mapping.PersistentMapping(
                    charts=BTrees.OOBTree.BTree())
                self.definitions[self.name] = defs
            old = defs['charts'].get(imgid)
            if ((not old)
                or (params != old
                    and (params.get('generation', BIG)
                         > old.get('generation', 0)
                         )
                    )
                ):
                defs['charts'][imgid] = params
                updated = ' updated'

        os.close(fd)
        with open(img_path) as f:
            result = f.read()
        os.remove(img_path)
        return result

    @bobo.post('/destroy', check=zc.graphmetrics.auth.checker)
    def destroy(self, imgid):
        logging.info("%r destroy %r %r %r",
                     who(self.request), self.user, self.name, imgid)
        if self.user == who(self.request):
            defs = self.definitions.get(self.name)
            if defs is None:
                return
            if imgid in defs['charts']:
                del defs['charts'][imgid]
                if not defs['charts']:
                    del self.definitions[self.name]
                    return 'empty'
                return 'destroyed %r' % defs['charts']._p_oid
        return ''

    @bobo.post(content_type='application/json',
               check=zc.graphmetrics.auth.checker)
    def save(self, name, overwrite=False):
        me = who(self.request)
        definitions = self.get_definitions(me)
        old = definitions.get(name)
        if (old is not None) and old['charts'] and not overwrite:
            return json.dumps(dict(exists=True))
        new = _copydefs(self.definitions.get(self.name))
        if (new is not None) and new['charts']:
            definitions[name] = new
        else:
            if old is not None:
                del definitions[name]

        return json.dumps(dict(url='../../%s/%s' % (me, name)))

def _copydefs(defs):
    if defs is None:
        return defs
    charts = defs['charts']
    return persistent.mapping.PersistentMapping(
        charts=BTrees.OOBTree.BTree(charts.items()))

dst = pytz.timezone('US/Eastern').dst

def parsedt(s):
    if 'T' in s:
        d, t = s.split('T')
        t = d.split('-')+t.split(':')
    else:
        t = s.split('-')
    t = map(int, t)

    t.extend([0]*(8-len(t)))
    t.append(bool(dst(datetime.datetime(*t[:6])).seconds))
    return int(time.mktime(t))

index_html = """
<html><head><title>Tracelog: %%s</title>
<style type="text/css">
@import "%(dojoroot)s/dojo/resources/dojo.css";
@import "%(dojoroot)s/dijit/themes/tundra/tundra.css";
@import "%(dojoroot)s/dojox/grid/resources/Grid.css";
</style>
<script type="text/javascript">
  djConfig={ baseUrl: "../../", modulePaths: { zc: "static" }};
</script>
<script type="text/javascript"
        src="%(dojoroot)s/dojo/dojo.js"
        ></script>
<script src="https://login.persona.org/include.js"></script>
<script type="text/javascript" src="/login.js"></script>
<script type="text/javascript" src="web.js"></script>
</head><body class="tundra"></body></html>
""" % globals()
