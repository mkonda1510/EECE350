import socket #network communication
import threading #handling multiple clients concurrently
import json #for encoding and decoding messages
from protocol import * #importing protocol constants

SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 8000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # creating stream socket
server.bind((SERVER_IP, SERVER_PORT))  # binding the server

players = {}  # Track all connected players
games = {}    # Track active games between two players
lock = threading.Lock()  # Prevent conflicts when multiple threads access shared data

server.listen() # Start listening for incoming connections


def send_message(client_socket, message):
    json_data = json.dumps(message) # Convert dictionary to JSON string
    client_socket.sendall(json_data.encode('utf-8') + b'\n') # Send message with newline as delimiter

def receive_message(client_socket):
    data = b''
    while b'\n' not in data: # Read until \n is found
        chunk = client_socket.recv(1024) # Receive data in chunks
        if not chunk:
            return None # close connection (client disconnected)
        data += chunk
    return json.loads(data.decode('utf-8').strip()) # Convert JSON string back to dictionary

def send_player_list(requesting_player):
    #send list of online players to the requesting player
    with lock: #Use lock to read players dictionary safely
        available_players = [name for name in players.keys() if name != requesting_player and players[name]['status'] == PLAYER_STATUS_ONLINE]

        message = {FIELD_TYPE: PLAYER_LIST, FIELD_PLAYERS: available_players}

    #send message to the requesting player
    send_message(players[requesting_player]['socket'], message)

def handle_client(client_socket,address):
    #handle 1 client connection from join to disconnect
    USERNAME = None
    try:
        # First message should be JOIN with username
        message = receive_message(client_socket)

        if message and message.get(FIELD_TYPE) == JOIN:
            username = message.get(FIELD_USERNAME)
            # Check if username used:
            with lock:
                if username in players:  # Send error if username already taken
                    send_message(client_socket, {
                        FIELD_TYPE: ERROR,
                        FIELD_MESSAGE: "Username already taken",
                        FIELD_STATUS: STATUS_FAIL
                    })
                    client_socket.close()
                    return

                # Add new player to server
                players[username] = {
                    "socket": client_socket,
                    "status": PLAYER_STATUS_ONLINE,
                    "opponent": None,
                    "snake_config": None,
                    "health": 100
                }

            # Confirm join
            send_message(client_socket, {
                FIELD_TYPE: JOIN,
                FIELD_STATUS: STATUS_OK,
                FIELD_USERNAME: username
            })
            print(f"Player {username} joined from {address}")

            send_player_list(username)  # Send list of online players

            handle_messages(client_socket, username)  # Handle client's messages

    except Exception as e:
        print(f"Error handling client {address}: {e}")

    finally:
        # Close connection when client leaves
        if username:
            with lock:
                players.pop(username, None)  # Remove username from dictionary
            print(f"Player {username} disconnected")
        client_socket.close()  # Close socket connection


def handle_messages(client_socket, username):
    """Handle incoming messages from a client"""
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


# Stub handler functions (replace with real implementations later)
def handle_select_opponent(username, message):
    """Handle opponent selection - TODO: implement matchmaking"""
    print(f"{username} wants to select opponent: {message.get(FIELD_OPPONENT)}")
    #  Add matchmaking logic

def handle_snake_config(username, message):
    """Handle snake configuration - TODO: implement"""
    print(f"{username} sent snake config: {message}")
    #  Store snake config

def handle_ready(username, message):
    """Handle ready status - TODO: implement"""
    print(f"{username} is ready")
    #  Start game when both ready

def handle_move(username, message):
    """Handle move - TODO: implement game logic"""
    print(f"{username} moved: {message.get(FIELD_DIRECTION)}")
    #  Update game state

def handle_disconnect(username):
    """Handle disconnection - TODO: implement"""
    print(f"{username} disconnected")
    #  Notify opponent


#MAIN LOOP

try:
    print(f"Server started on {SERVER_IP}:{SERVER_PORT}")
    while True:
        client_socket, address = server.accept()
        print(f"New connection from {address}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket, address))
        client_thread.daemon = True
        client_thread.start()
except KeyboardInterrupt:
    print("Server shutting down...")
finally:
    server.close()