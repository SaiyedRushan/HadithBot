from typing import Dict
from dataclasses import dataclass
import re


@dataclass
class Name:
    number: int
    name: str
    transliteration: str
    found: str
    en: Dict[str, str]
    fr: Dict[str, str]


def getHadithFormattedMessage(hadith) -> list[str]:
    formatted_messages = []
    formatted_messages.append(f"> ### Book: {hadith['books_metadata']['english_title']} - Chapter: {hadith['chapters']['english']}\n")
    formatted_hadith = f"> #{hadith['id_in_book']} - {hadith['english_narrator']} {hadith['english_text']}\n\n"
    formatted_hadith = re.sub(r'\s+', ' ', formatted_hadith).strip()

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


def getNameFormattedMessage(name) -> str:
    formatted_message = ""
    formatted_message += f"> ### ({name.number}) - {name.name} - {name.transliteration}\n"
    formatted_message += f"> {name.en['meaning']} - {name.en['desc']}\n"
    return formatted_message
