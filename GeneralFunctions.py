import re
from Constants import SEMITONE_TO_SHARP, NOTE_TO_SEMITONE, VOICES, VOICE_BASE_RANGES

# ===== FUNÇÕES DE NOTA =====
# Função para transpor uma nota
def transpose_note(note, semitones):
    """Transpõe uma nota musical por um número de semitons"""
    index = SEMITONE_TO_SHARP.index(note)
    transposed_index = (index + semitones) % 12
    return SEMITONE_TO_SHARP[transposed_index]


def transpose_key(root_name: str, mode: str, semitones: int) -> (str, str):
    root = root_name.strip().capitalize()
    if root not in NOTE_TO_SEMITONE:
        root = root_name.strip().replace('b', 'b').replace('#', '#')
        if root not in NOTE_TO_SEMITONE:
            raise ValueError(f"Root inválido: {root_name}")
    root_pc = NOTE_TO_SEMITONE[root]
    new_pc = (root_pc + semitones) % 12
    new_root = SEMITONE_TO_SHARP[new_pc]
    return new_root, mode

def midi_to_note(n: int) -> str:
    if not (0 <= n <= 127):
        raise ValueError(f"MIDI fora do range: {n}")
    octave = (n // 12) - 1
    semitone = n % 12
    return f"{SEMITONE_TO_SHARP[semitone]}{octave}"

def note_to_midi(note_str: str) -> int:
    s = note_str.strip().replace(' ', '')
    m = re.match(r'^([A-Ga-g])([#b]?)(-?\d+)$', s)
    if not m:
        raise ValueError(f"Nota inválida: '{note_str}'")
    note = m.group(1).upper()
    acc = m.group(2)
    octa = int(m.group(3))

    key = f"{note}{acc}" if acc else note
    if key not in NOTE_TO_SEMITONE:
        if acc:
            key = note
        if key not in NOTE_TO_SEMITONE:
            raise ValueError(f"Nota inválida: '{note_str}'")

    semitone = NOTE_TO_SEMITONE[key]
    midi = 12 * (octa + 1) + semitone
    if midi < 0 or midi > 127:
        raise ValueError(f"Nota fora do range MIDI (0-127): '{note_str}'")
    return midi

# ===== ANÁLISE DE RANGES =====
def analyze_ranges_with_penalty(original_root: str, original_mode: str, piece_ranges: dict) -> dict:
    """Análise com penalidade para encontrar melhor transposição"""
    voices = VOICES
    piece_mins = {}
    piece_maxs = {}

    for v in voices:
        if v in piece_ranges:
            mn, mx = piece_ranges[v]
            piece_mins[v] = note_to_midi(mn)
            piece_maxs[v] = note_to_midi(mx)
        else:
            piece_mins[v] = note_to_midi("A4")
            piece_maxs[v] = note_to_midi("A5")

    voice_base_mins = {}
    voice_base_maxs = {}
    for v in voices:
        mn, mx = VOICE_BASE_RANGES[v]
        voice_base_mins[v] = note_to_midi(mn)
        voice_base_maxs[v] = note_to_midi(mx)

    T_values = list(range(-24, 25))
    best = None
    all_feasible = []

    for T in T_values:
        offsets = {}
        penalties = {}
        total_penalty = 0

        for v in voices:
            min_i = piece_mins[v]
            max_i = piece_maxs[v]

            best_O = None
            best_penalty = float('inf')

            for O in range(-4, 5):
                low = min_i + T + 12 * O
                high = max_i + T + 12 * O
                pen = max(0, voice_base_mins[v] - low) + max(0, high - voice_base_maxs[v])

                if pen < best_penalty or (pen == best_penalty and (best_O is None or abs(O) < abs(best_O))):
                    best_O = O
                    best_penalty = pen

            offsets[v] = best_O
            penalties[v] = best_penalty
            total_penalty += best_penalty

        all_feasible.append((T, total_penalty, offsets))
        score = (total_penalty, abs(T), sum(1 for o in offsets.values() if o == 0))

        if best is None or score < best[0]:
            best = (score, T, offsets)

    if best is None:
        return {
            "best_T": None,
            "best_Os": {},
            "best_key_root": None,
            "best_key_mode": original_mode,
            "debug": all_feasible
        }

    score, best_T, best_offsets = best
    new_root, new_mode = transpose_key(original_root, original_mode, best_T)

    return {
        "best_T": best_T,
        "best_Os": best_offsets,
        "best_key_root": new_root,
        "best_key_mode": new_mode,
        "debug": all_feasible
    }
