import bobo
import BTrees.OOBTree
import datetime
import json
import logging
import os
import persistent.mapping
import pprint
import pytz
import re
import rrdtool
import sys
import tempfile
import time

dojoroot = 'http://ajax.googleapis.com/ajax/libs/dojo/1.4.3'

inst_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match
numbered_instance = re.compile('instance(\d+)$').match

def config(config):
    global rrd_dir, rrd_updated
    rrd_dir = config['metrics-rrd']
    rrd_updated = os.path.join(rrd_dir, '.updated')

def who(request):
    if 'HTTP_AUTHORIZATION' in request.environ:
        return request.environ['HTTP_AUTHORIZATION'
                               ].split()[1].decode('base64').split(':')[0]
    return 'anon'


series = None
series_update = None
def get_series_data():
    global series, series_update
    if series is not None and series_update >= os.stat(rrd_updated).st_mtime:
        return series
    result = []
    lprefix = len(rrd_dir)+1
    for path, dirs, files in os.walk(rrd_dir):
        result.extend(os.path.join(path, name)[lprefix:-4]
                      for name in files
                      if name.endswith('.rrd')
                      )
    series = json.dumps(dict(series=sorted(result)))
    series_update = os.stat(rrd_updated).st_mtime
    return series


@bobo.resource('/metrics')
def home(request):
    return bobo.redirect(request.url+'/%s/default/' % who(request))


BIG = 1<<31

plotparam = re.compile('(legend|color|data)(\d+)$').match

@bobo.subroute('/metrics/:user/:name', scan=True)
class App:

    def __init__(self, request, user, name):
        self.request = request
        self.user = user
        self.name = name

        root = request.environ['zodb.connection']

    @bobo.query('')
    def base(self):
        return bobo.redirect(self.request.url+'/')

    @bobo.query('/')
    def index(self):
        return index_html

    @bobo.query('/web.js', content_type="text/javascript")
    def js(self):
        return open(os.path.join(os.path.dirname(__file__), 'metrics.js')
                    ).read()

    def get_definitions(self, user=None):
        if user is None:
            user = self.user

        root = self.request.environ['zodb.connection'].root()
        try:
            definitions = root['metrics']
        except KeyError:
            definitions = root['metrics'] = BTrees.OOBTree.BTree()
        try:
            return definitions[user]
        except KeyError:
            definitions[user] = r = BTrees.OOBTree.BTree()
            return r

    definitions = property(get_definitions)

    @bobo.query(content_type='application/json')
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

    @bobo.query(content_type='application/json')
    def get_series(self):
        return get_series_data()

    @bobo.query('/show.png', content_type='image/png')
    def show(self, bobo_request, imgid, generation=0,
             start=None, end=None, start_time=None, end_time=None,
             width=900, height=None, step=None, title='',
             log=None, trail=None, upper_limit=None, lower_limit=None,
             ):

        params = dict(i for i in dict(
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

        plots = {}

        for name, value in bobo_request.GET.items():
            m = plotparam(name)
            if not m:
                continue
            params[name] = value
            i = int(m.group(2))
            plot = plots.get(i)
            if not plot:
                plot = plots[i] = {}
            plot[m.group(1)] = value

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
        for n, plot in sorted(plots.iteritems()):
            series = plot['data']
            if ',' in series:
                cdef = ''
                for i, s in enumerate(series.split(',')):
                    rrd_path = os.path.join(rrd_dir, s+'.rrd')
                    dname = "v%s_%s" % (n, i)
                    cdef += dname + ','
                    lines.append(
                        rrdtool.Def(dname, rrd_path,
                                    data_source='data', cf=rrdtool.AverageCF)
                        )
                lines.append( "CDEF:v%s=%s%s,AVG" % (n, cdef, i+1))
            else:
                rrd_path = os.path.join(rrd_dir, series+'.rrd')
                lines.append(
                    rrdtool.Def("v%s" % n, rrd_path, data_source='data',
                                cf=rrdtool.AverageCF),
                    )
            legend = plot['legend'] or plot['data']
            if len(legend) > 50:
                legend = legend[:47]+'...'
            lines.append("LINE1:v%s#%s:%s" % (n, plot['color'], legend))

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

        if log:
            options['logarithmic'] = None

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
        logging.info("%r show %r %r %r%s",
                     who(self.request), self.user, self.name, imgid, updated)
        return open(img_path).read()

    @bobo.post('/destroy')
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

    @bobo.post(content_type='application/json')
    def save(self, name, overwrite=False):
        me = who(self.request)
        definitions = self.get_definitions(me)
        old = definitions.get(name)
        if (old is not None) and old['charts'] and not overwrite:
            return json.dumps(dict(exists=True))
        new = self.definitions.get(self.name)
        if (new is not None) and new['charts']:
            definitions[name] = new
        else:
            if old is not None:
                del definitions[name]

        return json.dumps(dict(url='../../%s/%s' % (me, name)))

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
<html><head><title>ZIM Metrics</title>
<style type="text/css">
@import "%(dojoroot)s/dojo/resources/dojo.css";
@import "%(dojoroot)s/dijit/themes/tundra/tundra.css";
@import "%(dojoroot)s/dojox/grid/resources/Grid.css";
</style>
<script type="text/javascript"
        src="%(dojoroot)s/dojo/dojo.xd.js.uncompressed.js"
        djConfig="isDebug: true"></script>
<script type="text/javascript" src="web.js"></script>
</head><body class="tundra"></body></html>
""" % globals()
