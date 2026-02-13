from Constants import SEMITONE_TO_SHARP, SEMITONE_TO_BEMOL, NOTE_TO_SEMITONE
import numpy as np
import sounddevice as sd
import threading
import librosa

# ===== FUNÇÕES DE NOTA =====
# Função para transpor uma nota
def transpose_note(note,
                   semitones):
    """Transpõe uma nota musical por um número de semitons"""
    try:
        index = SEMITONE_TO_SHARP.index(note)
    except ValueError:
        index = SEMITONE_TO_BEMOL.index(note)
    transposed_index = (index + semitones) % 12
    return SEMITONE_TO_SHARP[transposed_index]


def transpose_key(root_name: str,
                  mode: str, semitones: int) -> (str, str):
    root = root_name.strip().capitalize()
    if root not in NOTE_TO_SEMITONE:
        root = root_name.strip().replace('b', 'b').replace('#', '#')
        if root not in NOTE_TO_SEMITONE:
            raise ValueError(f"Root inválido: {root_name}")
    root_pc = NOTE_TO_SEMITONE[root]
    new_pc = (root_pc + semitones) % 12
    new_root = SEMITONE_TO_SHARP[new_pc]
    return new_root, mode

# ===== FUNÇÕES DE PARSING E CONVERSÃO DE NOTAS =====

def parse_note(note
               ):
    """
    Retorna (nome_nota, oitava) de uma string como 'C#4'

    Args:
        note: String representando a nota (ex: 'C#4', 'Bb3', 'G2')

    Returns:
        tuple: (nome_nota, oitava) - ex: ('C#', 4)
    """
    i = 0
    while i < len(note) and not note[i].isdigit():
        i += 1
    note_name = note[:i]
    octave = int(note[i:])
    return (note_name, octave)

def is_black_key(note
                 ):
    """
    Retorna True se a nota é uma tecla preta

    Args:
        note: String representando a nota

    Returns:
        bool: True se for tecla preta (sustenido ou bemol)
    """
    note_name = parse_note(note)[0]
    return '#' in note_name or 'b' in note_name


# ===== FUNÇÕES DE GERAÇÃO DE NOTAS =====

def generate_note_range(start_note,
                        end_note):
    """
    Gera lista de notas do piano no range especificado

    Args:
        start_note: Nota inicial (ex: 'C2')
        end_note: Nota final (ex: 'C6')

    Returns:
        list: Lista de notas no formato string (ex: ['C2', 'C#2', 'D2', ...])
    """
    notes = []

    # Encontra índices de início e fim
    start_parts = parse_note(start_note)
    end_parts = parse_note(end_note)

    for octave in range(start_parts[1], end_parts[1] + 1):
        for note_name in SEMITONE_TO_SHARP:
            note = f"{note_name}{octave}"

            # Verifica se está no range
            if librosa.note_to_midi(note) >= librosa.note_to_midi(start_note) and \
                    librosa.note_to_midi(note) <= librosa.note_to_midi(end_note):
                notes.append(note)

    return notes


# ===== FUNÇÕES DE ÁUDIO =====

def play_note(note,
              duration=2.0):
    """
    Reproduz a nota por X segundos em uma thread separada

    Args:
        note: String representando a nota
        duration: Duração da nota em segundos (padrão: 2.0)
    """

    def play():
        try:
            if isinstance(note, float):
                frequency = note
                midi = librosa.hz_to_midi(note)
            elif isinstance(note, int):
                midi = note
                frequency = librosa.midi_to_hz(midi)
            elif isinstance(note, str):
                midi = librosa.note_to_midi(note)
                frequency = librosa.midi_to_hz(midi)

            # Parâmetros de áudio
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), False)

            # Gera onda senoidal simples
            wave = np.sin(2 * np.pi * frequency * t)

            # Aplica envelope ADSR simples para suavizar
            attack = int(0.1 * sample_rate)
            release = int(0.2 * sample_rate)

            # Attack
            wave[:attack] *= np.linspace(0, 1, attack)
            # Release
            wave[-release:] *= np.linspace(1, 0, release)

            # Normaliza e converte para float32
            wave = wave.astype(np.float32)

            # Reproduz o som
            sd.play(wave, sample_rate)
            sd.wait()

        except Exception as e:
            print(f"Erro ao reproduzir nota {note}: {e}")

    # Executa em thread separada para não bloquear a UI
    thread = threading.Thread(target=play, daemon=True)
    thread.start()
