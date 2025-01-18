import json
import random

def load_messages():
    with open('hadiths.json', 'r', encoding='utf-8') as f:
        return json.load(f)
    
def getHadithFormattedMessage(hadith) -> list[str]:
    formatted_messages = []
    formatted_messages.append(f"> ### {hadith.chapter}\n")
    for h in hadith.hadiths:
        formatted_hadith = f"> {h}\n\n" 

        # while formatted_hadith is not empty
        while formatted_hadith:
            if len(formatted_hadith) <= 2000:
                formatted_messages.append(formatted_hadith)
                formatted_hadith = ""
            else:
                split_index = find_last_newline(formatted_hadith[:2000])
                if split_index == -1:
                    split_index = 2000
                formatted_messages.append(formatted_hadith[:split_index])
                formatted_hadith = f'> {formatted_hadith[split_index:].lstrip()}'

    return formatted_messages

def find_last_newline(message: str):
    last_newline = message.rfind('\n\n')
    if last_newline == -1:
        last_newline = message.rfind('.')
    return last_newline + 2

def loadNames():
    with open('99names.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def getNameFormattedMessage(name) -> str:
    formatted_message = ""
    formatted_message += f"> ### ({name.number}) - {name.name} - {name.transliteration}\n"
    formatted_message += f"> {name.en['meaning']} - {name.en['desc']}\n"
    return formatted_message