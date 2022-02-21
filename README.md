# Tic-tac-toe solana program with anchor and anchorpy

A reimplementation of `anchor_lang`'s [tic-tac-toe example](https://book.anchor-lang.com/chapter_3/milestone_project_tic-tac-toe.html) from anchor's documentation. Here tests are written in python (using anchorpy) rather than in typescript. (Additionally, part of the rust code in tic-tac-toe has been modified).

NOTE: There seems to be a general ongoing issue with asserting equality of converted rust `enum` types both in typescript and in python. For now, for this repository I am simply printing the appropriate enums so their equality can be checked "manually".
