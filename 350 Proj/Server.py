import json
import random
import socket
import sys
import threading
import time

from protocol import *

# Board dimensions and game settings.
BOARD_WIDTH = 20
BOARD_HEIGHT = 20
TICK_RATE = 0.25
STARTING_HEALTH = 100
FOOD_HEALTH_GAIN = 15
COLLISION_HEALTH_LOSS = 25
MATCH_DURATION_SECONDS = 90

# Server configuration.
SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

players = {}
games = {}
lock = threading.Lock()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_IP, SERVER_PORT))
server.listen()
print(f"Server started on {SERVER_IP}:{SERVER_PORT}")


def send_message(client_socket, message):
    json_data = json.dumps(message)
    client_socket.sendall(json_data.encode("utf-8") + b"\n")


def receive_message(client_socket):
    data = b""
    while b"\n" not in data:
        chunk = client_socket.recv(1024)
        if not chunk:
            return None
        data += chunk
    return json.loads(data.decode("utf-8").strip())


def send_player_list(requesting_player):
    with lock:
        if requesting_player not in players:
            return

        available_players = [
            name for name, info in players.items()
            if name != requesting_player and info["status"] == PLAYER_STATUS_ONLINE
        ]

        message = {
            FIELD_TYPE: PLAYER_LIST,
            FIELD_PLAYERS: available_players,
            FIELD_STATUS: STATUS_OK,
        }

        target_socket = players[requesting_player]["socket"]

    send_message(target_socket, message)


def broadcast_player_lists():
    # Refresh lobby lists for all online users.
    with lock:
        online_users = [
            name for name, info in players.items()
            if info["status"] == PLAYER_STATUS_ONLINE
        ]

    for username in online_users:
        send_player_list(username)


def random_free_cell(occupied):
    # Pick a cell that is not already used.
    while True:
        cell = [random.randint(0, BOARD_WIDTH - 1), random.randint(0, BOARD_HEIGHT - 1)]
        if tuple(cell) not in occupied:
            return cell


def build_obstacles():
    # Fixed obstacles keep the layout simple.
    return [[8, 8], [8, 9], [8, 10], [11, 8], [11, 9], [11, 10]]


def create_food(occupied):
    return [random_free_cell(occupied)]


def build_game_state(player_one, player_two):
    # Start both snakes on opposite sides.
    snake_one = [[3, 5], [2, 5], [1, 5]]
    snake_two = [[16, 14], [17, 14], [18, 14]]
    obstacles = build_obstacles()

    occupied = {tuple(cell) for cell in snake_one + snake_two + obstacles}
    food = create_food(occupied)

    game_id = f"{player_one}_vs_{player_two}"
    return {
        "id": game_id,
        "players": [player_one, player_two],
        "snakes": {
            player_one: snake_one,
            player_two: snake_two,
        },
        "directions": {
            player_one: RIGHT,
            player_two: LEFT,
        },
        "pending_directions": {},
        "health": {
            player_one: STARTING_HEALTH,
            player_two: STARTING_HEALTH,
        },
        "colors": {
            player_one: players[player_one]["snake_config"] or "red",
            player_two: players[player_two]["snake_config"] or "blue",
        },
        "food": food,
        "obstacles": obstacles,
        "winner": None,
        "running": True,
        "started_at": time.time(),
    }


def serialize_game_state(game):
    # Convert internal state into one message for clients.
    players_data = {}
    for username in game["players"]:
        players_data[username] = {
            "positions": game["snakes"][username],
            FIELD_HEALTH: game["health"][username],
            FIELD_COLOR: game["colors"][username],
        }

    time_left = max(0, MATCH_DURATION_SECONDS - int(time.time() - game["started_at"]))

    return {
        FIELD_TYPE: GAME_STATE,
        FIELD_STATUS: STATUS_OK,
        FIELD_GAME_ID: game["id"],
        FIELD_BOARD: {"width": BOARD_WIDTH, "height": BOARD_HEIGHT},
        FIELD_PLAYERS_DATA: players_data,
        FIELD_FOOD: game["food"],
        FIELD_OBSTACLES: game["obstacles"],
        FIELD_TIME_LEFT: time_left,
        FIELD_SPECTATORS: 0,
    }


def broadcast_game_state(game):
    # Only send updates to players who are still connected.
    message = serialize_game_state(game)
    for username in game["players"]:
        if username in players:
            send_message(players[username]["socket"], message)


def opposite_direction(direction):
    return {
        UP: DOWN,
        DOWN: UP,
        LEFT: RIGHT,
        RIGHT: LEFT,
    }[direction]


def next_head_position(head, direction):
    x, y = head

    if direction == UP:
        return [x, y - 1]
    if direction == DOWN:
        return [x, y + 1]
    if direction == LEFT:
        return [x - 1, y]
    return [x + 1, y]


def apply_pending_directions(game):
    # Apply the latest requested direction, unless it reverses instantly.
    for username, direction in list(game["pending_directions"].items()):
        current_direction = game["directions"][username]
        if direction != opposite_direction(current_direction):
            game["directions"][username] = direction

    game["pending_directions"].clear()


def update_game(game):
    # First update both directions.
    apply_pending_directions(game)

    new_heads = {}
    for username in game["players"]:
        new_heads[username] = next_head_position(
            game["snakes"][username][0],
            game["directions"][username],
        )

    losers = []

    # Check wall collisions first.
    for username, head in new_heads.items():
        x, y = head
        if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
            losers.append(username)

    # Check obstacle collisions.
    obstacle_cells = {tuple(cell) for cell in game["obstacles"]}
    for username, head in new_heads.items():
        if tuple(head) in obstacle_cells and username not in losers:
            losers.append(username)

    # Check snake collisions.
    for username in game["players"]:
        other = game["players"][1] if game["players"][0] == username else game["players"][0]

        own_body = game["snakes"][username][1:]
        other_body = game["snakes"][other]

        if new_heads[username] in own_body and username not in losers:
            losers.append(username)

        if new_heads[username] in other_body and username not in losers:
            losers.append(username)

    # If both heads land on the same cell, both lose health.
    player1, player2 = game["players"]
    if new_heads[player1] == new_heads[player2]:
        if player1 not in losers:
            losers.append(player1)
        if player2 not in losers:
            losers.append(player2)

    # Apply collision damage.
    for username in losers:
        game["health"][username] -= COLLISION_HEALTH_LOSS

    food_cells = {tuple(cell) for cell in game["food"]}

    for username in game["players"]:
        # Only move the snake if it did not hit something.
        if username not in losers:
            snake = game["snakes"][username]
            snake.insert(0, new_heads[username])

            if tuple(new_heads[username]) in food_cells:
                game["health"][username] += FOOD_HEALTH_GAIN
                food_cells.remove(tuple(new_heads[username]))
            else:
                snake.pop()

    if not food_cells:
        occupied = {
            tuple(cell)
            for snake in game["snakes"].values()
            for cell in snake
        }
        occupied.update(tuple(cell) for cell in game["obstacles"])
        game["food"] = create_food(occupied)
    else:
        game["food"] = [list(cell) for cell in food_cells]

    # End game if someone dies.
    dead_players = [u for u in game["players"] if game["health"][u] <= 0]
    if dead_players:
        alive_players = [u for u in game["players"] if u not in dead_players]
        winner = alive_players[0] if alive_players else "Draw"
        game["running"] = False
        game["winner"] = winner
        return

    # End game when the time is over.
    if time.time() - game["started_at"] >= MATCH_DURATION_SECONDS:
        player_one, player_two = game["players"]
        health_one = game["health"][player_one]
        health_two = game["health"][player_two]

        if health_one > health_two:
            winner = player_one
        elif health_two > health_one:
            winner = player_two
        else:
            winner = "Draw"

        game["running"] = False
        game["winner"] = winner


def game_loop(game_id):
    while True:
        time.sleep(TICK_RATE)

        with lock:
            game = games.get(game_id)

            if not game or not game["running"]:
                return

            # Stop the game if one player disconnected.
            for username in game["players"]:
                if username not in players:
                    game["running"] = False
                    game["winner"] = "Disconnected"
                    return

            update_game(game)
            broadcast_game_state(game)

            if not game["running"]:
                final_scores = {
                    username: game["health"][username]
                    for username in game["players"]
                }

                for username in game["players"]:
                    if username in players:
                        send_message(players[username]["socket"], {
                            FIELD_TYPE: GAME_OVER,
                            FIELD_STATUS: STATUS_OK,
                            FIELD_WINNER: game["winner"],
                            FIELD_SCORE: final_scores,
                        })

                for username in game["players"]:
                    if username in players:
                        players[username]["status"] = PLAYER_STATUS_ONLINE
                        players[username]["game_id"] = None
                        players[username]["opponent"] = None

                if game_id in games:
                    del games[game_id]

                broadcast_player_lists()
                return


def handle_client(client_socket, address):
    username = None
    try:
        message = receive_message(client_socket)

        if message and message.get(FIELD_TYPE) == JOIN:
            username = message.get(FIELD_USERNAME)

            with lock:
                if username in players:
                    send_message(client_socket, {
                        FIELD_TYPE: ERROR,
                        FIELD_MESSAGE: "Username already taken",
                        FIELD_STATUS: STATUS_FAIL,
                    })
                    client_socket.close()
                    return

                players[username] = {
                    "socket": client_socket,
                    "status": PLAYER_STATUS_ONLINE,
                    "opponent": None,
                    "snake_config": None,
                    "health": STARTING_HEALTH,
                    "game_id": None,
                }

            send_message(client_socket, {
                FIELD_TYPE: JOIN,
                FIELD_STATUS: STATUS_OK,
                FIELD_USERNAME: username,
            })

            print(f"Player {username} joined from {address}")
            broadcast_player_lists()
            handle_messages(client_socket, username)

    except Exception as e:
        print(f"Error handling client {address}: {e}")

    finally:
        if username:
            with lock:
                if username in players:
                    game_id = players[username]["game_id"]
                    opponent = players[username]["opponent"]

                    # If a player disconnects during a match, end that match.
                    if game_id in games:
                        games[game_id]["running"] = False
                        if opponent in players:
                            games[game_id]["winner"] = opponent
                        else:
                            games[game_id]["winner"] = "Disconnected"

                    players.pop(username, None)

            print(f"Player {username} disconnected")
            broadcast_player_lists()

        client_socket.close()


def handle_messages(client_socket, username):
    while True:
        try:
            message = receive_message(client_socket)
            if not message:
                break

            msg_type = message.get(FIELD_TYPE)

            if msg_type == SELECT_OPPONENT:
                handle_select_opponent(username, message)
            elif msg_type == SNAKE_CONFIG:
                handle_snake_config(username, message)
            elif msg_type == READY:
                handle_ready(username, message)
            elif msg_type == MOVE:
                handle_move(username, message)
            elif msg_type == DISCONNECT:
                handle_disconnect(username)
                break

        except Exception as e:
            print(f"Error receiving message from {username}: {e}")
            break


def handle_select_opponent(username, message):
    opponent = message.get(FIELD_OPPONENT)

    with lock:
        if opponent not in players or players[opponent]["status"] != PLAYER_STATUS_ONLINE:
            send_message(players[username]["socket"], {
                FIELD_TYPE: ERROR,
                FIELD_MESSAGE: "Opponent not found",
                FIELD_STATUS: STATUS_FAIL,
            })
            return

        players[username]["opponent"] = opponent
        players[opponent]["opponent"] = username

    send_message(players[username]["socket"], {
        FIELD_TYPE: SELECT_OPPONENT,
        FIELD_STATUS: STATUS_OK,
        FIELD_OPPONENT: opponent,
    })

    send_message(players[opponent]["socket"], {
        FIELD_TYPE: SELECT_OPPONENT,
        FIELD_STATUS: STATUS_OK,
        FIELD_OPPONENT: username,
    })


def handle_snake_config(username, message):
    print(f"{username} sent snake config: {message}")
    with lock:
        if username in players:
            players[username]["snake_config"] = message.get(FIELD_COLOR, "red")


def handle_ready(username, message):
    with lock:
        if username not in players:
            return

        opponent = players[username]["opponent"]

        if not opponent or opponent not in players:
            return

        players[username]["status"] = PLAYER_STATUS_WAITING

        if players[opponent]["status"] != PLAYER_STATUS_WAITING:
            return

        game = build_game_state(username, opponent)
        games[game["id"]] = game

        players[username]["game_id"] = game["id"]
        players[opponent]["game_id"] = game["id"]
        players[username]["status"] = PLAYER_STATUS_IN_GAME
        players[opponent]["status"] = PLAYER_STATUS_IN_GAME

        broadcast_game_state(game)

    thread = threading.Thread(target=game_loop, args=(game["id"],), daemon=True)
    thread.start()


def handle_move(username, message):
    direction = message.get(FIELD_DIRECTION)
    game_id = message.get(FIELD_GAME_ID)

    with lock:
        if game_id in games and username in players:
            games[game_id]["pending_directions"][username] = direction


def handle_disconnect(username):
    print(f"{username} disconnected")


try:
    while True:
        client_socket, address = server.accept()
        print(f"New connection from {address}")
        thread = threading.Thread(target=handle_client, args=(client_socket, address), daemon=True)
        thread.start()
except KeyboardInterrupt:
    print("Server shutting down...")
finally:
    server.close()
