import json
import socket
import sys
import threading

import pygame

from protocol import *

pygame.init()

DEFAULT_SERVER_IP = socket.gethostbyname(socket.gethostname())
DEFAULT_SERVER_PORT = 8000

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 800

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)


class Client:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.socket = None
        self.username = None
        self.game_state = None
        self.players_list = []
        self.opponent = None
        self.snake_color = RED
        self.opponent_color = BLUE
        self.running = True
        self.game_id = None
        self.input_text = ""
        self.input_active = True

        # Default to WASD so the player can start immediately.
        self.controls = {
            UP: pygame.K_w,
            DOWN: pygame.K_s,
            LEFT: pygame.K_a,
            RIGHT: pygame.K_d,
        }
        self.control_order = [UP, DOWN, LEFT, RIGHT]
        self.control_index = 0
        self.controls_locked = True
        self.control_mode = "WASD"

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Python Arena")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        self.current_screen = "login"

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            print(f"Connected to server at {self.server_ip}:{self.server_port}")

            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def send_message(self, message):
        if not self.socket:
            return

        try:
            json_data = json.dumps(message)
            self.socket.sendall(json_data.encode("utf-8") + b"\n")
        except Exception as e:
            print(f"Error sending message: {e}")

    def receive_messages(self):
        while self.running:
            try:
                data = b""
                while b"\n" not in data:
                    chunk = self.socket.recv(1024)
                    if not chunk:
                        print("Server disconnected")
                        self.running = False
                        return
                    data += chunk

                message = json.loads(data.decode("utf-8").strip())
                self.handle_message(message)
            except Exception as e:
                print(f"Error receiving message: {e}")
                self.running = False
                break

    def handle_message(self, message):
        msg_type = message.get(FIELD_TYPE)

        if msg_type == JOIN:
            if message.get(FIELD_STATUS) == STATUS_OK:
                print("Successfully joined server")
                self.current_screen = "lobby"
                self.input_active = False
            else:
                print(f"Failed to join: {message.get(FIELD_MESSAGE)}")

        elif msg_type == PLAYER_LIST:
            self.players_list = message.get(FIELD_PLAYERS, [])
            print(f"Available players: {self.players_list}")

        elif msg_type == SELECT_OPPONENT:
            if message.get(FIELD_STATUS) == STATUS_OK:
                self.opponent = message.get(FIELD_OPPONENT)
                self.current_screen = "snake_config"

                # Reset to default WASD at the start of each match.
                self.controls = {
                    UP: pygame.K_w,
                    DOWN: pygame.K_s,
                    LEFT: pygame.K_a,
                    RIGHT: pygame.K_d,
                }
                self.control_index = 0
                self.controls_locked = True
                self.control_mode = "WASD"

                print(f"Selected opponent: {self.opponent}")
            else:
                print("Failed to select opponent")

        elif msg_type == SNAKE_CONFIG:
            opponent_color = message.get(FIELD_COLOR)
            if opponent_color:
                self.opponent_color = self.parse_color(opponent_color)

        elif msg_type == GAME_STATE:
            # The server owns the board; the client only stores and draws it.
            self.game_state = message
            self.game_id = message.get(FIELD_GAME_ID)
            self.current_screen = "game"
            print("Game state updated")

        elif msg_type == GAME_OVER:
            self.current_screen = "game_over"
            winner = message.get(FIELD_WINNER)
            print(f"Game over! Winner: {winner}")

        elif msg_type == ERROR:
            print(f"Server error: {message.get(FIELD_MESSAGE)}")

    def parse_color(self, color_str):
        color_map = {
            "red": RED,
            "blue": BLUE,
            "green": GREEN,
            "white": WHITE,
            "black": BLACK,
        }
        return color_map.get(color_str.lower(), RED)

    def key_name(self, key_code):
        return pygame.key.name(key_code).upper()

    def set_wasd_controls(self):
        self.controls = {
            UP: pygame.K_w,
            DOWN: pygame.K_s,
            LEFT: pygame.K_a,
            RIGHT: pygame.K_d,
        }
        self.controls_locked = True
        self.control_mode = "WASD"

    def set_arrow_controls(self):
        self.controls = {
            UP: pygame.K_UP,
            DOWN: pygame.K_DOWN,
            LEFT: pygame.K_LEFT,
            RIGHT: pygame.K_RIGHT,
        }
        self.controls_locked = True
        self.control_mode = "ARROWS"

    def start_custom_controls(self):
        self.controls = {}
        self.control_index = 0
        self.controls_locked = False
        self.control_mode = "CUSTOM"

    def join_server(self, username):
        self.username = username
        self.send_message({
            FIELD_TYPE: JOIN,
            FIELD_USERNAME: username,
        })

    def select_opponent(self, opponent_name):
        self.send_message({
            FIELD_TYPE: SELECT_OPPONENT,
            FIELD_OPPONENT: opponent_name,
        })

    def send_snake_config(self, color):
        self.snake_color = self.parse_color(color)
        self.send_message({
            FIELD_TYPE: SNAKE_CONFIG,
            FIELD_GAME_ID: self.game_id,
            FIELD_COLOR: color,
        })

    def send_ready(self):
        self.send_message({
            FIELD_TYPE: READY,
            FIELD_GAME_ID: self.game_id,
        })

    def send_move(self, direction):
        self.send_message({
            FIELD_TYPE: MOVE,
            FIELD_GAME_ID: self.game_id,
            FIELD_DIRECTION: direction,
        })

    def handle_login_input(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_RETURN and self.input_text.strip():
            self.join_server(self.input_text.strip())
        elif event.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        elif len(self.input_text) < 20:
            self.input_text += event.unicode

    def handle_control_setup(self, event):
        if event.type != pygame.KEYDOWN:
            return

        # Let the player switch modes at any time on the setup screen.
        if event.key == pygame.K_1:
            self.set_wasd_controls()
            return
        elif event.key == pygame.K_2:
            self.set_arrow_controls()
            return
        elif event.key == pygame.K_3:
            self.start_custom_controls()
            return

        # Preset modes only need SPACE to confirm.
        if self.control_mode in ("WASD", "ARROWS"):
            if event.key == pygame.K_SPACE:
                self.send_snake_config("red")
                self.send_ready()
            return

        # Custom mode collects 4 keys, then SPACE confirms.
        if self.control_mode == "CUSTOM":
            if self.controls_locked:
                if event.key == pygame.K_SPACE:
                    self.send_snake_config("red")
                    self.send_ready()
                return

            current_direction = self.control_order[self.control_index]

            # Avoid duplicate keys for different directions.
            if event.key in self.controls.values():
                return

            self.controls[current_direction] = event.key
            self.control_index += 1

            if self.control_index >= len(self.control_order):
                self.controls_locked = True

    def draw_login_screen(self):
        self.screen.fill(BLACK)

        title_text = self.font.render("Python Arena - Enter Username", True, WHITE)
        self.screen.blit(title_text, (SCREEN_WIDTH // 2 - 200, 100))

        input_box = pygame.Rect(SCREEN_WIDTH // 2 - 150, 200, 300, 50)
        pygame.draw.rect(self.screen, WHITE, input_box, 2)

        text_surface = self.font.render(self.input_text, True, WHITE)
        self.screen.blit(text_surface, (input_box.x + 10, input_box.y + 10))

        if self.input_active and pygame.time.get_ticks() % 1000 < 500:
            cursor_x = input_box.x + 10 + text_surface.get_width()
            pygame.draw.line(
                self.screen,
                WHITE,
                (cursor_x, input_box.y + 10),
                (cursor_x, input_box.y + 40),
            )

        join_text = self.font.render("Press ENTER to join server", True, GREEN)
        self.screen.blit(join_text, (SCREEN_WIDTH // 2 - 150, 280))

    def draw_lobby_screen(self):
        self.screen.fill(BLACK)

        title_text = self.font.render("Lobby - Select Opponent", True, WHITE)
        self.screen.blit(title_text, (50, 50))

        for i, player in enumerate(self.players_list):
            player_text = self.font.render(f"{i + 1}. {player}", True, WHITE)
            self.screen.blit(player_text, (50, 100 + i * 40))

        if self.players_list:
            select_text = self.font.render("Press 1-9 to select opponent", True, GREEN)
            self.screen.blit(select_text, (50, 100 + len(self.players_list) * 40 + 20))
        else:
            waiting_text = self.font.render("Waiting for other players...", True, WHITE)
            self.screen.blit(waiting_text, (50, 150))

    def draw_snake_config_screen(self):
        self.screen.fill(BLACK)

        title_text = self.font.render("Snake Config", True, WHITE)
        self.screen.blit(title_text, (50, 50))

        opponent_text = self.font.render(f"Opponent: {self.opponent}", True, WHITE)
        self.screen.blit(opponent_text, (50, 110))

        mode_title = self.font.render("Choose controls: 1=WASD  2=Arrow Keys  3=Custom", True, WHITE)
        self.screen.blit(mode_title, (50, 170))

        mode_text = self.font.render(f"Current Mode: {self.control_mode}", True, GREEN)
        self.screen.blit(mode_text, (50, 220))

        y = 280
        for direction in self.control_order:
            key_label = self.key_name(self.controls[direction]) if direction in self.controls else "-"
            line = self.font.render(f"{direction}: {key_label}", True, WHITE)
            self.screen.blit(line, (50, y))
            y += 45

        if self.control_mode == "CUSTOM" and not self.controls_locked:
            current_direction = self.control_order[self.control_index]
            prompt = self.font.render(f"Press a key for {current_direction}", True, GREEN)
            self.screen.blit(prompt, (50, y + 20))
        else:
            ready_text = self.font.render("Press SPACE to ready up", True, GREEN)
            self.screen.blit(ready_text, (50, y + 20))

    def draw_game_screen(self):
        self.screen.fill(BLACK)

        if not self.game_state:
            return

        board = self.game_state.get(FIELD_BOARD, {"width": 20, "height": 20})
        food = self.game_state.get(FIELD_FOOD, [])
        obstacles = self.game_state.get(FIELD_OBSTACLES, [])
        players_data = self.game_state.get(FIELD_PLAYERS_DATA, {})
        time_left = self.game_state.get(FIELD_TIME_LEFT, 0)
        spectators = self.game_state.get(FIELD_SPECTATORS, 0)

        top_bar_height = 70
        offset_x = 0
        offset_y = top_bar_height

        # Scale the board so it fills almost the whole window.
        cell_width = SCREEN_WIDTH / board["width"]
        cell_height = (SCREEN_HEIGHT - top_bar_height) / board["height"]

        usernames = list(players_data.keys())

        if len(usernames) > 0:
            health1 = players_data[usernames[0]].get(FIELD_HEALTH, 0)
            text1 = self.font.render(f"{usernames[0]}: {health1}", True, WHITE)
            self.screen.blit(text1, (20, 20))

        if len(usernames) > 1:
            health2 = players_data[usernames[1]].get(FIELD_HEALTH, 0)
            text2 = self.font.render(f"{usernames[1]}: {health2}", True, WHITE)
            self.screen.blit(text2, (220, 20))

        timer_text = self.font.render(f"Time Left: {time_left}", True, WHITE)
        timer_rect = timer_text.get_rect(center=(SCREEN_WIDTH // 2, 30))
        self.screen.blit(timer_text, timer_rect)

        spectator_text = self.font.render(f"Spectators: {spectators}", True, WHITE)
        spectator_rect = spectator_text.get_rect(topright=(SCREEN_WIDTH - 20, 15))
        self.screen.blit(spectator_text, spectator_rect)

        # Draw the grid.
        for x in range(board["width"]):
            for y in range(board["height"]):
                rect = pygame.Rect(
                    int(offset_x + x * cell_width),
                    int(offset_y + y * cell_height),
                    int(cell_width),
                    int(cell_height),
                )
                pygame.draw.rect(self.screen, WHITE, rect, 1)

        # Draw obstacles.
        for x, y in obstacles:
            rect = pygame.Rect(
                int(offset_x + x * cell_width),
                int(offset_y + y * cell_height),
                int(cell_width),
                int(cell_height),
            )
            pygame.draw.rect(self.screen, WHITE, rect)

        # Draw food.
        for x, y in food:
            rect = pygame.Rect(
                int(offset_x + x * cell_width + cell_width * 0.2),
                int(offset_y + y * cell_height + cell_height * 0.2),
                int(cell_width * 0.6),
                int(cell_height * 0.6),
            )
            pygame.draw.rect(self.screen, GREEN, rect)

        # Draw both snakes.
        for username, player_data in players_data.items():
            color = self.parse_color(player_data.get(FIELD_COLOR, "red"))
            for x, y in player_data.get("positions", []):
                rect = pygame.Rect(
                    int(offset_x + x * cell_width),
                    int(offset_y + y * cell_height),
                    int(cell_width),
                    int(cell_height),
                )
                pygame.draw.rect(self.screen, color, rect)

    def draw_game_over_screen(self):
        self.screen.fill(BLACK)

        game_over_text = self.font.render("Game Over!", True, RED)
        self.screen.blit(game_over_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 50))

        winner_text = self.font.render("Check console for results", True, WHITE)
        self.screen.blit(winner_text, (SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2))

        restart_text = self.font.render("Press R to restart", True, GREEN)
        self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 50))

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif self.current_screen == "login" and self.input_active:
                    self.handle_login_input(event)

                elif event.type == pygame.KEYDOWN:
                    if self.current_screen == "lobby":
                        if pygame.K_1 <= event.key <= pygame.K_9:
                            index = event.key - pygame.K_1
                            if index < len(self.players_list):
                                self.select_opponent(self.players_list[index])

                    elif self.current_screen == "snake_config":
                        self.handle_control_setup(event)

                    elif self.current_screen == "game":
                        # Map the chosen keys to game directions.
                        if event.key == self.controls.get(LEFT):
                            self.send_move(LEFT)
                        elif event.key == self.controls.get(RIGHT):
                            self.send_move(RIGHT)
                        elif event.key == self.controls.get(UP):
                            self.send_move(UP)
                        elif event.key == self.controls.get(DOWN):
                            self.send_move(DOWN)

                    elif self.current_screen == "game_over" and event.key == pygame.K_r:
                        self.current_screen = "login"
                        self.input_text = ""
                        self.input_active = True

            if self.current_screen == "login":
                self.draw_login_screen()
            elif self.current_screen == "lobby":
                self.draw_lobby_screen()
            elif self.current_screen == "snake_config":
                self.draw_snake_config_screen()
            elif self.current_screen == "game":
                self.draw_game_screen()
            elif self.current_screen == "game_over":
                self.draw_game_over_screen()

            pygame.display.flip()
            self.clock.tick(60)

        if self.socket:
            self.socket.close()
        pygame.quit()


def main():
    server_ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER_IP
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SERVER_PORT

    print(f"Starting client with server {server_ip}:{server_port}")

    client = Client(server_ip, server_port)

    if client.connect_to_server():
        client.run()
    else:
        print("Failed to connect to server")


if __name__ == "__main__":
    main()
