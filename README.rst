Hacktaculous ZC internal metrics graphics framework
===================================================

This is a system we use at ZC to graph various types of performance
data.  The code is really nasty, cuz it evolved over time as was a
bit of a side project.  OTOH, the result has been extremely useful.

We share it in case others might take inspiration or even make contributions.

There are 2 kinds of data that are graphed:

Trace logs
  For many years, the Zope project has had trace logs.

  The original pre-WSGI Zope server supported them as do the
  zope.server and zc.resumelb WSGI servers.

  Tracelogs track basic events in a request lifetime, like request
  start, input data read, started waiting for application thread,
  started computing request, finishes computing request, and so on.
  You can think of tracelogs as a sort of minimal and free version of
  New Relic.

  Here we provide time-series graphs based on tracelog that show:

  - request rate

  - estimated maximum request rate (missleading, but still useful. :) )

  - number of requests waiting for an application thread (backlog), and

  - error (500 response) rates.

  .. image:: tracelog.png

Generic metrics
  We also support generic metrics.

  We're in the process of migrating from an in-house metrics framework
  to a framnework based in `CIMAA <https://github.com/zc/cimaa>`_ and
  AWS Kinesis.  (OK, CIMAA is technically also an in-house monitoring
  framework, but we think it provides a lot of advantages and we plan
  to promote it as an open project when it's more mature.

  .. image:: metrics.png

The graphing UI was written when I didn't remember much Javascript or
Dojo, so the code is rather discusting.  The thing is, it works welll
enough and I'm busy enough that I haven't has reason to revisit it.

For hysterical reasons, tracelogs are accessed at ``/`` and generic
metrics at ``/metrics``.  The UI, especially at ``/metrics`` provides
a lot of flexibility for defining time-sries graphs, including
leveraging RRD's reverse-polish expression syntax.  Graphs are
automaticaly saved per user and user's can view each other's graphs.

Use authentication is done with Persona.

Data are collected in RRD files.

- Tracelog data are collected from a distectory populated by
  syslog-ng.

- Metrics are populated by reading data from Kinesis.  We put data
  into Kinesis from CIMAA. We look for JSON data records with:

  timestamp
     An ISO-date formatted UTC time

  value
     A numeric data value.

  Obviously, this format is pretty generic and could be used with
  other input sources.

If you are interested in learning more or want to collaborate, contact
jim@zope.com.
