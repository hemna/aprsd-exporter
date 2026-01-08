"""
Export TNC metrics using prometheus.
"""

import asyncio
import inspect
import logging
from loguru import logger

import click

from .exporter import APRSDExporter


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


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
@click.option(
    "--api",
    is_flag=True,
    default=False,
    help="Run Flask API server to accept stats from external APRSD instance"
)
@click.option(
    "--api-port",
    metavar="<api port>",
    type=int,
    default=8081,
    help="The port for the Flask API server. Default is 8081"
)
@click.option(
    "--stats-file",
    metavar="<stats file>",
    type=str,
    default=None,
    help="Path to the statsstore.p file to load stats from instead of fetching from APRSD"
)
def main(aprsd_url, host, port, update_interval, debug, quiet, api, api_port, stats_file):
    """Run prometheus exporter"""
    logging.getLogger("asyncio").setLevel(logging.ERROR)
    logging.getLogger("aiohttp").setLevel(logging.DEBUG)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    exp = APRSDExporter(
        aprsd_url=aprsd_url,
        host=host,
        port=port,
        stats_interval=update_interval,
        api=api,
        api_port=api_port,
        stats_file=stats_file,
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
