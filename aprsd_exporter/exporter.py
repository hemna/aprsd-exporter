import asyncio
import os
import socket
import threading
from asyncio.events import AbstractEventLoop

import requests
from aioprometheus import Gauge
from aioprometheus.service import Service
from aprsd.threads.stats import StatsStore
from flask import Flask, jsonify, request
from loguru import logger
from oslo_config import cfg

APRSD_STATS = 'aprsd'
PACKET_METRICS = 'packets'
THREAD_METRICS = 'threads'
SEEN_METRICS = 'seen'
PLUGINS_METRICS = 'plugins'


class APRSDExporter:
    def __init__(self, aprsd_url: str, host: str, port: int,
                 stats_interval: int, api: bool = False, api_port: int = 8081,
                 stats_file: str = None, loop: AbstractEventLoop = None):
        self.loop = loop or asyncio.get_event_loop()
        self.aprsd_url = aprsd_url
        self.host = host
        self.port = port
        self.stats_interval = stats_interval
        self.api = api
        self.api_port = api_port
        self.stats_file = stats_file
        self.metrics_task = None
        self.server = Service()
        self.flask_app = None
        self.flask_thread = None
        self.received_stats = None

        self.callsign = None
        self._metrics = None

    async def start(self):
        # start prometheus metrics server
        await self.server.start(addr=self.host, port=self.port)
        logger.info(f"Serving APRSD prometheus metrics on: {self.server.metrics_url}")

        if self.api:
            self._start_flask_api()

        # Schedule a timer to update metrics. In a realistic application
        # the metrics would be updated as needed. In this example, a simple
        # timer is used to emulate things happening, which conveniently
        # allows all metrics to be updated at once.
        self.timer = asyncio.get_event_loop().call_later(
            self.stats_interval, self.metric_updater)

    async def stop(self):
        if self.flask_thread and self.flask_thread.is_alive():
            # Flask doesn't have a clean shutdown, but since it's in a daemon thread, it will stop with the process
            pass
        await self.server.stop()

    def _start_flask_api(self):
        self.flask_app = Flask(__name__)

        @self.flask_app.route('/stats', methods=['POST'])
        def receive_stats():
            try:
                self.received_stats = request.get_json()
                logger.info("Received stats from external APRSD instance")
                return jsonify({"status": "ok"}), 200
            except Exception as e:
                logger.error(f"Failed to process stats: {e}")
                return jsonify({"error": str(e)}), 400

        @self.flask_app.route('/health', methods=['GET'])
        def health():
            return jsonify({"status": "healthy"}), 200

        logger.info(f"Starting Flask API server on port {self.api_port}")
        self.flask_thread = threading.Thread(target=self._run_flask, daemon=True)
        self.flask_thread.start()
        logger.info(f"Started Flask API server thread on port {self.api_port}")

    def _run_flask(self):
        logger.info(f"Flask app.run() called for port {self.api_port}")
        self.flask_app.run(host='0.0.0.0', port=self.api_port, debug=False, use_reloader=False, threaded=True)

    def register_metrics(self):
        if not self._metrics:
            # Define some constant labels that need to be added to all metrics
            self.const_labels = {
                "host": socket.gethostname(),
                "app": f"{self.__class__.__name__}",
                "callsign": self.callsign or "unknown",
            }
            const_labels = self.const_labels
            self._metrics = {
                APRSD_STATS: {
                    'aprsd': Gauge(
                        'aprsd',
                        'APRSD Stats',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'aprsd_memory': Gauge(
                        'aprsd_memory',
                        'APRSD Memory Usage',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                },
                PACKET_METRICS: {
                    'Packets': Gauge(
                        'Packets',
                        'Total number of packets sent/received',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'AckPacket': Gauge(
                        'AckPacket',
                        'Ack Packet Totals',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'BeaconPacket': Gauge(
                        'BeaconPacket',
                        'Beacon type packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'BulletinPacket': Gauge(
                        'BulletinPacket',
                        'Bulletin type packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'MessagePacket': Gauge(
                        'MessagePacket',
                        'Message type packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'MicEPacket': Gauge(
                        'MicEPacket',
                        'Mic E Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'ObjectPacket': Gauge(
                        'ObjectPacket',
                        'Object Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'RejectPacket': Gauge(
                        'RejectPacket',
                        'Reject Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'StatusPacket': Gauge(
                        'StatusPacket',
                        'Status Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'TelemetryPacket': Gauge(
                        'TelemetryPacket',
                        'Telemetry Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'ThirdPartyPacket': Gauge(
                        'ThirdPartyPacket',
                        'Third Party Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'WeatherPacket': Gauge(
                        'WeatherPacket',
                        'Weather Packets',
                        const_labels=const_labels,
                        registry=self.server.registry
                    ),
                    'UnknownPacket': Gauge(
                        'UnknownPacket',
                        'Total number of unknown packets received',
                        const_labels=const_labels,
                        registry=self.server.registry
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
            self.stats_interval, self.metric_updater)

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
                if not ss.data or 'APRSDStats' not in ss.data:
                    logger.warning("Stats file loaded but contains no valid data")
                    return None
                # Wrap in the same format as HTTP response
                stats_obj = {'stats': ss.data}
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
                r = requests.get(f"{self.aprsd_url}/stats")
                if r.status_code != 200:
                    logger.error(f"Failed to get stats from APRSD: {r.status_code}")
                    return
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
        stats = stats_obj.get('stats', {})
        if not stats or 'APRSDStats' not in stats:
            logger.error("Invalid stats object received, missing 'APRSDStats'")
            return

        self.callsign = stats['APRSDStats'].get('callsign', 'UNKNOWN')
        self.register_metrics()
        if self._metrics:
            self._update_aprsd_metrics(stats["APRSDStats"])
            self._update_packet_metrics(stats.get('PacketList', {}))
            if stats.get('APRSDThreadList'):
                self._update_thread_metrics(stats['APRSDThreadList'])
            if stats.get('PluginManager'):
                self._update_plugins_metrics(stats['PluginManager'])
            if stats.get('SeenList'):
                self._update_seen_metrics(stats['SeenList'])

    def _update_aprsd_metrics(self, aprsd_stats):
        logger.info("_update_aprsd_metrics")
        logger.debug(f"aprsd_stats: {aprsd_stats}")
        if not aprsd_stats:
            logger.warning("aprsd_stats is empty")
            return
 
        self._metrics[APRSD_STATS]['aprsd'].set(
            {'version': aprsd_stats.get('version', 'UNKNOWN')}, 1.0
        )
        # self._metrics[APRSD_STATS]['aprsd'].set(
        #     {'uptime': aprsd_stats['uptime']}, 1.0
        # )
        self._metrics[APRSD_STATS]['aprsd'].set(
            {'callsign': aprsd_stats.get('callsign', 'UNKNOWN')}, 1.0
        )
        self._metrics[APRSD_STATS]['aprsd_memory'].set(
            {'type': 'current'}, aprsd_stats.get('memory_current', 0)
        )
        self._metrics[APRSD_STATS]['aprsd_memory'].set(
            {'type': 'peak'}, aprsd_stats.get('memory_peak', 0)
        )

    def _update_packet_metrics(self, packet_list):
        logger.info("_update_packet_metrics")
        if not packet_list:
            logger.warning("packet_list is empty")
            return
        
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'total'}, packet_list.get('total_tracked', 0)
        )
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'tx'}, packet_list.get('tx', 0)
        )
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'rx'}, packet_list.get('rx', 0)
        )
        for packet_type in packet_list.get('types', {}):
            logger.debug(f"packet_type: {packet_type}")
            self._metrics[PACKET_METRICS][packet_type].set(
                {'count': 'tx'}, packet_list['types'][packet_type].get('tx', 0)
            )
            self._metrics[PACKET_METRICS][packet_type].set(
                {'count': 'rx'}, packet_list['types'][packet_type].get('rx', 0)
            )

    def _update_thread_metrics(self, thread_list):
        logger.info("_update_thread_metrics")
        if not thread_list:
            logger.warning("thread_list is empty")
            return
            
        for thread in thread_list:
            # logger.info(f"thread: {thread}")
            if thread not in self._metrics[THREAD_METRICS]:
                try:
                    self._metrics[THREAD_METRICS][thread] = Gauge(
                        thread,
                        f"Thread {thread} status",
                        const_labels=self.const_labels,
                        registry=self.server.registry
                    )
                except Exception:
                    logger.error(f"Failed to create metric for thread: {thread}")
                    continue
            
            thread_data = thread_list.get(thread, {})
            if not thread_data:
                logger.warning(f"No data for thread: {thread}")
                continue
                
            logger.info(f"thread_list[thread]: {thread_data}")
            self._metrics[THREAD_METRICS][thread].set(
                {'class': thread_data.get('class', 'UNKNOWN')}, 1.0
            )
            self._metrics[THREAD_METRICS][thread].set(
                {'alive': str(thread_data.get('alive', False))}, 1.0
            )
            # self._metrics[THREAD_METRICS][thread].set(
            #     {'age': thread_list[thread]['age']}, 1.0
            # )
            self._metrics[THREAD_METRICS][thread].set(
                {'status': 'loop_count'}, thread_data.get('loop_count', 0)
            )

    def _update_seen_metrics(self, seen_list):
        logger.info("_update_seen_metrics")
        if not seen_list:
            logger.warning("seen_list is empty")
            return

        if 'callsigns' not in self._metrics[SEEN_METRICS]:
            self._metrics[SEEN_METRICS]['callsigns'] = Gauge(
                'callsigns',
                "The stats of callsigns seen by APRSD",
                const_labels=self.const_labels,
                registry=self.server.registry
            )
        for callsign in seen_list:
            callsign_data = seen_list.get(callsign, {})
            if not callsign_data:
                logger.warning(f"No data for callsign: {callsign}")
                continue
                
            self._metrics[SEEN_METRICS]['callsigns'].set(
                {'callsign': callsign, 'status': 'count'},
                callsign_data.get('count', 0)
            )
            self._metrics[SEEN_METRICS]['callsigns'].set(
                {'callsign': callsign,
                 'last_seen': str(callsign_data.get('last', ''))},
                1.0
            )

    def _update_plugins_metrics(self, plugins_list):
        logger.info("_update_plugins_metrics")
        if not plugins_list:
            logger.warning("plugins_list is empty")
            return
            
        for plugin in plugins_list:
            plugin_name = plugin.split('.')[-1]
            if plugin_name not in self._metrics[PLUGINS_METRICS]:
                try:
                    self._metrics[PLUGINS_METRICS][plugin_name] = Gauge(
                        plugin_name,
                        f"Plugin {plugin_name} status",
                        const_labels=self.const_labels,
                        registry=self.server.registry
                    )
                except Exception:
                    logger.error(f"Failed to create metric for plugin: {plugin}")
                    continue
            
            plugin_data = plugins_list.get(plugin, {})
            if not plugin_data:
                logger.warning(f"No data for plugin: {plugin}")
                continue
                
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'packets': 'tx'}, plugin_data.get('tx', 0)
            )
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'packets': 'rx'}, plugin_data.get('rx', 0)
            )
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'enabled': plugins_list[plugin]['enabled']}, 1.0
            )
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'version': plugins_list[plugin]['version']}, 1.0
            )
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'name': plugin}, 1.0
            )
