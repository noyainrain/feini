"""TODO."""

import asyncio
from asyncio import Queue, wait_for
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from irc.client import Event
from irc.client_aio import AioConnection, AioReactor
from irc.connection import AioFactory

@dataclass
class Message:
    """TODO."""

    chat: str
    text: str

class Messenger:
    """TODO."""

    async def inbox(self) -> AsyncIterator[Message]:
        """TODO."""
        raise NotImplementedError()
        yield

    async def send(self, message: Message) -> None:
        """TODO."""
        raise NotImplementedError()

class IRC(Messenger):
    """TODO."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._inbox: Queue[Message] = Queue()
        self._connection = AioReactor().server()
        self._connection.add_global_handler('privmsg', self._on_private_message)
        self._connection.add_global_handler('pubmsg', self._on_public_message)
        self._connection.add_global_handler('invite', self._on_invite)
        self._connection.add_global_handler('whisper', self._on_whisper) # Twitch
        self._connection.add_global_handler('all_events', self._on_event)

    @staticmethod
    def _get_nick(prefix: str) -> str:
        return prefix.split('!', 1)[0]

    async def connect(self, chats: Iterable[str]) -> None:
        """TODO."""
        # We should probably handle all client commands like requests, i.e. wait and check for all
        # possible replies
        signal = asyncio.Event()
        def on_welcome(connection: AioConnection, event: Event) -> None:
            signal.set()
        self._connection.add_global_handler('welcome', on_welcome)
        try:
            components = urlsplit(self.url)
            assert components.hostname
            assert components.username
            tls = (components.scheme == 'ircs')
            default_port = 6697 if tls else 6667
            await self._connection.connect(
                components.hostname, components.port or default_port, components.username,
                components.password, username='feini', connect_factory=AioFactory(ssl=tls))
            self._connection.cap('REQ', 'twitch.tv/commands') # Twitch (whisper)
            await wait_for(signal.wait(), 20)
        finally:
            self._connection.remove_global_handler('welcome', on_welcome)

        chats = [f'#{components.username}', *chats] # Twitch (home)
        self._connection.join(','.join(chats))

    async def close(self) -> None:
        """TODO."""
        self._connection.disconnect()

    async def inbox(self) -> AsyncIterator[Message]:
        while True:
            yield await self._inbox.get()
            self._inbox.task_done()

    async def send(self, message: Message) -> None:
        self._connection.privmsg(message.chat, message.text)

    def _join(self, channel: str) -> None:
        self._connection.join(channel)
        self._inbox.put_nowait(Message(channel, '/invite'))

    def _on_private_message(self, connection: AioConnection, event: Event) -> None:
        self._inbox.put_nowait(Message(self._get_nick(event.source), event.arguments[0]))

    def _on_public_message(self, connection: AioConnection, event: Event) -> None:
        # Twitch (home)
        if event.target == f'#{connection.nickname}':
            nick = self._get_nick(event.source)
            self._join(f'#{nick}')
            self._connection.privmsg(event.target, f'@{nick} I have just joined your channel.')
            return

        text = event.arguments[0]

        # Twitch
        # global emotes not super helpful
        #   different animals dogs cats
        #   food: nomnom, cheese, doritos, sugar, pasta, cheers
        #   party hat
        #   rugby ball, football
        #   holiday tree
        # OQ use Twitch emotes tag in message?
        emotes = {'Getcamped': '⛺'}
        for emote, emoji in emotes.items():
            text = text.replace(emote, emoji)

        self._inbox.put_nowait(Message(event.target, text))

    def _on_invite(self, connection: AioConnection, event: Event) -> None:
        self._join(event.arguments[0])

    # Twitch (whisper)
    def _on_whisper(self, connection: AioConnection, event: Event) -> None:
        nick = self._get_nick(event.source)
        self._join(f'#{nick}')
        self._connection.privmsg(f'#{connection.nickname}',
                                 f'/w {nick} I have just joined your channel.')

    def _on_event(self, connection: AioConnection, event: Event) -> None:
        if event.type != 'all_raw_messages':
            print(event)

# OQ mixed with IRC, subclass or copy?
class Twitch(IRC):
    """TODO."""

    def __init__(self, user: str, key: str) -> None:
        super().__init__(f'ircs://{user}:oauth:{key}@irc.chat.twitch.tv')
        # Make _connection, _get_nick() and _join() available to subclass
        self._connection.add_global_handler('pubmsg', self._on_home_message, -1)

    async def connect(self, chats: Iterable[str]) -> None:
        await super().connect(chats)
        self._connection.join(f'#{self._connection.nickname}')

    def _on_home_message(self, connection: AioConnection, event: Event) -> object:
        if event.target == f'#{connection.nickname}':
            nick = self._get_nick(event.source)
            self._join(f'#{nick}')
            self._connection.privmsg(event.target, f'@{nick} I have just joined your channel.')
            return 'NO MORE'
        return None

# ---

# Join on ...
# Whisper: no way to reply & no URL to feini_bot :/
#          (^ Your settings prevent you from sending this whisper.)
#          maybe not so bad if there is no URL, e.g. invite feini to group in Telegram cannot
#          have link also
# #feini_bot: can reply + unique URL
# OQ could also use other signal, like follow

# ---

# We want to track state change, like:
# Connected to IRC
# Failed to connect to IRC (...)
# Disconnected from IRC (...)

# Inspiration?
# socket = connect()
# socket.read() # success or something like DisconnectedError
# socket.write(data) # success or something like DisconnectedError
# socket.close()

# connection only exists while connected by def
# client might be more than connection, e.g. has a connected state

# ---

#irc = IRC()
#
## a...
#while True:
#    try:
#        await irc.connect()
#        log('Connected')
#    except:
#        log('Failed to connect')
#        sleep(2)
#    else:
#        await irc.disconnected
#        log('Disconnected')
#
## b...
#async def connect():
#    try:
#        await irc.connect()
#        log('Connected')
#    except:
#        log('Failed to connect')
#        sleep(2)
#        await connect()
#async def disco():
#    log('Disconnected')
#    await connect()
#irc.on_disconnect(disco)
#await connect()
#
## c...
## maybe instead of own thread, build reconnect in read loop (because we read all the time, we only
## send sometimes)
