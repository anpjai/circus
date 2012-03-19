# -*- coding: utf-8 -

import getopt
import sys
import traceback


from circus.client import CircusClient
from circus.consumer import CircusConsumer
from circus.commands import get_commands
from circus.exc import CallError, ArgumentError


globalopts = [
    ('', 'endpoint', "tcp://127.0.0.1:5555", "connection endpointt"),
    ('', 'timeout', 5, "connection timeout"),
    ('h', 'help', None, "display help and exit"),
    ('v', 'version', None, "display version and exit")
]


def _get_switch_str(opt):
    """
    Output just the '-r, --rev [VAL]' part of the option string.
    """
    if opt[2] is None or opt[2] is True or opt[2] is False:
        default = ""
    else:
        default = "[VAL]"
    if opt[0]:
        # has a short and long option
        return "-%s, --%s %s" % (opt[0], opt[1], default)
    else:
        # only has a long option
        return "--%s %s" % (opt[1], default)


class ControllerApp(object):

    def __init__(self):
        self.commands = get_commands()

    def run(self, args):
        try:
            sys.exit(self.dispatch(args))
        except getopt.GetoptError as e:
            print("Error: %s\n" % str(e))
            self.display_help()
            sys.exit(2)
        except CallError as e:
            sys.stderr.write("%s\n" % str(e))
            sys.exit(1)
        except ArgumentError as e:
            sys.stderr.write("%s\n" % str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(1)
        except Exception, e:
            sys.stderr.write(traceback.format_exc())
            sys.exit(1)

    def dispatch(self, args):
        cmd, globalopts, opts, args = self._parse(args)

        if globalopts['help'] or cmd == "help":
            del globalopts["help"]
            return self.display_help(*args, **globalopts)
        elif globalopts['version'] or cmd == "version":
            return self.display_version()

        else:
            cmd = self.commands[cmd]

        if cmd.msg_type == "pub":
            default_endpoint = "tcp://127.0.0.1:5556"
        else:
            default_endpoint = "tcp://127.0.0.1:5555"
        endpoint = globalopts.get('endpoint', default_endpoint)
        timeout = globalopts.get("timeout", 5.0)
        msg = cmd.message(*args, **opts)
        return getattr(self, "handle_%s" % cmd.msg_type)(msg, endpoint,
                timeout)

    def display_help(self, *args, **opts):
        if opts.get('version', False):
            self.display_version(*args, **opts)

        if len(args) >= 1:
            print("help on %s [TODO]" % args[0])
            return 0

        print("usage: circusctl [--version] [--endpoint=<endpoint>]")
        print("                 [--timeout=<timeout>] [--help]")
        print("                 <command> [<args>]")
        print("")
        print("Commands:")
        commands = sorted([name for name in self.commands] + ["help"])

        max_len = len(max(commands, key=len))
        for name in commands:
            if name == "help":
                desc = "Get help on a command"
                print("\t%-*s\t%s" % (max_len, name, desc))
            else:
                cmd = self.commands[name]
                # Command name is max_len characters.
                # Used by the %-*s formatting code
                print("\t%-*s\t%s" % (max_len, name, cmd.desc))

        return 0

    def display_version(self, *args, **opts):
        from circus import __version__

        print("Circus (version %s)" % __version__)
        print("Licensed under the Apache License, Version 2.0.")
        print("")
        return 0

    def handle_sub(self, topics, endpoint, timeout):
        consumer = CircusConsumer(topics, endpoint=endpoint)
        for topic, msg in consumer:
            print("%s: %s" % (topic, msg))
        return 0

    def handle_dealer(self, msg, endpoint, timeout):
        client = CircusClient(endpoint=endpoint, timeout=timeout)
        try:
            print(client.call(msg))
        except CallError as e:

            sys.stderr.write(str(e))
            return 1
        finally:
            client.stop()
        return 0

    def _parse(self, args):
        options = {}
        cmdoptions = {}
        args = self._parseopts(args, globalopts, options)

        if args:
            cmd, args = args[0], args[1:]
            cmd = cmd.lower()

            if cmd in self.commands:
                cmdopts = self.commands[cmd].options
            else:
                cmdopts = []
        else:
            cmd = "help"
            cmdopts = []

        for opt in globalopts:
            cmdopts.append((opt[0], opt[1], options[opt[1]], opt[3]))

        args = self._parseopts(args, cmdopts, cmdoptions)

        for opt, val in cmdoptions.items():
            if opt in options:
                options[opt] = val
                del cmdoptions[opt]

        return cmd, options, cmdoptions, args

    def _parseopts(self, args, options, state):
        namelist = []
        shortlist = ''
        argmap = {}
        defmap = {}

        for short, name, default, comment in options:
            oname = name
            name = name.replace('-', '_')
            argmap['-' + short] = argmap['--' + oname] = name
            defmap[name] = default

            if isinstance(default, list):
                state[name] = default[:]
            else:
                state[name] = default

            if not (default is None or default is True or default is False):
                if short:
                    short += ':'
                if oname:
                    oname += '='
            if short:
                shortlist += short
            if name:
                namelist.append(oname)

        opts, args = getopt.getopt(args, shortlist, namelist)
        for opt, val in opts:
            name = argmap[opt]
            t = type(defmap[name])
            if t is type(1):
                state[name] = int(val)
            elif t is type(''):
                state[name] = val
            elif t is type([]):
                state[name].append(val)
            elif t is type(None) or t is type(False):
                state[name] = True

        return args


def main():
    controller = ControllerApp()
    controller.run(sys.argv[1:])

if __name__ == '__main__':
    main()
