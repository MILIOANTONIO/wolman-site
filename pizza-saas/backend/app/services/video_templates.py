"""
Template Reel data-driven (Promoziona milestone 2): pochi template fissi,
definiti qui in codice - non personalizzabili dal titolare per ora, non
serve una tabella finche' non lo diventano. Ogni template descrive come
video_engine.py deve animare l'unica foto sorgente e sovrapporre il testo,
non contiene testo pronto (quello lo scrive l'owner/AI a parte).
"""
from typing import TypedDict


class VideoTemplate(TypedDict):
    id: str
    name: str
    category: str
    duration: int  # secondi
    ken_burns: str  # "zoom_in" | "zoom_out" | "pan_left" | "pan_right"
    text_position: str  # "bottom" | "center" | "top"
    accent_color: str  # colore del testo/overlay, hex


TEMPLATES: list[VideoTemplate] = [
    {
        "id": "pizza_del_giorno",
        "name": "Pizza del giorno",
        "category": "menu",
        "duration": 12,
        "ken_burns": "zoom_in",
        "text_position": "bottom",
        "accent_color": "#E5533F",
    },
    {
        "id": "offerta_speciale",
        "name": "Offerta speciale",
        "category": "promo",
        "duration": 10,
        "ken_burns": "zoom_out",
        "text_position": "center",
        "accent_color": "#C99A4E",
    },
    {
        "id": "appena_sfornata",
        "name": "Pizza appena sfornata",
        "category": "menu",
        "duration": 12,
        "ken_burns": "pan_right",
        "text_position": "bottom",
        "accent_color": "#E5533F",
    },
    {
        "id": "dietro_le_quinte",
        "name": "Dietro le quinte",
        "category": "locale",
        "duration": 15,
        "ken_burns": "pan_left",
        "text_position": "top",
        "accent_color": "#F1E6D6",
    },
]

TEMPLATES_BY_ID: dict[str, VideoTemplate] = {t["id"]: t for t in TEMPLATES}
