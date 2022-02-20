from pathlib import Path
from pytest import fixture, mark
from solana.keypair import Keypair
from solana.system_program import SYS_PROGRAM_ID
import asyncio
from anchorpy import (
    Context,
    Program,
    create_workspace,
    close_workspace,
)


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
async def play(
    program: Program,
    key_pair_data: KeyPairData,
    player,
    tile,
    expected_turn,
    expected_game_state,
    expected_tyle_sign,
):
    await program.rpc["play"](
        tile,
        ctx=Context(
            accounts={
                "game": key_pair_data.game_kp.public_key,
                "player_to_move": player.public_key,
            },
            #signers=[player.public_key],
        )
    )
    game_state = await get_game_state(program, key_pair_data)
    assert game_state.turn == expected_turn
    print(game_state.state)
    print(expected_game_state)
    #assert game_state.state == expected_game_state
    print(game_state.board[tile.x][tile.y], expected_tyle_sign)
    #assert game_state.board[tile.x][tile.y] == expected_tyle_sign

@mark.asyncio
async def test_play(
    program: Program,
    key_pair_data: KeyPairData,
):
    player = key_pair_data.player1_kp
    tile = program.type["Tile"](x=0, y=0)
    expected_turn = 2
    expected_game_state = program.type["GameState"].Active() 
    X = program.type["Sign"].X()
    expected_tyle_sign = X # [([X, None, None]), [None, None, None], [None, None, None]]
    await play(
        program,
        key_pair_data,
        player,
        tile,
        expected_turn,
        expected_game_state,
        expected_tyle_sign,
    )