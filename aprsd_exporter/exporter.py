import asyncio
from asyncio.events import AbstractEventLoop
from aioprometheus.service import Service
from aioprometheus import Counter, Gauge, Histogram, Summary
from loguru import logger
import requests
import socket


APRSD_STATS = 'aprsd'
PACKET_METRICS = 'packets'
THREAD_METRICS = 'threads'
SEEN_METRICS = 'seen'
PLUGINS_METRICS = 'plugins'



class APRSDExporter:
    def __init__(self, aprsd_url: str, host: str, port: int,
                 stats_interval: int, loop: AbstractEventLoop = None):
        self.loop = loop or asyncio.get_event_loop()
        self.aprsd_url = aprsd_url
        self.host = host
        self.port = port
        self.stats_interval = stats_interval
        self.metrics_task = None
        self.server = Service()

        self.callsign = None
        self._metrics = None

    async def start(self):
        # start prometheus metrics server
        await self.server.start(addr=self.host, port=self.port)
        logger.info(f"Serving APRSD prometheus metrics on: {self.server.metrics_url}")

        # Schedule a timer to update metrics. In a realistic application
        # the metrics would be updated as needed. In this example, a simple
        # timer is used to emulate things happening, which conveniently
        # allows all metrics to be updated at once.
        self.timer = asyncio.get_event_loop().call_later(
            self.stats_interval, self.metric_updater)

    async def stop(self):
        await self.server.stop()

    def register_metrics(self):
        if not self._metrics:
            # Define some constant labels that need to be added to all metrics
            self.const_labels = {
                "host": socket.gethostname(),
                "app": f"{self.__class__.__name__}",
                "callsign": self.callsign,
            }
            const_labels = self.const_labels
            self._metrics = {
                APRSD_STATS: {
                    'aprsd': Gauge(
                        'aprsd',
                        'APRSD Stats',
                        const_labels=const_labels
                    ),
                    'aprsd_memory': Gauge(
                        'aprsd_memory',
                        'APRSD Memory Usage',
                        const_labels=const_labels
                    ),
                },
                PACKET_METRICS: {
                    'Packets': Gauge(
                        'Packets',
                        'Total number of packets sent/received',
                        const_labels=const_labels
                    ),
                    'AckPacket': Gauge(
                        'AckPacket',
                        'Ack Packet Totals',
                        const_labels=const_labels
                    ),
                    'BeaconPacket': Gauge(
                        'BeaconPacket',
                        'Beacon type packets',
                        const_labels=const_labels
                    ),
                    'BulletinPacket': Gauge(
                        'BulletinPacket',
                        'Bulletin type packets',
                        const_labels=const_labels
                    ),
                    'MessagePacket': Gauge(
                        'MessagePacket',
                        'Message type packets',
                        const_labels=const_labels
                    ),
                    'MicEPacket': Gauge(
                        'MicEPacket',
                        'Mic E Packets',
                        const_labels=const_labels
                    ),
                    'ObjectPacket': Gauge(
                        'ObjectPacket',
                        'Object Packets',
                        const_labels=const_labels
                    ),
                    'RejectPacket': Gauge(
                        'RejectPacket',
                        'Reject Packets',
                        const_labels=const_labels
                    ),
                    'StatusPacket': Gauge(
                        'StatusPacket',
                        'Status Packets',
                        const_labels=const_labels
                    ),
                    'TelemetryPacket': Gauge(
                        'TelemetryPacket',
                        'Telemetry Packets',
                        const_labels=const_labels
                    ),
                    'ThirdPartyPacket': Gauge(
                        'ThirdPartyPacket',
                        'Third Party Packets',
                        const_labels=const_labels
                    ),
                    'WeatherPacket': Gauge(
                        'WeatherPacket',
                        'Weather Packets',
                        const_labels=const_labels
                    ),
                    'UnknownPacket': Gauge(
                        'UnknownPacket',
                        'Total number of unknown packets received',
                        const_labels=const_labels
                    ),
                },
                THREAD_METRICS: {},
                SEEN_METRICS: {},
                PLUGINS_METRICS: {},
            }

    def metric_updater(self):
        logger.info(f"metric_updater")
        self.update_metrics()

        # re-schedule another metrics update
        self.timer = asyncio.get_event_loop().call_later(
            self.stats_interval, self.metric_updater)

    def collect_metrics(self):
        logger.info(f"collect_metrics")
        r = requests.get(f"{self.aprsd_url}/stats")
        if r.status_code != 200:
            logger.error(f"Failed to get stats from APRSD: {r.status_code}")
            return
        stats_obj = r.json()
        return stats_obj

    def update_metrics(self):
        # Update metrics here
        stats_obj = self.collect_metrics()
        if stats_obj:
            # Now process the stats and create/update the metrics.

            stats = stats_obj['stats']
            self.callsign = stats['APRSDStats']['callsign']
            self.register_metrics()
            if self._metrics:
                self._update_aprsd_metrics(stats["APRSDStats"])
                self._update_packet_metrics(stats['PacketList'])
                if stats['APRSDThreadList']:
                    self._update_thread_metrics(stats['APRSDThreadList'])
                if stats['PluginManager']:
                   self._update_plugins_metrics(stats['PluginManager'])
                if stats['SeenList']:
                    self._update_seen_metrics(stats['SeenList'])

    def _update_aprsd_metrics(self, aprsd_stats):
        logger.info("_update_aprsd_metrics")
        logger.debug(f"aprsd_stats: {aprsd_stats}")
        self._metrics[APRSD_STATS]['aprsd'].set(
            {'version': aprsd_stats['version']}, 1.0
        )
        self._metrics[APRSD_STATS]['aprsd'].set(
            {'uptime': aprsd_stats['uptime']}, 1.0
        )
        self._metrics[APRSD_STATS]['aprsd'].set(
            {'callsign': aprsd_stats['callsign']}, 1.0
        )
        self._metrics[APRSD_STATS]['aprsd_memory'].set(
            {'type': 'current'}, aprsd_stats['memory_current']
        )
        self._metrics[APRSD_STATS]['aprsd_memory'].set(
            {'type': 'peak'}, aprsd_stats['memory_peak']
        )

    def _update_packet_metrics(self, packet_list):
        logger.info(f"_update_packet_metrics")
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'total'}, packet_list['total_tracked']
        )
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'tx'}, packet_list['tx']
        )
        self._metrics[PACKET_METRICS]['Packets'].set(
            {'count': 'rx'}, packet_list['rx']
        )
        for packet_type in packet_list['types']:
            logger.debug(f"packet_type: {packet_type}")
            self._metrics[PACKET_METRICS][packet_type].set(
                {'count': 'tx'}, packet_list['types'][packet_type]['tx']
            )
            self._metrics[PACKET_METRICS][packet_type].set(
                {'count': 'rx'}, packet_list['types'][packet_type]['rx']
            )

    def _update_thread_metrics(self, thread_list):
        logger.info("_update_thread_metrics")
        for thread in thread_list:
            # logger.info(f"thread: {thread}")
            if thread not in self._metrics[THREAD_METRICS]:
                try:
                    self._metrics[THREAD_METRICS][thread] = Gauge(
                        thread,
                        f"Thread {thread} status",
                        const_labels=self.const_labels
                    )
                except Exception:
                    logger.error(f"Failed to create metric for thread: {thread}")
                    continue
            logger.info(f"thread_list[thread]: {thread_list[thread]}")
            self._metrics[THREAD_METRICS][thread].set(
                {'class': thread_list[thread]['class']}, 1.0
            )
            self._metrics[THREAD_METRICS][thread].set(
                {'alive': thread_list[thread]['alive']}, 1.0
            )
            self._metrics[THREAD_METRICS][thread].set(
                {'age': thread_list[thread]['age']}, 1.0
            )
            self._metrics[THREAD_METRICS][thread].set(
                {'status': 'loop_count'}, thread_list[thread]['loop_count']
            )

    def _update_seen_metrics(self, seen_list):
        logger.info("_update_seen_metrics")

        if 'callsigns' not in self._metrics[SEEN_METRICS]:
            self._metrics[SEEN_METRICS]['callsigns'] = Gauge(
                'callsigns',
                f"The stats of callsigns seen by APRSD",
                const_labels=self.const_labels
            )
        for callsign in seen_list:
            self._metrics[SEEN_METRICS]['callsigns'].set(
                {'callsign': callsign, 'status': 'count'},
                seen_list[callsign]['count']
            )
            self._metrics[SEEN_METRICS]['callsigns'].set(
                {'callsign': callsign,
                 'last_seen': seen_list[callsign]['last']},
                1.0
            )

    def _update_plugins_metrics(self, plugins_list):
        logger.info("_update_plugins_metrics")
        for plugin in plugins_list:
            plugin_name = plugin.split('.')[-1]
            if plugin_name not in self._metrics[PLUGINS_METRICS]:
                try:
                    self._metrics[PLUGINS_METRICS][plugin_name] = Gauge(
                        plugin_name,
                        f"Plugin {plugin_name} status",
                        const_labels=self.const_labels
                    )
                except Exception:
                    logger.error(f"Failed to create metric for plugin: {plugin}")
                    continue
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'packets': 'tx'}, plugins_list[plugin]['tx']
            )
            self._metrics[PLUGINS_METRICS][plugin_name].set(
                {'packets': 'rx'}, plugins_list[plugin]['rx']
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

