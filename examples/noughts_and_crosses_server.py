import asyncio
import itertools
from typing import Tuple, List

import hijacknet
import random

class NoughtsAndCrossesServerHandler(hijacknet.HijackServerHandler):
  def check_lobby_complete(self, lobby: hijacknet.HijackLobby) -> bool:
    print(f"{len(lobby.members)} in {lobby.lobby_id}")
    return len(lobby.members) == 2

  async def run_lobby(self, lobby: hijacknet.HijackLobby) -> None:
    members: List[hijacknet.HijackClient] = list(lobby.members)
    random.shuffle(members)
    players = [("X", members[0]), ("O", members[1])]

    # Tell each side who's who
    await asyncio.gather(*[client.send_message(side) for side, client in players])

    # Initialise the board
    board = [["_" for x in range(3)] for y in range(3)]

    print(f"lobby {lobby.lobby_id} ready!")

    async def call_game(maybe_winner_no: int, is_draw: bool) -> None:
      mayber_loser_no = (player_no + 1) % 2
      if is_draw:
        await asyncio.gather(members[maybe_winner_no].send_message(0.5),
                             members[mayber_loser_no].send_message(0.5))
      else:
        await asyncio.gather(members[maybe_winner_no].send_message(1.),
                             members[mayber_loser_no].send_message(0.))


    for player_no in itertools.cycle(range(2)):
      side, client = players[player_no]
      opponent_player_no = (player_no + 1) % 2

      # Tell the client it's their turn
      await client.send_message(board)
      coords = await client.read_message()
      # Autolose on invalid move
      if board[coords[0]][coords[1]] != "_":
        await call_game(opponent_player_no, False)
        return
      board[coords[0]][coords[1]] = side
      # We only need to check the side that just played
      for step in range(3):
        if all([i == side for i in board[step]]) or \
           all([i[step] == side for i in board]) or \
           all([board[i][2-i] == side for i in range(2)]) or \
           all([board[2-i][i] == side for i in range(2)]):
          await call_game(player_no, False)
          return

      # If the board is full and no-one has won, it's a draw
      if all(i != "_" for j in board for i in j):
        await call_game(player_no, True)
        return

async def main():
  server = hijacknet.HijackServer(NoughtsAndCrossesServerHandler())
  await server.run()

asyncio.run(main())