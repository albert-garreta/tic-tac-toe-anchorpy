from pathlib import Path
from pytest import fixture, mark
from solana.keypair import Keypair
from solana.system_program import SYS_PROGRAM_ID
from solana.rpc.api import Client
import solana
import asyncio
from anchorpy import (
    Context,
    Program,
    create_workspace,
    close_workspace,
)
import pytest


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


class KeyPairData(object):
    def __init__(self, game_kp, player1_kp, player2_kp):
        self.game_kp = game_kp
        self.player1_kp = player1_kp
        self.player2_kp = player2_kp


@fixture(scope="module")
async def key_pair_data(program: Program) -> KeyPairData:
    """Generate a keypair and initialize it."""
    player_one = program.provider.wallet
    player_two = Keypair()
    game_keypair = Keypair()
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
    kpd = KeyPairData(game_keypair, player_one, player_two)
    yield kpd


@mark.asyncio
async def get_game_state(program: Program, key_pair_data: KeyPairData):
    game_state = await program.account["Game"].fetch(key_pair_data.game_kp.public_key)
    return game_state


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
async def play(program: Program, key_pair_data: KeyPairData, player, tile):
    await program.rpc["play"](
        tile,
        ctx=Context(
            accounts={
                "game": key_pair_data.game_kp.public_key,
                "player_to_move": player.public_key,
            },
            # signers=[player.public_key],
        ),
    )
    game_state = await get_game_state(program, key_pair_data)


def print_players_info():
    player1_pubkey = key_pair_data.player1_kp.public_key
    player2_pubkey = key_pair_data.player2_kp.public_key
    print(f"\nPlayer addresses: " f"\n{player1_pubkey}" f"\n{player2_pubkey}")
    print("Transfering some lamports from player 1 to player 2...")
    instruction = solana.system_program.transfer(
        solana.system_program.TransferParams(
            player1_pubkey, player2_pubkey, 100_000_000_000_000_000
        )
    )
    print(instruction)
    solana_client = Client("http://localhost:8899")
    balance1 = solana_client.get_balance(player1_pubkey)
    balance2 = solana_client.get_balance(player2_pubkey)
    print(f"Player balances:\n" f"Player 1: {balance1}\nPlayer 2: {balance2}\n")



@mark.asyncio
async def play_check_assertions(
    program: Program,
    key_pair_data: KeyPairData,
    expected_turn,
    expected_game_state,
    expected_board
):
    game_state = await get_game_state(program, key_pair_data)
    assert game_state.turn == expected_turn
    print(game_state.state)
    print(expected_game_state)
    # assert game_state.state == expected_game_state
    print(expected_board)
    print(game_state.board)
    # assert expected_board == game_state.board


@mark.aasyncio
async def test_not_players_turn(
    program: Program,
    key_pair_data: KeyPairData,
):
    with pytest.raises(Exception):
        player2 = key_pair_data.player2_kp
        await play(program, key_pair_data, player2, tile=program.type["Tile"](x=0, y=0))


@mark.aasyncio
async def test_tile_out_of_bounds(
    program: Program,
    key_pair_data: KeyPairData,
):
    with pytest.raises(Exception):
        player1 = key_pair_data.player1_kp
        await play(
            program, key_pair_data, player1, tile=program.type["Tile"](x=5, y=10)
        )


@mark.aasyncio
async def test_tile_already_set(
    program: Program,
    key_pair_data: KeyPairData,
):
    with pytest.raises(Exception):
        player1 = key_pair_data.player1_kp
        await play(program, key_pair_data, player1, tile=program.type["Tile"](x=1, y=1))
        player2 = key_pair_data.player2_kp
        await play(program, key_pair_data, player2, tile=program.type["Tile"](x=1, y=1))


@mark.asyncio
async def test_player1_wins(
    program: Program,
    key_pair_data: KeyPairData,
):
    X = program.type["Sign"].X()
    O = program.type["Sign"].O()

    # First turn
    print("Turn 1")
    player = key_pair_data.player1_kp
    tile = program.type["Tile"](x=0, y=0)
    expected_turn = 2
    expected_game_state = program.type["GameState"].Active()
    expected_board = [([X, None, None]), [None, None, None], [None, None, None]]
    await play(
        program,
        key_pair_data,
        player,
        tile,
    )
    await play_check_assertions(
        expected_turn,
        expected_game_state,
        expected_board=[[X, None, None], [None, None, None], [None, None, None]],
    )

    print("Turn 2")
    tile = program.type["Tile"](x=1, y=0)
    expected_turn = 3
    expected_game_state = program.type["GameState"].Active()
    expected_tyle_sign = X
    expected_board = [([X, X, None]), [None, None, None], [None, None, None]]
    game_state = await get_game_state(program, key_pair_data)

    print(game_state.turn)
    await play(
        program,
        key_pair_data,
        player,
        tile,
        expected_turn,
        expected_game_state,
        expected_tyle_sign,
        expected_board,
    )

    # Make player2 play till winning
    print("Turn 3")
    tile = program.type["Tile"](x=2, y=0)
    expected_turn = 4
    expected_game_state = program.type["GameState"].Won({"winner": player})
    expected_tyle_sign = X
    expected_board = [([X, X, X]), [None, None, None], [None, None, None]]
    await play(
        program,
        key_pair_data,
        player,
        tile,
        expected_turn,
        expected_game_state,
        expected_tyle_sign,
        expected_board,
    )
