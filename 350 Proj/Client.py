import json
import socket
import sys
import threading

import pygame

from protocol import *


pygame.init()

# Basic window/server settings. The IP can still be passed from the terminal.
DEFAULT_SERVER_IP = socket.gethostbyname(socket.gethostname())
DEFAULT_SERVER_PORT = 8000
SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 800
TOP_BAR = 70

# Simple color names used by the game and by snake configuration.
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
COLORS = {"red": RED, "blue": BLUE, "green": GREEN, "white": WHITE, "black": BLACK}


class Client:
    def __init__(self, server_ip, server_port):
        # Connection and game state kept by this client.
        self.server_ip, self.server_port = server_ip, server_port
        self.socket = None
        self.running = True
        self.username = None
        self.current_screen = "login"

        # Data received from the server.
        self.players_list = []
        self.game_state = None
        self.game_id = None
        self.opponent = None
        self.final_winner = None
        self.final_scores = {}

        # Small pieces of UI state.
        self.input_text = ""
        self.input_active = True
        self.status_message = ""
        self.pending_request_from = None
        self.pending_request_message = ""

        # Controls start as WASD, but the player can switch before each match.
        self.control_order = [UP, DOWN, LEFT, RIGHT]
        self.controls_locked = True
        self.control_index = 0
        self.set_controls("WASD")

        # Pygame setup.
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Python Arena")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

    # -------------------- Networking --------------------
    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            threading.Thread(target=self.receive_messages, daemon=True).start()
            print(f"Connected to server at {self.server_ip}:{self.server_port}")
            return True
        except Exception as e:
            self.status_message = f"Failed to connect: {e}"
            print(self.status_message)
            return False

    def send(self, msg_type, **fields):
        # Every network message is JSON plus a newline, so the receiver knows where it ends.
        if not self.socket:
            return
        try:
            message = {FIELD_TYPE: msg_type, **fields}
            self.socket.sendall(json.dumps(message).encode("utf-8") + b"\n")
        except Exception as e:
            self.status_message = f"Send error: {e}"
            print(self.status_message)

    def receive_messages(self):
        # Runs in the background so the Pygame window does not freeze.
        data = b""
        while self.running:
            try:
                chunk = self.socket.recv(1024)
                if not chunk:
                    self.status_message = "Server disconnected"
                    self.running = False
                    return

                data += chunk
                while b"\n" in data:
                    line, data = data.split(b"\n", 1)
                    self.handle_message(json.loads(line.decode("utf-8")))
            except Exception as e:
                self.status_message = f"Receive error: {e}"
                print(self.status_message)
                self.running = False

    def handle_message(self, message):
        # One place where all server messages update the client screen/state.
        msg_type = message.get(FIELD_TYPE)
        status = message.get(FIELD_STATUS)

        if msg_type == JOIN:
            if status == STATUS_OK:
                self.current_screen = "lobby"
                self.input_active = False
                self.status_message = "Joined successfully"
            else:
                self.current_screen = "login"
                self.input_text = ""
                self.input_active = True
                self.status_message = message.get(FIELD_MESSAGE, "Username taken, try another one")

        elif msg_type == PLAYER_LIST:
            self.players_list = message.get(FIELD_PLAYERS, [])

        elif msg_type == SELECT_OPPONENT:
            if status == STATUS_PENDING:
                self.pending_request_from = message.get(FIELD_OPPONENT)
                self.pending_request_message = message.get(FIELD_MESSAGE, "")
                self.current_screen = "match_request"
            else:
                self.status_message = message.get(FIELD_MESSAGE, "Request sent")

        elif msg_type == MATCH_RESPONSE:
            if status == STATUS_ACCEPT:
                self.opponent = message.get(FIELD_OPPONENT)
                self.current_screen = "snake_config"
            else:
                self.opponent = None
                self.current_screen = "lobby"
            self.status_message = message.get(FIELD_MESSAGE, "")

        elif msg_type == GAME_STATE:
            self.game_state = message
            self.game_id = message.get(FIELD_GAME_ID)
            self.current_screen = "game"

        elif msg_type == GAME_OVER:
            self.final_winner = message.get(FIELD_WINNER, "Unknown")
            self.final_scores = message.get(FIELD_SCORE, {})
            self.game_state = None
            self.game_id = None
            self.opponent = None
            self.current_screen = "game_over"

        elif msg_type == ERROR:
            self.status_message = message.get(FIELD_MESSAGE, "Unknown server error")
            if self.status_message == "Username already taken":
                self.current_screen = "login"
                self.input_text = ""
                self.input_active = True

    # -------------------- Small Helpers --------------------
    def text(self, content, x, y, color=WHITE, center=False, right=False):
        # Tiny drawing helper so the screen code stays readable.
        surface = self.font.render(str(content), True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        elif right:
            rect.topright = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)
        return surface

    def color(self, name):
        return COLORS.get(str(name).lower(), RED)

    def set_controls(self, mode):
        # Presets do not need rebinding; custom mode asks for four keys.
        self.control_mode = mode
        self.controls_locked = mode != "CUSTOM"
        self.control_index = 0

        if mode == "WASD":
            self.controls = {UP: pygame.K_w, DOWN: pygame.K_s, LEFT: pygame.K_a, RIGHT: pygame.K_d}
        elif mode == "ARROWS":
            self.controls = {UP: pygame.K_UP, DOWN: pygame.K_DOWN, LEFT: pygame.K_LEFT, RIGHT: pygame.K_RIGHT}
        else:
            self.controls = {}

    def return_to_lobby(self):
        # After a match, keep the same username and controls.
        self.final_winner = None
        self.final_scores = {}
        self.game_state = None
        self.game_id = None
        self.opponent = None
        self.current_screen = "lobby"
        self.status_message = "Back in lobby"

    # -------------------- Player Actions --------------------
    def join_server(self):
        if self.input_text.strip():
            self.username = self.input_text.strip()
            self.send(JOIN, **{FIELD_USERNAME: self.username})

    def select_opponent(self, index):
        if 0 <= index < len(self.players_list):
            opponent = self.players_list[index]
            self.status_message = f"Request sent to {opponent}"
            self.send(SELECT_OPPONENT, **{FIELD_OPPONENT: opponent})

    def answer_request(self, accepted):
        decision = STATUS_ACCEPT if accepted else STATUS_REJECT
        self.send(MATCH_RESPONSE, **{FIELD_OPPONENT: self.pending_request_from, FIELD_DECISION: decision})

        if accepted:
            self.opponent = self.pending_request_from
            self.current_screen = "snake_config"
        else:
            self.current_screen = "lobby"

        self.pending_request_from = None
        self.pending_request_message = ""

    def ready_up(self):
        self.send(SNAKE_CONFIG, **{FIELD_GAME_ID: self.game_id, FIELD_COLOR: "red"})
        self.send(READY, **{FIELD_GAME_ID: self.game_id})

    # -------------------- Input Handling --------------------
    def handle_key(self, event):
        if self.current_screen == "login":
            if event.key == pygame.K_RETURN:
                self.join_server()
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif len(self.input_text) < 20:
                self.input_text += event.unicode

        elif self.current_screen == "lobby" and pygame.K_1 <= event.key <= pygame.K_9:
            self.select_opponent(event.key - pygame.K_1)

        elif self.current_screen == "match_request":
            if event.key == pygame.K_y:
                self.answer_request(True)
            elif event.key == pygame.K_n:
                self.answer_request(False)

        elif self.current_screen == "snake_config":
            self.handle_control_key(event)

        elif self.current_screen == "game":
            for direction, key in self.controls.items():
                if event.key == key:
                    self.send(MOVE, **{FIELD_GAME_ID: self.game_id, FIELD_DIRECTION: direction})

        elif self.current_screen == "game_over" and event.key == pygame.K_r:
            self.return_to_lobby()

    def handle_control_key(self, event):
        if event.key == pygame.K_1:
            self.set_controls("WASD")
        elif event.key == pygame.K_2:
            self.set_controls("ARROWS")
        elif event.key == pygame.K_3:
            self.set_controls("CUSTOM")
        elif event.key == pygame.K_SPACE and self.controls_locked:
            self.ready_up()
        elif self.control_mode == "CUSTOM" and event.key not in self.controls.values():
            direction = self.control_order[self.control_index]
            self.controls[direction] = event.key
            self.control_index += 1
            self.controls_locked = self.control_index == len(self.control_order)

    # -------------------- Screens --------------------
    def draw_login(self):
        self.screen.fill(BLACK)
        self.text("Python Arena - Enter Username", SCREEN_WIDTH // 2, 100, center=True)

        box = pygame.Rect(SCREEN_WIDTH // 2 - 150, 200, 300, 50)
        pygame.draw.rect(self.screen, WHITE, box, 2)
        typed = self.text(self.input_text, box.x + 10, box.y + 10)

        if pygame.time.get_ticks() % 1000 < 500:
            cursor_x = box.x + 10 + typed.get_width()
            pygame.draw.line(self.screen, WHITE, (cursor_x, box.y + 10), (cursor_x, box.y + 40))

        self.text("Press ENTER to join server", SCREEN_WIDTH // 2, 280, GREEN, center=True)
        self.text(self.status_message, 50, 340, YELLOW)

    def draw_lobby(self):
        self.screen.fill(BLACK)
        self.text("Lobby - Select Opponent", 50, 50)

        if not self.players_list:
            self.text("Waiting for other players...", 50, 150)
        else:
            for i, player in enumerate(self.players_list):
                self.text(f"{i + 1}. {player}", 50, 100 + i * 40)
            self.text("Press 1-9 to select opponent", 50, 140 + len(self.players_list) * 40, GREEN)

        self.text(self.status_message, 50, 500, YELLOW)

    def draw_match_request(self):
        self.screen.fill(BLACK)
        self.text("Match Request", 50, 80)
        self.text(self.pending_request_message, 50, 160)
        self.text("Press Y to accept or N to reject", 50, 240, GREEN)

    def draw_snake_config(self):
        self.screen.fill(BLACK)
        self.text("Snake Config", 50, 50)
        self.text(f"Opponent: {self.opponent}", 50, 110)
        self.text("Choose controls: 1=WASD  2=Arrow Keys  3=Custom", 50, 170)
        self.text(f"Current Mode: {self.control_mode}", 50, 220, GREEN)

        y = 280
        for direction in self.control_order:
            key = pygame.key.name(self.controls[direction]).upper() if direction in self.controls else "-"
            self.text(f"{direction}: {key}", 50, y)
            y += 45

        if self.control_mode == "CUSTOM" and not self.controls_locked:
            self.text(f"Press a key for {self.control_order[self.control_index]}", 50, y + 20, GREEN)
        else:
            self.text("Press SPACE to ready up", 50, y + 20, GREEN)

    def draw_game(self):
        self.screen.fill(BLACK)
        if not self.game_state:
            return

        board = self.game_state.get(FIELD_BOARD, {"width": 20, "height": 20})
        players_data = self.game_state.get(FIELD_PLAYERS_DATA, {})
        cell_w = SCREEN_WIDTH / board["width"]
        cell_h = (SCREEN_HEIGHT - TOP_BAR) / board["height"]

        # Top bar shows the important live match info.
        for i, (name, data) in enumerate(players_data.items()):
            self.text(f"{name}: {data.get(FIELD_HEALTH, 0)}", 20 + i * 200, 20)
        self.text(f"Time Left: {self.game_state.get(FIELD_TIME_LEFT, 0)}", SCREEN_WIDTH // 2, 30, center=True)
        self.text(f"Spectators: {self.game_state.get(FIELD_SPECTATORS, 0)}", SCREEN_WIDTH - 20, 15, right=True)

        # Draw board cells, then objects on top of them.
        for x in range(board["width"]):
            for y in range(board["height"]):
                rect = pygame.Rect(int(x * cell_w), int(TOP_BAR + y * cell_h), int(cell_w), int(cell_h))
                pygame.draw.rect(self.screen, WHITE, rect, 1)

        self.draw_cells(self.game_state.get(FIELD_OBSTACLES, []), WHITE, cell_w, cell_h)
        self.draw_cells(self.game_state.get(FIELD_FOOD, []), GREEN, cell_w, cell_h, shrink=0.2)

        for player_data in players_data.values():
            self.draw_cells(player_data.get("positions", []), self.color(player_data.get(FIELD_COLOR)), cell_w, cell_h)

    def draw_cells(self, cells, color, cell_w, cell_h, shrink=0):
        # Same grid-to-pixels math for food, obstacles, and snakes.
        for x, y in cells:
            rect = pygame.Rect(
                int(x * cell_w + cell_w * shrink),
                int(TOP_BAR + y * cell_h + cell_h * shrink),
                int(cell_w * (1 - 2 * shrink)),
                int(cell_h * (1 - 2 * shrink)),
            )
            pygame.draw.rect(self.screen, color, rect)

    def draw_game_over(self):
        self.screen.fill(BLACK)
        self.text("Game Over!", SCREEN_WIDTH // 2, 140, RED, center=True)
        self.text(f"Winner: {self.final_winner or 'Unknown'}", SCREEN_WIDTH // 2, 220, center=True)

        y = 290
        for username, score in self.final_scores.items():
            self.text(f"{username}: {score}", SCREEN_WIDTH // 2, y, center=True)
            y += 50

        self.text("Press R to return to the lobby", SCREEN_WIDTH // 2, y + 40, GREEN, center=True)

    # -------------------- Main Loop --------------------
    def run(self):
        screens = {
            "login": self.draw_login,
            "lobby": self.draw_lobby,
            "match_request": self.draw_match_request,
            "snake_config": self.draw_snake_config,
            "game": self.draw_game,
            "game_over": self.draw_game_over,
        }

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)

            screens[self.current_screen]()
            pygame.display.flip()
            self.clock.tick(60)

        if self.socket:
            self.socket.close()
        pygame.quit()


def main():
    server_ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER_IP
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SERVER_PORT

    client = Client(server_ip, server_port)
    if client.connect_to_server():
        client.run()


if __name__ == "__main__":
    main()
