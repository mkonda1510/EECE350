import json
import random
import socket
import sys
import threading
import time

from protocol import *


# The server owns all real game rules. Clients only ask to move.
BOARD_WIDTH, BOARD_HEIGHT = 20, 20
TICK_RATE = 0.25
STARTING_HEALTH = 100
FOOD_HEALTH_GAIN = 15
COLLISION_HEALTH_LOSS = 25
MATCH_DURATION_SECONDS = 90

SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

players = {}
games = {}
lock = threading.Lock()


# -------------------- Network Helpers --------------------
def send_message(client_socket, message):
    client_socket.sendall(json.dumps(message).encode("utf-8") + b"\n")


def receive_message(reader):
    # Messages are newline-separated JSON objects.
    line = reader.readline()
    if not line:
        return None
    return json.loads(line.strip())


def send_to(username, msg_type, **fields):
    if username in players:
        send_message(players[username]["socket"], {FIELD_TYPE: msg_type, **fields})


def broadcast_lobbies():
    # Whenever players join/leave/finish, everyone online gets a fresh lobby list.
    with lock:
        online = [name for name, p in players.items() if p["status"] == PLAYER_STATUS_ONLINE]
        lists = {
            name: [other for other in online if other != name]
            for name in online
        }

    for name, available in lists.items():
        send_to(name, PLAYER_LIST, **{FIELD_PLAYERS: available, FIELD_STATUS: STATUS_OK})


# -------------------- Game Creation --------------------
def player_record(client_socket):
    # Each player keeps connection info plus matchmaking/game state.
    return {
        "socket": client_socket,
        "status": PLAYER_STATUS_ONLINE,
        "opponent": None,
        "snake_config": None,
        "game_id": None,
        "pending_request_from": None,
        "requested_opponent": None,
    }


def build_obstacles():
    # Small separated blocks make the board more interesting without trapping players.
    return [
        [4, 4], [4, 5], [5, 4],
        [14, 3], [15, 3], [15, 4],
        [9, 8],
        [3, 12], [3, 13], [4, 13],
        [10, 14], [11, 14], [10, 15],
        [16, 10], [16, 11], [17, 11],
    ]


def random_free_cell(occupied):
    while True:
        cell = [random.randrange(BOARD_WIDTH), random.randrange(BOARD_HEIGHT)]
        if tuple(cell) not in occupied:
            return cell


def make_game(player_one, player_two):
    # Both snakes start facing each other from opposite sides.
    snakes = {
        player_one: [[3, 5], [2, 5], [1, 5]],
        player_two: [[16, 14], [17, 14], [18, 14]],
    }
    obstacles = build_obstacles()
    occupied = {tuple(cell) for snake in snakes.values() for cell in snake}
    occupied.update(tuple(cell) for cell in obstacles)

    return {
        "id": f"{player_one}_vs_{player_two}",
        "players": [player_one, player_two],
        "snakes": snakes,
        "directions": {player_one: RIGHT, player_two: LEFT},
        "pending_directions": {},
        "health": {player_one: STARTING_HEALTH, player_two: STARTING_HEALTH},
        "colors": {
            player_one: players[player_one]["snake_config"] or "red",
            player_two: players[player_two]["snake_config"] or "blue",
        },
        "food": [random_free_cell(occupied)],
        "obstacles": obstacles,
        "winner": None,
        "running": True,
        "started_at": time.time(),
    }


def serialize_game(game):
    # This is the snapshot each client draws.
    players_data = {
        name: {
            "positions": game["snakes"][name],
            FIELD_HEALTH: game["health"][name],
            FIELD_COLOR: game["colors"][name],
        }
        for name in game["players"]
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


def broadcast_game(game):
    message = serialize_game(game)
    for name in game["players"]:
        if name in players:
            send_message(players[name]["socket"], message)


# -------------------- Game Rules --------------------
def opposite(direction):
    return {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}[direction]


def next_cell(head, direction):
    x, y = head
    moves = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
    dx, dy = moves[direction]
    return [x + dx, y + dy]


def decide_winner(game):
    one, two = game["players"]
    if game["health"][one] > game["health"][two]:
        return one
    if game["health"][two] > game["health"][one]:
        return two
    return "Draw"


def end_game(game, winner):
    game["winner"] = winner
    game["running"] = False


def update_game(game):
    # Apply only legal turns, then calculate the next head for each snake.
    for name, direction in list(game["pending_directions"].items()):
        if direction != opposite(game["directions"][name]):
            game["directions"][name] = direction
    game["pending_directions"].clear()

    new_heads = {
        name: next_cell(game["snakes"][name][0], game["directions"][name])
        for name in game["players"]
    }

    losers = find_collisions(game, new_heads)
    for name in losers:
        game["health"][name] -= COLLISION_HEALTH_LOSS

    move_safe_snakes(game, new_heads, losers)

    if time.time() - game["started_at"] >= MATCH_DURATION_SECONDS:
        end_game(game, decide_winner(game))
    else:
        dead = [name for name in game["players"] if game["health"][name] <= 0]
        if len(dead) == 2:
            end_game(game, "Draw")
        elif len(dead) == 1:
            end_game(game, [name for name in game["players"] if name not in dead][0])


def find_collisions(game, new_heads):
    # A player loses health if their next head hits anything dangerous.
    losers = set()
    obstacle_cells = {tuple(cell) for cell in game["obstacles"]}
    p1, p2 = game["players"]

    for name, head in new_heads.items():
        x, y = head
        other = p2 if name == p1 else p1

        if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
            losers.add(name)
        if tuple(head) in obstacle_cells:
            losers.add(name)
        if head in game["snakes"][name][1:] or head in game["snakes"][other]:
            losers.add(name)

    if new_heads[p1] == new_heads[p2]:
        losers.update([p1, p2])

    return losers


def move_safe_snakes(game, new_heads, losers):
    # Colliding snakes lose health and stay put; safe snakes move normally.
    food = {tuple(cell) for cell in game["food"]}

    for name in game["players"]:
        if name in losers:
            continue

        snake = game["snakes"][name]
        snake.insert(0, new_heads[name])

        if tuple(new_heads[name]) in food:
            game["health"][name] += FOOD_HEALTH_GAIN
            food.remove(tuple(new_heads[name]))
        else:
            snake.pop()

    if food:
        game["food"] = [list(cell) for cell in food]
    else:
        occupied = {tuple(cell) for snake in game["snakes"].values() for cell in snake}
        occupied.update(tuple(cell) for cell in game["obstacles"])
        game["food"] = [random_free_cell(occupied)]


def game_loop(game_id):
    while True:
        time.sleep(TICK_RATE)
        refresh_lobby = False

        with lock:
            game = games.get(game_id)
            if not game:
                return

            if any(name not in players for name in game["players"]):
                end_game(game, "Disconnected")
            elif game["running"]:
                update_game(game)
                broadcast_game(game)

            if not game["running"]:
                finish_game(game)
                games.pop(game_id, None)
                refresh_lobby = True

        if refresh_lobby:
            broadcast_lobbies()
            return


def finish_game(game):
    # Send the result, then put connected players back into the lobby.
    scores = {name: game["health"][name] for name in game["players"]}

    for name in game["players"]:
        if name in players:
            send_to(name, GAME_OVER, **{
                FIELD_STATUS: STATUS_OK,
                FIELD_WINNER: game["winner"],
                FIELD_SCORE: scores,
            })
            players[name].update({
                "status": PLAYER_STATUS_ONLINE,
                "game_id": None,
                "opponent": None,
                "pending_request_from": None,
                "requested_opponent": None,
            })


# -------------------- Client Message Handlers --------------------
def handle_join(client_socket, reader, address):
    # Keep asking for a username until it is unique, instead of closing the client.
    while True:
        message = receive_message(reader)
        if not message:
            return None
        if message.get(FIELD_TYPE) != JOIN:
            continue

        username = message.get(FIELD_USERNAME, "").strip()
        with lock:
            if not username or username in players:
                send_message(client_socket, {
                    FIELD_TYPE: ERROR,
                    FIELD_STATUS: STATUS_FAIL,
                    FIELD_MESSAGE: "Username already taken",
                })
                continue

            players[username] = player_record(client_socket)

        send_to(username, JOIN, **{FIELD_STATUS: STATUS_OK, FIELD_USERNAME: username})
        print(f"Player {username} joined from {address}")
        broadcast_lobbies()
        return username


def handle_select_opponent(username, message):
    opponent = message.get(FIELD_OPPONENT)

    with lock:
        valid = (
            username in players
            and opponent in players
            and players[opponent]["status"] == PLAYER_STATUS_ONLINE
        )
        if not valid:
            send_to(username, ERROR, **{FIELD_STATUS: STATUS_FAIL, FIELD_MESSAGE: "Opponent not found"})
            return

        players[username]["requested_opponent"] = opponent
        players[opponent]["pending_request_from"] = username

    send_to(username, SELECT_OPPONENT, **{
        FIELD_STATUS: STATUS_OK,
        FIELD_OPPONENT: opponent,
        FIELD_MESSAGE: "Request sent. Waiting for response.",
    })
    send_to(opponent, SELECT_OPPONENT, **{
        FIELD_STATUS: STATUS_PENDING,
        FIELD_OPPONENT: username,
        FIELD_MESSAGE: f"{username} wants to play with you. Accept or reject?",
    })


def handle_match_response(username, message):
    requester = message.get(FIELD_OPPONENT)
    decision = message.get(FIELD_DECISION)

    with lock:
        if username not in players or requester not in players:
            return
        if players[username].get("pending_request_from") != requester:
            return

        players[username]["pending_request_from"] = None
        players[requester]["requested_opponent"] = None

        if decision == STATUS_ACCEPT:
            players[username]["opponent"] = requester
            players[requester]["opponent"] = username

    if decision == STATUS_ACCEPT:
        send_to(requester, MATCH_RESPONSE, **{
            FIELD_STATUS: STATUS_ACCEPT,
            FIELD_OPPONENT: username,
            FIELD_MESSAGE: f"{username} accepted your request.",
        })
        send_to(username, MATCH_RESPONSE, **{
            FIELD_STATUS: STATUS_ACCEPT,
            FIELD_OPPONENT: requester,
            FIELD_MESSAGE: "You accepted the match request.",
        })
    else:
        send_to(requester, MATCH_RESPONSE, **{
            FIELD_STATUS: STATUS_REJECT,
            FIELD_OPPONENT: username,
            FIELD_MESSAGE: f"{username} rejected your request.",
        })
        send_to(username, MATCH_RESPONSE, **{
            FIELD_STATUS: STATUS_REJECT,
            FIELD_OPPONENT: requester,
            FIELD_MESSAGE: "You rejected the match request.",
        })


def handle_ready(username):
    # The match starts only after both accepted players press SPACE.
    with lock:
        if username not in players:
            return

        opponent = players[username]["opponent"]
        if not opponent or opponent not in players:
            return

        players[username]["status"] = PLAYER_STATUS_WAITING
        if players[opponent]["status"] != PLAYER_STATUS_WAITING:
            return

        game = make_game(username, opponent)
        games[game["id"]] = game

        for name in game["players"]:
            players[name]["status"] = PLAYER_STATUS_IN_GAME
            players[name]["game_id"] = game["id"]

        broadcast_game(game)

    threading.Thread(target=game_loop, args=(game["id"],), daemon=True).start()


def handle_message(username, message):
    msg_type = message.get(FIELD_TYPE)

    if msg_type == SELECT_OPPONENT:
        handle_select_opponent(username, message)
    elif msg_type == MATCH_RESPONSE:
        handle_match_response(username, message)
    elif msg_type == SNAKE_CONFIG:
        with lock:
            if username in players:
                players[username]["snake_config"] = message.get(FIELD_COLOR, "red")
    elif msg_type == READY:
        handle_ready(username)
    elif msg_type == MOVE:
        game_id = message.get(FIELD_GAME_ID)
        with lock:
            if game_id in games and username in players:
                games[game_id]["pending_directions"][username] = message.get(FIELD_DIRECTION)
    elif msg_type == DISCONNECT:
        raise ConnectionError("Client disconnected")


def client_thread(client_socket, address):
    username = None
    reader = client_socket.makefile("r", encoding="utf-8")
    try:
        username = handle_join(client_socket, reader, address)
        while username:
            message = receive_message(reader)
            if not message:
                break
            handle_message(username, message)
    except Exception as e:
        print(f"Error with {username or address}: {e}")
    finally:
        cleanup_player(username)
        reader.close()
        client_socket.close()


def cleanup_player(username):
    if not username:
        return

    with lock:
        if username not in players:
            return

        game_id = players[username]["game_id"]
        opponent = players[username]["opponent"]

        if game_id in games:
            end_game(games[game_id], opponent if opponent in players else "Disconnected")

        for info in players.values():
            if info.get("pending_request_from") == username:
                info["pending_request_from"] = None
            if info.get("requested_opponent") == username:
                info["requested_opponent"] = None

        players.pop(username, None)

    print(f"Player {username} disconnected")
    broadcast_lobbies()


# -------------------- Server Start --------------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_IP, SERVER_PORT))
server.listen()
print(f"Server started on {SERVER_IP}:{SERVER_PORT}")

try:
    while True:
        client_socket, address = server.accept()
        print(f"New connection from {address}")
        threading.Thread(target=client_thread, args=(client_socket, address), daemon=True).start()
except KeyboardInterrupt:
    print("Server shutting down...")
finally:
    server.close()
