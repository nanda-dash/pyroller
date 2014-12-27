import pygame as pg
from ..components.labels import Label, Button, PayloadButton, Blinker, MultiLineLabel
from .. import tools, prepare


class Keno(tools._State):
    """Class to represent a casino game."""
    def __init__(self):
        super(Keno, self).__init__()
        self.screen_rect = pg.Rect((0, 0), prepare.RENDER_SIZE)
        self.game_started = False
        self.font = prepare.FONTS["Saniretro"]
        
        b_width = 360
        b_height = 90
        side_margin = 10
        vert_space = 20
        left = self.screen_rect.right - (b_width + side_margin)
        top = self.screen_rect.bottom - ((b_height * 5) + vert_space * 4)

        font_size = 64
        
        lobby_label = Label(self.font, font_size, "Lobby", "gold3", {"center": (0, 0)})
        self.lobby_button = Button(self.screen_rect.right - (b_width + side_margin), self.screen_rect.bottom - (b_height + 15),
                                                 b_width, b_height, lobby_label)

    def startup(self, current_time, persistent):
        """This method will be called each time the state resumes."""
        self.persist = persistent
        #This is the object that represents the user.
        self.casino_player = self.persist["casino_player"]

    def get_event(self, event, scale=(1,1)):
        """This method will be called for each event in the event queue
        while the state is active.
        """
        if event.type == pg.QUIT:
            self.done = True
            self.next = "LOBBYSCREEN"
        elif event.type == pg.MOUSEBUTTONDOWN:
            #Use tools.scaled_mouse_pos(scale, event.pos) for correct mouse
            #position relative to the pygame window size.
            event_pos = tools.scaled_mouse_pos(scale, event.pos)
            self.persist["music_handler"].get_event(event, scale)

            if self.lobby_button.rect.collidepoint(event_pos):
                self.game_started = False
                self.done = True
                self.next = "LOBBYSCREEN"

    def draw(self, surface):
        """This method handles drawing/blitting the state each frame."""
        surface.fill(pg.Color("darkgreen"))
        self.lobby_button.draw(surface)
        self.persist["music_handler"].draw(surface)

    def update(self, surface, keys, current_time, dt, scale):
        """
        This method will be called once each frame while the state is active.
        Surface is a reference to the rendering surface which will be scaled
        to pygame's display surface, keys is the return value of the last call
        to pygame.key.get_pressed. current_time is the number of milliseconds
        since pygame was initialized. dt is the number of milliseconds since
        the last frame.
        """
        mouse_pos = tools.scaled_mouse_pos(scale)
        self.persist["music_handler"].update()
        self.draw(surface)
