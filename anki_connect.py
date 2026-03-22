"""AnkiConnect helper — talks to Anki via its localhost API."""

import json
import urllib.request

ANKI_CONNECT_URL = "http://localhost:8765"
ANKI_CONNECT_VERSION = 6


def _request(action, **params):
    return {"action": action, "params": params, "version": ANKI_CONNECT_VERSION}


def invoke(action, **params):
    """Send a request to AnkiConnect and return the result."""
    payload = json.dumps(_request(action, **params)).encode("utf-8")
    req = urllib.request.Request(ANKI_CONNECT_URL, payload)
    response = json.load(urllib.request.urlopen(req, timeout=10))
    if len(response) != 2:
        raise Exception("AnkiConnect response has unexpected number of fields")
    if "error" not in response:
        raise Exception("AnkiConnect response missing error field")
    if "result" not in response:
        raise Exception("AnkiConnect response missing result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]


def get_deck_names():
    """Return list of deck names from Anki."""
    return invoke("deckNames")


def create_deck(name):
    """Create a new deck in Anki."""
    return invoke("createDeck", deck=name)


def get_model_names():
    """Return list of note type (model) names."""
    return invoke("modelNames")


def ensure_german_model(model_name="GermanYouTubeCard"):
    """Create the German note type if it doesn't exist. Returns model name."""
    existing = get_model_names()
    if model_name in existing:
        return model_name

    invoke(
        "createModel",
        modelName=model_name,
        inOrderFields=[
            "Sentence",
            "Image",
            "Target Phrase",
            "Sentence Audio",
            "Word Audio",
            "Dictionary Entry (English)",
            "Dictionary Entry (German)",
            "Source",
        ],
        cardTemplates=[
            {
                "Name": "Card 1",
                "Front": (
                    '<div style="font-size:24px;text-align:center;">{{Sentence}}</div>'
                    "<br>{{Image}}"
                    "<br>{{Sentence Audio}}"
                ),
                "Back": (
                    '{{FrontSide}}<hr id="answer">'
                    '<div style="font-size:20px;text-align:center;">{{Target Phrase}}</div>'
                    "<br>{{Word Audio}}"
                    '<div style="font-size:16px;margin-top:10px;">'
                    "<b>EN:</b> {{Dictionary Entry (English)}}<br>"
                    "<b>DE:</b> {{Dictionary Entry (German)}}"
                    "</div>"
                    '<div style="font-size:12px;color:gray;margin-top:8px;">{{Source}}</div>'
                ),
            }
        ],
    )
    return model_name


def add_note(deck_name, model_name, fields, audio_files=None, picture_files=None):
    """Add a note to Anki.

    audio_files: list of {"path": ..., "filename": ..., "fields": [...]}
    picture_files: list of {"path": ..., "filename": ..., "fields": [...]}
    """
    note = {
        "deckName": deck_name,
        "modelName": model_name,
        "fields": fields,
        "options": {"allowDuplicate": True},
        "audio": audio_files or [],
        "picture": picture_files or [],
    }
    return invoke("addNote", note=note)
