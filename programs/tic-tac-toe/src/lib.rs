use anchor_lang::prelude::*;
use num_derive::*; // see the Sign documentation below
use num_traits::*;

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

#[program]
pub mod tic_tac_toe {
    use super::*;
    /*
    Why didn't we just add player_two as an account in the accounts struct?
    There are two reasons for this. First, adding it there requires a
    little more space in the transaction that saves whether the account
    is writable and whether it's a signer. But we care about neither of
    that. We just want the address. This brings us to the second and more
    important reason: Simultaneous network transactions can affect each
    other if they share the same accounts. For example, if we add player_two
    to the accounts struct, during our transaction, no other transaction
    can edit player_two's account. Therefore, we block all other transactions
    that want to edit player_two's account, even though we neither want to
    read from nor write to the account. We just care about its address!
     */
    pub fn setup_game(ctx: Context<SetupGame>, player_two: Pubkey) -> ProgramResult {
        let game: &mut Account<Game> = &mut ctx.accounts.game;
        game.turn = 1;
        // TODO: Why not `*ctx.accounts.player_one.key` ?
        game.players = [ctx.accounts.player_one.key(), player_two];
        game.state = GameState::Active;
        Ok(())
    }


    pub fn play(ctx: Context<Play>, tile: Tile) -> ProgramResult {
        let game = &mut ctx.accounts.game; 
        require!(
            game.current_player() == ctx.accounts.player_to_move.key(),
            TicTacToeError::NotPlayersTurn
        );
        game.play(&tile)
    }

}

// The Accounts struct is where you define which accounts your
// instruction expects and which constraints these accounts
// should adhere to. You do this via two constructs:
// Types and constraints.
#[derive(Accounts)]
pub struct SetupGame<'info> {
    // init immediately shouts at us and tells us to add a payer.
    // Why do we need it? Because init creates rent-exempt accounts
    // and someone has to pay for that
    
    // See comments above the declaration of MAXIMUM_SIZE
    #[account(init, payer=player_one, space = Game::MAXIMUM_SIZE +8)]
    pub game: Account<'info, Game>, // account where teh game is stored
    #[account(mut)]
    pub player_one: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Play<'info> {
    #[account(mut)]
    pub game: Account<'info, Game>,
    #[account(mut)]
    pub player_to_move: Signer<'info>,
}

// Each game has players, turns, a board, and a game state.
// This game state describes whether the game is active, tied,
// or one of the two players won. We can save all this data in
// an account. This means that each new game will have its own
// account
#[account]
// **ME: The following is needed when creating SetupGame**
// Every account is created with a fixed amount of space.
// init can try to infer how much space an account needs if
// it derives Default
#[derive(Default)]
pub struct Game {
    players: [Pubkey; 2],          // 32+32 bytes
    turn: u8,                      // 1 bytes
    board: [[Option<Sign>; 3]; 3], // 9*(1+1) = 18 bytes
    state: GameState,              // 32 + 1 bytes  -- because if the state is Won, then it stores the winner pubkey (32 bytes)
}
impl Game {
    // Max byte size Game can achieve.
    // Alternatively, the derived Default trait will try to infer 
    // (via borsch serialization) the 
    // max byte size. This will default to 64 + 1 + 9 +1 bytes 
    // The GameState is given 1 byte, because its default implementation
    // (given below) sets it to ::Active (one byte)
    // The board is defaulted to a 3x3 array of None, which requires 
    // only 9 bytes
    const MAXIMUM_SIZE: usize = 116; 

    pub fn is_active(&self) -> bool {
        self.state == GameState::Active
    }

    pub fn current_player_index(&self) -> usize {
        ((self.turn % 2) - 1) as usize
    }

    pub fn current_player(&self) -> Pubkey {
        self.players[self.current_player_index()]
    }

    pub fn play(&mut self, tile: &Tile) -> ProgramResult {
        self.check_if_active()?;
        self.update_board(tile)?;
        self.update_state_and_turn()?;
        Ok(())
    }

    pub fn check_if_active(&self) -> ProgramResult {
        if !self.is_active() {
            // See description of #[error] for an explanation of this into()
            return Err(TicTacToeError::GameAlreadyOver.into());
        }
        Ok(())
    }

    pub fn update_board(&mut self, tile: &Tile) -> ProgramResult {
        let current_player_index = self.current_player_index();
        if tile.x > 2 || tile.y > 2 {
            return Err(TicTacToeError::TileOutOfBounds.into());
        }
        match self.board[tile.y as usize][tile.x as usize] {
            Some(_) => return Err(TicTacToeError::TileAlreadySet.into()),
            None => {
                self.board[tile.y as usize][tile.x as usize] = Sign::from_usize(current_player_index);
            } 
        }
        Ok(())
    }

    pub fn update_state_and_turn(&mut self) -> ProgramResult {
        match self.get_new_gamestate() {
            GameState::Won{winner: winning_player} => {
                self.state = GameState::Won{winner: winning_player};
            }
            GameState::Tied => {
                self.state = GameState::Tied;
            }
            GameState::Active => {
                self.state = GameState::Active;
                self.turn += 1;
            }
        }
        Ok(())
    }

    pub fn get_new_gamestate(&mut self) -> GameState {
        if self.is_won() {
            return GameState::Won{winner:self.current_player()};
        } else if self.is_tied() {
            return GameState::Tied;
        }
        GameState::Active
    }

    pub fn is_won(&self) -> bool {
        for i in 0..3 {
            if self.three_same_row(i as usize) || self.three_same_column(i as usize) {
                return true;
            }
        }
        if self.three_diagonal() {
            return true;
        }
        return false;
    }

    pub fn three_same_row(&self, row: usize) -> bool {
        return self.is_winning_trio([(row, 0), (row, 1), (row, 2)]);
    }

    pub fn three_same_column(&self, col: usize) -> bool {
        return self.is_winning_trio([(0, col), (1, col), (2, col)]);
    }

    pub fn three_diagonal(&self) -> bool {
        self.is_winning_trio([(0, 0), (1, 1), (2, 2)])
            || self.is_winning_trio([(0, 2), (1, 1), (2, 0)])
    }

    fn is_winning_trio(&self, trio: [(usize, usize); 3]) -> bool {
        let [first, second, third] = trio;
        self.board[first.0][first.1].is_some()
            && self.board[first.0][first.1] == self.board[second.0][second.1]
            && self.board[first.0][first.1] == self.board[third.0][third.1]
    }

    pub fn is_tied(&self) -> bool {
        if let GameState::Won{winner: _}= self.state {
            return false;
        }
        return self.are_all_tiles_full();
    }

    pub fn are_all_tiles_full(&self) -> bool {
        for row in 0..3 {
            for column in 0..3 {
                match self.board[row][column] {
                    Some(_) => {}
                    None => return false,
                }
            }
        }
        true
    }
}

#[error]
pub enum TicTacToeError {
    GameAlreadyOver,
    TileOutOfBounds,
    TileAlreadySet,
    NotPlayersTurn,
}


#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct Tile {
    x: u8, // NOTE: here I used to have usize and I was getting an error
    y: u8,
}

// Both GameState and Sign derive some traits. AnchorSerialize and
// AnchorDeserialize are the crucial ones. All types that are used in
// types that are marked with #[account] must implement these two traits
// (or be marked with #[account] themselves). All other traits are
// important to our game logic and we are going to use them later.
// Generally, it is good practice to derive even more traits to make the
// life of others trying to interface with your program easier
// (see Rust's API guidelines) but for brevity's sake, we are not going
// to do that in this guide.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum GameState {
    Active,
    Tied,
    Won{winner: Pubkey}, //Note: we cannot use Won(winner) here because
                         // it is not supported by anchor
}
// This is added because GameState also needs to implement Default, but
// rustc won't accept deriving it as in #[derive(Debug)]
impl Default for GameState {
    fn default() -> Self {
        Self::Active
    }
}

#[derive(
    AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, FromPrimitive, ToPrimitive,
)]
// FromPrimitive and ToPrimitive are used so that we can access
// instantiate Sign with a usize datatype as in `Sign::from_usize(1)`
// This is the same as `Sign::O`
// For this we need to import `num_derive` and `num_traits`
pub enum Sign {
    X,
    O,
}
