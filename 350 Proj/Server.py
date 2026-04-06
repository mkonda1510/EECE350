import socket
import threading
import json
from protocol import *

SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 8000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_IP, SERVER_PORT))

players = {}
games = {}
lock = threading.Lock()

server.listen()


def send_message(client_socket, message):
    json_data = json.dumps(message)
    client_socket.sendall(json_data.encode('utf-8') + b'\n')


def receive_message(client_socket):
    data = b''
    while b'\n' not in data:
        chunk = client_socket.recv(1024)
        if not chunk:
            return None
        data += chunk
    return json.loads(data.decode('utf-8').strip())


def send_player_list(requesting_player):
    with lock:
        available_players = [
            name for name in players.keys()
            if name != requesting_player and players[name]['status'] == PLAYER_STATUS_ONLINE
        ]

        message = {
            FIELD_TYPE: PLAYER_LIST,
            FIELD_PLAYERS: available_players,
            FIELD_STATUS: STATUS_OK
        }

    send_message(players[requesting_player]['socket'], message)


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
                        FIELD_STATUS: STATUS_FAIL
                    })
                    client_socket.close()
                    return

                players[username] = {
                    "socket": client_socket,
                    "status": PLAYER_STATUS_ONLINE,
                    "opponent": None,
                    "snake_config": None,
                    "health": 100,
                    "game_id": None
                }

            send_message(client_socket, {
                FIELD_TYPE: JOIN,
                FIELD_STATUS: STATUS_OK,
                FIELD_USERNAME: username
            })

            print(f"Player {username} joined from {address}")
            send_player_list(username)
            handle_messages(client_socket, username)

    except Exception as e:
        print(f"Error handling client {address}: {e}")

    finally:
        if username:
            with lock:
                players.pop(username, None)
            print(f"Player {username} disconnected")
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
        if opponent not in players:
            send_message(players[username]['socket'], {
                FIELD_TYPE: ERROR,
                FIELD_MESSAGE: "Opponent not found",
                FIELD_STATUS: STATUS_FAIL
            })
            return

        players[username]['opponent'] = opponent
        players[opponent]['opponent'] = username

    send_message(players[username]['socket'], {
        FIELD_TYPE: SELECT_OPPONENT,
        FIELD_STATUS: STATUS_OK,
        FIELD_OPPONENT: opponent
    })

    send_message(players[opponent]['socket'], {
        FIELD_TYPE: SELECT_OPPONENT,
        FIELD_STATUS: STATUS_OK,
        FIELD_OPPONENT: username
    })


def handle_snake_config(username, message):
    print(f"{username} sent snake config: {message}")
    players[username]['snake_config'] = message.get(FIELD_COLOR)


def handle_ready(username, message):
    opponent = players[username]['opponent']

    if not opponent:
        return

    players[username]['status'] = PLAYER_STATUS_WAITING

    if players[opponent]['status'] == PLAYER_STATUS_WAITING:
        game_id = f"{username}_vs_{opponent}"

        players[username]['game_id'] = game_id
        players[opponent]['game_id'] = game_id

        send_message(players[username]['socket'], {
            FIELD_TYPE: GAME_STATE,
            FIELD_STATUS: STATUS_OK,
            FIELD_GAME_ID: game_id
        })

        send_message(players[opponent]['socket'], {
            FIELD_TYPE: GAME_STATE,
            FIELD_STATUS: STATUS_OK,
            FIELD_GAME_ID: game_id
        })


def handle_move(username, message) :
    direction = message.get(FIELD_DIRECTION)
    game_id = message.get(FIELD_GAME_ID)

    print(f"{username} moved: {direction} in game {game_id}")


def handle_disconnect(username):
    print(f"{username} disconnected")


print(f"Server started on {SERVER_IP}:{SERVER_PORT}")

try:
    while True:
        client_socket, address = server.accept()
        print(f"New connection from {address}")
        thread = threading.Thread(target=handle_client, args=(client_socket, address))
        thread.daemon = True
        thread.start()
except KeyboardInterrupt:
    print("Server shutting down...")
finally:
    server.close()