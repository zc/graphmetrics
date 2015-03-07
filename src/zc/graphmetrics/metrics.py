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
import zc.graphmetrics.auth

from zc.graphmetrics.auth import who

dojoroot = 'http://ajax.googleapis.com/ajax/libs/dojo/1.5'

inst_tracelog_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match

tracelog_vars = 'bl|epm|rpm|start|spr'

inst_tracelog_series = re.compile(
    r'([^/]+)/([^/]+)-z4m/([^/]+)/tracelog/(%s)' % tracelog_vars
    ).match

tracelog_vars = tracelog_vars.split('|')

def config(config):
    global rrd_dir, rrd_updated, tracelog_rrd_dir, tracelog_updated
    rrd_dir = config['metrics-rrd']
    rrd_updated = os.path.join(rrd_dir, '.updated')
    tracelog_rrd_dir = config.get('rrd')
    if tracelog_rrd_dir:
        tracelog_updated = os.path.join(tracelog_rrd_dir, '.updated')

def rrd_id(series):
    m = inst_tracelog_series(series)
    if m:
        ds = m.group(4)
        rrd_path = os.path.join(
            tracelog_rrd_dir,
            "%s__%s__%s.rrd" % m.group(1, 2, 3))
    else:
        ds='data'
        rrd_path = os.path.join(rrd_dir, series+'.rrd')
    return rrd_path, ds

series = None
series_update = tracelog_update = None
def get_series_data():
    global series, series_update, tracelog_update
    if series is not None and (
        series_update >= os.stat(rrd_updated).st_mtime
        and
        tracelog_update >= os.stat(tracelog_updated).st_mtime
        ):
        return series
    result = []

    # metrics
    lprefix = len(rrd_dir)+1
    for path, dirs, files in os.walk(rrd_dir):
        result.extend(os.path.join(path, name)[lprefix:-4]
                      for name in files
                      if name.endswith('.rrd')
                      )

    # trace logs
    if tracelog_rrd_dir:
        for inst in sorted(f[:-4] for f in os.listdir(tracelog_rrd_dir)
                           if inst_tracelog_rrd(f)):
            host, customer, inst_name = inst.split('__')
            result.extend([
                "%s/%s-z4m/%s/tracelog/%s" % (host, customer, inst_name, v)
                for v in tracelog_vars
                ])
        if os.path.exists(tracelog_updated):
            tracelog_update = os.stat(tracelog_updated).st_mtime

    series = sorted(result)
    series_update = os.stat(rrd_updated).st_mtime
    return series


@bobo.resource('/metrics', check=zc.graphmetrics.auth.checker)
def home(request):
    return bobo.redirect(request.url+'/%s/default/' % who(request))

@bobo.resource('/metrics/', check=zc.graphmetrics.auth.checker)
def home_(request):
    return bobo.redirect(request.url+'%s/default/' % who(request))


BIG = 1<<31

plotparam = re.compile('(legend|color|data|thick|tick|dash)(\d+)$').match

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

    @bobo.query('/', check=zc.graphmetrics.auth.checker)
    def index(self):
        # if self.user == 'jim':
        #     return """
        #     <html><head><title>ZIM Metrics</title>
        #     <style type="text/css">
        #     @import "%(dojoroot)s/dojo/resources/dojo.css";
        #     @import "%(dojoroot)s/dijit/themes/tundra/tundra.css";
        #     @import "%(dojoroot)s/dojox/grid/resources/Grid.css";
        #     </style>
        #     <script type="text/javascript"
        #     src="%(dojoroot)s/dojo/dojo.js"
        #     djConfig="isDebug: true"></script>
        #     <script type="text/javascript" src="web.js"></script>
        #     </head><body class="tundra"></body></html>
        #     """ %  dict(dojoroot='/static')
        return index_html % ("%s/%s" % (self.user, self.name))

    @bobo.query('/web.js', content_type="text/javascript")
    def js(self):
        base = os.path.join(os.path.dirname(__file__), 'metrics')
        path = base+'-%s.js' % self.user
        if not (self.name.startswith('dev-') and os.path.exists(path)):
            path = base+'.js'
        return open(path).read()

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
    def get_series(self):
        return json.dumps(dict(
            series=get_series_data(),
            saved=list(self.get_definitions(who(self.request))),
            ))

    @bobo.query('/show.png', content_type='image/png',
                check=zc.graphmetrics.auth.checker)
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
            title=title,
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
            if AGGREGATE_DELIMITER in series:
                rpn = aggregate(lines, n, series)
                if not rpn:
                    continue
                print 'aggregate', n, `rpn`
                lines.append("CDEF:v%s=%s" % (n, rpn))
            else:
                rrd_path, data_source = rrd_id(series)
                lines.append(
                    rrdtool.Def("v%s" % n, rrd_path, data_source=data_source,
                                cf=rrdtool.AverageCF),
                    )
            legend = plot['legend'] or plot['data']
            dash = plot.get('dash')
            if dash:
                legend = '- '+legend
            if len(legend) > 50:
                legend = legend[:47]+'...'
            if plot.get('tick'):
              lines.append("TICK:v%s#%s55:1:%s" % (
                  n, plot['color'], legend,
                  ))
            else:
              lines.append("LINE%s:v%s#%s:%s%s" % (
                  2 if plot.get('thick') else 1,
                  n, plot['color'], legend,
                  ":dashes" if dash else "",
                  ))

        fd, img_path = tempfile.mkstemp('.png')
        g = rrdtool.RoundRobinGraph(img_path)

        options = dict(
            width=int(width)-111,
            height=height and int(height) or 200,
            title=title,
            )
        if upper_limit:
            options['upper_limit'] = float(upper_limit)
            options['rigid'] = None
        if lower_limit:
            options['lower_limit'] = float(lower_limit)
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

        options['right-axis'] = '1:0'

        try:
            g.graph(*lines, **options)
        except Exception, v:
            v = '%s.%s: %s' % (v.__class__.__module__, v.__class__.__name__,
                               v)
            g = rrdtool.RoundRobinGraph(img_path)
            options = dict(
                width=int(width)-70,
                height=height and int(height) or 200,
                title=v,
                )
            try:
                g.graph('HRULE:1',
                    **options)
            except Exception, v:
                logging.exception('Trying to recover from %s', v)
                raise

            return open(img_path).read()

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

# Aggregatiions
#
# Of the form:
#
# AGGREGATIION = SNAMES AGGREGATE_DELIMITER2
#                TYPE AGGREGATE_DELIMITER VNAMES
#                AGGREGATE_DELIMITER2 EXPR
#
# SNAMES = SNAME (AGGREGATE_DELIMITER SNAME)*
# TYPE = average | total | custom
# VNAMES = VNAME (AGGREGATE_DELIMITER VNAME)*
# EXPR = VNAMEOROP (, VNAMEOROP)*
# VNAMEOROP = VNAME | OP

AGGREGATE_DELIMITER = '|'
AGGREGATE_DELIMITER2 = '||'
def aggregate(lines, basevar, data):
    basevar = 'v%s' % basevar
    data = data.split(AGGREGATE_DELIMITER2)
    n = 0
    names = []
    for s in data.pop(0).split(AGGREGATE_DELIMITER):
        rrd_path, data_source = rrd_id(s)
        name = "%s_%s" % (basevar, n)
        names.append(name)
        lines.append(rrdtool.Def(name, rrd_path, data_source=data_source,
                                 cf=rrdtool.AverageCF))
        n += 1

    if not n:
        return ''

    if not data or data[0].split(AGGREGATE_DELIMITER)[0] == 'average':
        # average
        return ','.join(names)+',%s,AVG' % n
    elif data[0].split(AGGREGATE_DELIMITER)[0] == 'total':
        if n == 1:
            return names[0]
        return ','.join(names)+(',ADDNAN'*(n-1))

    assert len(data) > 1, data
    anames = {}
    assert data[0].startswith('custom'+AGGREGATE_DELIMITER), `data`
    for i, name in enumerate(data.pop(0).split(AGGREGATE_DELIMITER)[1:]):
        anames[name] = names[i]
    return ','.join(
        ','.join(anames.get(e, e)
                 for e in d.split(','))
        for d in data)


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
<html><head><title>Metrics: %%s</title>
<style type="text/css">
@import "%(dojoroot)s/dojo/resources/dojo.css";
@import "%(dojoroot)s/dijit/themes/tundra/tundra.css";
@import "%(dojoroot)s/dojox/grid/resources/Grid.css";
</style>
<script type="text/javascript">
  djConfig={ baseUrl: "../../../", modulePaths: { zc: "static" }};
</script>
<script type="text/javascript"
        src="%(dojoroot)s/dojo/dojo.xd.js.uncompressed.js"
        djConfig="isDebug: true"></script>
<script type="text/javascript" src="web.js"></script>
</head><body class="tundra"></body></html>
""" % globals()
