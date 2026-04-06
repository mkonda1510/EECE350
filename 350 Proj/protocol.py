#Protocols
# Message types

JOIN = "JOIN"
PLAYER_LIST = "PLAYER_LIST"
SELECT_OPPONENT = "SELECT_OPPONENT"
MOVE = "MOVE"
GAME_STATE = "GAME_STATE"
GAME_OVER = "GAME_OVER"
READY ="READY"
DISCONNECT = "DISCONNECT"
ERROR = "ERROR"

# Directions
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"

# Common message fields
FIELD_TYPE = "TYPE"
FIELD_USERNAME = "USERNAME"
FIELD_GAME_ID = "GAME_ID"
FIELD_DIRECTION = "DIRECTION"
FIELD_PLAYERS = "PLAYERS"
FIELD_OPPONENT = "OPPONENT"
FIELD_BOARD = "BOARD"
FIELD_SCORE = "SCORE"
FIELD_WINNER = "WINNER"
FIELD_MESSAGE = "MESSAGE"

# Error codes
ERROR_PLAYER_NOT_FOUND = "PLAYER_NOT_FOUND"
ERROR_GAME_FULL = "GAME_FULL"
ERROR_GAME_NOT_FOUND = "GAME_NOT_FOUND"
ERROR_INVALID_STATE = "INVALID_STATE"

# Game states
GAME_STATE_LOBBY = "LOBBY"
GAME_STATE_WAITING = "WAITING"
GAME_STATE_PLAYING = "PLAYING"
GAME_STATE_FINISHED = "FINISHED"

# Player statuses
PLAYER_STATUS_ONLINE = "ONLINE"
PLAYER_STATUS_OFFLINE = "OFFLINE"
PLAYER_STATUS_IN_GAME = "IN_GAME"
PLAYER_STATUS_WAITING = "WAITING"

# Message Status Codes
STATUS_OK = "OK"
STATUS_FAIL = "FAIL"
STATUS_INVALID = "INVALID"

# MESSAGE FORMATS (examples of what each message contains)
# JOIN: {"type": "join", "username": "player_name"}
# PLAYER_LIST: {"type": "player_list", "players": ["p1", "p2", ...]}
# SELECT_OPPONENT: {"type": "select_opponent", "opponent": "player_name"}
# READY: {"type": "ready", "game_id": "12345"}
# MOVE: {"type": "move", "game_id": "12345", "direction": "UP"}
# GAME_STATE: {"type": "game_state", "board": [...], "score": {...}}
# GAME_OVER: {"type": "game_over", "winner": "player_name"}
# DISCONNECT: {"type": "disconnect", "player": "player_name"}
# ERROR: {"type": "error", "message": "error description"}