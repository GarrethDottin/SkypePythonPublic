import inspect
import traceback
import threading
import Queue
import re
import datetime

from util import logger
import permissions

func_handlers = {}
commands = {}  # Name to function
command_permissions = {}  # Command to permission
command_helps = {}

events = {}  # Name to function
event_regex = {}  # Name to regex


def add_command(args, func):
    cmd = args['name']
    if cmd is None:
        print('No name found for a command...ignoring...')
        return
    registered_text = "Registered a command with the name '%s'" % cmd
    new_command = {cmd: func}
    commands.update(new_command)
    if 'permission' in args and args['permission'] is not None:
        new_permission = {cmd: args['permission']}
        command_permissions.update(new_permission)
        registered_text += " with the permission %s" % str(new_permission.get(cmd))
    if 'help' in args and args['help'] is not None:
        new_help = {cmd: args['help']}
        command_helps.update(new_help)
        registered_text += " the help text of %s" % str(new_help.get(cmd))
    if 'aliases' in args and args['aliases'] is not None:
        aliases = args['aliases'].split(", ")
        for alias in aliases:
            commands.update({alias: func})
        registered_text += " and the aliases of %s" % str(list(aliases))
    logger.log(registered_text)
    handler = Handler(func)
    func_handlers.update({func: handler})


def register_event(args, func):
    name = args['name']
    regex = args['regex']
    if name is None or regex is None:
        print "No %s found for an event...skipping..." % 'regex' if regex is None else 'name'
        return
    registered_text = "Registered an event with the name '%s' and the regex: %s" % (name, regex)
    new_event = {name: func}
    events.update(new_event)
    new_regex = {name: re.compile(regex)}
    event_regex.update(new_regex)
    handler = Handler(func)
    func_handlers.update({func: handler})
    logger.log(registered_text)


def command(arg=None, **kwargs):
    args = {}

    def wrapper(func):
        add_command(args, func)
        return func

    args.update({"name": kwargs.get('name', None)})
    args.update({"permission": kwargs.get('permission', None)})
    args.update({"aliases": kwargs.get('aliases', None)})
    args.update({"help": kwargs.get('help', None)})
    if kwargs or not inspect.isfunction(arg):
        if arg is not None:
            args['name'] = arg
        args.update(kwargs)
        return wrapper
    else:
        return wrapper(arg)


def event(arg=None, **kwargs):
    args = {}

    def wrapper(func):
        register_event(args, func)
        return func

    args.update({"name": kwargs.get('name', None)})
    args.update({"regex": kwargs.get('regex', None)})

    if kwargs or not inspect.isfunction(arg):
        if arg is not None:
            args['name'] = arg
        args.update(kwargs)
        return wrapper
    else:
        return wrapper(arg)


def get_minute_ago():
    return datetime.datetime.now() - datetime.timedelta(minutes=1)


def dispatch(message, status):
    """

    :type message: ChatMessage
    :type status: String
    """
    if status == 'SENDING' or status == 'READ':
        return
    msg_time = message.Datetime
    if msg_time < get_minute_ago():
        return
    logger.log_message(message)
    for e in events:
        func = events[e]
        regex = event_regex[e]
        f = re.findall(regex, message.Body)
        if len(f) > 0:
            for found in f:
                handler = func_handlers[func]
                handler.add({'data': message, 'type': 'event', 'extra': {'found': found}})
            return
    if not message.Body.startswith('!'):
        return
    # Get args and command from message
    words = message.Body.split()
    cmd = words[0]
    cmd = cmd[1:]
    args = words[1:]
    # Check for valid command
    if not cmd in commands:
        message.Chat.SendMessage("Command not found!")
        return

    if cmd in command_permissions:
        permission = command_permissions[cmd]
        if not permissions.has_permission(message.Sender.Handle, permission):
            message.Chat.SendMessage("No permission to execute this command")
            return

    # Log command
    #base = u'Received command \'%s\'' % cmd
    #if len(args) > 0:
    #    base += u' with arguments: %s' % ' '.join(args)
    #logger.log(base)
    # Execute command
    func = commands[cmd]
    handler = func_handlers[func]
    handler.add({'data': message, 'type': 'command'})


def run(func, args):
    extra = args.get('extra', None)
    message = args['data']
    command_args = message.Body.split()
    command_args = command_args[1:]
    t = args['type']
    if t == 'command':
        func(message.Chat, message.Body, command_args, message.Sender)
    elif t == 'event':
        found = extra['found']
        func(message.Chat, message.Body, command_args, message.Sender, found)


class Handler(object):
    def __init__(self, func):
        self.func = func
        self.input_queue = Queue.Queue()
        self.thread = threading.Thread(name='handler-%s' % func.__name__, target=self.start)
        self.thread.start()

    def start(self):
        while True:
            args = self.input_queue.get()

            if args == StopIteration:
                break

            try:
                run(self.func, args)
            except:
                import traceback

                traceback.print_exc()

    def stop(self):
        self.input_queue.put(StopIteration)

    def add(self, message):
        self.input_queue.put(message)
