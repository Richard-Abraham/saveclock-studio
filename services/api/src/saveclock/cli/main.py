"""`saveclock`: argparse entry. Commands come from `commands.COMMANDS`; nothing else lives here."""

import argparse
import sys
from collections.abc import Sequence

from saveclock.cli import __version__
from saveclock.cli.client import Client, CliError, Refused
from saveclock.cli.commands import COMMANDS, Ctx
from saveclock.cli.output import fail
from saveclock.config import CliSettings

EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="saveclock",
        description="Make a beat-synced video from a song with the local SaveClock app. "
        "Talks only to this machine. Exit codes: 0 ok, 1 API or job error (the code is printed), "
        "2 usage or refusal, 3 network, timeout or redirect (a timeout means still running).",
    )
    parser.add_argument("--version", action="version", version=f"saveclock {__version__}")
    parser.add_argument("--json", action="store_true", help="print one JSON document")
    parser.add_argument(
        "--api-url", help="API base URL (default: SAVECLOCK_API_URL, loopback only)"
    )
    subs = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    for cmd in COMMANDS:
        sub = subs.add_parser(cmd.name, help=cmd.help, description=cmd.help)
        # the same two options after the command (`show <id> --json`); unset keeps the global one
        sub.add_argument(
            "--json", action="store_true", default=argparse.SUPPRESS, help="print one JSON document"
        )
        sub.add_argument("--api-url", default=argparse.SUPPRESS, help="API base URL")
        for names, kwargs in cmd.args:
            sub.add_argument(*names, **kwargs)
        sub.set_defaults(_handler=cmd.handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    as_json = bool(args.json)
    try:
        settings = CliSettings()
        client = Client(args.api_url or settings.saveclock_api_url)
    except Refused as err:
        return fail(err, as_json=as_json)
    try:
        return int(args._handler(Ctx(client, as_json, settings.app_origin), args))
    except CliError as err:
        return fail(err, as_json=as_json)
    except OSError as err:  # a local file the command could not read or write
        msg = f"{type(err).__name__}: {err}"
        return fail(CliError("io_error", msg, exit_code=1), as_json=as_json)
    except (KeyError, TypeError) as err:  # an API answer of a shape this CLI does not know
        msg = f"unexpected API answer ({type(err).__name__}: {err})"
        return fail(CliError("internal_error", msg, exit_code=1), as_json=as_json)
    except KeyboardInterrupt:
        print("interrupted (a running job keeps running)", file=sys.stderr)
        return 3
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
