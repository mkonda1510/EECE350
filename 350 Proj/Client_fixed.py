import json
import socket
import sys
import threading

import pygame

from protocol import *

pygame.init()

DEFAULT_SERVER_IP = socket.gethostbyname(socket.gethostname())
DEFAULT_SERVER_PORT = 8000

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

CELL_SIZE = 20


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
                print(f"Selected opponent: {self.opponent}")
            else:
                print("Failed to select opponent")

        elif msg_type == SNAKE_CONFIG:
            opponent_color = message.get(FIELD_COLOR)
            if opponent_color:
                self.opponent_color = self.parse_color(opponent_color)

        elif msg_type == GAME_STATE:
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

        ready_text = self.font.render("Press SPACE to ready up with red snake", True, GREEN)
        self.screen.blit(ready_text, (50, 170))

    def draw_game_screen(self):
        self.screen.fill(BLACK)

        for x in range(0, SCREEN_WIDTH, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (0, y), (SCREEN_WIDTH, y))

        status_text = self.font.render("Game in progress...", True, WHITE)
        self.screen.blit(status_text, (50, 50))

        if self.opponent:
            opponent_text = self.font.render(f"vs {self.opponent}", True, WHITE)
            self.screen.blit(opponent_text, (50, 100))

        move_text = self.font.render("Use WASD or Arrow keys to move", True, GREEN)
        self.screen.blit(move_text, (50, SCREEN_HEIGHT - 50))

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
                        if event.key == pygame.K_SPACE:
                            self.send_snake_config("red")
                            self.send_ready()

                    elif self.current_screen == "game":
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            self.send_move(LEFT)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            self.send_move(RIGHT)
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            self.send_move(UP)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
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
