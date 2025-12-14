Grafana Dashboard Guide
========================

This guide provides PromQL queries and examples for creating Grafana dashboards to visualize APRSD metrics exported by the Prometheus exporter.

Quick Start
-----------

A pre-built Grafana dashboard is available in the project root directory (``grafana-dashboard.json``). To use it:

1. Open Grafana and navigate to **Dashboards** → **Import**
2. Upload or paste the contents of ``grafana-dashboard.json``
3. Select your Prometheus data source
4. Click **Import** to load the dashboard

The dashboard includes 12 panels covering all major APRSD metrics:

* Packet rate monitoring (RX/TX)
* Memory usage tracking
* Packet type distribution
* Top active callsigns
* Thread status and performance
* Plugin metrics
* Key statistics overview

You can customize the dashboard or use the queries below to create your own panels.

Overview
--------

The APRSD Prometheus Exporter exposes the following metric categories:

* **APRSD Stats**: Version, callsign, memory usage
* **Packet Metrics**: Total packets and packet types (TX/RX)
* **Thread Metrics**: Thread status, loop counts, alive status
* **Seen Metrics**: Callsign tracking statistics
* **Plugin Metrics**: Plugin performance and status

All metrics include constant labels:

* ``host``: Hostname where the exporter is running
* ``app``: Application name (APRSDExporter)
* ``callsign``: APRSD callsign

Metric Reference
-----------------

APRSD Stats Metrics
~~~~~~~~~~~~~~~~~~~

``aprsd``
    Gauge metric for APRSD version and callsign information.

    **Labels:**

    * ``version``: APRSD version
    * ``callsign``: APRSD callsign

``aprsd_memory``
    Gauge metric for APRSD memory usage.

    **Labels:**

    * ``type``: Memory type (``current`` or ``peak``)

Packet Metrics
~~~~~~~~~~~~~~

``Packets``
    Total packet counts.

    **Labels:**

    * ``count``: Count type (``total``, ``tx``, ``rx``)

Packet Type Metrics
    Individual packet type metrics: ``AckPacket``, ``BeaconPacket``, ``BulletinPacket``, ``MessagePacket``, ``MicEPacket``, ``ObjectPacket``, ``RejectPacket``, ``StatusPacket``, ``TelemetryPacket``, ``ThirdPartyPacket``, ``WeatherPacket``, ``UnknownPacket``

    **Labels:**

    * ``count``: Count type (``tx`` or ``rx``)

Thread Metrics
~~~~~~~~~~~~~~

Dynamic metrics created for each thread (e.g., ``APRSDRXThread``, ``BeaconSendThread``).

**Labels:**

* ``class``: Thread class name
* ``alive``: Thread alive status (``True``/``False``)
* ``status``: Status type (``loop_count``)

Seen Metrics
~~~~~~~~~~~~

``callsigns``
    Callsign tracking statistics.

    **Labels:**

    * ``callsign``: Callsign identifier
    * ``status``: Status type (``count`` or timestamp for ``last_seen``)

Plugin Metrics
~~~~~~~~~~~~~~

Dynamic metrics created for each plugin.

**Labels:**

* ``packets``: Packet direction (``tx`` or ``rx``)
* ``enabled``: Plugin enabled status (``True``/``False``)
* ``version``: Plugin version
* ``name``: Full plugin name

PromQL Queries for Grafana
---------------------------

APRSD Overview
~~~~~~~~~~~~~~

APRSD Version
^^^^^^^^^^^^^

.. code-block:: promql

   aprsd{version!=""}

Current Memory Usage
^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   aprsd_memory{type="current"}

Peak Memory Usage
^^^^^^^^^^^^^^^^^

.. code-block:: promql

   aprsd_memory{type="peak"}

Memory Usage Over Time
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   aprsd_memory{type="current"}

Packet Statistics
~~~~~~~~~~~~~~~~~

Total Packets Received
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   Packets{count="rx"}

Total Packets Transmitted
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   Packets{count="tx"}

Total Packets Tracked
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   Packets{count="total"}

Packet Rate (Packets per Second)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   rate(Packets{count="total"}[5m])

Packet Rate by Direction
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   rate(Packets{count="rx"}[5m])  # RX rate
   rate(Packets{count="tx"}[5m])   # TX rate

Message Packets Received
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   MessagePacket{count="rx"}

Message Packets Transmitted
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   MessagePacket{count="tx"}

Beacon Packets Received
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   BeaconPacket{count="rx"}

Beacon Packets Transmitted
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   BeaconPacket{count="tx"}

Weather Packets Received
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   WeatherPacket{count="rx"}

Unknown Packets
^^^^^^^^^^^^^^^

.. code-block:: promql

   UnknownPacket{count="rx"}

Packet Type Distribution (Pie Chart)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   sum by (__name__) ({__name__=~".*Packet", count="rx"})

Top Packet Types by Count
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   topk(10, sum by (__name__) ({__name__=~".*Packet", count="rx"}))

Thread Monitoring
~~~~~~~~~~~~~~~~~

All Threads Status
^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", class!=""}

Thread Alive Status
^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", alive="True"}

Dead Threads (Alert Condition)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", alive="False"}

Thread Loop Counts
^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", status="loop_count"}

Thread Loop Rate (Loops per Second)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   rate({__name__!~".*", status="loop_count"}[5m])

Specific Thread Status (e.g., APRSDRXThread)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   APRSDRXThread{alive="True"}

Thread Loop Count for Specific Thread
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   APRSDRXThread{status="loop_count"}

Callsign Tracking
~~~~~~~~~~~~~~~~~

Total Unique Callsigns Seen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   count(callsigns{status="count"})

Callsigns Seen Count
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   callsigns{status="count"}

Top 10 Most Active Callsigns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   topk(10, callsigns{status="count"})

Callsign Activity Over Time
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   sum by (callsign) (callsigns{status="count"})

Callsigns Seen in Last Hour
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   callsigns{status="count"} > 0

Plugin Performance
~~~~~~~~~~~~~~~~~~

Plugin Packet TX Count
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", packets="tx"}

Plugin Packet RX Count
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", packets="rx"}

Enabled Plugins
^^^^^^^^^^^^^^^

.. code-block:: promql

   {__name__!~".*", enabled="True"}

Plugin Packet Rates
^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   rate({__name__!~".*", packets="rx"}[5m])
   rate({__name__!~".*", packets="tx"}[5m])

Top Plugins by RX Packets
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   topk(10, {__name__!~".*", packets="rx"})

Top Plugins by TX Packets
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: promql

   topk(10, {__name__!~".*", packets="tx"})

Example Grafana Dashboard Panels
---------------------------------

Panel 1: APRSD Overview Stat Panel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Stat

**Query:**

.. code-block:: promql

   aprsd{version!=""}

**Options:**

* Value: Last
* Unit: None
* Display: Value and name

Panel 2: Memory Usage Graph
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Time Series

**Queries:**

.. code-block:: promql

   aprsd_memory{type="current"}  # Current memory
   aprsd_memory{type="peak"}     # Peak memory

**Options:**

* Unit: bytes (SI)
* Legend: Show as table

Panel 3: Packet Rate Over Time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Time Series

**Queries:**

.. code-block:: promql

   rate(Packets{count="rx"}[5m])  # RX Rate
   rate(Packets{count="tx"}[5m])   # TX Rate

**Options:**

* Unit: packets/sec
* Legend: RX, TX

Panel 4: Packet Type Distribution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Pie Chart

**Query:**

.. code-block:: promql

   sum by (__name__) ({__name__=~".*Packet", count="rx"})

**Options:**

* Legend: Show as table
* Values: Current

Panel 5: Thread Status Table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Table

**Query:**

.. code-block:: promql

   {__name__!~".*", class!=""}

**Options:**

* Format: Table
* Columns: class, alive, status

Panel 6: Top 10 Callsigns
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Bar Chart

**Query:**

.. code-block:: promql

   topk(10, callsigns{status="count"})

**Options:**

* Orientation: Horizontal
* Legend: Show as table

Panel 7: Plugin Performance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Panel Type:** Time Series

**Queries:**

.. code-block:: promql

   rate({__name__!~".*", packets="rx"}[5m])
   rate({__name__!~".*", packets="tx"}[5m])

**Options:**

* Unit: packets/sec
* Legend: RX, TX

Alert Rules
-----------

Alert: Dead Thread Detected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   groups:
     - name: aprsd_alerts
       rules:
         - alert: APRSDDeadThread
           expr: {__name__!~".*", alive="False"} == 1
           for: 1m
           labels:
             severity: warning
           annotations:
             summary: "APRSD thread {{ $labels.__name__ }} is dead"
             description: "Thread {{ $labels.class }} on {{ $labels.host }} is not alive"

Alert: High Memory Usage
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

         - alert: APRSDHighMemory
           expr: aprsd_memory{type="current"} > 500000000  # 500MB
           for: 5m
           labels:
             severity: warning
           annotations:
             summary: "APRSD memory usage is high"
             description: "APRSD on {{ $labels.host }} is using {{ $value }} bytes of memory"

Alert: No Packets Received
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

         - alert: APRSDNoPackets
           expr: rate(Packets{count="rx"}[5m]) == 0
           for: 10m
           labels:
             severity: critical
           annotations:
             summary: "No packets received"
             description: "APRSD on {{ $labels.host }} has not received packets for 10 minutes"

Alert: Unknown Packets Threshold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

         - alert: APRSDHighUnknownPackets
           expr: rate(UnknownPacket{count="rx"}[5m]) > 10
           for: 5m
           labels:
             severity: warning
           annotations:
             summary: "High rate of unknown packets"
             description: "APRSD on {{ $labels.host }} is receiving {{ $value }} unknown packets/sec"

Tips and Best Practices
-----------------------

1. **Use Rate Functions**: Always use ``rate()`` or ``irate()`` for counter metrics to get meaningful per-second values.

2. **Time Ranges**: Use appropriate time ranges in ``rate()`` functions:

   * ``[5m]`` for short-term monitoring
   * ``[15m]`` for medium-term trends
   * ``[1h]`` for long-term analysis

3. **Label Filtering**: Use label selectors to filter metrics:

   .. code-block:: promql

      Packets{count="rx", callsign="YOURCALL"}

4. **Aggregation**: Use ``sum()``, ``avg()``, ``max()``, ``min()`` for aggregating across multiple instances:

   .. code-block:: promql

      sum(rate(Packets{count="rx"}[5m]))

5. **TopK Queries**: Use ``topk()`` to identify top performers:

   .. code-block:: promql

      topk(10, callsigns{status="count"})

6. **Variable Usage**: Create Grafana variables for dynamic filtering:

   * Variable: ``callsign`` (query: ``label_values(callsign)``)
   * Variable: ``host`` (query: ``label_values(host)``)

7. **Refresh Intervals**: Set appropriate refresh intervals based on your exporter's ``stats_interval`` setting.

8. **Unit Formatting**: Use appropriate units in Grafana:

   * Bytes: ``bytes (SI)`` or ``bytes (IEC)``
   * Rates: ``ops/sec`` or ``packets/sec``
   * Time: ``seconds`` or ``milliseconds``

Troubleshooting
---------------

No Metrics Appearing
~~~~~~~~~~~~~~~~~~~~~

1. Verify the exporter is running and accessible
2. Check Prometheus is scraping the exporter endpoint
3. Verify the APRSD ``/stats`` endpoint is accessible
4. Check exporter logs for errors

Incorrect Values
~~~~~~~~~~~~~~~~

1. Verify the time range matches your data collection interval
2. Check for label mismatches in queries
3. Ensure rate functions use appropriate time windows

High Cardinality
~~~~~~~~~~~~~~~~

1. Avoid queries that create too many time series
2. Use aggregation functions (``sum``, ``avg``) when possible
3. Filter by specific labels when needed

Additional Resources
---------------------

* `PromQL Documentation <https://prometheus.io/docs/prometheus/latest/querying/basics/>`_
* `Grafana Documentation <https://grafana.com/docs/grafana/latest/>`_
* `Prometheus Best Practices <https://prometheus.io/docs/practices/naming/>`_

