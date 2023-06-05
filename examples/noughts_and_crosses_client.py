import asyncio

import hijacknet
async def main():
  async with await hijacknet.HijackClient.connect(input("name: "), input("lobby: ")) as client:
    side = await client.read_message()
    print(f"Playing as {side}")

    while type(message := await client.read_message()) == list:
      print(message)
      print("\n".join(" ".join(i) for i in message))
      x = int(input("x: "))
      y = int(input("y: "))
      await client.send_message([y, x])
    print(message)
asyncio.run(main())
