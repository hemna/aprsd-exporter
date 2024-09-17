"""
Export TNC metrics using prometheus.
"""

import asyncio
from loguru import logger

import click

from .exporter import APRSDExporter

@click.command()
@click.option(
    "--aprsd-url",
    metavar="<aprsd url>",
    type=str,
    default="http://localhost:8080",
    help="The APRSD ADMIN URL to connect to. Default is http://localhost:8080"
)
@click.option(
    "--host",
    metavar="<exporter host>",
    type=str,
    default="0.0.0.0",
    help="The IP address to expose collected metrics from. Default is"
)
@click.option(
    "--port",
    metavar="<exporter port>",
    type=int,
    default=8080,
    help="The port to expose collected metrics from. Default is 9110",
)
@click.option(
    "--update-interval",
    metavar="<update interval>",
    type=int,
    default=60,
    help="The interval in seconds to update metrics. Default is 5 seconds",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Print debug messages to stdout"
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Only print error messages to stdout"
)
def main(aprsd_url, host, port, update_interval, debug, quiet):
    """Run prometheus exporter"""
    # set up command-line argument parser
    # set logging message verbosity
    # if debug:
    #     logging.basicConfig(level=logging.DEBUG,
    #                         format='%(levelname)s: %(asctime)s - %(message)s',
    #                         datefmt='%d-%b-%y %H:%M:%S')
    # elif quiet:
    #     logging.basicConfig(level=logging.ERROR,
    #                         format='%(levelname)s: %(asctime)s - %(message)s',
    #                         datefmt='%d-%b-%y %H:%M:%S')
    # else:
    #     logging.basicConfig(level=logging.INFO,
    #                         format='%(levelname)s: %(asctime)s - %(message)s',
    #                         datefmt='%d-%b-%y %H:%M:%S')

    loop = asyncio.get_event_loop()
    exp = APRSDExporter(
        aprsd_url=aprsd_url,
        host=host,
        port=port,
        stats_interval=update_interval,
    )
    try:
        # start metrics server and listener
        loop.run_until_complete(exp.start())
    except KeyboardInterrupt:
        pass
    else:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(exp.stop())
    loop.stop()
    loop.close()


if __name__ == "__main__":
    main()
