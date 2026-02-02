# ===== CONSTANTES =====
VOICE_BASE_RANGES = {
    "Soprano": ("C4", "C6"),
    "Mezzo-soprano": ("A3", "A5"),
    "Contralto": ("F3", "E5"),
    "Tenor": ("C3", "A4"),
    "Barítono": ("A2", "F4"),
    "Baixo": ("E2", "E4"),
}

NOTE_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1,
    'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4,
    'F': 5, 'F#': 6, 'Gb': 6,
    'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10,
    'B': 11, 'Cb': 11
}
VOICES = ["Soprano", "Mezzo-soprano", "Contralto", "Tenor", "Barítono", "Baixo"]

SEMITONE_TO_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

DATA_FILE = "coristas_data.json"