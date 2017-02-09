Fastatsd
========

This is a Python client for the statsd daemon, which can be used as a drop-in replacement for the
`statsd module <https://pypi.python.org/pypi/statsd/>`_.

Fastatsd is only tested with Python 3.5. There are no plans to support older Python versions.


Features
--------

- `cystatsd <https://github.com/scivey/cystatsd>`_ is used to encode metrics.
- Metrics are sent over the network in a worker thread to avoid blocking the main thread.


Example
-------

.. code-block:: python

	>>> import fastatsd
	>>> c = fastatsd.Fastatsd('localhost', 8125)
	>>> c.incr('foo')  # Increment the 'foo' counter.
	>>> c.timing('stats.timed', 320)  # Record a 320ms 'stats.timed'.

The client also supports the context manager interface. This ensures that the worker thread sends all metrics on exit:

.. code-block:: python

	>>> import fastatsd
	>>> with fastatsd.Fastatsd('localhost', 8125) as c:
	>>>     c.incr('foo')


Installation
------------

.. code-block::

	$ pip install cython
	$ pip install -e git+https://github.com/qntln/cystatsd.git#egg=ql-cystatsd
	$ pip install -e git+https://github.com/qntln/fastatsd.git#egg=fastatsd
