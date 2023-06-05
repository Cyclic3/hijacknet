import asyncio

import hijacknet

server: hijacknet.HijackServer

class SimpleServerHandler(hijacknet.HijackServerHandler):
  async def run_lobby_inner(self, lobby: hijacknet.HijackLobby, client: hijacknet.HijackClient):
    while (message := await client.read_message()) is not None:
      await asyncio.gather(*[i.send_message({"sender": client.name, "body": message})
                             for i in lobby.get_other_members(client)])
    # Stop the whole server after both clients disconnect
    await server.stop()

  def check_lobby_complete(self, lobby: hijacknet.HijackLobby) -> bool:
    print(len(lobby.members))
    return len(lobby.members) >= 2

  async def run_lobby(self, lobby: hijacknet.HijackLobby) -> None:
    await asyncio.gather(*[self.run_lobby_inner(lobby, i) for i in lobby])
    print("done")

async def client(name: str):
  async with await hijacknet.HijackClient.connect(name, "test") as client:
    await client.send_message({"msg": "hi", "my_name": name, "your_names": client.others})
    print(await client.read_message())

async def main():
  global server
  server = hijacknet.HijackServer(SimpleServerHandler())
  await asyncio.gather(server.run(), client("alice"), client("bob"))

asyncio.run(main())