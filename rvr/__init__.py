"""
Package for the RvR web application, to be run by run.py

Initial version described below (user view)

Maybe only one situation (heads-up preflop), maybe three (BB vs. steal, CO vs.
resteal, BTN cold call). Only 100 BB deep. Only random flop.

1. Unauthenticated landing page.
Describes the software. Has a OpenID login button.
Flow:
 - click login, return to authenticated landing page

2. The authenticated landing page.
Shows a list of the user's games: open, running and finished. Show's a list of
open games the user can join. Allows creating a new game.
Flow:
 - click running game, go to game page (open, action, observing, finished)
 - click open game, go to join game confirmation page
 - click start new game, go to start game confirmation page

3. Game page (redirect page)
Open game we're in -> leave/cancel game confirmation page
Open game we're not in -> join game confirmation page
Running game we're in and it's our turn -> play page
Running game we're in and it's not our turn -> view game page
Running game we're not in -> view game page
Finished game we were in -> view game page
Finished game we weren't in -> view game page

4. Leave/cancel game confirmation page
This game page is shown when the user is registered for a game that has not yet
started. It shows registered users, and gives the user the option to leave the
game.

5. Join game confirmation page
This game page is shown when the game does not yet exist. It gives the user the
option to create a new game.

6. Play page
This game page is shown when the game has started and it is the user's turn. The
user can enter a move and have it performed by the back end. This then redirects
the user to the view game page because it is no longer their turn.

7. View game page
This game page is shown when the it is not the user's turn, or for a game that
the user is not part of. This will only work if we do not show the user's
current range. If we want to do that, we will have to split this into a page for
a participant in an active game, plus a page for a non-participant.

Now, let's consider what core has to do. In general, any call will be either
requesting something be *done*, or requesting some *information*. Here's a list,
based on the above.

1.
- create-or-validate OpenID

2.
- retrieve open games including registered users
- retrieve user's games and their statuses

3.
- leave/cancel game we're in
- join/start game we're not in
- retrieve game history without current player's ranges

4. (per 2)

5. (none)

6.
- retrieve game history with current player's ranges
- perform action in game we're in

7. (per 3)

In summary:
- create-or-validate OpenID-based account
- retrieve open games including registered users
- retrieve user's games and their statuses
- leave/cancel game we're in
- join/start game we're not in
- perform action in game we're in
- retrieve game history without current player's ranges
- retrieve game history with current player's ranges
"""