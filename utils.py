import json

# Load messages from JSON file
def load_messages():
    with open('hadiths.json', 'r', encoding='utf-8') as f:
        return json.load(f)
# Get the next message
def get_next_message(messages, current_index):
    if current_index >= len(messages):
        return messages[0], 1
    return messages[current_index], current_index + 1

def find_last_newline(message: str):
    last_newline = message.rfind('\n\n')
    if last_newline == -1:
        last_newline = message.rfind('.')
    return last_newline + 2