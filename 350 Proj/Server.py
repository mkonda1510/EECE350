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
    client_socket.sendall(json_data.encode('utf-8')+b'\n') # Send message with newline as delimiter
def recieve_message(client_socket):
    data = b''
    while b'\n' not in data: # Read until newline is found
        chunk = client_socket.recv(1024) # Receive data in chunks
        if not chunk:
            return None # Connection closed
        data += chunk
    return json.loads(data.decode('utf-8').strip()) # Convert JSON string back to dictionary

def send_player_list(requesting_player):
    #send list of online players to the requesting player
    with lock: #Use lock to read players dictionary safely
        available_players = [name for name in players.keys() if name != requesting_player and players[name]['status'] == PLAYER_STATUS_ONLINE]

        message = { "type ": PLAYER_LIST, "players": available_players}

    #send message to the requesting player
    send_message(players[requesting_player]['socket'], message)