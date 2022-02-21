from pathlib import Path
from pytest import fixture, mark
from solana.keypair import Keypair
from solana.system_program import SYS_PROGRAM_ID, transfer, TransferParams
from solana.transaction import Transaction
from solana.rpc.api import Client
import asyncio
from anchorpy import (
    Context,
    Program,
    create_workspace,
    close_workspace,
)
import pytest


class KeyPairData(object):
    def __init__(self, game_kp, player1_kp, player2_kp):
        self.game_kp = game_kp
        self.player1_kp = player1_kp
        self.player2_kp = player2_kp


class PlayDataHelper(object):
    def __init__(
        self,
    ):
        self.player = None
        self.tile = None
        self.program = None
        self.key_pair_data = None
        self.game_keypair = None
        self.expected_turn = None
        self.expected_game_state = None
        self.expected_board = None


# Since our other fixtures have module scope, we need to define
# this event_loop fixture and give it module scope otherwise
# pytest-asyncio will break.


@fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@fixture(scope="module")
async def program() -> Program:
    """Create a Program instance."""
    workspace = create_workspace("/Users/alb/dev/solana-practice/tic-tac-toe")
    yield workspace["tic_tac_toe"]
    await close_workspace(workspace)


@fixture(scope="module")
async def key_pair_data(program: Program):
    player_one = program.provider.wallet.payer
    player_two = Keypair()
    game_keypair = Keypair()
    kpd = KeyPairData(game_keypair, player_one, player_two)
    await program.rpc["setup_game"](
        player_two.public_key,
        ctx=Context(
            accounts={
                "game": game_keypair.public_key,
                "player_one": player_one.public_key,
                "system_program": SYS_PROGRAM_ID,
            },
            signers=[game_keypair],
        ),
    )
    yield kpd


@mark.asyncio
async def get_game_state(program: Program, key_pair_data: KeyPairData):
    game_state = await program.account["Game"].fetch(key_pair_data.game_kp.public_key)
    return game_state


@mark.asyncio
async def play(play_data):

    await play_data.program.rpc["play"](
        play_data.tile,
        ctx=Context(
            accounts={
                "game": play_data.game_keypair.public_key,
                "player_to_move": play_data.player.public_key,
            },
            signers=[play_data.player],
        ),
    )


@mark.asyncio
async def print_players_info(program: Program, key_pair_data: KeyPairData):
    player1_pubkey = key_pair_data.player1_kp.public_key
    player2_pubkey = key_pair_data.player2_kp.public_key
    print(f"\nPlayer addresses: " f"\n{player1_pubkey}" f"\n{player2_pubkey}")

    # game_state = await get_game_state(program, key_pair_data)
    # print(game_state.current_player())

    solana_client = Client("http://localhost:8899")
    balance1 = solana_client.get_balance(player1_pubkey)
    balance2 = solana_client.get_balance(player2_pubkey)
    print(f"Player balances:\n" f"Player 1: {balance1}\nPlayer 2: {balance2}\n")


@mark.asyncio
async def play_check_assertions(play_data):
    game_state = await get_game_state(play_data.program, play_data.key_pair_data)
    assert game_state.turn == play_data.expected_turn
    print(game_state.state)
    print(play_data.expected_game_state)
    # assert game_state.state == expected_game_state
    print(play_data.expected_board)
    print(game_state.board)
    # assert expected_board == game_state.board


@mark.asyncio
async def send_lamports(program, key_pair_data):
    player1, player2 = key_pair_data.player1_kp, key_pair_data.player2_kp
    # Send lamports to player2
    transaction = Transaction().add(
        transfer(
            TransferParams(
                from_pubkey=player1.public_key,
                to_pubkey=player2.public_key,
                lamports=100_000_000_000_000_000,
            )
        )
    )
    solana_client = Client("http://localhost:8899")
    response = solana_client.send_transaction(transaction, player1)
    # time.sleep(40)


"""----------------------------------------------------------------
Tests
----------------------------------------------------------------"""


@mark.asyncio
async def test_setup_game(program: Program, key_pair_data: KeyPairData):
    game_state = await get_game_state(program, key_pair_data)
    assert game_state.turn == 1
    assert game_state.players == [
        key_pair_data.player1_kp.public_key,
        key_pair_data.player2_kp.public_key,
    ]
    # assert game_state.state == GameState.Active()
    print(game_state.state)
    assert game_state.board == [
        [None, None, None],
        [None, None, None],
        [None, None, None],
    ]


@mark.asyncio
async def test_not_players_turn(
    program: Program,
    key_pair_data: KeyPairData,
):
    player2 = key_pair_data.player2_kp
    with pytest.raises(Exception):
        await play(program, key_pair_data, player2, tile=program.type["Tile"](x=0, y=0))


@mark.asyncio
async def test_tile_out_of_bounds(
    program: Program,
    key_pair_data: KeyPairData,
):
    player1 = key_pair_data.player1_kp
    with pytest.raises(Exception):
        player1 = key_pair_data.player1_kp
        await play(
            program, key_pair_data, player1, tile=program.type["Tile"](x=5, y=10)
        )


@mark.asyncio
async def test_tile_already_set(
    program: Program,
    key_pair_data: KeyPairData,
):
    play_data = PlayDataHelper()
    play_data.program = program
    play_data.game_keypair = key_pair_data.game_kp
    play_data.player = key_pair_data.player1_kp
    play_data.tile = program.type["Tile"](x=1, y=1)
    await play(play_data)
    play_data.tile = program.type["Tile"](x=1, y=1)
    play_data.player = key_pair_data.player2_kp
    # await play(program, key_pair_data, player2, tile=program.type["Tile"](x=1, y=1))
    with pytest.raises(Exception):
        await play(play_data)


@mark.asyncio
async def test_player1_wins(
    program: Program,
    key_pair_data: KeyPairData,
):

    X = program.type["Sign"].X()
    O = program.type["Sign"].O()
    player1 = key_pair_data.player1_kp
    player2 = key_pair_data.player2_kp
    game_keypair = key_pair_data.game_kp

    # Reset game
    await program.rpc["reset_game"](
        ctx=Context(
            accounts={
                "game": game_keypair.public_key,
                "player_one": player1.public_key,
                "system_program": SYS_PROGRAM_ID,
            },
            signers=[game_keypair],
        ),
    )

    play_data = PlayDataHelper()

    # First turn
    print("\nTurn 1")
    play_data.tile = program.type["Tile"](x=0, y=0)
    play_data.player = player1
    play_data.program = program
    play_data.key_pair_data = key_pair_data
    play_data.game_keypair = key_pair_data.game_kp
    play_data.expected_turn = 2
    play_data.expected_game_state = program.type["GameState"].Active()
    play_data.expected_board = [
        ([X, None, None]),
        [None, None, None],
        [None, None, None],
    ]
    await play(play_data)
    await play_check_assertions(play_data)

    print("Turn 2")
    play_data.tile = program.type["Tile"](x=1, y=1)
    play_data.player = player2
    play_data.expected_turn = 3
    play_data.expected_game_state = program.type["GameState"].Active()
    play_data.expected_board = [([X, None, None]), [None, O, None], [None, None, None]]
    await play(play_data)
    await play_check_assertions(play_data)

    # Make player2 play till winning
    print("Turn 3")
    play_data.tile = program.type["Tile"](x=1, y=0)
    play_data.player = player1
    play_data.expected_turn = 4
    play_data.expected_game_state = program.type["GameState"].Active()
    play_data.expected_board = [([X, X, None]), [None, O, None], [None, None, None]]
    await play(play_data)
    await play_check_assertions(play_data)

    # Make player2 play till winning
    print("Turn 4")
    play_data.tile = program.type["Tile"](x=1, y=2)
    play_data.player = player2
    play_data.expected_turn = 5
    play_data.expected_game_state = program.type["GameState"].Active()
    play_data.expected_board = [([X, X, None]), [None, O, None], [None, O, None]]
    await play(play_data)
    await play_check_assertions(play_data)

    # Make player2 play till winning
    print("Turn 5")
    play_data.tile = program.type["Tile"](x=2, y=0)
    play_data.player = player1
    play_data.expected_turn = 5  # Because the game is won, the turn does not inrease
    play_data.expected_game_state = program.type["GameState"].Won(winner=player1.public_key)
    play_data.expected_board = [([X, X, X]), [None, O, None], [None, O, None]]
    await play(play_data)
    await play_check_assertions(play_data)
