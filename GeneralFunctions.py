import re
from typing import Dict, Optional, Any
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
        return
        #raise ValueError(f"Nota inválida: '{note_str}'")
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
def compute_best_transposition(original_root: str,
                             original_mode: str,
                             piece_ranges: Dict[str, tuple],
                             group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, Any]:
    """
    Helper de convenção: expor apenas a API de "melhor transposição".
    Chama analyze_ranges_with_penalty e retorna o mesmo formato.
    """
    return analyze_ranges_with_penalty(original_root, original_mode, piece_ranges, group_ranges)


def compute_per_voice_Os_for_T(T: int,
                             piece_ranges: Dict[str, tuple],
                             group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, int]:
    """
    Calcula, para uma transposição T dada, os O_i para cada voz.
    Usa a regra de penalidade semelhante à usada em on_t_change.
    """
    # Vozes consideradas
    voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if group_ranges is None else list(group_ranges.keys())

    if group_ranges is None:
        group_ranges = VOICE_BASE_RANGES

    per_voice_Os: Dict[str, int] = {}

    for v in voices:
        if v not in piece_ranges:
            continue

        mn = note_to_midi(piece_ranges[v][0])
        mx = note_to_midi(piece_ranges[v][1])

        # Faixa da voz (grupo/base)
        if v in group_ranges:
            g_min = note_to_midi(group_ranges[v][0])
            g_max = note_to_midi(group_ranges[v][1])
        else:
            g_min = note_to_midi(VOICE_BASE_RANGES[v][0])
            g_max = note_to_midi(VOICE_BASE_RANGES[v][1])

        best_O = None
        best_pen = float('inf')

        for O in range(-4, 5):
            low = mn + T + 12 * O
            high = mx + T + 12 * O

            pen = max(0, g_min - low) + max(0, high - g_max)

            if pen < best_pen or (pen == best_pen and (best_O is None or abs(O) < abs(best_O))):
                best_O = O
                best_pen = pen

        per_voice_Os[v] = best_O

    return per_voice_Os

def analyze_ranges_with_penalty(original_root: str,
                                original_mode: str,
                                piece_ranges: Dict[str, tuple],
                                group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, Any]:
    """
    Análise com pontuação para encontrar o melhor T usando o esquema descrito.
    Retorna um dict com:
      - best_T
      - best_Os (offsets por voz)
      - best_key_root, best_key_mode
      - debug (ranking de Ts para debug)
    """
    voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if group_ranges is None else list(group_ranges.keys())

    if group_ranges is None:
        group_ranges = VOICE_BASE_RANGES

    # Mapear ranges por voz, com fallback para valores padrão se ausentes
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
        mn, mx = group_ranges[v]
        voice_base_mins[v] = note_to_midi(mn)
        voice_base_maxs[v] = note_to_midi(mx)

    # Faixas de transposição consideradas
    T_values = list(range(-11, 12))

    best_T = None
    best_score = -float('inf')
    best_offsets = {}

    t_scores = {}
    feasible_Ts = []
    all_feasible = []

    for T in T_values:
        offsets = {}
        total_score = 0.0
        feasible_for_T = True
        for v in voices:
            min_i = piece_mins[v]
            max_i = piece_maxs[v]

            min_v = voice_base_mins[v]
            max_v = voice_base_maxs[v]

            required_span = max_i - min_i
            allowed_span = max_v - min_v

            best_score_v = -float('inf')
            best_O = None
            best_L = best_H = None
            best_d_min = best_d_max = None

            for O in range(-4, 5):
                low = min_i + T + 12 * O
                high = max_i + T + 12 * O

                # Verificar encaixe na faixa da voz
                if low < min_v or high > max_v:
                    continue

                d_min = low - min_v
                d_max = max_v - high

                m = (allowed_span - required_span) / 2.0

                if m > 0:
                    score_v = 1.0 - (abs(d_min - m) + abs(d_max - m)) / (2.0 * m)
                else:
                    score_v = 1.0 if (d_min == 0 and d_max == 0) else 0.0

                if (score_v > best_score_v) or (abs(score_v - best_score_v) < 1e-12 and (best_O is None or abs(O) < abs(best_O))):
                    best_score_v = score_v
                    best_O = O
                    best_L = low
                    best_H = high
                    best_d_min = d_min
                    best_d_max = d_max

            if best_O is None:
                feasible_for_T = False
                break

            offsets[v] = best_O
            total_score += best_score_v

        if feasible_for_T:
            t_scores[T] = total_score
            feasible_Ts.append(T)

            if best_T is None or total_score > best_score or (abs(total_score - best_score) < 1e-12 and abs(T) < abs(best_T)):
                best_T = T
                best_score = total_score
                best_offsets = offsets

        all_feasible.append((T, total_score, offsets))

    debug_ranking_T = sorted(feasible_Ts, key=lambda t: (-t_scores.get(t, -float('inf')), abs(t)))

    if best_T is None:
        return {
            "best_T": None,
            "best_Os": {},
            "best_key_root": original_root,
            "best_key_mode": original_mode,
            "debug": debug_ranking_T
        }

    new_root, new_mode = transpose_key(original_root, original_mode, best_T)

    return {
        "best_T": best_T,
        "best_Os": best_offsets,
        "best_key_root": new_root,
        "best_key_mode": new_mode,
        "debug": debug_ranking_T
    }