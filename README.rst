asyncio-foundationdb
####################

.. image:: https://api.travis-ci.org/amirouche/found.svg?branch=master

.. image:: https://codecov.io/gh/amirouche/found/branch/master/graph/badge.svg

asyncio drivers for foundationdb tested with CPython 3.5+

.. code:: python

	  In [1]: import found
	  In [2]: import asyncio
	  In [3]: found.api_version(510)
	  In [4]: loop = asyncio.get_event_loop()
	  In [5]: db = loop.run_until_complete(found.open())
	  In [6]: tr = db._create_transaction()
	  In [7]: loop.run_until_complete(tr.get(b'hello'))
	  In [8]: tr.set(b'hello', b'world')
	  In [9]: loop.run_until_complete(tr.get(b'hello'))
	  Out[9]: b'world'

Also ``@transactional`` is also supported.

Getting started
===============

::

   pip install asyncio-foundationdb

Differences with ``fdb``
========================

- support asyncio
- no shorthand syntax like: ``foo[b'bar']``
- key and values are returned as python base types, that is you can do
  ``value is None`` instead of ``value == None``
