
aprsd-exporter
==============


.. image:: https://badge.fury.io/py/aprsd-exporter.png
   :target: http://badge.fury.io/py/aprsd-exporter
   :alt: PyPI version


.. image:: https://travis-ci.org/hemna/aprsd-exporter.png?branch=master
   :target: https://travis-ci.org/hemna/aprsd-exporter
   :alt: Build Status


APRSD Stats Prometheus exporter

Features
--------


* Exports APRSD server statistics as Prometheus metrics
* Collects metrics for APRSD stats, packets, threads, seen list, and plugins
* Configurable update interval for metric collection
* Lightweight and easy to deploy

Installation
------------

From PyPI
^^^^^^^^^

.. code-block:: bash

   pip install aprsd-exporter

From Source
^^^^^^^^^^^

.. code-block:: bash

   git clone https://github.com/hemna/aprsd-exporter.git
   cd aprsd-exporter
   pip install .

Development Installation
------------------------

For development, install with dev dependencies:

.. code-block:: bash

   pip install -e ".[dev]"

Requirements
------------


* Python 3.10 or higher
* APRSD server with admin API enabled

Usage
-----

Basic Usage
^^^^^^^^^^^

Run the exporter with default settings:

.. code-block:: bash

   aprsd_exporter

This will:


* Connect to APRSD admin API at ``http://localhost:8080``
* Expose Prometheus metrics on ``0.0.0.0:8080``
* Update metrics every 60 seconds

Command-Line Options
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   aprsd_exporter [OPTIONS]

**Options:**


* ``--aprsd-url <aprsd url>`` - The APRSD ADMIN URL to connect to (default: ``http://localhost:8080``\ )
* ``--host <exporter host>`` - The IP address to expose collected metrics from (default: ``0.0.0.0``\ )
* ``--port <exporter port>`` - The port to expose collected metrics from (default: ``8080``\ )
* ``--update-interval <update interval>`` - The interval in seconds to update metrics (default: ``60``\ )
* ``--debug`` - Print debug messages to stdout
* ``--quiet`` - Only print error messages to stdout

Examples
^^^^^^^^

**Connect to remote APRSD server:**

.. code-block:: bash

   aprsd_exporter --aprsd-url http://aprsd.example.com:8080

**Expose metrics on a different port:**

.. code-block:: bash

   aprsd_exporter --port 9110

**Update metrics more frequently:**

.. code-block:: bash

   aprsd_exporter --update-interval 30

**Enable debug logging:**

.. code-block:: bash

   aprsd_exporter --debug

**Complete example with all options:**

.. code-block:: bash

   aprsd_exporter \
     --aprsd-url http://aprsd.example.com:8080 \
     --host 0.0.0.0 \
     --port 9110 \
     --update-interval 30 \
     --debug

Prometheus Configuration
------------------------

Add the exporter to your Prometheus configuration:

.. code-block:: yaml

   scrape_configs:
     - job_name: 'aprsd-exporter'
       static_configs:
         - targets: ['localhost:8080']

Metrics
-------

The exporter provides the following Prometheus metrics:


* **APRSD Stats**\ : Version, callsign, memory usage
* **Packet Metrics**\ : Total packets, ACK packets, beacon packets, bulletin packets, message packets, Mic-E packets, object packets, and more
* **Thread Metrics**\ : Status and information for APRSD threads
* **Seen Metrics**\ : Statistics about callsigns seen by APRSD
* **Plugin Metrics**\ : Status and statistics for APRSD plugins

All metrics include labels for ``host``\ , ``app``\ , and ``callsign``.

Project Links
-------------


* **Homepage**\ : https://github.com/hemna/aprsd-exporter
* **Bug Reports**\ : https://github.com/hemna/aprsd-exporter/issues
* **Source**\ : https://github.com/hemna/aprsd-exporter
