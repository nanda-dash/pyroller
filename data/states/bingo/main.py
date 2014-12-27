import time
import sys
import pygame as pg
from collections import OrderedDict

from ... import tools, prepare
from ...components.labels import Button
from ...prepare import BROADCASTER as B

from . import statemachine
from . import states
from . import utils
from . import playercard
from . import dealercard
from . import patterns
from . import ballmachine
from . import cardselector
from . import events
from .settings import SETTINGS as S


class Bingo(statemachine.StateMachine):
    """State to represent a bing game"""

    def __init__(self):
        """Initialise the bingo game"""
        #
        self.verbose = False
        self.sound_muted = prepare.ARGS['debug']
        #
        self.font = prepare.FONTS["Saniretro"]
        font_size = 64
        b_width = 360
        b_height = 90
        #
        self.screen_rect = pg.Rect((0, 0), prepare.RENDER_SIZE)
        self.music_icon = prepare.GFX["speaker"]
        topright = (self.screen_rect.right - 10, self.screen_rect.top + 10)
        self.music_icon_rect = self.music_icon.get_rect(topright=topright)
        self.mute_icon = prepare.GFX["mute"]
        self.play_music = True
        self.auto_pick = S['debug-auto-pick']
        #
        self.ui = utils.ClickableGroup()
        #
        lobby_label = utils.getLabel('button', (0, 0), 'Lobby')
        self.lobby_button = Button(20, self.screen_rect.bottom - (b_height + 15),
                                   b_width, b_height, lobby_label)
        #
        # The controls to allow selection of different numbers of cards
        self.card_selector = cardselector.CardSelector('card-selector', self)
        self.card_selector.linkEvent(events.E_NUM_CARDS_CHANGED, self.change_number_of_cards)
        self.ui.append(self.card_selector.ui)
        #
        self.cards = self.get_card_collection()
        self.ui.extend(self.cards)
        self.dealer_cards = dealercard.DealerCardCollection(
            'dealer-card',
            S['dealer-cards-position'],
            S['dealer-card-offsets'],
            self
        )
        #
        self.winning_pattern = patterns.PATTERNS[0]
        #
        self.pattern_buttons = utils.DrawableGroup()
        self.debug_buttons = utils.DrawableGroup()
        self.buttons = utils.DrawableGroup([self.pattern_buttons])
        #
        if prepare.DEBUG:
            self.buttons.append(self.debug_buttons)
        #
        super(Bingo, self).__init__(states.S_INITIALISE)
        #
        # The machine for picking balls
        self.ball_machine = ballmachine.BallMachine('ball-machine', self)
        self.ball_machine.start_machine()
        self.ui.append(self.ball_machine.buttons)
        #
        self.all_cards = utils.DrawableGroup()
        self.all_cards.extend(self.cards)
        self.all_cards.extend(self.dealer_cards)
        #
        B.linkEvent(events.E_PLAYER_PICKED, self.player_picked)
        B.linkEvent(events.E_PLAYER_UNPICKED, self.player_unpicked)
        #
        self.current_pick_sound = 0
        self.last_pick_time = 0

    def startup(self, current_time, persistent):
        """This method will be called each time the state resumes."""
        self.persist = persistent
        self.casino_player = self.persist["casino_player"]
        #
        # Make sure the player has stat markers
        if 'Bingo' not in self.casino_player.stats:
            self.casino_player.stats['Bingo'] = OrderedDict([
                ('games played', 0),
                ('games won', 0),
                ('_last squares', []),
                ])
        #
        self.casino_player.stats['Bingo']['games played'] += 1
        self.cards.set_card_numbers(self.casino_player.stats['Bingo'].get('_last squares', []))

    def get_event(self, event, scale=(1,1)):
        """Check for events"""
        super(Bingo, self).get_event(event, scale)
        if event.type == pg.QUIT:
            if prepare.ARGS['straight']:
                pg.quit()
                sys.exit()
            else:
                self.done = True
                self.next = "LOBBYSCREEN"
        elif event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEMOTION):
            #
            self.ui.process_events(event, scale)
            #
            pos = tools.scaled_mouse_pos(scale, event.pos)
            if event.type == pg.MOUSEBUTTONDOWN:
                if self.music_icon_rect.collidepoint(pos):
                    self.play_music = not self.play_music
                    if self.play_music:
                        pg.mixer.music.play(-1)
                    else:
                        pg.mixer.music.stop()
                elif self.lobby_button.rect.collidepoint(pos):
                    self.game_started = False
                    self.done = True
                    self.next = "LOBBYSCREEN"
                    self.casino_player.stats['Bingo']['_last squares'] = self.cards.get_card_numbers()
                    pass
        elif event.type == pg.KEYUP:
            if event.key == pg.K_ESCAPE:
                self.done = True
                self.next = "LOBBYSCREEN"
            elif event.key == pg.K_SPACE:
                self.next_ball(None)
            elif event.key == pg.K_m:
                self.sound_muted = not self.sound_muted

    def drawUI(self, surface, scale):
        """Update the main surface once per frame"""
        surface.fill(S['table-color'])
        #
        self.lobby_button.draw(surface)
        self.all_cards.draw(surface)
        self.ball_machine.draw(surface)
        self.buttons.draw(surface)
        self.card_selector.draw(surface)
        #
        if self.play_music:
            surface.blit(self.mute_icon, self.music_icon_rect)
        else:
            surface.blit(self.music_icon, self.music_icon_rect)

    def initUI(self):
        """Initialise the UI display"""
        #
        # Buttons that show the winning patterns
        for idx, pattern in enumerate(patterns.PATTERNS):
            self.pattern_buttons.append(utils.ImageOnOffButton(
                pattern.name, (200 + idx * 240, 400),
                'bingo-red-button', 'bingo-red-off-button', 'button',
                pattern.name,
                pattern == self.winning_pattern,
                self.change_pattern, pattern
            ))
        self.ui.extend(self.pattern_buttons)
        #
        # Simple generator to flash the potentially winning squares
        self.add_generator('potential-winners', self.flash_potential_winners())
        #
        # Debugging buttons
        if prepare.DEBUG:
            self.debug_buttons.append(utils.ImageOnOffButton(
                'auto-pick', S['debug-auto-pick-position'],
                'bingo-yellow-button', 'bingo-yellow-off-button', 'small-button',
                'Auto pick',
                S['debug-auto-pick'],
                self.toggle_auto_pick, None,
                scale=S['small-button-scale']
            ))
            #
            self.debug_buttons.append(utils.ImageButton(
                'restart', S['debug-restart-position'],
                'bingo-yellow-button', 'small-button',
                'Restart',
                self.restart_game, None,
                scale=S['small-button-scale']
            ))
            #
            self.debug_buttons.append(utils.ImageButton(
                'next-ball', S['debug-next-ball-position'],
                'bingo-yellow-button', 'small-button',
                'Next Ball',
                self.next_ball, None,
                scale=S['small-button-scale']
            ))
            #
            self.debug_buttons.append(utils.ImageButton(
                'new-cards', S['debug-new-cards-position'],
                'bingo-yellow-button', 'small-button',
                'New Cards',
                self.draw_new_cards, None,
                scale=S['small-button-scale']
            ))
            self.ui.extend(self.debug_buttons)

    def change_pattern(self, pattern):
        """Change the winning pattern"""
        self.log.info('Changing pattern to {0}'.format(pattern.name))
        self.winning_pattern = pattern
        self.highlight_patterns(self.winning_pattern, one_shot=True)
        #
        # Clear all flashing squares
        for card in self.all_cards:
            card.potential_winning_squares = []
            for square in card.squares.values():
                square.is_focused = False
        #
        # Update UI
        for button in self.pattern_buttons:
            button.state = (button.arg == self.winning_pattern)

    def toggle_auto_pick(self, arg):
        """Toggle whether we are auto-picking numbers"""
        self.log.debug('Toggling auto-pick')
        self.auto_pick = not self.auto_pick
        self.debug_buttons[0].state = self.auto_pick

    def restart_game(self, arg):
        """Restart the game"""
        self.log.info('Restart game')
        self.ball_machine.reset_machine(self.ball_machine.interval)
        self.cards.reset()
        self.dealer_cards.reset()
        self.current_pick_sound = 0
        self.last_pick_time = 0

    def next_ball(self, arg):
        """Move on to the next ball"""
        self.ball_machine.call_next_ball()

    def draw_new_cards(self, arg):
        """Draw a new set of cards"""
        self.log.debug('Drawing new set of cards')
        self.cards.draw_new_numbers()
        self.cards.reset()

    def get_card_collection(self):
        """Return a new card collection"""
        return playercard.PlayerCardCollection(
            'player-card',
            S['player-cards-position'],
            S['player-card-offsets'][:self.card_selector.number_of_cards],
            self
        )

    def change_number_of_cards(self, number, arg=None):
        """Change the number of cards in play"""
        self.log.info('Changing the number of cards to {0}'.format(number))
        #
        # Store off the old card number to reuse
        self.casino_player.stats['Bingo']['_last squares'] = self.cards.get_card_numbers()
        #
        # Remove old cards
        for card in self.cards:
            self.all_cards.remove(card)
        #
        # Create new cards
        self.cards = self.get_card_collection()
        self.cards.set_card_numbers(self.casino_player.stats['Bingo'].get('_last squares', []))
        #
        self.all_cards.extend(self.cards)
        self.restart_game(None)

    def highlight_patterns(self, pattern, one_shot):
        """Test method to cycle through the winning patterns"""
        for card in self.cards:
            self.add_generator(
                'highlight-patterns-card-%s' % card.name,
                self.highlight_pattern(card, pattern, one_shot)
            )

    def highlight_pattern(self, card, pattern, one_shot):
        """Highlight a particular pattern on a card"""
        for squares in pattern.get_matches(card):
            for square in squares:
                square.is_highlighted = True
            yield 100
            for square in squares:
                square.is_highlighted = False
            yield 10
        #
        if not one_shot:
            self.add_generator('highlight', self.highlight_pattern(card, pattern, one_shot=False))

    def initialise(self):
        """Start the game state"""
        yield 0
        self.add_generator('main-game-loop', self.main_game_loop())

    def main_game_loop(self):
        """The main game loop"""
        while True:
            yield 0

    def ball_picked(self, ball):
        """A ball was picked"""
        #
        # If auto-picking then update the cards
        auto_pick_cards = list(self.dealer_cards)
        if self.auto_pick:
            auto_pick_cards.extend(self.cards)
        for card in auto_pick_cards:
            card.call_square(ball.number)
        #
        # Highlight the card labels
        for card in self.all_cards:
            card.highlight_column(ball.letter)

    def player_picked(self, square, arg):
        """The player picked a square"""
        if not square.card.is_active:
            return
        #
        # Check to see if we created a new potentially winning square
        called_squares = list(square.card.called_squares)
        prior_called_squares = list(called_squares)
        prior_called_squares.remove(square.text)
        #
        _, winners = self.winning_pattern.get_number_to_go_and_winners(square.card, called_squares)
        _, prior_winners = self.winning_pattern.get_number_to_go_and_winners(square.card, prior_called_squares)
        self.log.debug('{0} / {1}'.format(winners, prior_winners))
        #
        if len(winners) > len(prior_winners):
            self.play_sound('bingo-potential-winner')
        #
        # Increment sound if we did this quickly
        if time.time() - self.last_pick_time < S['player-pick-interval']:
            self.current_pick_sound = min(self.current_pick_sound + 1, len(S['player-pick-sounds']) - 1)
        else:
            self.current_pick_sound = 0
        self.last_pick_time = time.time()
        self.play_sound(S['player-pick-sounds'][self.current_pick_sound])
        #
        self.log.info('Player picked {0}'.format(square))

    def player_unpicked(self, square, arg):
        """The player unpicked a square"""
        self.log.info('Player unpicked {0}'.format(square))
        self.play_sound('bingo-unpick')

    def flash_potential_winners(self):
        """Flash the squares that are potential winners"""
        while True:
            for state, delay in S['card-focus-flash-timing']:
                for card in self.all_cards:
                    for square in card.potential_winning_squares:
                        square.is_focused = state
                yield delay * 1000

    def play_sound(self, name):
        """Play a named sound - respects the mute settings"""
        if not self.sound_muted:
            prepare.SFX[name].play()