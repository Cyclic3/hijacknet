# SPDX-FileCopyrightText: 2023-present Cyclic3 <cyclic3.git@gmail.com>
#
# SPDX-License-Identifier: MIT
import asyncio
import json
import warnings
from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional, Awaitable, Tuple, Iterator, Union, ValuesView, List

# https://github.com/python/typing/issues/182#issuecomment-1259412066
Jsonable = Union[dict[str, 'Jsonable'], list['Jsonable'], str, int, float, bool, None]

default_port = 42042

class HijackClient:
  _metadata: Dict[str, Jsonable]
  _starting_metadata: Optional[Dict[str, Jsonable]]
  _reader: asyncio.StreamReader
  _writer: asyncio.StreamWriter

  @property
  def name(self) -> str:
    return self._metadata["name"]

  @property
  def lobby(self) -> str:
    return self._metadata["lobby"]

  @property
  def others(self) -> List[str]:
    return self._starting_metadata["others"]

  async def _send_message_raw(self, plod: str) -> None:
    if '\n' in plod:
      raise Exception("Message payload contained newline")
    self._writer.write((plod + "\n").encode())
    await self._writer.drain()
  async def _read_message_raw(self) -> Optional[str]:
    res = (await self._reader.readline()).decode()
    if not res.endswith('\n') or len(res) == 0:
      return None
    else:
      return res

  async def send_message(self, msg: Jsonable) -> None:
    """
    Sends a message to the remote
    :param msg: The Jsonable message to send
    """
    await self._send_message_raw(json.dumps(msg, separators=(',', ':')))

  async def read_message(self) -> Optional[Jsonable]:
    """
    Tries to receive a message from the remote
    :return: None if the connection was closed, the Jsonable message otherwise
    """
    msg_raw = await self._read_message_raw()
    if msg_raw is None:
      return None
    else:
      return json.loads(msg_raw)

  async def send_starting_metadata(self, others: List[str]) -> None:
    """
    Sets the value of starting_metadata, and sends the value across to the remote. You should never have to call this manually.
    :param others: A list of other players in the lobby
    """
    if self._starting_metadata is not None:
      raise Exception("Tried to send starting metadata twice")
    self._starting_metadata = {"state": "starting", "others": others}
    await self.send_message(self._starting_metadata)

  async def close(self) -> None:
    """
    Disconnects from the remote. You should not call this for server-provided clients,
    and for manually constructed clients, you should be using "async with".
    """
    self._writer.close()
    await self._writer.wait_closed()
    self._reader.feed_eof()

  async def __aenter__(self) -> "HijackClient":
    return self

  async def __aexit__(self, exc_type, exc_val, exc_tb):
    """A helper function so that we can use "with" for this class"""
    await self.close()

  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, do_not_call_this_function: int):
    """
    Creates an uninitialised remote. DO NOT CALL THIS MANUALLY: use connect() or HijackServer instead
    :param reader: A read stream for the remote
    :param writer: A write stream for the remote
    """
    # warnings module is not thread safe
    if do_not_call_this_function != 42:
      raise Exception("Do not call HijackClient() directly! Use connect() or HijackServer instead")

    self._reader = reader
    self._writer = writer
    self._starting_metadata = None
  @staticmethod
  async def finish_connect_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> "HijackClient":
    """
    Handles the IO for connecting as a server. You should never have to call this manually.
    :param reader: A read stream for the remote
    :param writer: A write stream for the remote
    :return: A HijackRemote object to talk to the remote
    """
    this = HijackClient(reader, writer, do_not_call_this_function=42)
    this._metadata = await this.read_message()
    return this

  @staticmethod
  async def _finish_connect_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, metadata: Jsonable) -> "HijackClient":
    """
    Handles the IO for connecting as a client. You should never have to call this manually.
    :param reader: A read stream for the remote
    :param writer: A write stream for the remote
    :param metadata: The metadata to send to the remote
    :return: A tuple, containing the (now connected) remote, and the start message automatically sent by the server
    """
    with warnings.catch_warnings():
      this = HijackClient(reader, writer, do_not_call_this_function=42)
    this._metadata = metadata
    await this.send_message(metadata)
    # Wait for metadata
    this._starting_metadata = await this.read_message()
    return this

  @classmethod
  async def connect(cls, name: str, lobby: str, host: str = "localhost", port: int = default_port) -> "HijackClient":
    """
    Connects to a remote, returning once the lobby has started
    :param host: The hostname or IP address of the remote
    :param port: The port of the remote
    :param name: The name this client should provide
    :param lobby: The lobby to join/create
    :return: A tuple, containing the (now connected) remote, and the start message automatically sent by the server
    """
    reader, writer = await asyncio.open_connection(host, port)
    return await cls._finish_connect_client(reader, writer, metadata={
      "name": name,
      "lobby": lobby
    })

class HijackLobby:
  lobby_id: str
  _members: Dict[str, HijackClient]

  def add_remote(self, remote: HijackClient) -> None:
    """
    Adds a remote to the lobby. You should never have to call this manually.
    :param remote: The remote to add
    """
    if remote.name in self._members:
      raise Exception("Duplicate name in lobby")
    self._members[remote.name] = remote

  @property
  def members(self) -> ValuesView[HijackClient]:
    return self._members.values()

  def __getitem__(self, name: str) -> HijackClient:
    return self._members[name]

  def __iter__(self) -> Iterator[HijackClient]:
    return iter(self._members.values())

  def get(self, name: str) -> Optional[HijackClient]:
    return self._members.get(name)

  def __contains__(self, item: Union[str, HijackClient]):
    if type(item) == HijackClient:
      excluded = item.name
    return item in self._members

  def get_other_members(self, excluded: Union[str, HijackClient]) -> Iterator[HijackClient]:
    """
    Convenience function for iterating over "other" members
    :param excluded: The name of the remote to be excluded, or the HijackRemote object itself
    :return: A sequence of remotes that are *not* the excluded member
    """
    if type(excluded) == HijackClient:
      excluded = excluded.name
    return filter(lambda i: i.name != excluded, self._members.values())

  def __init__(self, lobby_id: str):
    self.lobby_id = lobby_id
    self._members = dict()

class HijackServerHandler(ABC):
  @abstractmethod
  def check_lobby_complete(self, lobby: HijackLobby) -> bool:
    """
    Checks to see if the given lobby is ready to start
    :param lobby: The lobby to check
    :return: True if the lobby should start, False otherwise
    """
    pass

  @abstractmethod
  async def run_lobby(self, lobby: HijackLobby) -> None:
    """
    async function that runs the main game logic for the lobby
    :param lobby: The complete lobby
    """
    pass

class HijackServer:
  _sock = None
  async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    # Handle the server-side connection
    remote = await HijackClient.finish_connect_server(reader, writer)
    # Add it to the lobby, creating a new one if it doesn't exist
    lobby = self._building_lobbies.setdefault(remote.lobby, HijackLobby(remote.lobby))
    lobby.add_remote(remote)

    # If the lobby isn't ready yet, we've done everything we need to
    if not self._handler.check_lobby_complete(lobby):
      return

    # Otherwise, start the lobby!
    #
    # First, we remote the lobby from the list of unready ones, so that we can't have reentrancy that overfills lobbies
    del self._building_lobbies[remote.lobby]
    # Then we tell all the remotes that they can start in parallel
    await asyncio.gather(*[remote.send_starting_metadata(list(i.name for i in lobby.get_other_members(remote)))
                           for remote in lobby.members])

    # try:
    # Then we actually dispatch the handler
    await self._handler.run_lobby(lobby)
    # finally:
    for i in lobby:
      await i.close()

  async def run(self):
    if self._sock is not None:
      raise Exception("Server is already running")
    self._sock = await asyncio.start_server(self._handle_client, "0.0.0.0", self._port)
    await self._sock.start_serving()
    await self._sock.wait_closed()
    # await self._sock.serve_forever()

  async def stop(self):
    self._sock.close()
    await self._sock.wait_closed()

  def __init__(self, handler: HijackServerHandler, port: int = default_port):
    self._handler = handler
    self._port = port
    self._building_lobbies = dict()