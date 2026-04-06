import pygame
import socket
import json
import threading
import sys
from protocol import *

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

# Game settings
CELL_SIZE = 20
GRID_WIDTH = 20
GRID_HEIGHT = 20

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

        # Input handling
        self.input_text = ""
        self.input_active = True

        # Pygame setup
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Πthon Arena")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        # Game state
        self.current_screen = "login"  # login, lobby, game, game_over

    def connect_to_server(self):
        """Connect to the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            print(f"Connected to server at {self.server_ip}:{self.server_port}")

            # Start message receiving thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def send_message(self, message):
        """Send a message to the server"""
        if self.socket:
            try:
                json_data = json.dumps(message)
                self.socket.sendall(json_data.encode('utf-8') + b'\n')
            except Exception as e:
                print(f"Error sending message: {e}")

    def receive_messages(self):
        """Receive messages from server in a separate thread"""
        while self.running:
            try:
                if not self.socket:
                    break

                data = b''
                while b'\n' not in data:
                    chunk = self.socket.recv(1024)
                    if not chunk:
                        print("Server disconnected")
                        self.running = False
                        return
                    data += chunk

                message = json.loads(data.decode('utf-8').strip())
                self.handle_message(message)

            except Exception as e:
                print(f"Error receiving message: {e}")
                self.running = False
                break

    def handle_message(self, message):
        """Handle incoming messages from server"""
        msg_type = message.get(FIELD_TYPE)

        if msg_type == JOIN:
            if message.get(FIELD_STATUS) == STATUS_OK:
                print("Successfully joined server")
                self.current_screen = "lobby"
                self.input_active = False
            else:
                print("Failed to join:", message.get(FIELD_MESSAGE))

        elif msg_type == PLAYER_LIST:
            self.players_list = message.get(FIELD_PLAYERS, [])
            print(f"Available players: {self.players_list}")

        elif msg_type == SELECT_OPPONENT:
            if message.get(FIELD_STATUS) == STATUS_OK:
                self.opponent = message.get(FIELD_OPPONENT)
                print(f"Selected opponent: {self.opponent}")
                self.current_screen = "snake_config"
            else:
                print("Failed to select opponent")

        elif msg_type == SNAKE_CONFIG:
            # Received opponent's snake config
            opponent_color = message.get(FIELD_COLOR)
            if opponent_color:
                self.opponent_color = self.parse_color(opponent_color)
            print(f"Opponent color: {self.opponent_color}")

        elif msg_type == GAME_STATE:
            self.game_state = message
            if self.current_screen != "game":
                self.current_screen = "game"
            print("Game state updated")

        elif msg_type == GAME_OVER:
            self.current_screen = "game_over"
            winner = message.get(FIELD_WINNER)
            print(f"Game over! Winner: {winner}")

        elif msg_type == ERROR:
            print(f"Server error: {message.get(FIELD_MESSAGE)}")

    def parse_color(self, color_str):
        """Parse color string to RGB tuple"""
        color_map = {
            "red": RED,
            "blue": BLUE,
            "green": GREEN,
            "white": WHITE,
            "black": BLACK
        }
        return color_map.get(color_str.lower(), RED)

    def join_server(self, username):
        """Send join message to server"""
        self.username = username
        join_message = {
            FIELD_TYPE: JOIN,
            FIELD_USERNAME: username
        }
        self.send_message(join_message)

    def select_opponent(self, opponent_name):
        """Send opponent selection to server"""
        select_message = {
            FIELD_TYPE: SELECT_OPPONENT,
            FIELD_OPPONENT: opponent_name
        }
        self.send_message(select_message)

    def send_snake_config(self, color):
        """Send snake configuration to server"""
        self.snake_color = self.parse_color(color)
        config_message = {
            FIELD_TYPE: SNAKE_CONFIG,
            FIELD_COLOR: color
        }
        self.send_message(config_message)

    def send_ready(self):
        """Send ready message to server"""
        ready_message = {
            FIELD_TYPE: READY
        }
        self.send_message(ready_message)

    def send_move(self, direction):
        """Send move message to server"""
        move_message = {
            FIELD_TYPE: MOVE,
            FIELD_DIRECTION: direction
        }
        self.send_message(move_message)

    def handle_login_input(self, event):
        """Handle text input for username"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN and self.input_text.strip():
                self.join_server(self.input_text.strip())
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif len(self.input_text) < 20:  # Limit username length
                self.input_text += event.unicode

    def draw_login_screen(self):
        """Draw the login screen with text input"""
        self.screen.fill(BLACK)

        title_text = self.font.render("Πthon Arena - Enter Username", True, WHITE)
        self.screen.blit(title_text, (SCREEN_WIDTH//2 - 180, 100))

        # Input box
        input_box = pygame.Rect(SCREEN_WIDTH//2 - 150, 200, 300, 50)
        pygame.draw.rect(self.screen, WHITE, input_box, 2)

        # Render input text
        text_surface = self.font.render(self.input_text, True, WHITE)
        self.screen.blit(text_surface, (input_box.x + 10, input_box.y + 10))

        # Cursor blink
        if self.input_active and pygame.time.get_ticks() % 1000 < 500:
            cursor_x = input_box.x + 10 + text_surface.get_width()
            pygame.draw.line(self.screen, WHITE, (cursor_x, input_box.y + 10), (cursor_x, input_box.y + 40))

        join_text = self.font.render("Press ENTER to join server", True, GREEN)
        self.screen.blit(join_text, (SCREEN_WIDTH//2 - 150, 280))

    def draw_lobby_screen(self):
        """Draw the lobby screen with player list"""
        self.screen.fill(BLACK)

        title_text = self.font.render("Lobby - Select Opponent", True, WHITE)
        self.screen.blit(title_text, (50, 50))

        # Display available players
        for i, player in enumerate(self.players_list):
            player_text = self.font.render(f"{i+1}. {player}", True, WHITE)
            self.screen.blit(player_text, (50, 100 + i * 40))

        if self.players_list:
            select_text = self.font.render("Press 1-9 to select opponent", True, GREEN)
            self.screen.blit(select_text, (50, 100 + len(self.players_list) * 40 + 20))
        else:
            waiting_text = self.font.render("Waiting for other players...", True, WHITE)
            self.screen.blit(waiting_text, (50, 150))

    def draw_game_screen(self):
        """Draw the game screen"""
        self.screen.fill(BLACK)

        # Draw grid (simplified)
        for x in range(0, SCREEN_WIDTH, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (0, y), (SCREEN_WIDTH, y))

        # Draw game state (placeholder - would parse actual game data)
        status_text = self.font.render("Game in progress...", True, WHITE)
        self.screen.blit(status_text, (50, 50))

        if self.opponent:
            opponent_text = self.font.render(f"vs {self.opponent}", True, WHITE)
            self.screen.blit(opponent_text, (50, 100))

        # Movement instructions
        move_text = self.font.render("Use WASD or Arrow keys to move", True, GREEN)
        self.screen.blit(move_text, (50, SCREEN_HEIGHT - 50))

    def draw_game_over_screen(self):
        """Draw the game over screen"""
        self.screen.fill(BLACK)

        game_over_text = self.font.render("Game Over!", True, RED)
        self.screen.blit(game_over_text, (SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 - 50))

        # Would show winner and scores here
        winner_text = self.font.render("Check console for results", True, WHITE)
        self.screen.blit(winner_text, (SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2))

        restart_text = self.font.render("Press R to restart", True, GREEN)
        self.screen.blit(restart_text, (SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 50))

    def run(self):
        """Main game loop"""
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif self.current_screen == "login" and self.input_active:
                    self.handle_login_input(event)

                elif event.type == pygame.KEYDOWN:
                    if self.current_screen == "lobby":
                        # Select opponent with number keys
                        if pygame.K_1 <= event.key <= pygame.K_9:
                            index = event.key - pygame.K_1
                            if index < len(self.players_list):
                                self.select_opponent(self.players_list[index])

                    elif self.current_screen == "snake_config":
                        if event.key == pygame.K_SPACE:
                            self.send_snake_config("red")  # Auto-config for testing
                            self.send_ready()

                    elif self.current_screen == "game":
                        # Handle movement
                        if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                            self.send_move(LEFT)
                        elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                            self.send_move(RIGHT)
                        elif event.key == pygame.K_UP or event.key == pygame.K_w:
                            self.send_move(UP)
                        elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                            self.send_move(DOWN)

                    elif self.current_screen == "game_over":
                        if event.key == pygame.K_r:
                            self.current_screen = "login"
                            self.input_text = ""
                            self.input_active = True

            # Draw current screen
            if self.current_screen == "login":
                self.draw_login_screen()
            elif self.current_screen == "lobby":
                self.draw_lobby_screen()
            elif self.current_screen == "snake_config":
                self.draw_game_screen()  # Reuse for config screen
            elif self.current_screen == "game":
                self.draw_game_screen()
            elif self.current_screen == "game_over":
                self.draw_game_over_screen()

            pygame.display.flip()
            self.clock.tick(60)

        # Cleanup
        if self.socket:
            self.socket.close()
        pygame.quit()


def main():
    if len(sys.argv) < 3:
        print("Usage: python Client.py <server_ip> <server_port>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])

    client = Client(server_ip, server_port)

    if client.connect_to_server():
        client.run()
    else:
        print("Failed to connect to server")


if __name__ == "__main__":
    main()