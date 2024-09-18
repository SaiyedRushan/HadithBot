import json
import random

def load_messages():
    with open('hadiths.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# takes in actual index, not 0 indexed
def getHadithFormattedMessage(messages, chapterNumber:int):
    valid_index = (chapterNumber - 1) if chapterNumber <= len(messages) and chapterNumber > 0 else 0
    object = messages[valid_index]
    formatted_messages = []
    formatted_messages.append(f"> **{object['chapter']}**\n")
    for hadith in object['hadiths']:
        formatted_hadith = f"> {hadith}\n\n" 

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

# takes in actual index, not 0 indexed
def getNameFormattedMessage(names, number=None):
    if number is None:
        number = random.randint(1, len(names))
    validNumber = (number - 1) if (number <= len(names) and number > 0) else 0
    name = names[validNumber]
    formatted_message = ""
    formatted_message += f"> **{name['name']}**\n"
    formatted_message += f"> {name['transliteration']}\n"
    formatted_message += f"> {name['number']}\n"
    formatted_message += f"> {name['en']['meaning']}\n"
    formatted_message += f"> {name['en']['desc']}\n"
    return formatted_message