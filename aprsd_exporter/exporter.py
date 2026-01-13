import asyncio
import linecache
import os
import resource
import socket
import threading
import tracemalloc
from asyncio.events import AbstractEventLoop

import requests
from prometheus_client import Gauge, start_http_server
from aprsd.threads.stats import StatsStore
from flask import Flask, jsonify, request
from loguru import logger
from oslo_config import cfg

APRSD_STATS = "aprsd"
PACKET_METRICS = "packets"
THREAD_METRICS = "threads"
SEEN_METRICS = "seen"
PLUGINS_METRICS = "plugins"


class APRSDExporter:
    def __init__(
        self,
        aprsd_url: str,
        host: str,
        port: int,
        stats_interval: int,
        api: bool = False,
        api_port: int = 8081,
        stats_file: str = None,
        loop: AbstractEventLoop = None,
        max_seen_callsigns: int = 1000,
    ):
        self.loop = loop or asyncio.get_event_loop()
        self.aprsd_url = aprsd_url
        self.host = host
        self.port = port
        self.stats_interval = stats_interval
        self.api = api
        self.api_port = api_port
        self.stats_file = stats_file
        self.metrics_task = None
        self.metrics_server_thread = None
        self.flask_app = None
        self.flask_thread = None
        self.received_stats = None

        self.callsign = None
        self._metrics = None
        self.memory_logger_timer = None
        # Track ALL callsigns we've ever created metrics for (not just previous iteration)
        # This helps us identify time series that can be cleaned up
        self._all_tracked_callsigns = set()
        # Track previous callsigns to enable cleanup of old metrics
        self._previous_seen_callsigns = set()
        # Limit number of callsigns tracked to prevent unbounded memory growth
        # Only track top N most active callsigns by count
        self.max_seen_callsigns = max_seen_callsigns
        # Use a requests session for connection pooling and better resource management
        self.requests_session = requests.Session()

    async def start(self):
        # start prometheus metrics server in a separate thread
        self.metrics_server_thread = threading.Thread(
            target=start_http_server,
            args=(self.port,),
            kwargs={"addr": self.host},
            daemon=True,
        )
        self.metrics_server_thread.start()
        logger.info(f"Serving APRSD prometheus metrics on: http://{self.host}:{self.port}")

        if self.api:
            self._start_flask_api()

        # Schedule a timer to update metrics. In a realistic application
        # the metrics would be updated as needed. In this example, a simple
        # timer is used to emulate things happening, which conveniently
        # allows all metrics to be updated at once.
        self.timer = asyncio.get_event_loop().call_later(
            self.stats_interval,
            self.metric_updater,
        )

        # Schedule memory usage logging every 60 seconds
        self.memory_logger_timer = asyncio.get_event_loop().call_later(
            60,
            self.memory_logger,
        )

    async def stop(self):
        # Cancel memory logger timer
        if self.memory_logger_timer:
            self.memory_logger_timer.cancel()
        if self.flask_thread and self.flask_thread.is_alive():
            # Flask doesn't have a clean shutdown, but since it's in a daemon thread, it will stop with the process
            pass
        # Close requests session to free resources
        if hasattr(self, 'requests_session'):
            self.requests_session.close()
        # prometheus_client server runs in a daemon thread, so it will stop with the process

    def _start_flask_api(self):
        self.flask_app = Flask(__name__)

        @self.flask_app.route("/stats", methods=["POST"])
        def receive_stats():
            try:
                self.received_stats = request.get_json()
                logger.info("Received stats from external APRSD instance")
                return jsonify({"status": "ok"}), 200
            except Exception as e:
                logger.error(f"Failed to process stats: {e}")
                return jsonify({"error": str(e)}), 400

        @self.flask_app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy"}), 200

        logger.info(f"Starting Flask API server on port {self.api_port}")
        self.flask_thread = threading.Thread(target=self._run_flask, daemon=True)
        self.flask_thread.start()
        logger.info(f"Started Flask API server thread on port {self.api_port}")

    def _run_flask(self):
        logger.info(f"Flask app.run() called for port {self.api_port}")
        self.flask_app.run(
            host="0.0.0.0",
            port=self.api_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    def register_metrics(self):
        if not self._metrics:
            # Ensure const_labels is defined (should be set in update_metrics before calling this)
            if not hasattr(self, 'const_labels'):
                self.const_labels = {
                    "host": socket.gethostname(),
                    "app": f"{self.__class__.__name__}",
                    "callsign": self.callsign or "unknown",
                }
            # prometheus_client uses labelnames parameter instead of const_labels
            # We'll add const_labels as default labels when setting values
            self._metrics = {
                APRSD_STATS: {
                    "aprsd": Gauge(
                        "aprsd",
                        "APRSD Stats",
                        labelnames=list(self.const_labels.keys()) + ["version", "callsign"],
                    ),
                    "aprsd_memory": Gauge(
                        "aprsd_memory",
                        "APRSD Memory Usage",
                        labelnames=list(self.const_labels.keys()) + ["type"],
                    ),
                },
                PACKET_METRICS: {
                    "Packets": Gauge(
                        "Packets",
                        "Total number of packets sent/received",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "AckPacket": Gauge(
                        "AckPacket",
                        "Ack Packet Totals",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "BeaconPacket": Gauge(
                        "BeaconPacket",
                        "Beacon type packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "BulletinPacket": Gauge(
                        "BulletinPacket",
                        "Bulletin type packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "MessagePacket": Gauge(
                        "MessagePacket",
                        "Message type packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "MicEPacket": Gauge(
                        "MicEPacket",
                        "Mic E Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "ObjectPacket": Gauge(
                        "ObjectPacket",
                        "Object Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "RejectPacket": Gauge(
                        "RejectPacket",
                        "Reject Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "StatusPacket": Gauge(
                        "StatusPacket",
                        "Status Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "TelemetryPacket": Gauge(
                        "TelemetryPacket",
                        "Telemetry Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "ThirdPartyPacket": Gauge(
                        "ThirdPartyPacket",
                        "Third Party Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "WeatherPacket": Gauge(
                        "WeatherPacket",
                        "Weather Packets",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                    "UnknownPacket": Gauge(
                        "UnknownPacket",
                        "Total number of unknown packets received",
                        labelnames=list(self.const_labels.keys()) + ["count"],
                    ),
                },
                THREAD_METRICS: {},
                SEEN_METRICS: {},
                PLUGINS_METRICS: {},
            }

    def metric_updater(self):
        logger.info("metric_updater")
        self.update_metrics()

        # re-schedule another metrics update
        self.timer = asyncio.get_event_loop().call_later(
            self.stats_interval,
            self.metric_updater,
        )

    def log_tracemalloc(self, snap):
        """Log the top 5 offending memory allocations"""
        limit = 5
        key_type = "lineno"
        snapshot = snap.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        ))
        top_stats = snapshot.statistics(key_type)

        logger.info(f"Top {limit}%s lines")
        for index, stat in enumerate(top_stats[:limit], 1):
            frame = stat.traceback[0]
            # replace "/path/to/module/file.py" with "module/file.py"
            filename = os.sep.join(frame.filename.split(os.sep)[-2:])
            logger.info("#%s: %s:%s: %.1f KiB" % (index, filename, frame.lineno, stat.size / 1024))
            line = linecache.getline(frame.filename, frame.lineno).strip()
            if line:
                logger.info(f'    {line}')

        other = top_stats[limit:]
        if other:
            size = sum(stat.size for stat in other)
            logger.info(f"{len(other)} other: {size / 1024} KiB")
        total = sum(stat.size for stat in top_stats)
        logger.info(f"Total allocated size: {total / 1024} KiB")

    def _get_memory_usage(self):
        """Get current memory usage in bytes. Returns RSS (Resident Set Size)."""

        try:
            # Try to use psutil if available (more accurate)
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # Fallback to resource module (standard library)
            # Note: getrusage returns maxrss in KB on Linux, bytes on macOS
            usage = resource.getrusage(resource.RUSAGE_SELF)
            maxrss = usage.ru_maxrss
            # Convert to bytes (Linux returns KB, macOS returns bytes)
            if os.name != 'posix' or hasattr(resource, 'RLIM_INFINITY'):
                # macOS returns bytes directly
                return maxrss
            else:
                # Linux returns KB, convert to bytes
                return maxrss * 1024

    def memory_logger(self):
        """Log current memory usage and reschedule."""
        try:
            memory_bytes = self._get_memory_usage()
            # Convert to human-readable format
            if memory_bytes < 1024:
                memory_str = f"{memory_bytes} B"
            elif memory_bytes < 1024 * 1024:
                memory_str = f"{memory_bytes / 1024:.2f} KB"
            elif memory_bytes < 1024 * 1024 * 1024:
                memory_str = f"{memory_bytes / (1024 * 1024):.2f} MB"
            else:
                memory_str = f"{memory_bytes / (1024 * 1024 * 1024):.2f} GB"

            logger.info(f"Exporter memory usage: {memory_str} ({memory_bytes:,} bytes)")
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")

        try:
            snap = tracemalloc.take_snapshot()
            self.log_tracemalloc(snap)
        except Exception:
            logger.error("Failed to log tracemalloc")

        # Re-schedule memory logging every 60 seconds
        self.memory_logger_timer = asyncio.get_event_loop().call_later(
            60,
            self.memory_logger,
        )

    def collect_metrics(self):
        logger.info("collect_metrics")
        if self.stats_file:
            logger.info(f"Loading stats from file: {self.stats_file}")
            try:
                # Temporarily set save_location to the directory of the file
                original_save_location = cfg.CONF.save_location
                cfg.CONF.save_location = os.path.dirname(self.stats_file)
                ss = StatsStore()
                ss.load()
                # Restore
                cfg.CONF.save_location = original_save_location
                # Verify we have valid stats data
                if not ss.data or "APRSDStats" not in ss.data:
                    logger.warning("Stats file loaded but contains no valid data")
                    # Explicitly delete to free memory
                    del ss
                    return None
                # Wrap in the same format as HTTP response
                # Note: We keep a reference to ss.data, but ss itself can be GC'd
                # The data will be processed and then explicitly deleted in update_metrics()
                stats_obj = {"stats": ss.data}
                # Delete the StatsStore object (data is still referenced by stats_obj)
                # This allows Python to free any other memory used by the StatsStore object
                del ss
                return stats_obj
            except Exception as e:
                logger.error(f"Error loading stats from file {self.stats_file}: {e}")
                return None
        elif self.api and self.received_stats:
            logger.info("Using received stats from API")
            return self.received_stats
        elif self.api:
            logger.info("No stats received yet from API")
            return None
        else:
            logger.info("Fetching stats from APRSD URL")
            try:
                r = self.requests_session.get(f"{self.aprsd_url}/stats", timeout=10)
                if r.status_code != 200:
                    logger.error(f"Failed to get stats from APRSD: {r.status_code}")
                    return None
                stats_obj = r.json()
                return stats_obj
            except Exception as e:
                logger.error(f"Error fetching stats from APRSD: {e}")
                return None

    def update_metrics(self):
        # Update metrics here
        stats_obj = self.collect_metrics()
        if not stats_obj:
            logger.warning("No valid stats object received")
            return

        # Now process the stats and create/update the metrics.
        stats = stats_obj.get("stats", {})
        if not stats or "APRSDStats" not in stats:
            logger.error("Invalid stats object received, missing 'APRSDStats'")
            return

        self.callsign = stats["APRSDStats"].get("callsign", "UNKNOWN")
        # Update const_labels with current callsign before registering metrics
        if not hasattr(self, 'const_labels') or self.const_labels.get("callsign") != self.callsign:
            self.const_labels = {
                "host": socket.gethostname(),
                "app": f"{self.__class__.__name__}",
                "callsign": self.callsign or "unknown",
            }
        self.register_metrics()
        if self._metrics:
            self._update_aprsd_metrics(stats["APRSDStats"])
            self._update_packet_metrics(stats.get("PacketList", {}))
            if stats.get("APRSDThreadList"):
                self._update_thread_metrics(stats["APRSDThreadList"])
            if stats.get("PluginManager"):
                self._update_plugins_metrics(stats["PluginManager"])
            if stats.get("SeenList"):
                self._update_seen_metrics(stats["SeenList"])

        # Clear reference to stats_obj to help with garbage collection
        # The stats dict may be large, especially if SeenList grows unbounded
        # CRITICAL: Explicitly delete large data structures to free memory immediately
        if "SeenList" in stats:
            # The SeenList can be very large - delete it explicitly
            del stats["SeenList"]
        del stats_obj
        del stats
        # Force garbage collection hint (Python will decide when to actually GC)
        import gc
        gc.collect()

    def _update_aprsd_metrics(self, aprsd_stats):
        logger.info("_update_aprsd_metrics")
        logger.debug(f"aprsd_stats: {aprsd_stats}")
        if not aprsd_stats:
            logger.warning("aprsd_stats is empty")
            return

        self._metrics[APRSD_STATS]["aprsd"].labels(
            **{**self.const_labels, "version": aprsd_stats.get("version", "UNKNOWN")}
        ).set(1.0)
        # self._metrics[APRSD_STATS]['aprsd'].labels(
        #     **{**self.const_labels, 'uptime': aprsd_stats['uptime']}
        # ).set(1.0)
        self._metrics[APRSD_STATS]["aprsd"].labels(
            **{**self.const_labels, "callsign": aprsd_stats.get("callsign", "UNKNOWN")}
        ).set(1.0)
        self._metrics[APRSD_STATS]["aprsd_memory"].labels(
            **{**self.const_labels, "type": "current"}
        ).set(aprsd_stats.get("memory_current", 0))
        self._metrics[APRSD_STATS]["aprsd_memory"].labels(
            **{**self.const_labels, "type": "peak"}
        ).set(aprsd_stats.get("memory_peak", 0))

    def _update_packet_metrics(self, packet_list):
        logger.info("_update_packet_metrics")
        if not packet_list:
            logger.warning("packet_list is empty")
            return

        self._metrics[PACKET_METRICS]["Packets"].labels(
            **{**self.const_labels, "count": "total"}
        ).set(packet_list.get("total_tracked", 0))
        self._metrics[PACKET_METRICS]["Packets"].labels(
            **{**self.const_labels, "count": "tx"}
        ).set(packet_list.get("tx", 0))
        self._metrics[PACKET_METRICS]["Packets"].labels(
            **{**self.const_labels, "count": "rx"}
        ).set(packet_list.get("rx", 0))
        for packet_type in packet_list.get("types", {}):
            logger.debug(f"packet_type: {packet_type}")
            self._metrics[PACKET_METRICS][packet_type].labels(
                **{**self.const_labels, "count": "tx"}
            ).set(packet_list["types"][packet_type].get("tx", 0))
            self._metrics[PACKET_METRICS][packet_type].labels(
                **{**self.const_labels, "count": "rx"}
            ).set(packet_list["types"][packet_type].get("rx", 0))

    def _update_thread_metrics(self, thread_list):
        logger.info("_update_thread_metrics")
        if not thread_list:
            logger.warning("thread_list is empty")
            return

        # Clean up metrics for threads that no longer exist
        current_threads = set(thread_list.keys())
        existing_threads = set(self._metrics[THREAD_METRICS].keys())
        for thread in existing_threads - current_threads:
            logger.debug(f"Removing metric for thread that no longer exists: {thread}")
            del self._metrics[THREAD_METRICS][thread]

        for thread in thread_list:
            # logger.info(f"thread: {thread}")
            if thread not in self._metrics[THREAD_METRICS]:
                try:
                    self._metrics[THREAD_METRICS][thread] = Gauge(
                        thread,
                        f"Thread {thread} status",
                        labelnames=list(self.const_labels.keys()) + ["class", "alive", "status"],
                    )
                except Exception:
                    logger.error(f"Failed to create metric for thread: {thread}")
                    continue

            thread_data = thread_list.get(thread, {})
            if not thread_data:
                logger.warning(f"No data for thread: {thread}")
                continue

            logger.info(f"thread_list[thread]: {thread_data}")
            self._metrics[THREAD_METRICS][thread].labels(
                **{**self.const_labels, "class": thread_data.get("class", "UNKNOWN"), "alive": "", "status": ""}
            ).set(1.0)
            self._metrics[THREAD_METRICS][thread].labels(
                **{**self.const_labels, "class": "", "alive": str(thread_data.get("alive", False)), "status": ""}
            ).set(1.0)
            # self._metrics[THREAD_METRICS][thread].labels(
            #     **{**self.const_labels, 'class': '', 'alive': '', 'age': thread_list[thread]['age']}
            # ).set(1.0)
            self._metrics[THREAD_METRICS][thread].labels(
                **{**self.const_labels, "class": "", "alive": "", "status": "loop_count"}
            ).set(thread_data.get("loop_count", 0))

    def _update_seen_metrics(self, seen_list):
        logger.info("_update_seen_metrics")
        if not seen_list:
            logger.warning("seen_list is empty")
            # Clean up all previous callsigns if seen_list is empty
            self._previous_seen_callsigns.clear()
            # Still report 0 for total count
            if "seen_callsigns_total" not in self._metrics[SEEN_METRICS]:
                self._metrics[SEEN_METRICS]["seen_callsigns_total"] = Gauge(
                    "seen_callsigns_total",
                    "Total number of unique callsigns in the seen list",
                    labelnames=list(self.const_labels.keys()),
                )
            self._metrics[SEEN_METRICS]["seen_callsigns_total"].labels(**self.const_labels).set(0)
            return

        if "callsigns" not in self._metrics[SEEN_METRICS]:
            self._metrics[SEEN_METRICS]["callsigns"] = Gauge(
                "callsigns",
                "The stats of callsigns seen by APRSD",
                labelnames=list(self.const_labels.keys()) + ["callsign", "status", "last_seen"],
            )

        # Initialize metric for total count of callsigns in seen list
        if "seen_callsigns_total" not in self._metrics[SEEN_METRICS]:
            self._metrics[SEEN_METRICS]["seen_callsigns_total"] = Gauge(
                "seen_callsigns_total",
                "Total number of unique callsigns in the seen list",
                labelnames=list(self.const_labels.keys()),
            )

        # Report accurate total count of callsigns in seen list
        total_callsigns = len(seen_list)
        self._metrics[SEEN_METRICS]["seen_callsigns_total"].labels(**self.const_labels).set(total_callsigns)

        # Limit to top N most active callsigns to prevent unbounded memory growth
        # Sort by count (activity) and take top N
        callsign_items = []
        for callsign, callsign_data in seen_list.items():
            if not callsign_data:
                continue
            count = callsign_data.get("count", 0)
            callsign_items.append((callsign, callsign_data, count))

        # Sort by count descending and take top N
        callsign_items.sort(key=lambda x: x[2], reverse=True)
        top_callsigns = callsign_items[:self.max_seen_callsigns]

        # Track current callsigns for cleanup
        current_callsigns = {item[0] for item in top_callsigns}

        # Clean up metrics for callsigns that are no longer in top N
        # CRITICAL: Prometheus time series accumulate in memory. Each unique label combination
        # creates a time series that persists. We need to be aggressive about cleanup.
        removed_callsigns = self._previous_seen_callsigns - current_callsigns
        for callsign in removed_callsigns:
            logger.debug(f"Cleaning up metric for callsign no longer in top {self.max_seen_callsigns}: {callsign}")
            try:
                # Set count to 0 to mark as inactive
                # Note: We can't fully remove time series from Prometheus registry,
                # but setting to 0 helps and prevents further updates
                self._metrics[SEEN_METRICS]["callsigns"].labels(
                    **{**self.const_labels, "callsign": callsign, "status": "count", "last_seen": ""}
                ).set(0)
                # Also clean up the last_seen metric (use empty string for last_seen since we don't have the data)
                self._metrics[SEEN_METRICS]["callsigns"].labels(
                    **{**self.const_labels, "callsign": callsign, "status": "", "last_seen": ""}
                ).set(0)
                # Remove from tracking set to free memory
                self._all_tracked_callsigns.discard(callsign)
            except Exception as e:
                logger.debug(f"Error cleaning up metric for {callsign}: {e}")

        # Only update metrics for callsigns currently in top N
        # This prevents creating new time series for callsigns that aren't active
        for callsign, callsign_data, _ in top_callsigns:
            # Track that we've seen this callsign
            self._all_tracked_callsigns.add(callsign)

            self._metrics[SEEN_METRICS]["callsigns"].labels(
                **{**self.const_labels, "callsign": callsign, "status": "count", "last_seen": ""}
            ).set(callsign_data.get("count", 0))
            self._metrics[SEEN_METRICS]["callsigns"].labels(
                **{**self.const_labels, "callsign": callsign, "status": "", "last_seen": str(callsign_data.get("last", ""))}
            ).set(1.0)

        # Update tracking set for next iteration
        self._previous_seen_callsigns = current_callsigns

        # Log memory usage info periodically
        if len(self._all_tracked_callsigns) > self.max_seen_callsigns * 2:
            logger.warning(
                f"Tracking {len(self._all_tracked_callsigns)} total callsign time series "
                f"(limit: {self.max_seen_callsigns}). This may indicate memory growth. "
                f"Consider reducing --max-seen-callsigns or increasing cleanup frequency."
            )

        if len(seen_list) > self.max_seen_callsigns:
            logger.debug(
                f"Seen list has {len(seen_list)} callsigns, "
                f"tracking top {self.max_seen_callsigns} to limit memory usage"
            )

    def _update_plugins_metrics(self, plugins_list):
        logger.info("_update_plugins_metrics")
        if not plugins_list:
            logger.warning("plugins_list is empty")
            return

        for plugin in plugins_list:
            plugin_name = plugin.split(".")[-1]
            if plugin_name not in self._metrics[PLUGINS_METRICS]:
                try:
                    self._metrics[PLUGINS_METRICS][plugin_name] = Gauge(
                        plugin_name,
                        f"Plugin {plugin_name} status",
                        labelnames=list(self.const_labels.keys()) + ["packets", "enabled", "version", "name"],
                    )
                except Exception:
                    logger.error(f"Failed to create metric for plugin: {plugin}")
                    continue

            plugin_data = plugins_list.get(plugin, {})
            if not plugin_data:
                logger.warning(f"No data for plugin: {plugin}")
                continue

            self._metrics[PLUGINS_METRICS][plugin_name].labels(
                **{**self.const_labels, "packets": "tx", "enabled": "", "version": "", "name": ""}
            ).set(plugin_data.get("tx", 0))
            self._metrics[PLUGINS_METRICS][plugin_name].labels(
                **{**self.const_labels, "packets": "rx", "enabled": "", "version": "", "name": ""}
            ).set(plugin_data.get("rx", 0))
            self._metrics[PLUGINS_METRICS][plugin_name].labels(
                **{**self.const_labels, "packets": "", "enabled": str(plugins_list[plugin]["enabled"]), "version": "", "name": ""}
            ).set(1.0)
            self._metrics[PLUGINS_METRICS][plugin_name].labels(
                **{**self.const_labels, "packets": "", "enabled": "", "version": str(plugins_list[plugin]["version"]), "name": ""}
            ).set(1.0)
            self._metrics[PLUGINS_METRICS][plugin_name].labels(
                **{**self.const_labels, "packets": "", "enabled": "", "version": "", "name": plugin}
            ).set(1.0)
