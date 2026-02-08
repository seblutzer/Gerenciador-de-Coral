from tkinter import ttk, simpledialog
import shutil
import os
from tkinter import messagebox
import sounddevice as sd
import threading
import time
from collections import deque
import tkinter as tk
import re
from typing import Dict, Optional, Any
import json
import math
import numpy as np
import librosa
import pretty_midi
from pathlib import Path

# ===== CONSTANTES =====
VOICE_BASE_RANGES = {
    "Soprano": ("C4", "A5"),
    "Mezzo-soprano": ("A3", "F5"),
    "Contralto": ("F3", "D5"),
    "Tenor": ("C3", "G4"),
    "Barítono": ("G2", "E4"),
    "Baixo": ("E2", "C4"),
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

NOTES_FREQUENCY_HZ = {'C0': 16.35, 'C#0': 17.32, 'D0': 18.35, 'D#0': 19.45, 'E0': 20.6, 'F0': 21.83, 'F#0': 23.12,
                      'G0': 24.5, 'G#0': 25.96, 'A0': 27.5, 'A#0': 29.13, 'B0': 30.87, 'C1': 32.7, 'C#1': 34.65,
                      'D1': 36.71, 'D#1': 38.89, 'E1': 41.2, 'F1': 43.65, 'F#1': 46.25, 'G1': 49.0, 'G#1': 51.91,
                      'A1': 55.0, 'A#1': 58.27, 'B1': 61.73, 'C2': 65.41, 'C#2': 69.29, 'D2': 73.41, 'D#2': 77.78,
                      'E2': 82.41, 'F2': 87.31, 'F#2': 92.5, 'G2': 98.0, 'G#2': 103.82, 'A2': 110.0, 'A#2': 116.54,
                      'B2': 123.47, 'C3': 130.81, 'C#3': 138.59, 'D3': 146.83, 'D#3': 155.56, 'E3': 164.81,
                      'F3': 174.61, 'F#3': 184.99, 'G3': 195.99, 'G#3': 207.65, 'A3': 220.0, 'A#3': 233.08,
                      'B3': 246.94, 'C4': 261.62, 'C#4': 277.18, 'D4': 293.66, 'D#4': 311.12, 'E4': 329.62,
                      'F4': 349.22, 'F#4': 369.99, 'G4': 391.99, 'G#4': 415.3, 'A4': 439.99, 'A#4': 466.15,
                      'B4': 493.87, 'C5': 523.24, 'C#5': 554.35, 'D5': 587.32, 'D#5': 622.24, 'E5': 659.24,
                      'F5': 698.44, 'F#5': 739.97, 'G5': 783.97, 'G#5': 830.59, 'A5': 879.98, 'A#5': 932.31,
                      'B5': 987.75, 'C6': 1046.48, 'C#6': 1108.71, 'D6': 1174.63, 'D#6': 1244.48, 'E6': 1318.48,
                      'F6': 1396.88, 'F#6': 1479.95, 'G6': 1567.95, 'G#6': 1661.18, 'A6': 1759.96, 'A#6': 1864.62,
                      'B6': 1975.49, 'C7': 2092.96, 'C#7': 2217.41, 'D7': 2349.27, 'D#7': 2488.96, 'E7': 2636.96,
                      'F7': 2793.77, 'F#7': 2959.89, 'G7': 3135.9, 'G#7': 3322.37, 'A7': 3519.93, 'A#7': 3729.23,
                      'B7': 3950.98, 'C8': 4185.92, 'C#8': 4434.83, 'D8': 4698.54, 'D#8': 4977.93, 'E8': 5273.93,
                      'F8': 5587.53, 'F#8': 5919.78, 'G8': 6271.79, 'G#8': 6644.73, 'A8': 7039.85, 'A#8': 7458.46,
                      'B8': 7901.96}

VOICES = ["Soprano", "Mezzo-soprano", "Contralto", "Tenor", "Barítono", "Baixo"]

SEMITONE_TO_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SEMITONE_TO_BEMOL = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

#DATA_FILE = "coristas_music_data.json"
#DATA_FILE = "C:\Users\Sérgio\PycharmProjects\Gerenciador de Coral\coristas_music_data.json"
DATA_FILE = "C:/Users/Sérgio/PycharmProjects/Gerenciador de Coral/coristas_music_data.json"


# ===== FUNÇÕES DE NOTA =====
# Função para transpor uma nota
def transpose_note(note, semitones):
    """Transpõe uma nota musical por um número de semitons"""
    try:
        index = SEMITONE_TO_SHARP.index(note)
    except ValueError:
        index = SEMITONE_TO_BEMOL.index(note)
    transposed_index = (index + semitones) % 12
    return SEMITONE_TO_SHARP[transposed_index]

def play_note(self, frequency, duration=2):
    """Reproduz uma nota com envelope de piano"""
    t = np.linspace(0, duration, int(self.sample_rate * duration), False)

    # Envelope ADSR de piano
    attack_time = 0.05  # 50ms - ataque rápido
    decay_time = 0.3  # 300ms - decay rápido
    sustain_level = 0.3  # nível de sustain
    release_time = 0.3  # release suave

    attack_samples = int(self.sample_rate * attack_time)
    decay_samples = int(self.sample_rate * decay_time)
    sustain_samples = int(self.sample_rate * (duration - attack_time - decay_time - release_time))
    release_samples = int(self.sample_rate * release_time)

    envelope = np.ones_like(t)

    # Attack
    envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

    # Decay
    decay_start = attack_samples
    decay_end = decay_start + decay_samples
    if decay_end < len(envelope):
        envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_samples)

    # Sustain
    sustain_start = decay_end
    sustain_end = sustain_start + sustain_samples
    if sustain_end < len(envelope):
        envelope[sustain_start:sustain_end] = sustain_level

    # Release
    release_start = sustain_end
    if release_start < len(envelope):
        release_samples_actual = len(envelope) - release_start
        envelope[release_start:] = np.linspace(sustain_level, 0, release_samples_actual)

    # Gera tom puro com harmônicos para simular piano
    signal_audio = 0.25 * np.sin(2 * np.pi * frequency * t) * envelope

    # Adiciona harmônicos para enriquecer o som
    signal_audio += 0.08 * np.sin(2 * np.pi * frequency * 2 * t) * envelope
    signal_audio += 0.04 * np.sin(2 * np.pi * frequency * 3 * t) * envelope

    sd.play(signal_audio, self.sample_rate)
    sd.wait()

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
def compute_per_voice_Os_for_T(T: int,
                             piece_ranges: Dict[str, tuple],
                             group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, int]:
    """
    Calcula, para uma transposição T dada, os O_i para cada voz.
    Usa a regra de penalidade semelhante à usada em on_t_change.
    """
    # Vozes consideradas
    voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if not group_ranges else list(group_ranges.keys())

    if group_ranges is None:
        group_ranges = VOICE_BASE_RANGES

    per_voice_Os: Dict[str, int] = {}

    for v in voices:
        if v not in piece_ranges or piece_ranges[v] == ('', ''):
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
      - voice_scores: dicionário com {voice: {T: score}} para todas as transposições
      - debug (ranking de Ts para debug)
    """
    voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if group_ranges is None else list(
        group_ranges.keys())

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

    # Inicializar dicionário de scores por voz
    voice_scores_by_voice = {v: {} for v in voices}

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
            if v in piece_ranges and piece_ranges[v] != ('', ''):
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

                    score_v = 1.0 - (abs(d_min - m) + abs(d_max - m)) / (2*m) if m != 0 else 0#-math.inf

                    if (score_v > best_score_v) or (
                            abs(score_v - best_score_v) < 1e-12 and (best_O is None or abs(O) < abs(best_O))):
                        best_score_v = score_v
                        best_O = O
                        best_L = low
                        best_H = high
                        best_d_min = d_min
                        best_d_max = d_max

                if best_O is None:
                    feasible_for_T = False
                    voice_scores_by_voice[v][T] = 0.0  # Transposição inviável para esta voz
                    #break

                offsets[v] = best_O
                voice_scores_by_voice[v][T] = best_score_v  # Armazenar score por voz
                total_score += best_score_v
            else:
                voice_scores_by_voice[v][T] = 0.0

        if feasible_for_T:
            t_scores[T] = total_score
            feasible_Ts.append(T)

            if best_T is None or total_score > best_score or (
                    abs(total_score - best_score) < 1e-12 and abs(T) < abs(best_T)):
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
            "voice_scores": voice_scores_by_voice,
            "debug": debug_ranking_T
        }

    new_root, new_mode = transpose_key(original_root, original_mode, best_T)

    return {
        "best_T": best_T,
        "best_Os": best_offsets,
        "best_key_root": new_root,
        "best_key_mode": new_mode,
        "voice_scores": voice_scores_by_voice,
        "debug": debug_ranking_T
    }

class VoiceRangeApp:
    def __init__(self, master):
        self.analyzer = AudioAnalyzer(root_dir='Musicas')
        self.master = master
        self.master.title("Programa de Transposição Vocal - com Gerenciamento de Coristas")
        self.master.geometry("1000x900")
        self.master.resizable(True, True)

        # Testing Time
        self.testing_time = VocalTestCore.DEFAULT_TESTING_TIME
        self.testing_time_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Gerenciador de coristas
        self.coristas_mgr = CoristasManager()

        # Notebook para abas
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Aba 1: Gerenciar Coristas
        self.frame_coristas = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_coristas, text="Gerenciar Coristas")
        self.setup_coristas_tab()

        # Aba 2: Análise de Transposição
        self.frame_analise = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_analise, text="Análise de Transposição")

        # Dados de música carregados
        self.group_ranges = None
        self.group_extension = None
        self.solistas = None
        self.analysis_all = {}
        self.music_library = []  # música(s) salvas
        self.solist_rows = []  # lista de linhas de Soloists UI
        self.solist_count = 0

        # Dados da música atual
        self.music_name_var = tk.StringVar()
        self.root_var = tk.StringVar()
        self.mode_var = tk.StringVar()

        # Visualização de solistas no painel de análise
        self.setup_analise_tab()
        self._build_solists_ui()
    ### DATA MANAGER ESTRUTURAL
    def _sort_column(self, col_name):
        """Ordena a TreeView pela coluna clicada"""

        # Se clicou na mesma coluna, inverte a direção
        if self.sort_column == col_name:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col_name
            self.sort_reverse = False

        # Obtém os itens da TreeView
        items = []
        for item in self.tree_coristas.get_children():
            values = self.tree_coristas.item(item, 'values')
            items.append((item, values))

        # Define a função de ordenação baseada na coluna
        if col_name == "Range":
            # Para Range, precisa fazer sorting especial
            if not self.sort_reverse:
                # Ordena pela primeira nota (grave para agudo)
                items.sort(key=lambda x: self.coristas_mgr.note_to_number(x[1][1].split("⟷")[0].strip()))
            else:
                # Ordena pela segunda nota (agudo para grave)
                items.sort(key=lambda x: self.coristas_mgr.note_to_number(x[1][1].split("⟷")[1].strip()), reverse=True)
        else:
            # Para outras colunas, ordena alfabeticamente
            col_index = {
                "Nome": 0,
                "Range": 1,
                "Voz Atribuída": 2,
                "Voz(es) Recomendada(s)": 3,
                "Voz(es) Possível(is)": 4
            }
            index = col_index.get(col_name, 0)
            items.sort(key=lambda x: x[1][index], reverse=self.sort_reverse)

        # Remove todos os itens
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        # Reinsere os itens na ordem ordenada
        for item, values in items:
            self.tree_coristas.insert("", "end", values=values)

        # Atualiza o visual do cabeçalho (opcional - adiciona indicador de sort)
        self._atualizar_indicador_sort(col_name)

    def _atualizar_indicador_sort(self, col_name):
        """Atualiza o texto do cabeçalho com indicador de direção"""
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")

        for col in columns:
            if col == col_name:
                # Adiciona indicador
                if col == "Range" and not self.sort_reverse:
                    texto = f"{col} ▲"  # Primeira nota (grave para agudo)
                elif col == "Range" and self.sort_reverse:
                    texto = f"{col} ▼"  # Segunda nota (agudo para grave)
                else:
                    texto = f"{col} {'▲' if not self.sort_reverse else '▼'}"
            else:
                texto = col

            self.tree_coristas.heading(col, text=texto)

    def _on_noise_gate_changed(self, value):
        """Atualiza o NOISE_GATE_THRESHOLD quando o slider é movido"""
        try:
            new_threshold = float(value)
            # Atualiza o valor na classe VocalTestCore
            VocalTestCore.NOISE_GATE_THRESHOLD = new_threshold

            # Se houver um teste em andamento, atualiza também na instância
            if self.vocal_tester is not None:
                self.vocal_tester.NOISE_GATE_THRESHOLD = new_threshold

            # Atualiza o label com o valor formatado
            self.noise_gate_value_label.config(text=f"{new_threshold:.4f}")
        except ValueError:
            pass

    def setup_coristas_tab(self):
        """Configura a aba de gerenciamento de coristas com frames independentes lado a lado"""
        # Container principal com duas colunas independentes
        main_frame = ttk.Frame(self.frame_coristas)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: Adicionar/Editar Corista
        left_frame = ttk.LabelFrame(main_frame, text="Adicionar/Editar Corista", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Right: Teste Vocal Integrado
        right_frame = ttk.LabelFrame(main_frame, text="Teste Vocal Integrado", padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Ajusta peso das colunas para manter os frames proporcionais
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # ===== LEFT FRAME: Campos Adicionar/Editar Corista =====
        ttk.Label(left_frame, text="Nome:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entrada_nome = ttk.Entry(left_frame, width=30)
        self.entrada_nome.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Min (ex: G3):").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entrada_min = ttk.Entry(left_frame, width=15)
        self.entrada_min.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Max (ex: C5):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entrada_max = ttk.Entry(left_frame, width=15)
        self.entrada_max.grid(row=1, column=3, padx=5, pady=5)

        # Botão Adicionar na esquerda
        btn_add = ttk.Button(left_frame, text="Adicionar Corista", command=self.add_corista)
        btn_add.grid(row=2, column=0, columnspan=4, pady=10)

        # ===== RIGHT FRAME: Teste Vocal Integrado =====
        # Estado e repetição
        state_row = ttk.Frame(right_frame)
        state_row.pack(anchor="w", pady=(0, 5))

        ttk.Label(state_row, text="Tempo de teste (s):").pack(side="left", padx=(8, 0))
        self.testing_time_cb = ttk.Combobox(state_row, values=self.testing_time_values, state="readonly", width=5)
        self.testing_time_cb.pack(side="left", padx=(8, 0))
        self.testing_time_cb.current(self.testing_time_values.index(self.testing_time))
        self.testing_time_cb.bind("<<ComboboxSelected>>", self._on_testing_time_changed)

        self.btn_repeat_tone = ttk.Button(state_row, text="🔁 Repetir Tom",
                                          command=self.repeat_tone_vocal)
        self.btn_repeat_tone.pack(side="left", padx=(8, 0))

        # ================= Botões de Teste =================

        buttons_row = ttk.Frame(right_frame)
        buttons_row.pack(fill="x", pady=5)

        self.btn_start_test = ttk.Button(buttons_row, text="🏁 Iniciar Teste",
                                         command=self.start_vocal_test)
        self.btn_start_test.grid(row=0, column=0, padx=3, sticky="ew")

        self.btn_quick_test = ttk.Button(buttons_row, text="⚡ Teste Rápido",
                                         command=self.start_quick_vocal_test)
        self.btn_quick_test.grid(row=0, column=1, padx=3, sticky="ew")

        buttons_row.columnconfigure(0, weight=1)
        buttons_row.columnconfigure(1, weight=1)

        # ===== Botões de marcação =====
        marking_row = ttk.Frame(right_frame)
        marking_row.pack(fill="x", pady=5)

        self.btn_too_low = ttk.Button(marking_row, text="🔽️ Grave D.",
                                      command=self.mark_too_low_vocal, state='disabled')
        self.btn_too_low.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_too_high = ttk.Button(marking_row, text="🔼 Agudo D.",
                                       command=self.mark_too_high_vocal, state='disabled')
        self.btn_too_high.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_stop_test = ttk.Button(marking_row, text="🛑 Parar",
                                        command=self.stop_vocal_test, state='disabled')
        self.btn_stop_test.grid(row=0, column=2, padx=2, sticky="ew")

        marking_row.columnconfigure(0, weight=1)
        marking_row.columnconfigure(1, weight=1)
        marking_row.columnconfigure(2, weight=1)
        # ===== CONTROLE DE ABAFAMENTO DO MICROFONE (NOISE GATE) =====
        noise_gate_frame = ttk.LabelFrame(right_frame, text="Controle de Abafamento", padding=8)
        noise_gate_frame.pack(fill="x", pady=5)

        # Label informativo
        ttk.Label(noise_gate_frame, text="Nível de abafamento do microfone:",
                  font=("Arial", 9)).pack(anchor="w", padx=5)

        # Frame para slider e valor
        slider_frame = ttk.Frame(noise_gate_frame)
        slider_frame.pack(fill="x", padx=5, pady=5)

        # Slider
        self.noise_gate_slider = tk.Scale(
            slider_frame,
            from_=0,
            to=0.02,
            resolution=0.0001,
            orient="horizontal",
            length=300,
            command=self._on_noise_gate_changed
        )
        self.noise_gate_slider.set(VocalTestCore.NOISE_GATE_THRESHOLD)
        self.noise_gate_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Label para exibir valor atual
        self.noise_gate_value_label = ttk.Label(
            slider_frame,
            text=f"{VocalTestCore.NOISE_GATE_THRESHOLD:.4f}",
            font=("Arial", 9, "bold"),
            foreground="#2E86AB",
            width=8
        )
        self.noise_gate_value_label.pack(side="left")

        # ===== INDICADOR VISUAL (BELT) =====
        self.belt_indicator = BeltIndicator(right_frame, width=300, height=50)
        # Opcional: definir o alcance de semitons que o belt deve cobrir
        self.belt_indicator.set_range(-12, 12)
        self.belt_indicator.pack(pady=5)

        # Visualizador do pitch ao longo do tempo
        self.pitch_line_chart = PitchLineChart(left_frame, width=640, height=300,
                                               min_midi=40, max_midi=84)
        self.pitch_line_chart.grid(row=3, column=0, columnspan=5, pady=10)

        # ===== PROGRESSO DE TEMPO =====
        self.time_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.time_var,
                                            maximum=100, length=300, mode='determinate')
        self.progress_bar.pack(pady=3)

        self.time_label = ttk.Label(right_frame, text=f"Tempo: 0.0s / {self.testing_time}.0s",
                                    font=("Arial", 8))
        self.time_label.pack(pady=(0, 5))

        # ===== NOTAS ESPERADA E DETECTADA =====
        notes_frame = ttk.Frame(right_frame)
        notes_frame.pack(fill="x", pady=5)

        ttk.Label(notes_frame, text="Esperada:", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        self.expected_note_label = ttk.Label(notes_frame, text="--", font=("Arial", 9),
                                             foreground="#2E86AB")
        self.expected_note_label.pack(side="left", padx=2)

        ttk.Label(notes_frame, text="→", font=("Arial", 10)).pack(side="left", padx=5)

        ttk.Label(notes_frame, text="Detectada:", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        self.detected_note_label = ttk.Label(notes_frame, text="--", font=("Arial", 9),
                                             foreground="#888")
        self.detected_note_label.pack(side="left", padx=2)

        # ===== STATUS =====
        self.status_label = ttk.Label(right_frame, text="Aguardando...",
                                      font=("Arial", 9), foreground="#666")
        self.status_label.pack(pady=5)

        # Inicializa a instância do VocalTestCore
        self.vocal_tester = None

        # TABELA
        # Tabela de coristas
        table_frame = ttk.LabelFrame(self.frame_coristas, text="Coristas Cadastrados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        group_frame = ttk.Frame(table_frame, padding=10)
        group_frame.pack(side='left', fill="y", padx=10, pady=10)

        # ===== NOVO: Grupo de Coristas (carrega de coristas_music_data.json) =====
        ttk.Label(group_frame, text="Grupo de Coristas:").pack()
        # combobox de grupos carregados do coristas_music_data.json
        self.grupos_var = tk.StringVar()
        self.grupo_combo = ttk.Combobox(group_frame, textvariable=self.grupos_var, state="readonly", width=20)
        groups = self.coristas_mgr.read_data(extract='grupos', group_list=True)
        self.grupo_combo['values'] = groups
        if groups:
            self.grupo_combo.current(0)
        self.grupo_combo.pack()
        self.grupo_combo.bind("<<ComboboxSelected>>", self._on_group_selected)
        self.grupo_nome_var = tk.StringVar()

        # Botão "Adicionar Grupo"
        self.add_group_btn = ttk.Button(group_frame, text="Adicionar Grupo", command=self.adicionar_grupo)
        self.add_group_btn.pack(pady=2)

        # Cria Treeview
        self.sort_column = None
        self.sort_reverse = False
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="headings")

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(col, text=col)
            # Bind ao clique do cabeçalho
            self.tree_coristas.heading(col, command=lambda c=col: self._sort_column(c))

        self.tree_coristas.pack(fill="both", expand=True)

        # Atalhos da treeview
        self.tree_coristas.bind("<Double-1>", self._on_double_click_corista)
        self.tree_coristas.bind("<Delete>", self.on_delete_key)

        # Botões de ação
        button_frame = ttk.Frame(self.frame_coristas)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(group_frame, text="Remover Selecionado", command=self.remove_corista).pack(pady=2)
        ttk.Button(group_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(pady=2)

        # Determine o grupo atual (pode vir do combobox de grupo ou do campo de nome do grupo)
        grupo_selecionado = None
        if hasattr(self, "grupo_combo"):
            grupo_selecionado = self.grupo_combo.get()
        elif hasattr(self, "grupo_nome_var"):
            grupo_selecionado = self.grupo_nome_var.get()

        # Atualiza o CoristasManager para o grupo atual
        if grupo_selecionado:
            self.coristas_mgr.set_group(grupo_selecionado)
        else:
            # Caso não haja grupo definido, ainda assim tente manter o estado
            self.coristas_mgr.set_group("")

        self.grupo_nome_var.set(self.coristas_mgr.grupo)

        # Carrega dados iniciais
        self.reload_coristas_table()

    def setup_analise_tab(self):
        """Configura a aba de análise de transposição"""
        # Cabeçalho
        header = ttk.Label(self.frame_analise, text="Ajuste de tom e alcance por voz (compensação por penalidade)",
                           font=("Arial", 12, "bold"))
        header.pack(pady=10)

        # Slider de transposição
        self.t_slider = tk.Scale(self.frame_analise, from_=-11, to=11, orient="horizontal", label="Transposição (semítons)", command=self.on_t_change, length=600)
        self.t_slider.set(0)
        self.t_slider.pack(fill="x", padx=10, pady=10)

        # Novo container para manter dois painéis lado a lado
        main_pane = ttk.Frame(self.frame_analise)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # Faixas da peça (à esquerda)
        ranges_frame = ttk.LabelFrame(main_pane, text="Faixa da Música por Voz", padding=10)
        ranges_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Biblioteca de músicas (à direita)
        library_frame = ttk.LabelFrame(main_pane, text="Biblioteca de Músicas", padding=10)
        library_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Distribuição igual entre as duas colunas
        main_pane.columnconfigure(0, weight=1)
        main_pane.columnconfigure(1, weight=1)

        # Placeholder do nome da música
        self.music_name_var = tk.StringVar()
        self.music_name_entry = tk.Entry(library_frame, textvariable=self.music_name_var, width=30, fg="grey")
        self.music_name_placeholder = "Nome da música"
        self.music_name_entry.insert(0, self.music_name_placeholder)

        def _clear_name(event):
            if self.music_name_entry.get() == self.music_name_placeholder:
                self.music_name_entry.delete(0, tk.END)
                self.music_name_entry.config(fg="black")

        def _fill_name(event):
            val = self.music_name_entry.get()
            if val == "":
                self.music_name_entry.insert(0, self.music_name_placeholder)
                self.music_name_entry.config(fg="grey")
                self.music_name_var.set("")  # keep var sem placeholder
            else:
                # Atualiza a StringVar com o valor real (ignora o placeholder)
                self.music_name_var.set(val)

        self.music_name_entry.bind("<FocusIn>", _clear_name)
        self.music_name_entry.bind("<FocusOut>", _fill_name)
        self.music_name_entry.grid(row=0, column=0, padx=5, pady=5)  # ocupa o espaço da antiga label

        # Combobox com placeholder
        self.music_var = tk.StringVar()
        self.music_combo = ttk.Combobox(library_frame, textvariable=self.music_var, state="readonly", width=25)
        self.load_music_library()
        self.music_combo.set("-- Selecione uma música --")
        self.music_combo.grid(row=1, column=0, padx=5, pady=5)
        self.music_combo.bind("<<ComboboxSelected>>",
                              lambda e: self.load_music_ranges_for_selection(self.music_combo.get()))

        # Botões com ícones (em vez de textos)
        btn_save = ttk.Button(library_frame, text='💾', width=5, command=lambda: self.save_music_ranges_to_json(
            piece_name=(self.music_name_var.get() if self.music_name_var.get() != self.music_name_placeholder else "")
        ))
        btn_save.grid(row=0, column=1, padx=5, pady=5)

        btn_load = ttk.Button(library_frame, text='📂', command=self.load_voice_audio_files, width=5)
        btn_load.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(library_frame, text="Tom original (raiz):").grid(row=2, column=0, padx=5, pady=5)
        self.root_var = tk.StringVar()
        self.root_combo = ttk.Combobox(library_frame, textvariable=self.root_var, state="readonly", width=8,
                                       values=["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab",
                                               "A", "A#", "Bb", "B"])
        self.root_combo.current(0)
        self.root_combo.grid(row=2, column=1, padx=5, pady=5)
        self.root_combo.bind("<<ComboboxSelected>>", self._on_root_selected)

        ttk.Label(library_frame, text="Modo:").grid(row=3, column=0, padx=5, pady=5)
        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(library_frame, textvariable=self.mode_var, state="readonly", width=10,
                                       values=["maior", "menor"])
        self.mode_combo.current(0)
        self.mode_combo.grid(row=3, column=1, padx=5, pady=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        # Min/Max por voz: 3 linhas x 2 vozes (total de 6 vozes)
        self.voice_vars = {}

        for idx, v in enumerate(VOICES):
            row = idx // 2  # 3 linhas
            col = idx % 2  # 2 colunas
            frame_v = ttk.Frame(ranges_frame)
            frame_v.grid(row=row, column=col, padx=10, pady=5, sticky="w")

            ttk.Label(frame_v, text=f"{v}:").pack()

            min_entry = ttk.Entry(frame_v, width=10)
            min_entry.pack(side="left", padx=2)
            max_entry = ttk.Entry(frame_v, width=10)
            max_entry.pack(side="left", padx=2)

            # Valores padrão
            min_entry.insert(0, "")
            max_entry.insert(0, "")

            self.voice_vars[v] = {"min": min_entry, "max": max_entry}
            # Após criar os entries
            #self.voice_vars[v]["min_value"] = ""
            #self.voice_vars[v]["max_value"] = ""

            #self.bind_entry_to_var(min_entry, self.voice_vars[v], "min_value")
            #self.bind_entry_to_var(max_entry, self.voice_vars[v], "max_value")

        # ===== SOLISTAS (layout ajustado para refletir grupo quando carregado) =====
        # Novo: Combobox de número de solistas (0 a 5)
        solo_frame_header = ttk.LabelFrame(main_pane, padding=10, text='Solistas')
        solo_frame_header.grid(row=0, column=1, pady=5, padx=5, sticky="nsew")
        self.solist_count_cb = ttk.Combobox(solo_frame_header, values=[0,1,2,3,4,5], width=5, state="readonly")
        self.solist_count_cb.pack(side="left")
        self.solist_count_cb.set(0)
        self.solist_count_cb.bind("<<ComboboxSelected>>", self._on_solists_count_changed)

        # Frame para os solistas (dinâmico)
        self.solist_frame = ttk.Frame(solo_frame_header, padding=10)
        self.solist_frame.pack()

        # Botões de ação (continua)
        action_frame = ttk.Frame(self.frame_analise)
        action_frame.pack(fill="x", padx=10, pady=10)

        # Botão dinâmico de uso de coristas/base
        self.dynamic_ranges_button = ttk.Button(action_frame, text="Vozes Grupo",
                                                command=self.toggle_group_or_voice_ranges)
        self.dynamic_ranges_button.pack(side="left", padx=5)

        ttk.Button(action_frame, text="Executar análise", command=self.run_analysis).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Limpar resultados", command=self.clear_results).pack(side="left", padx=5)

        # Visualizador
        self.visualizer = RangeVisualizer(self.frame_analise, voices=VOICES, base_ranges=VOICE_BASE_RANGES, coristas=self.coristas_mgr.coristas)

        # Biblioteca de músicas (à direita)
        result_frame = ttk.LabelFrame(main_pane, text="Resultados", padding=10)
        result_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.results_text = tk.Text(result_frame, height=9, width=50, wrap="word", font=("Consolas", 10))
        self.results_text.pack(anchor="w", padx=5, pady=3, fill="x")

        self.results_text.insert("end", "Resultados: Informe os ranges vocais e a faixa da música por voz.\n")

        self.current_result = None

    def _build_solists_ui(self):
        """
        Constrói/Atualiza a UI para os solistas com base no número indicado na combobox.
        """
        # Limpa conteúdos existentes
        for child in self.solist_frame.winfo_children():
            child.destroy()
        self.solist_rows.clear()

        count = int(self.solist_count_cb.get()) if self.solist_count_cb.get() != "" else 0
        self.solist_count = count

        coristas_nomes = [c for c in self.coristas_mgr.coristas] or []
        corista_choices = ["Selecionar..."] + coristas_nomes

        for i in range(count):
            row_frame = ttk.Frame(self.solist_frame)
            row_frame.pack(fill="x", pady=3)

            ttk.Label(row_frame, text=f"Solista {i+1}:").pack(side="left", padx=(0,5))

            cb = ttk.Combobox(row_frame, values=corista_choices, state="readonly", width=20)
            cb.current(0)  # sem seleção
            cb.pack(side="left", padx=(0,5))

            min_ent = ttk.Entry(row_frame, width=8)
            min_ent.pack(side="left", padx=(0,5))

            max_ent = ttk.Entry(row_frame, width=8)
            max_ent.pack(side="left", padx=(0,5))

            self.solist_rows.append({
                "cb": cb,
                "min": min_ent,
                "max": max_ent,
            })

    def _on_solists_count_changed(self, event=None):
        self._build_solists_ui()
    ### DATA MANAGER SAVE/LOAD
    def _on_group_selected(self, event=None):
        """Atualiza estado ao selecionar grupo e refaz UI de solistas se necessário."""
        grupo = self.grupo_combo.get()
        self.grupo_nome_var.set(grupo)
        self.coristas_mgr.grupo = grupo
        data = self.coristas_mgr.read_data()
        self.music_library = {nome: info for nome, info in data.get("musicas", {}).items() if info.get("grupo") == grupo}
        self.music_names = list(self.music_library.keys())
        # versão: coristas é um dicionário, não lista
        self.coristas_mgr.coristas = data["grupos"][grupo]

        # limpar músicas
        # Resetar músicas
        self.music_name_var.set(self.music_name_placeholder)
        self.music_name_entry.delete(0, tk.END)
        self.music_name_entry.config(fg="black")
        self.music_name_entry.insert(0, self.music_name_placeholder)
        self.music_var.set('')
        self.music_combo.set("-- Selecione uma música --")
        self._clear_music_fields()

        # Atualisar lista de músicas
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names

        # Atualiza a UI dos solistas para refletir o grupo atual
        self.reload_coristas_table()

    def add_corista(self):
        nome = self.entrada_nome.get().strip()
        range_min = self.entrada_min.get().strip().upper()
        range_max = self.entrada_max.get().strip().upper()

        if not nome or not range_min or not range_max:
            messagebox.showerror("Erro", "Preenchimento obrigatório em todos os campos")
            return

        success, result = self.coristas_mgr.add_corista(nome, range_min, range_max)
        if success:
            voz_calc = result['voz_calculada']
            vozes_rec = result.get('vozes_recomendadas', [])
            vozes_poss = result.get('vozes_possiveis', [])

            msg = f"Corista '{nome}' adicionado!\n\n"
            msg += f"Voz Calculada: {voz_calc}\n\n"
            msg += f"Vozes Recomendadas: {', '.join(vozes_rec) if vozes_rec else 'Nenhuma'}\n"
            msg += f"Vozes Possíveis: {', '.join([v for v in vozes_poss]) if vozes_poss else 'Nenhuma'}"

            messagebox.showinfo("Sucesso", msg)
            self.entrada_nome.delete(0, "end")
            self.entrada_min.delete(0, "end")
            self.entrada_max.delete(0, "end")
            self.reload_coristas_table()

    def remove_corista(self):
        selection = self.tree_coristas.selection()

        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para remover")
            return
        item = selection[0]

        vals = self.tree_coristas.item(item, "values")
        corista_nome = vals[0] if vals else None
        sucesso = self.coristas_mgr.remove_corista(corista_nome)
        if sucesso:
            self.music_library = sucesso['musicas']
            self.reload_coristas_table()
            messagebox.showinfo("Sucesso", "Corista removido!")

    def reload_coristas_table(self):
        # Recarrega a visualização da tabela com os coristas do grupo atual
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        for corista in self.coristas_mgr.coristas:
            self.tree_coristas.insert("", "end", values=(
                corista,
                self.coristas_mgr.coristas[corista]['range_min'] + "  ⟷  " + self.coristas_mgr.coristas[corista]['range_max'],
                self.coristas_mgr.coristas[corista]['voz_atribuida'],
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_recomendadas']),
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_possiveis']))
            )

    def save_music_ranges_to_json(self, piece_name=None):
        """
        Orquestra a coleta de dados e delegação para CoristasManager.
        Responsável apenas por: UI, validações de entrada, confirmação.
        """
        # ===== COLETA DE DADOS DA UI =====

        # 1) Nome da música
        name = piece_name or "Untitled"
        if name == "Untitled":
            messagebox.showerror("Erro", "Preencha o nome da música")
            return

        # 2) Ranges de vozes
        piece_ranges = {}
        for voz in VOICES:
            min_val = self.voice_vars[voz]["min"].get().upper().strip()
            max_val = self.voice_vars[voz]["max"].get().upper().strip()
            if min_val or max_val:  # Se preenchido
                piece_ranges[voz] = {"min": min_val, "max": max_val}

        if not piece_ranges:
            messagebox.showwarning("Aviso", "Preencha ao menos um range de voz")
            return

        # 3) Solistas
        solistas = {}
        for row in getattr(self, 'solist_rows', []) or []:
            cb_widget = row.get('cb')
            min_widget = row.get('min')
            max_widget = row.get('max')

            if cb_widget is None:
                continue

            try:
                cb_name = cb_widget.get()
                min_val = min_widget.get() if min_widget else ""
                max_val = max_widget.get() if max_widget else ""

                # Só adiciona se houver nome de solista
                if cb_name and cb_name != "Selecionar...":
                    solistas[cb_name] = [min_val, max_val]
            except Exception:
                pass

        # 4) Voices (mapeamento de coristas por voz)
        voices = {}
        for corista in getattr(self.coristas_mgr, 'coristas', []) or []:
            nome = corista
            voz_atribuida = self.coristas_mgr.coristas[nome].get('voz_atribuida')
            if voz_atribuida and nome:
                voices.setdefault(voz_atribuida, []).append(nome)

        # 5) Música info
        orig_root = self.root_var.get()
        orig_mode = self.mode_var.get()

        # ===== VERIFICAR SE JÁ EXISTE =====
        existe = self.coristas_mgr.check_music_exists(name)

        if existe:
            substituir = messagebox.askyesno(
                "Música Existente",
                f"A música '{name}' já existe. Deseja substituir?"
            )
            if not substituir:
                messagebox.showinfo("Cancelado", "Operação cancelada.")
                return

        # ===== DELEGAÇÃO PARA CORISTASMANAGER =====
        sucesso, mensagem = self.coristas_mgr.save_music_ranges_to_json(
            music_name=name,
            ranges=piece_ranges,
            solistas=solistas,
            vozes_por_corista=voices,
            root=orig_root,
            mode=orig_mode
        )

        if sucesso:
            messagebox.showinfo("Sucesso", mensagem)
            # Atualizar biblioteca após salvar
            self.load_music_library()
        else:
            messagebox.showerror("Erro", mensagem)

    def load_music_library(self):
        """Carrega a biblioteca de músicas do coristas_music_data.json."""
        # Limpa/reinicializa listas
        self.music_library.clear()
        self.music_names = []

        data, musicas, groups = self.coristas_mgr.read_data(extract='musicas', all_in=True, group_list=True)
        grupo = self.grupo_nome_var.get() if hasattr(self.grupo_nome_var, "get") else self.grupo_nome_var
        self.music_library = {nome: info for nome, info in musicas.items() if info.get("grupo") == grupo}
        self.music_names = list(self.music_library.keys())

        # Carrega grupos: atualiza combobox de grupos com nomes disponíveis
        if hasattr(self, "grupo_combo") and groups:
            self.grupo_combo['values'] = groups

        # Atualiza combobox se existir
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names

    def load_music_ranges_for_selection(self, name):
        """Carrega os ranges de uma música selecionada na combobox."""

        # Validação básica
        if not name or name.startswith("--"):
            messagebox.showwarning("Aviso", "Nenhuma música válida selecionada.")
            self._clear_music_fields()
            return

        item = self.music_library.get(name)

        if item is None:
            messagebox.showerror("Erro", f"Música '{name}' não encontrada na biblioteca.")
            return

        # Preenche ranges
        ranges = item.get("ranges", {})
        for voice, vr in ranges.items():
            min_val = vr.get("min", "") if isinstance(vr, dict) else ""
            max_val = vr.get("max", "") if isinstance(vr, dict) else ""

            # Suporte a formatos alternativos
            if not min_val and isinstance(vr, dict):
                min_val = vr.get("0", "")
            if not max_val and isinstance(vr, dict):
                max_val = vr.get("1", "")

            if min_val == "" and max_val == "":
                continue

            if voice in self.voice_vars:
                self.voice_vars[voice]["min"].delete(0, "end")
                self.voice_vars[voice]["min"].insert(0, min_val)
                self.voice_vars[voice]["max"].delete(0, "end")
                self.voice_vars[voice]["max"].insert(0, max_val)

        # Determina e aplica grupo da música
        grupo = item.get("grupo")
        if grupo:
            # Tenta selecionar o grupo na combobox, se existir
            grupos_disponiveis = self.coristas_mgr.read_data(extract='grupos', group_list=True)
            if grupo in grupos_disponiveis:
                self.grupo_combo.set(grupo)
            else:
                # Se grupo não estiver na lista, mantém atual e seta nome do grupo
                self.grupo_combo.set(grupo)
                self.grupo_nome_var.set(grupo)

            self.grupo_nome_var.set(grupo)
        else:
            # Se não houver grupo definido, mantém o estado atual
            pass

        # Atualiza o name da música (campo)
        self.music_name_var.set(name)

        # Atualiza o tom da música (campo)
        self.root_var.set(item['root'])

        # Atualiza o modo da música (campo)
        self.mode_var.set(item['mode'])

        # Novo: carregar solistas da música (robusto para diferentes formatos de solistas)
        solistas_raw = item.get("solistas", None)

        # Atualiza UI de solistas com a lista normalizada
        if hasattr(self, "solist_count_cb"):
            cnt = min(max(len(solistas_raw.keys()), 0), 5)  # 0 a 5
            self.solist_count_cb.set(cnt)
            self._on_solists_count_changed()
            self.solistas = {}
            for idx, name in enumerate(solistas_raw):
                if idx >= len(self.solist_rows):
                    break
                row = self.solist_rows[idx]
                # Define o nome do solista
                if "cb" in row:
                    row["cb"].set(name)
                # Define range mínimo e máximo
                if "min" in row:
                    row["min"].delete(0, "end")
                    row["min"].insert(0, solistas_raw[name][0])
                if "max" in row:
                    row["max"].delete(0, "end")
                    row["max"].insert(0, solistas_raw[name][1])
                self.solistas[name] = (solistas_raw[name][0], solistas_raw[name][1])

        # Atribuir as vozes de cada corista para essa música
        voices = item.get("voices", {})
        for voice in voices:
            for name in voices[voice]:
                if self.coristas_mgr.coristas[name]['voz_atribuida'] != voice:
                    self.coristas_mgr.coristas[name]['voz_atribuida'] = voice

        self.reload_coristas_table()

        # Executa a análise com os dados carregados
        if getattr(self, '_use_group_ranges', None):
            self._use_group_ranges = not self._use_group_ranges
            self.toggle_group_or_voice_ranges()
        else:
            self.run_analysis()

    def read_voice_ranges(self):
        ranges = {}
        for v in VOICES:
            min_str = self.voice_vars[v]["min"].get().strip()
            max_str = self.voice_vars[v]["max"].get().strip()
            #if not min_str or not max_str:
            #    raise ValueError(f"Faixa de {v} está vazia.")
            ranges[v] = (min_str, max_str)
        return ranges

    # DATA MANAGER FUNCTIONS
    def edit_corista_voz(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        item = selection[0]

        # Obter o nome do corista a partir da treeview
        vals = self.tree_coristas.item(item, "values")
        corista_nome = vals[0] if vals else None

        if corista_nome is None:
            messagebox.showwarning("Aviso", "Corista inválido selecionado")
            return

        # Acesso ao dicionário reestruturado: coristas_mgr.coristas é dict {nome: {...}}
        corista = self.coristas_mgr.coristas.get(corista_nome)
        if corista is None:
            messagebox.showwarning("Aviso", "Corista não encontrado no gerenciador")
            return

        # Janela de diálogo para edição de voz
        dialog = tk.Toplevel(self.master)
        dialog.title("Editar Voz do Corista")
        dialog.geometry("900x750")

        # ===== Frame de Dados do Corista =====
        dados_frame = ttk.LabelFrame(dialog, text="Dados do Corista", padding=10)
        dados_frame.pack(fill="x", padx=10, pady=10)

        # Editar Nome
        ttk.Label(dados_frame, text="Nome:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5,
                                                                              pady=5)
        var_nome = tk.StringVar(value=corista_nome)
        entry_nome = ttk.Entry(dados_frame, textvariable=var_nome, width=30, font=("Arial", 10))
        entry_nome.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Editar Range Mínimo
        ttk.Label(dados_frame, text="Range Mínimo:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w",
                                                                                      padx=5, pady=5)
        var_range_min = tk.StringVar(value=corista['range_min'])
        entry_range_min = ttk.Entry(dados_frame, textvariable=var_range_min, width=30, font=("Arial", 10))
        entry_range_min.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Editar Range Máximo
        ttk.Label(dados_frame, text="Range Máximo:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w",
                                                                                      padx=5, pady=5)
        var_range_max = tk.StringVar(value=corista['range_max'])
        entry_range_max = ttk.Entry(dados_frame, textvariable=var_range_max, width=30, font=("Arial", 10))
        entry_range_max.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        dados_frame.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="💡 Dica: Use o teste vocal na aba de Adicionar Corista para determinar o range",
                  font=("Arial", 8), foreground="#666").pack(pady=5)

        # ===== Frame de Voz Calculada =====
        voz_calc_frame = ttk.LabelFrame(dialog, text="Voz Calculada", padding=5)
        voz_calc_frame.pack(fill="x", padx=10, pady=5)

        label_voz_calc = ttk.Label(voz_calc_frame, text=f"Voz Calculada: {corista['voz_calculada']}",
                                   font=("Arial", 10, "bold"))
        label_voz_calc.pack(anchor="w", padx=10, pady=5)

        # Separador
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista.get('voz_atribuida'))

        # ===== Visualizador de teclado =====
        keyboard = KeyboardVisualizer(dialog)

        # Frame para as opções de voz
        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Variável para armazenar os dados de vozes compatíveis
        vozes_data = {
            'recomendadas': [],
            'possiveis': []
        }

        # Função para atualizar a lista de vozes na interface
        def update_vozes_display():
            # Obter novos valores
            range_min = var_range_min.get()
            range_max = var_range_max.get()

            # Validação básica
            try:
                note_to_midi(range_min)
                note_to_midi(range_max)
                if note_to_midi(range_min) > note_to_midi(range_max):
                    return False
            except:
                return False

            # Calcular vozes compatíveis
            vozes_recomendadas, vozes_possiveis = self.coristas_mgr.calculate_compatible_voices(range_min, range_max, True)
            vozes_data['recomendadas'] = vozes_recomendadas
            vozes_data['possiveis'] = vozes_possiveis

            # Calcular nova voz calculada
            nova_voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0][0] if vozes_possiveis else VOICES[0])

            # Atualizar label de voz calculada
            label_voz_calc.config(text=f"Voz Calculada: {nova_voz_calculada}")

            # Se a voz atribuída não está mais compatível, redefine para a calculada
            voz_atual = var_voz.get()
            todas_vozes = vozes_recomendadas + [v[0] for v in vozes_possiveis]
            if voz_atual not in todas_vozes:
                var_voz.set(nova_voz_calculada)

            # Limpar frame de vozes antigo
            for widget in vozes_frame.winfo_children():
                widget.destroy()

            # Reconstruir radiobuttons com novas vozes
            # RECOMENDADAS
            if vozes_recomendadas:
                ttk.Label(vozes_frame, text="✓ Recomendadas (Encaixe Perfeito)",
                          font=("Arial", 11, "bold"), foreground="green").pack(anchor="w", pady=(10, 5))
                for v in vozes_recomendadas:
                    def on_select_recomendada(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(vozes_frame, text=v, variable=var_voz, value=v,
                                    command=on_select_recomendada).pack(anchor="w", padx=50, pady=3)

            # POSSÍVEIS
            if vozes_possiveis:
                ttk.Label(vozes_frame, text="⚠ Possíveis (com ressalva)",
                          font=("Arial", 11, "bold"), foreground="orange").pack(anchor="w", pady=(10, 5))
                for v, diff, obs in vozes_possiveis:
                    frame_poss = ttk.Frame(vozes_frame)
                    frame_poss.pack(anchor="w", padx=40, pady=3, fill="x")

                    def on_select_possivel(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(frame_poss, text=v, variable=var_voz, value=v,
                                    command=on_select_possivel).pack(side="left")
                    ttk.Label(frame_poss, text=f"({obs})", font=("Arial", 9),
                              foreground="gray").pack(side="left", padx=5)

            # Atualizar teclado
            voz_selecionada = var_voz.get()
            if voz_selecionada:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_selecionada]
                keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

            return True

        # Vinculação de eventos para validação e atualização em tempo real
        def on_range_changed(*args):
            try:
                update_vozes_display()
            except Exception as e:
                # Silencioso durante digitação, evita erro durante edição
                pass

        var_range_min.trace('w', on_range_changed)
        var_range_max.trace('w', on_range_changed)

        # Atualizar a exibição inicial
        update_vozes_display()

        def confirm():
            novo_nome = var_nome.get().strip()
            novo_range_min = var_range_min.get().strip().upper()
            novo_range_max = var_range_max.get().strip().upper()
            nova_voz = var_voz.get()

            # Validações
            if not novo_nome:
                messagebox.showerror("Erro", "Nome do corista não pode estar vazio")
                return

            # Validação de notas
            NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|B)?[2-7])?$")
            invalids = []
            if not NOTA_PATTERN.fullmatch(novo_range_min):
                invalids.append(novo_range_min)
            if not NOTA_PATTERN.fullmatch(novo_range_max):
                invalids.append(novo_range_max)

            if invalids:
                msgs = f"'{' e '.join(invalids)}' são inválidos!" if len(
                    invalids) > 1 else f"'{invalids[0]}' é inválido!"
                messagebox.showerror("Nota inexistente",
                                     msgs + "\nEsperado: uma letra A-G seguida de um número 2-7.\n")
                return

            # Padronizar bemois em sustenidos
            novo_range_min = self.coristas_mgr._note_to_sharp(novo_range_min)
            novo_range_max = self.coristas_mgr._note_to_sharp(novo_range_max)

            # Validar ranges
            try:
                note_to_midi(novo_range_min)
                note_to_midi(novo_range_max)
                if note_to_midi(novo_range_min) > note_to_midi(novo_range_max):
                    raise ValueError(f"Range inválido: {novo_range_min} > {novo_range_max}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao validar range: {str(e)}")
                return

            try:
                # Se o nome mudou, precisamos renomear no gerenciador
                if novo_nome != corista_nome:
                    # Verificar se novo nome já existe
                    if novo_nome in self.coristas_mgr.coristas:
                        messagebox.showerror("Erro", f"Corista '{novo_nome}' já existe!")
                        return
                    # Remover antigo e adicionar com novo nome
                    self.coristas_mgr.coristas.pop(corista_nome)

                # Recalcular vozes compatíveis com a lógica de add_corista
                vozes_recomendadas, vozes_possiveis = self.coristas_mgr.calculate_compatible_voices(
                    novo_range_min, novo_range_max)
                all_compatible = vozes_recomendadas + [v[0] for v in vozes_possiveis]
                voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                    vozes_possiveis[0][0] if vozes_possiveis else VOICES[0])

                # Atualizar dados do corista
                corista_atualizado = {
                    'range_min': novo_range_min,
                    'range_max': novo_range_max,
                    'voz_calculada': voz_calculada,
                    'voz_atribuida': nova_voz,
                    'vozes_recomendadas': vozes_recomendadas,
                    'vozes_possiveis': vozes_possiveis
                }

                self.coristas_mgr.coristas[novo_nome] = corista_atualizado
                self.coristas_mgr.save_corista(corista_nome=novo_nome, replace=corista_nome)

                # Se houve mudança de nome, remover arquivo antigo
                if novo_nome != corista_nome:
                    self.coristas_mgr.remove_corista(corista_nome)

                self.reload_coristas_table()
                self.coristas_mgr.save_corista(corista_nome=novo_nome)

                # Atualizar ranges de grupo/voz se necessário
                if self.music_name_var.get() != "Nome da música" and self.music_name_var.get() != "":
                    self.toggle_group_or_voice_ranges()
                    if not self._use_group_ranges:
                        self.toggle_group_or_voice_ranges()

                self.load_music_library()

                messagebox.showinfo("Sucesso", f"Corista '{novo_nome}' atualizado com sucesso!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Erro ao salvar", f"Erro ao atualizar corista: {str(e)}")

        # Botões
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Confirmar", command=confirm).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side="left", padx=10)

    def on_delete_key(self, event):
        """Chamado quando a tecla Delete é pressionada"""
        selected_item = self.tree_coristas.selection()
        if selected_item:
            self.remove_corista()
        return "break"  # Impede que o evento propague

    def _clear_music_fields(self):
        """Limpa todos os campos da UI relacionados à música atual (robusto)."""

        # Helper local para limpar variáveis que podem ser StringVar ou string comum
        def safe_clear_var(var):
            if var is None:
                return
            if hasattr(var, "set"):
                try:
                    var.set("")
                except Exception:
                    pass
            else:
                # Caso seja uma string simples armazenada como atributo
                return ""

        # Limpar ranges das vozes
        for voice, vr in getattr(self, "voice_vars", {}).items():
            min_entry = vr.get("min")
            max_entry = vr.get("max")

            for entry in (min_entry, max_entry):
                if entry is None:
                    continue
                if hasattr(entry, "delete"):
                    try:
                        entry.delete(0, "end")
                    except Exception:
                        pass
                if hasattr(entry, "insert"):
                    try:
                        entry.insert(0, "")
                    except Exception:
                        pass

        # Limpar o nome da música
        if hasattr(self, "music_name_var"):
            safe_clear_var(self.music_name_var)

        # Nova: limpar solistas
        if hasattr(self, "solist_count_cb"):
            try:
                self.solist_count_cb.set(0)
                self._build_solists_ui()
            except Exception:
                pass
        self.solistas = {}
        if hasattr(self, "solist_rows"):
            for idx, row in enumerate(self.solist_rows):
                if idx >= len(getattr(self, "solist_rows", [])):
                    break
                # Define o nome do solista
                if "cb" in row and row["cb"]:
                    try:
                        row["cb"].set("")
                    except Exception:
                        pass
                # Define range mínimo e máximo
                if "min" in row and row["min"]:
                    try:
                        row["min"].delete(0, "end")
                        row["min"].insert(0, "")
                    except Exception:
                        pass
                if "max" in row and row["max"]:
                    try:
                        row["max"].delete(0, "end")
                        row["max"].insert(0, "")
                    except Exception:
                        pass

        # Limpar coristas/voz atribuída (se aplicável)
        if hasattr(self, "coristas_mgr"):
            try:
                for c in self.coristas_mgr.coristas.values():
                    if isinstance(c, dict) and "voz_atribuida" in c:
                        c["voz_atribuida"] = ""
                self.reload_coristas_table()
            except Exception:
                pass

        # Limpar resultados e Análise
        self.clear_results()
        self.run_analysis()

    def adicionar_grupo(self):
        nome = simpledialog.askstring("Adicionar Grupo", "Nome do Novo Grupo:")
        if nome and nome.strip():
            nome = nome.strip()

            # Adicionar no banco de dados
            self.coristas_mgr.adicionar_grupo(nome)

            # Acrescentar grupo à lista de grupos
            self.grupo_combo.set(nome)
            self.grupo_combo['values'] = self.coristas_mgr.read_data(extract='grupos', group_list=True)

            # Resetar músicas
            self.music_name_var.set(self.music_name_placeholder)
            self.music_name_entry.delete(0, tk.END)
            self.music_name_entry.config(fg="black")
            self.music_name_entry.insert(0, self.music_name_placeholder)
            self.music_var.set('')
            self.music_combo.set("-- Selecione uma música --")
            self.load_music_ranges_for_selection(self.music_combo.get())

            # Atualisar lista de coristas
            self.coristas_mgr.coristas.clear()
            self._on_group_selected()

    def load_voice_audio_files(self):
        from tkinter import filedialog
        self.voice_audio_paths = {}
        for v in VOICES:
            path = filedialog.askopenfilename(title=f"Selecione áudio para a voz {v}",
                                              filetypes=[("Audio", "*.wav *.mp3 *.flac"), ("All files", "*.*")])
            if path:
                self.voice_audio_paths[v] = path
            else:
                self.voice_audio_paths[v] = None

        # Determina o nome da música
        music_name = None
        if hasattr(self, "music_name_var") and self.music_name_var:
            music_name = self.music_name_var.get().strip()

        if not music_name:
            # Deriva do primeiro caminho disponível
            for p in self.voice_audio_paths.values():
                if p:
                    base = os.path.basename(p)
                    music_name = os.path.splitext(base)[0]
                    break

        if not music_name:
            messagebox.showerror("Erro", "Nome da música não informado nem derivável a partir dos caminhos fornecidos.")
            return

        # Caminho de saída raiz (conforme sua organização)
        root_musicas = Path("root") / "Musicas"  # atende ao formato root/Musicas/{nome_da_musica}
        music_root = root_musicas / music_name
        # Não criamos ainda; criaremos ao salvar outputs por voz

        # Processa cada faixa por voz
        for voz, path in self.voice_audio_paths.items():
            if not path:
                continue

            # Processo com AudioAnalyzer
            result = self.analyzer.process_music(path, music_name)

            # Preenche min/max com extrema (extrema é uma lista tipo [min_note, max_note])
            extrema = result.get("extrema")
            if extrema and len(extrema) >= 2:
                min_name, max_name = extrema[0], extrema[1]
                if voz in self.voice_vars:
                    # Atualiza UI com as novas faixas
                    self.voice_vars[voz]["min"].delete(0, "end")
                    self.voice_vars[voz]["min"].insert(0, min_name)
                    self.voice_vars[voz]["max"].delete(0, "end")
                    self.voice_vars[voz]["max"].insert(0, max_name)

            # Hard: salvar outputs em root/Musicas/{nome_da_musica}/{voz}/
            voice_dir = music_root / voz
            voice_dir.mkdir(parents=True, exist_ok=True)

            # Caminhos de origem retornados pelo AudioAnalyzer
            notes_src = result.get("notes_detected_path")
            normalized_src = result.get("normalized_path")
            midi_src = result.get("midi_path")

            # Copia/Move para a pasta da música e com nomes únicos por voz
            if notes_src:
                dest_notes = voice_dir / f"{music_name}_notes_detected.json"
                try:
                    shutil.copy2(notes_src, dest_notes)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar notes para {dest_notes}: {e}")

            if normalized_src:
                dest_normalized = voice_dir / f"{music_name}_normalized.json"
                try:
                    shutil.copy2(normalized_src, dest_normalized)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar normalized para {dest_normalized}: {e}")

            if midi_src:
                dest_midi = voice_dir / f"{music_name}_midi.mid"
                try:
                    shutil.copy2(midi_src, dest_midi)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar MIDI para {dest_midi}: {e}")

        messagebox.showinfo("Sucesso",
                            f"Processamento concluído para '{music_name}'. Saídas salvas em root/Musicas/{music_name}/ (por voz).")

    def _on_root_selected(self, event):
        self.root_var.set(self.root_combo.get())

    def _on_mode_selected(self, event):
        self.mode_var.set(self.mode_combo.get())

    def _on_double_click_corista(self, event):
        item_id = self.tree_coristas.focus()
        if not item_id:
            return

        # Opcional: garanta que o item esteja selecionado
        self.tree_coristas.selection_set(item_id)

        # Tenta chamar a função de edição de corista já existente
        # Se edit_corista_voz aceitar um argumento, passe-o; senão, chame sem argumentos
        try:
            self.edit_corista_voz(item_id)
        except TypeError:
            self.edit_corista_voz()

    def clear_results(self):
        """Limpa a área de resultados"""
        self.results_text.delete(1.0, "end")
        self.results_text.insert("end", "Resultados limpos. Informe os ranges vocais e execute a análise novamente.\n")

    ### TESTE VOCAL
    def _on_testing_time_changed(self, event):
        try:
            new_time = int(self.testing_time_cb.get())

            # Atualiza o valor por padrão no core (padrão global) e na UI
            VocalTestCore.DEFAULT_TESTING_TIME = new_time

            # Atualiza o valor local da UI
            self.testing_time = new_time

            # Se houver uma instância rodando do core de teste, atualize-a também
            if getattr(self, "vocal_tester", None) is not None:
                self.vocal_tester.testing_time = new_time

            # Atualiza o rótulo do tempo na UI (se aplicável)
            self.time_label.config(text=f"Tempo: 0.0s / {new_time}.0s")
        except Exception:
            pass

    def repeat_tone_vocal(self):
        """Reproduz o tom atual novamente (se houver tom ativo)"""
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            freq = self.vocal_tester.current_playing_frequency
            if freq and freq > 0:
                # Executa em outra thread para não bloquear a UI
                threading.Thread(target=self.vocal_tester.play_note, args=(freq, 2), daemon=True).start()
                self.status_label.config(text="Reproduzindo tom atual...", foreground='#27AE60')
                return
        # Caso não haja tom disponível
        messagebox.showinfo("Aviso", "Nenhum tom atual para repetir.")

    def start_vocal_test(self):
        """Inicia o teste vocal normal"""
        if self.vocal_tester is not None:
            messagebox.showwarning("Aviso", "Um teste já está em andamento!")
            return

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.update_vocal_test_ui,
            complete_callback=self.on_vocal_test_complete,
            button_callback=self.update_button_states
        )

        self.btn_start_test.config(state='disabled')
        self.btn_quick_test.config(state='disabled')
        self.btn_stop_test.config(state='normal')
        self.status_label.config(text="Iniciando teste normal...", foreground='#F39C12')

        threading.Thread(target=self.vocal_tester.start_test, daemon=True).start()

    def start_quick_vocal_test(self):
        """Inicia o teste vocal rápido"""
        if self.vocal_tester is not None:
            messagebox.showwarning("Aviso", "Um teste já está em andamento!")
            return

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.update_vocal_test_ui,
            complete_callback=self.on_vocal_test_complete,
            button_callback=self.update_button_states
        )

        self.btn_start_test.config(state='disabled')
        self.btn_quick_test.config(state='disabled')
        self.btn_stop_test.config(state='normal')

        self.status_label.config(text="Iniciando teste rápido...", foreground='#F39C12')

        threading.Thread(target=self.vocal_tester.start_quick_test, daemon=True).start()

    def mark_too_low_vocal(self):
        """Marca como grave demais"""
        if self.vocal_tester:
            self.vocal_tester.mark_too_low()

    def mark_too_high_vocal(self):
        """Marca como agudo demais"""
        if self.vocal_tester:
            self.vocal_tester.mark_too_high()

    def stop_vocal_test(self):
        """Para o teste vocal"""
        if self.vocal_tester:
            self.vocal_tester.stop_test()

        self.btn_start_test.config(state='normal')
        self.btn_quick_test.config(state='normal')
        self.btn_stop_test.config(state='disabled')
        self.btn_too_low.config(state='disabled')
        self.btn_too_high.config(state='disabled')

        self.status_label.config(text="Teste cancelado", foreground='#E74C3C')
        self.vocal_tester = None

    def update_vocal_test_ui(self, **kwargs):
        """Atualiza os elementos visuais do teste vocal"""
        if 'expected_note' in kwargs:
            self.expected_note_label.config(text=kwargs['expected_note'])

        if 'expected_freq' in kwargs:
            # Pode ser frequência ou texto
            pass

        if 'detected_note' in kwargs:
            self.detected_note_label.config(text=kwargs['detected_note'])

        if 'status' in kwargs:
            color = kwargs.get('status_color', '#666')
            self.status_label.config(text=kwargs['status'], foreground=color)

        if 'time' in kwargs:
            self.time_var.set(kwargs['time'])

        if 'time_text' in kwargs:
            self.time_label.config(text=kwargs['time_text'])

        if 'offset_cents' in kwargs:
            self.belt_indicator.set_offset(kwargs['offset_cents'])

        # Novo: aceitar também atualizações diretas de botões
        button_map = [
            ('start_button', getattr(self, 'btn_start_test', None)),
            ('start_quick_button', getattr(self, 'btn_quick_test', None)),
            ('stop_button', getattr(self, 'btn_stop_test', None)),
            ('repeat_button', getattr(self, 'btn_repeat', None)),  # pode não existir
            ('too_low_button', getattr(self, 'btn_too_low', None)),
            ('too_high_button', getattr(self, 'btn_too_high', None)),
        ]

        for key, btn in button_map:
            if btn is None:
                continue
            if key in kwargs:
                btn.config(state=kwargs[key])

        # Compatibilidade com o formato antigo: button_states
        if 'button_states' in kwargs:
            states = kwargs['button_states']
            if self.btn_too_low:
                self.btn_too_low.config(state=states.get('too_low', 'disabled'))
            if self.btn_too_high:
                self.btn_too_high.config(state=states.get('too_high', 'disabled'))
            # opcional: mapear outros botões se houver
            # Exemplos adicionais:
            if 'start' in states and self.btn_start_test:
                self.btn_start_test.config(state=states['start'])
            if 'start_quick' in states and self.btn_quick_test:
                self.btn_quick_test.config(state=states['start_quick'])
            if 'stop' in states and self.btn_stop_test:
                self.btn_stop_test.config(state=states['stop'])

        # Novo: alimentar gráfico de pitch em tempo real
        if 'pitch_hz' in kwargs:
            hz = kwargs['pitch_hz']
            if hz is not None and hz > 0:
                # Executa na thread da UI
                self.master.after(0, self.pitch_line_chart.add_sample, hz)

    def update_button_states(self, **kwargs):
        """Atualiza estado dos botões"""
        button_states = kwargs.get('button_states', {})
        self.btn_too_low.config(state=button_states.get('too_low', 'disabled'))
        self.btn_too_high.config(state=button_states.get('too_high', 'disabled'))

    def on_vocal_test_complete(self, range_min, range_max):
        """Chamado quando o teste vocal termina"""
        if range_min and range_max:
            self.entrada_min.delete(0, "end")
            self.entrada_min.insert(0, range_min)
            self.entrada_max.delete(0, "end")
            self.entrada_max.insert(0, range_max)

            self.status_label.config(
                text=f"✓ Ranges preenchidos: {range_min} - {range_max}",
                foreground='#27AE60'
            )
            messagebox.showinfo("Sucesso", f"Ranges preenchidos:\nMín: {range_min}\nMáx: {range_max}")
        else:
            self.status_label.config(text="Nenhum resultado", foreground='#E74C3C')
            messagebox.showwarning("Aviso", "Teste foi cancelado ou não retornou resultados")

        # Reset dos botões
        self.btn_start_test.config(state='normal')
        self.btn_quick_test.config(state='normal')
        self.btn_stop_test.config(state='disabled')
        self.btn_too_low.config(state='disabled')
        self.btn_too_high.config(state='disabled')

        self.vocal_tester = None
    ### ANÁLISE
    def toggle_group_or_voice_ranges(self):
        # Inverte o modo entre "Vozes Grupo" e "Vozes Base" (ou "VOICES")
        current = getattr(self, "_use_group_ranges", False)
        self._use_group_ranges = not current
        if getattr(self, "_use_group_ranges", False):
            # Estamos usando os ranges de grupo
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                self.group_ranges, self.group_extension = self.coristas_mgr.get_voice_group_ranges(solistas=self.solistas if self.solistas else None)

                # Atualiza o visualizador se ele suportar ranges de grupo
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(self.group_ranges)
            else:
                # Sem ranges de grupo disponíveis; fallback para base
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(None)
        else:
            self.group_ranges = None
            self.group_extension = None

        # Reexecuta a análise para refletir o novo range com o T atual
        self.run_analysis()

    def run_analysis(self):
        """
        Versão unificada de run_analysis:
        - Calcula a melhor transposição global (best_T, best_Os, nova chave)
        - Calcula O_i para o T atual (barra de transposição) para atualização do visualizador
        - Exibe resultados de forma consistente
        """
        try:
            piece_ranges = self.read_voice_ranges() if not getattr(self, "_use_group_ranges", False) or not self.solistas else self.solistas | self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            # T atual vindo da barra de transposição
            t_current = int(float(self.t_slider.get())) if hasattr(self, "t_slider") else 0

            # Obter ranking completo de Ts (debug) para exibir possíveis transposições
            self.analysis_all = analyze_ranges_with_penalty(self.root_var.get(), self.mode_var.get(), piece_ranges, self.group_ranges)

            # Exibir resultados de forma consistente
            self.on_t_change(t_current)

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def on_t_change(self, value):
        """
        Atualização: quando o usuário altera T, exibimos todas as mensagens de display_results
        usando os valores já aplicados (T atual) para manter consistência.
        """
        try:
            T = int(float(value))
            piece_ranges = getattr(self, "current_piece_ranges", None)

            if not piece_ranges:
                return

            # Calcula os O_i para o T atual
            per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, self.group_ranges)

            # Atualiza visualização gráfica com o T atual
            self.visualizer.update(piece_ranges, T, per_voice_Os, self.group_ranges, self.group_extension, self.analysis_all['voice_scores'])

            current_root = self.root_var.get()

            # Transposição atual para exibição
            transposed_root = transpose_note(current_root, T)

            # Construção consolidada do bloco de resultados
            self.results_text.delete(1.0, "end")

            best_T_global = self.analysis_all.get("best_T")
            best_key_root = self.analysis_all.get("best_key_root")
            best_key_mode = self.analysis_all.get("best_key_mode")
            if best_T_global is not None:
                self.results_text.insert("end", f"Melhor transposição: {best_T_global:+d} semitons → {best_key_root} {best_key_mode}\n")

            self.results_text.insert("end",
                                     f"Transposição atual: {T:+d} semitons ({current_root} → {transposed_root})\n")

            debug = self.analysis_all.get("debug", [])
            # Possíveis transposições (debug)
            if debug:
                if len(debug) > 0:
                    pairs = []
                    i = 0
                    while i < len(debug):
                        if debug[i] == 0:
                            pairs.append(str(debug[i]))  # 0 fica sozinho
                            i += 1
                        else:
                            pairs.append(f"({debug[i]}/{debug[i + 1]})")
                            i += 2
                    self.results_text.insert("end", "Possíveis transposições: " + ", ".join(pairs) + " semitons\n")
                else:
                    self.results_text.insert("end", f"Transposição possível: {debug[0]:+d} semitons\n")

            # Faixas resultantes após a transposição aplicada
            self.results_text.insert("end", "\nFaixas resultantes:\n")
            for v in self.group_ranges.keys() if getattr(self, "_use_group_ranges", False) else VOICES:
                mn, mx = piece_ranges.get(v, (None, None))
                if not mn or not mx:
                    continue
                min_m = note_to_midi(mn)
                max_m = note_to_midi(mx)
                O = per_voice_Os.get(v, 0)
                O_i = 'oitava' if O > -2 and O < 2 else 'oitavas'
                min_final = min_m + T + 12 * O
                max_final = max_m + T + 12 * O
                self.results_text.insert("end",f"  {v}: {midi_to_note(int(min_final))} → {midi_to_note(int(max_final))}")
                self.results_text.insert("end",f" ({O} {O_i})\n") if O != 0 else self.results_text.insert("end","\n")

        except Exception:
            pass

class CoristasManager:
    def __init__(self, data_file=DATA_FILE, grupo=None):
        self.data_file = data_file
        self.grupo = grupo          # Nome do grupo atual
        self.coristas = {}          # Dict de coristas do grupo atual

    def set_group(self, grupo):
        """Atualiza o grupo atual e recarrega os coristas desse grupo."""
        self.grupo = grupo
        self.load_data()

    def load_data(self):
        #data, lista_grupos = self.read_data('grupos', both=True, group_list=True)
        with open(self.data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            lista_grupos = list(data.get('grupos', {}).keys())

        self.grupo = lista_grupos[0] if len(lista_grupos) > 0 and not self.grupo else self.grupo

        # versão: coristas é um dicionário, não lista
        self.coristas = data['grupos'][self.grupo]

    def save_music_ranges_to_json(self,
                                  music_name: str,
                                  ranges: dict,
                                  solistas: dict,
                                  vozes_por_corista: dict,
                                  root: str,
                                  mode: str) -> bool:
        """
        Salva ou atualiza uma música no arquivo de dados.
        Realiza UMA ÚNICA LEITURA E ESCRITA do arquivo.

        Args:
            music_name: Nome da música
            ranges: Dict {voz: {"min": nota, "max": nota}} - ranges da música
            solistas: Dict {nome_solista: [min, max]} - ranges dos solistas
            vozes_por_corista: Dict {voz: [lista_de_coristas]} - vozes atribuídas
            root: Nota raiz (ex: "C")
            mode: Modo ("maior" ou "menor")

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if not music_name or music_name == "Untitled":
            return False, "Nome da música é obrigatório"

        # Normalizar ranges com _note_to_sharp
        ranges_normalized = {}
        for voz, rng in ranges.items():
            min_val = self._note_to_sharp(rng.get("min", "").upper())
            max_val = self._note_to_sharp(rng.get("max", "").upper())
            ranges_normalized[voz] = {"min": min_val, "max": max_val}

        # Validar ranges
        NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|b)?[2-7])?$")
        invalids = []
        for voz, rng in ranges_normalized.items():
            if not NOTA_PATTERN.fullmatch(rng.get("min", "")):
                invalids.append((voz, "min", rng.get("min")))
            if not NOTA_PATTERN.fullmatch(rng.get("max", "")):
                invalids.append((voz, "max", rng.get("max")))

        if invalids:
            msgs = [f"'{valor}' é inválido para {voz} ({campo})"
                    for voz, campo, valor in invalids]
            return False, "; ".join(msgs) + "\nEsperado: letra A-G + número 2-7"

        try:
            # ===== UMA ÚNICA ABERTURA DO ARQUIVO =====
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"grupos": {}, "musicas": {}}

            # ===== TODAS AS MODIFICAÇÕES EM MEMÓRIA =====
            # 1) Atualizar/criar grupo se necessário
            if self.grupo and self.grupo not in data.get("grupos", {}):
                data.setdefault("grupos", {})[self.grupo] = self.coristas

            # 2) Criar ou sobrescrever música
            data.setdefault("musicas", {})[music_name] = {
                "root": root,
                "mode": mode,
                "grupo": self.grupo,
                "ranges": ranges_normalized,
                "solistas": solistas or {},
                "voices": vozes_por_corista or {},
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            # ===== ÚNICA ESCRITA NO ARQUIVO =====
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True, f"Faixa '{music_name}' salva com sucesso!"

        except Exception as e:
            return False, f"Erro ao salvar faixa: {str(e)}"

    def check_music_exists(self, music_name: str) -> bool:
        """Verifica se uma música já existe no arquivo"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return music_name in data.get("musicas", {})
        except Exception:
            pass
        return False


    def save_corista(self, corista_nome=None, replace=None):
        """Salva dados no arquivo JSON sob o grupo atual: grupos -> nome_grupo -> coristas"""
        if not self.grupo:
            print("Grupo não definido para salvar coristas.")
            return False

        try:
            mode = 'r+' if os.path.exists(self.data_file) else 'w+'

            with open(self.data_file, mode, encoding='utf-8') as f:
                if mode == 'r+':
                    try:
                        f.seek(0)
                        data = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        data = {}

                if not isinstance(data, dict):
                    data = {}

                if 'grupos' not in data or not isinstance(data['grupos'], dict):
                    data['grupos'] = {}

                if self.grupo not in data['grupos']:
                    data['grupos'][self.grupo] = {}

                # Atualiza coristas
                if replace:
                    data['grupos'][self.grupo][corista_nome] = data['grupos'][self.grupo].pop(replace)

                    # Atualiza referências em músicas do mesmo grupo
                    if 'musicas' in data and isinstance(data['musicas'], dict):
                        for musica in data['musicas'].values():
                            if musica.get('grupo') == self.grupo:
                                # Solistas: renomeia chave mantendo valor
                                if 'solistas' in musica and replace in musica['solistas']:
                                    musica['solistas'][corista_nome] = musica['solistas'].pop(replace)

                                # Voices: substitui nome em listas de naipes
                                if 'voices' in musica and isinstance(musica['voices'], dict):
                                    for naipe in musica['voices'].values():
                                        if isinstance(naipe, list) and replace in naipe:
                                            naipe[naipe.index(replace)] = corista_nome

                if corista_nome:
                    data['grupos'][self.grupo][corista_nome] = self.coristas[corista_nome]
                else:
                    data['grupos'][self.grupo] = self.coristas

                # Escreve no arquivo
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"Erro ao salvar dados: {e}")
            return False

    def _note_to_sharp(self, note: str) -> str:
        if len(note) < 3:
            return note
        letter = note[0]
        acc = note[1].lower()
        octave = int(note[2])

        natural_offsets = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        midi = 12 * (octave + 1) + natural_offsets[letter]

        if acc == '#':
            midi += 1
        elif acc == 'b':
            midi -= 1

        name = SEMITONE_TO_SHARP[midi % 12]
        out_oct = (midi // 12) - 1

        return f"{name}{out_oct}"

    def note_to_number(self, nota):
        """Converte nota musical (ex: 'C4', 'B#2') para número comparável"""
        nota = nota.strip()

        # Mapa de notas
        notas_map = {
            'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
        }

        # Extrai a nota base e oitava
        nota_base = nota[0]

        # Verifica acidentes
        valor = notas_map.get(nota_base, 0)

        if '#' in nota:
            valor += 1
        elif 'b' in nota:
            valor -= 1

        # Extrai a oitava
        oitava_str = ''.join(c for c in nota if c.isdigit() or c == '-')
        oitava = int(oitava_str) if oitava_str else 0

        # Retorna um número único: oitava * 12 + nota
        return oitava * 12 + valor

    def adicionar_grupo(self, nome):
        with open(DATA_FILE, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data['grupos'][nome] = {}
            # Salvar
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()

    def read_data(self, extract=None, all_in=False, both=False, group_list=False):
        if not os.path.exists(self.data_file):
            return {} if not extract else {f'{extract}_não_encontrado': True}

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Retorna apenas o que foi solicitado
            if extract:
                if all_in:
                    if group_list:
                        return data, data.get(extract, {}), list(data.get('grupos', {}).keys())
                    return data, data.get(extract, {})
                if group_list:
                    if both:
                        return data, list(data.get('grupos', {}).keys())
                    return list(data.get('grupos', {}).keys())
                return data.get(extract, {})

            return data

        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")
            return {} if not extract else {}
        except Exception as e:
            print(f"Erro ao ler dados: {e}")
            return {} if not extract else {}

    def add_corista(self, nome, range_min, range_max):
        """Adiciona um corista com vozes compatíveis"""
        try:
            # Validação: cada valor deve ser do formato A-G seguido de 2-7
            NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|B)?[2-7])?$")

            invalids = []
            if not NOTA_PATTERN.fullmatch(range_min):
                invalids.append(range_min)
            if not NOTA_PATTERN.fullmatch(range_max):
                invalids.append(range_max)
            if invalids:
                # Opcional: construir uma mensagem mais legível
                msgs = [f"'{" e ".join(invalids)}' são inválidos!"] if len(invalids) > 1 else f"'{invalids[0]}' é inválido!"
                messagebox.showerror("Nota inexistente",
                                     msgs + "\nEsperado: uma letra A-G seguida de um número 2-7.\n"
                                     )
                return False, []

            # Padroniza bemois em sustenidos
            range_min = self._note_to_sharp(range_min)
            range_max = self._note_to_sharp(range_max)

            # Valida ranges
            note_to_midi(range_min)
            note_to_midi(range_max)
            if note_to_midi(range_min) > note_to_midi(range_max):
                raise ValueError(f"Range inválido: {range_min} > {range_max}")

            # Calcula vozes compatíveis
            vozes_recomendadas, vozes_possiveis = self.calculate_compatible_voices(range_min, range_max)
            all_compatible = vozes_recomendadas + [v for v in vozes_possiveis]
            voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0] if vozes_possiveis else VOICES[0])

            corista = {
                    'range_min': range_min,
                    'range_max': range_max,
                    'voz_calculada': voz_calculada,
                    'voz_atribuida': voz_calculada,
                    'vozes_recomendadas': vozes_recomendadas,
                    'vozes_possiveis': vozes_possiveis  # Lista de tuples: (voz, diff, obs)
                }

            self.coristas[nome] = corista
            self.save_corista(nome)
            return True, corista
        except Exception as e:
            return False, str(e)

    def remove_corista(self, corista_nome):
        # Verifica se o corista existe no grupo atual
        if corista_nome not in self.coristas:
            return False

        # Remove o corista do grupo na memória (já usaremos self.grupo apenas para referência)
        self.coristas.pop(corista_nome, None)
        grupo = self.grupo

        def rreplace(s, old, new):
            if old == "":
                return ""

            i = s.rfind(old)
            if i == -1:
                return s
            return s[:i] + new + s[i + len(old):]

        try:
            with open(self.data_file, 'r+', encoding='utf-8') as f:
                data = json.load(f)

                # 1) Construir todas_vozes a partir das informações do corista antes da remoção
                groups = data.setdefault("grupos", {})
                grupo_dict = groups.setdefault(grupo, {})

                corista_info = grupo_dict.get(corista_nome, {})
                todas_vozes = set()

                if corista_info:
                    voz_atribuida = corista_info.get("voz_atribuida")
                    if voz_atribuida:
                        todas_vozes.add(voz_atribuida)

                    todas_vozes.update(corista_info.get("vozes_recomendadas", []))
                    todas_vozes.update(corista_info.get("vozes_possiveis", []))

                # 2) Remover o corista do grupo
                grupo_dict.pop(corista_nome, None)

                # 3) Atualizar músicas do mesmo grupo
                musics = data.get("musicas", {})
                solista = []
                corista = []
                vozes = {}
                for music, value in musics.items():
                    if value.get("grupo") != grupo:
                        continue

                    # 3a) Remover do mapeamento de voices
                    voices_map = value.setdefault("voices", {})
                    for voice_name, members in list(voices_map.items()):
                        if voice_name in todas_vozes and isinstance(members, list) and corista_nome in members:
                            corista.append(music)
                            members.remove(corista_nome)
                            # Se a lista ficou vazia, remova a voz por completo
                            if len(members) == 0:
                                vozes[music] =  voice_name
                                del voices_map[voice_name]

                    # 3b) Remover do campo solistas, se estiver presente
                    solistas_map = value.get("solistas", {})
                    if corista_nome in solistas_map:
                        solista.append(music)
                        del solistas_map[corista_nome]

                # 4) Gravação atômica de volta no arquivo (ou simples overwrite com truncate)
                msg = f"Tem certeza que quer remover '{corista_nome}'?"
                if solista or corista or vozes:
                    msg += " Isso afetará:\n"
                    if corista:
                        msg += f" - a lista de coristas de '{rreplace("', '".join(corista), ", ", " e ")}'\n"
                    if vozes:
                        for key in vozes:
                            msg += f"     - removerá '{vozes[key]}' da música: '{key}'\n"
                    if solista:
                        msg += f" - a lista de solistas de '{rreplace("', '".join(solista), ", ", ' e ')}'"
                remover = messagebox.askyesno(
                    "Aviso",
                    msg
                )
                if remover:
                    f.seek(0)
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.truncate()

                    return data
                return False
        except Exception as e:
            # Opcional: loga o erro
            print(f"Erro ao atualizar dados: {e}")
            return False

    def update_corista_voz(self, nome, voz_atribuida):
        """Atualiza a voz atribuída de um corista"""
        if nome in self.coristas.keys():
            self.coristas[nome]['voz_atribuida'] = voz_atribuida
            return True
        return False

    def calculate_compatible_voices(self, range_min: str, range_max: str, observations=False) -> tuple:
        """
        Calcula todas as vozes compatíveis com o range fornecido.

        Retorna: (vozes_recomendadas, vozes_possiveis)
        - vozes_recomendadas: lista de vozes com encaixe perfeito
        - vozes_possiveis: lista de tuples (voz, max_diff, obs) com até 3 semitons de diferença
        """
        try:
            min_midi = note_to_midi(range_min)
            max_midi = note_to_midi(range_max)

            vozes_recomendadas = []
            vozes_possiveis = []

            for voice in VOICES:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                voice_min = note_to_midi(voice_min_str)
                voice_max = note_to_midi(voice_max_str)

                # Encaixe perfeito: o range do corista CABE dentro da faixa da voz
                if min_midi <= voice_min and max_midi >= voice_max:
                    vozes_recomendadas.append(voice)
                else:
                    diff_min = max(0, min_midi - voice_min)
                    diff_max = max(0, voice_max - max_midi)
                    max_diff = max(diff_min, diff_max)

                    if max_diff <= 5:
                        if observations:
                            obs = ""
                            if diff_min > 0:
                                obs += f"Falta {diff_min} semitom"
                                obs += " grave"
                            if diff_max > 0:
                                if obs:
                                    obs += " e "
                                obs += f"Falta {diff_max} semitom"
                                obs += " agudo"
                            vozes_possiveis.append((voice, max_diff, obs))
                        else:
                            vozes_possiveis.append(voice)

            vozes_possiveis.sort(key=lambda x: x[1])

            return vozes_recomendadas, vozes_possiveis
        except Exception as e:
            print(f"Erro ao calcular vozes compatíveis: {e}")
            return [], []

    def calculate_voice(self, range_min, range_max) -> str:
        """
        Retorna a voz primária (a melhor entre as compatíveis).
        """
        vozes_recomendadas, vozes_possiveis = self.calculate_compatible_voices(range_min, range_max)

        if vozes_recomendadas:
            return vozes_recomendadas[0]
        elif vozes_possiveis:
            return vozes_possiveis[0][0]
        else:
            return VOICES[0]

    def get_voice_group_ranges(self, solistas=None) -> dict:
        """
        Calcula os ranges do grupo por voz.
        """
        voice_groups = {v: [] for v in VOICES}

        # Agrupa coristas por voz atribuída
        for corista in self.coristas:
            voz = self.coristas[corista]['voz_atribuida']
            min_midi = note_to_midi(self.coristas[corista]['range_min'])
            max_midi = note_to_midi(self.coristas[corista]['range_max'])
            voice_groups[voz].append((min_midi, max_midi))

        # Calcula range do grupo: maior mínimo e menor máximo
        group_ranges = {}
        group_extension = {}
        for voz in VOICES:
            if voice_groups[voz]:
                mins = [r[0] for r in voice_groups[voz]]
                maxs = [r[1] for r in voice_groups[voz]]

                group_min = max(mins)  # maior mínimo
                group_max = min(maxs)  # menor máximo

                if group_min <= group_max:
                    group_ranges[voz] = (midi_to_note(int(group_min)), midi_to_note(int(group_max)))
                    group_extension[voz] = (midi_to_note(int(min(mins))), midi_to_note(int(max(maxs))))

        if solistas:
            # Atualiza os valores de solistas com os ranges de coristas quando disponíveis
            solistas_updated = {
                k: (self.coristas[k]['range_min'], self.coristas[k]['range_max'])
                if k in self.coristas else v
                for k, v in solistas.items()
            }

            # Une com as ranges de grupo
            group_ranges = solistas_updated | group_ranges

        return group_ranges, group_extension

class BeltIndicator(tk.Canvas):
    """
    BeltIndicator self-contained:
    - Semitons na faixa [semitone_min, semitone_max] com espaçamento não-linear
      (centrado em 0, controlado por sigma).
    - O marcador vermelho posiciona-se no semitomo atual correspondente ao offset.
    - O cent-line (indicação de cents) fica dentro do semitomo atual.
    - Fácil de copiar/colar entre arquivos sem dependências externas.
    """

    def __init__(self, master, width=640, height=180,
                 semitone_min=-12, semitone_max=12, sigma=3.0, **kwargs):
        super().__init__(master, width=width, height=height,
                         bg='white', highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.semitone_min = semitone_min
        self.semitone_max = semitone_max
        self.offset_cents = 0  # deslocamento total em cents
        self.sigma = sigma      # controle de centralização dos semitons

        # Cache opcional para evitar recalculos redundantes (instante de draw)
        self._segments_cache = {}

        self.draw()

    def set_offset(self, offset_cents):
        """Atualiza o offset em cents e redesenha, com travas de faixa."""
        if offset_cents is None:
            offset_cents = 0
        # Trava o offset dentro do range permitido pelo belt
        min_cents = self.semitone_min * 100
        max_cents = self.semitone_max * 100
        self.offset_cents = int(max(min(offset_cents, max_cents), min_cents))
        self.draw()

    def set_sigma(self, sigma):
        """Ajusta o sigma (centralização) e redesenha."""
        self.sigma = sigma
        self.draw()

    def set_range(self, semitone_min, semitone_max):
        """Atualiza o range de semitons e redesenha."""
        self.semitone_min = semitone_min
        self.semitone_max = semitone_max
        self.draw()

    def _compute_segments(self, w, pad):
        """
        Compute left_edges e widths para cada semitomo usando
        uma distribuição de peso baseada na distância ao 0.
        Retorna (left_edges, widths, span).
        """
        total_range = self.semitone_max - self.semitone_min
        span = w - 2 * pad
        N = max(-self.semitone_min, self.semitone_max)

        # Pesos por distância d = |semitone|
        # w(d) = exp(-d^2 / (2*sigma^2))
        weights_by_dist = [math.exp(- (d * d) / (2.0 * (self.sigma ** 2))) for d in range(0, N + 1)]

        # Sumarização dos pesos na faixa de semitons
        sum_weights = sum(weights_by_dist[abs(s)]
                          for s in range(self.semitone_min, self.semitone_max + 1))

        left_edges = {}
        widths = {}
        current_x = pad
        for s in range(self.semitone_min, self.semitone_max + 1):
            w_i = span * weights_by_dist[abs(s)] / sum_weights
            left_edges[s] = current_x
            widths[s] = w_i if w_i > 0 else 0.0
            current_x += w_i

        return left_edges, widths, span

    def draw(self):
        self.delete("all")
        w, h = self.width, self.height
        pad = 14
        belt_y = h // 2
        belt_height = max(8, h // 4)

        # Fundo com listras suaves (esteira)
        stripe_w = 8
        for x in range(pad, w - pad, stripe_w):
            color = '#f7fbff' if (x // stripe_w) % 2 == 0 else '#eef6fd'
            self.create_rectangle(
                x, belt_y - belt_height // 2,
                x + stripe_w, belt_y + belt_height // 2,
                fill=color, outline=''
            )

        # Linha central (referência 0)
        self.create_line(pad, belt_y, w - pad, belt_y, fill='#a8a8a8', dash=(4, 6))

        # Calcular segmentos não-lineares
        left_edges, widths, _span = self._compute_segments(w, pad)

        # Ticks de semitomo (usando centro de cada semitomo)
        for s in range(self.semitone_min, self.semitone_max + 1):
            x_tick_center = left_edges[s] + (widths[s] / 2.0)
            self.create_line(x_tick_center, belt_y - belt_height // 2,
                             x_tick_center, belt_y - belt_height // 2 + 6, fill='#555')
            self.create_text(x_tick_center, belt_y + belt_height // 2 + 10,
                             text=f"{s}", font=("Arial", 8), fill='#555')

        # marcador correspondente ao offset total
        semitone_offset = int(round(self.offset_cents / 100.0))
        if semitone_offset < self.semitone_min:
            semitone_offset = self.semitone_min
        if semitone_offset > self.semitone_max:
            semitone_offset = self.semitone_max

        # Posição do semitomo atual (centro)
        x_left = left_edges[semitone_offset]
        width_s = widths[semitone_offset]
        center_x = x_left + width_s / 2.0

        # marcador em formato de triângulo/indicador
        self.create_polygon(
            [center_x - 8, belt_y - belt_height // 2 - 10,
             center_x + 8, belt_y - belt_height // 2 - 10,
             center_x, belt_y - belt_height // 2 - 2],
            fill='#e74c3c', outline='')

        # Indicação de centavos dentro do semitone atual
        within_cents = self.offset_cents - semitone_offset * 100
        # Limita entre -100 e 100
        within_cents = max(-100, min(100, within_cents))

        # Mapear dentro do semitomo: -100 -> lado esquerdo, +100 -> lado direito
        delta = (within_cents / 100.0) * (width_s / 2.0)
        cents_x = center_x + delta

        self.create_line(cents_x, belt_y - belt_height // 2 - 4,
                         cents_x, belt_y + belt_height // 2 + 4,
                         fill='#2c3e50', width=2)

class PitchLineChart(tk.Canvas):
    """
    Gráfico de pitch em tempo real com janela de 5 segundos.
    - Novo ponto fica na borda direita; o histórico preenche para a esquerda.
    - Mostra nomes de notas na esquerda para a faixa visível.
    - Altura ajustável para ocupar espaço vertical desejado.
    """
    def __init__(self, master, width=700, height=230,
                 min_midi=40, max_midi=84, max_points=600,
                 window_seconds=5.0, **kwargs):
        super().__init__(master, width=width, height=height,
                         bg='white', highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.min_midi = min_midi
        self.max_midi = max_midi
        self.max_points = max_points
        self.window_seconds = window_seconds

        # Dados: cada item é {'ts': float, 'midi': float}
        self._samples = deque(maxlen=self.max_points)

        self.plot_min_midi = self.min_midi
        self.plot_max_midi = self.max_midi
        self.draw_initial()

    def _midi_to_note_name(self, midi):
        note_names = ["C", "C#", "D", "D#", "E", "F",
                      "F#", "G", "G#", "A", "A#", "B"]
        octave = int(midi // 12) - 1
        return f"{note_names[int(midi % 12)]}{octave}"

    def add_sample(self, freq_hz):
        now = time.time()
        midi_float = None
        if freq_hz and freq_hz > 0:
            # MIDI como float (para maior precisão)
            midi_float = 69.0 + 12.0 * math.log2(freq_hz / 440.0)
        if midi_float is None:
            return

        # Limite de MIDI float
        midi_float = max(0.0, min(127.0, midi_float))
        self._samples.append({'ts': now, 'midi': midi_float})

        # Remover amostras antigas (janela de 5s)
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0]['ts'] < cutoff:
            self._samples.popleft()

        # Atualizar faixa visível com base nos dados da janela
        if self._samples:
            min_midi = min(s['midi'] for s in self._samples)
            max_midi = max(s['midi'] for s in self._samples)
            self.plot_min_midi = max(0.0, min_midi - 3.0)
            self.plot_max_midi = min(127.0, max_midi + 3.0)
        else:
            self.plot_min_midi = self.min_midi
            self.plot_max_midi = self.max_midi

        self.draw()

    def draw_initial(self):
        self.delete("all")
        self.create_rectangle(0, 0, self.width, self.height, fill='white', outline='')

    def draw(self):
        self.delete("all")

        w, h = self.width, self.height
        pad = 12

        # Fundo
        self.create_rectangle(0, 0, w, h, fill='white', outline='')

        if not self._samples:
            return

        # Função: MIDI (float) -> Y considerando a faixa visível
        def midi_to_y(midi_val):
            span = max(1e-6, self.plot_max_midi - self.plot_min_midi)
            return pad + (h - 2*pad) * (1.0 - (midi_val - self.plot_min_midi) / span)

        # Desenhar grade de semitons visíveis (na faixa atual)
        # Mostrar apenas inteiros dentro da faixa visível
        min_int = int(math.floor(self.plot_min_midi))
        max_int = int(math.ceil(self.plot_max_midi))
        for m in range(min_int, max_int + 1):
            y = midi_to_y(float(m))
            self.create_line(pad, y, w - pad, y, fill="#f0f0f0")
            note_name = self._midi_to_note_name(float(m))
            self.create_text(20, y, text=note_name, anchor="e", fill="#666", font=("Arial", 8))

        # Desenhar linha com os samples da janela (histórico)
        samples = list(self._samples)
        if len(samples) < 2:
            return

        t0 = time.time() - self.window_seconds
        span_time = max(1e-6, self.window_seconds)

        xs = []
        ys = []
        for s in samples:
            ts = s['ts']
            midi = s['midi']
            # x vai do pad (quando ts == t0) até w - pad (quando ts == now)
            x = pad + ((ts - t0) / span_time) * (w - 2*pad)
            x = max(pad, min(w - pad, x))
            y = midi_to_y(midi)
            xs.append(x)
            ys.append(y)

        coords = []
        for x, y in zip(xs, ys):
            coords.extend([x, y])

        self.create_line(*coords, fill='#1f77b4', width=2)

        # marcador na amostra mais recente (à direita)
        x_last, y_last = xs[-1], ys[-1]
        self.create_oval(x_last-4, y_last-4, x_last+4, y_last+4, fill='#e74c3c', outline='')

class VocalTestCore:
    """Núcleo de teste vocal sem interface gráfica - retorna dados apenas"""
    NOISE_GATE_ENABLED = True
    NOISE_GATE_THRESHOLD = 0.0115  # valor em amplitude RMS (ajuste conforme o conjunto de mic)
    DEFAULT_TESTING_TIME = 5

    def __init__(self):
        # Notas musicais...
        self.notes = NOTES_FREQUENCY_HZ

        # Ordem das notas
        self.note_sequence = list(self.notes.keys())
        self.current_note_index = self.note_sequence.index('C4')

        # Break em caso de parar
        self.max_amplitude = 1e-6
        self.silence_break_time = 0.0

        # Novo: flag para calibração rápida pronta + controle de repetição
        self.quick_test_calibration_complete = False

        # Nota atual para repetição
        self.current_playing_note = None
        self.current_playing_frequency = None

        # Range do usuário
        self.lowest_note = None
        self.highest_note = None

        # Estado
        self.phase = 'ascending'
        self.is_testing = False
        self.is_listening = True
        self.correct_time = 0
        self.sample_rate = 44100
        self.chunk_size = 2048
        self.tolerance_cents = 50

        # Buffer circular para frequências detectadas
        self.frequency_buffer = deque(maxlen=30)

        # Estados do teste
        self.c4_skipped_as_low = False
        self.c4_skipped_as_high = False
        self.first_note_achieved = False
        self.should_descend_after_ascending = True
        self._testing_time = VocalTestCore.DEFAULT_TESTING_TIME


        # Modo do teste: 'normal' ou 'quick'
        self.test_mode = 'normal'
        self.quick_test_calibration_complete = False

        # Callbacks para UI (serão fornecidos por VoiceRangeApp)
        self.on_update_ui = None
        self.on_test_complete = None
        self.on_request_button_state = None


    def testing_time(self, value):
        # Garantir que seja inteiro (ou ajuste conforme o esperado)
        self._testing_time = int(value)

    def set_ui_callbacks(self, update_callback, complete_callback, button_callback):
        """Define callbacks para comunicação com a UI"""
        self.on_update_ui = update_callback
        self.on_test_complete = complete_callback
        self.on_request_button_state = button_callback

    def _update_ui(self, **kwargs):
        """Invoca callback de atualização de UI"""
        if self.on_update_ui:
            self.on_update_ui(**kwargs)

    def _button_state(self, **kwargs):
        """Invoca callback para estado de botões"""
        if self.on_request_button_state:
            self.on_request_button_state(**kwargs)

    def _test_complete(self):
        """Invoca callback de conclusão de teste"""
        if self.on_test_complete:
            self.on_test_complete(self.lowest_note, self.highest_note)

    def frequency_to_note(self, frequency):
        """Converte frequência em nota musical"""
        if frequency is None or frequency <= 0:
            return None, None

        min_diff = float('inf')
        closest_note = None

        for note, freq in self.notes.items():
            diff = abs(frequency - freq)
            if diff < min_diff:
                min_diff = diff
                closest_note = note

        return closest_note, min_diff

    def frequency_to_cents(self, freq1, freq2):
        """Converte diferença de frequência em cents"""
        if freq1 <= 0 or freq2 <= 0:
            return float('inf')
        return 1200 * np.log2(freq1 / freq2)

    def detect_pitch(self, audio_data):
        """Detecta o pitch fundamental usando librosa YIN"""
        if len(audio_data) < self.chunk_size:
            return None

        audio_data = np.array(audio_data, dtype=np.float32)
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data))

        try:
            f0 = librosa.yin(audio_data, fmin=50, fmax=1000, sr=self.sample_rate, trough_threshold=0.1)

            if isinstance(f0, np.ndarray):
                f0 = np.mean(f0[f0 > 0])

            if f0 > 0:
                return float(f0)
        except:
            pass

        return None

    def start_test(self):
        """Inicia o teste normal"""
        self.test_mode = 'normal'
        self.phase = 'ascending'
        self.current_note_index = self.note_sequence.index('C4')
        self.lowest_note = None
        self.highest_note = None

        self.is_testing = True
        self.is_listening = True
        self.correct_time = 0
        self.frequency_buffer.clear()

        self.c4_skipped_as_low = False
        self.c4_skipped_as_high = False
        self.first_note_achieved = False
        self.should_descend_after_ascending = True
        self.quick_test_calibration_complete = False

        self._update_ui(too_high_button='disabled',
                        too_low_button='disabled',
                        start_button='disabled',
                        start_quick_button='disabled',
                        stop_button='normal')

        threading.Thread(target=self.run_test, daemon=True).start()

    def start_quick_test(self):
        """Inicia o teste rápido com calibração"""
        self.test_mode = 'quick'
        self.lowest_note = None
        self.highest_note = None

        self.is_testing = True
        self.is_listening = False
        self.correct_time = 0
        self.frequency_buffer.clear()
        self.quick_test_calibration_complete = False

        self._update_ui(start_button='disabled',
                        start_quick_button='disabled',
                        stop_button='normal')

        threading.Thread(target=self.run_quick_test_calibration, daemon=True).start()

    def run_quick_test_calibration(self):
        """Fase de calibração do teste rápido: identifica nota mais aguda, depois mais grave"""
        # Fase 1: Calibração da nota MAIS AGUDA
        self.calibrate_highest_note()

        if not self.is_testing:
            return

        # Fase 2: Calibração da nota MAIS GRAVE
        self.calibrate_lowest_note()

        if not self.is_testing:
            return

        # Calibração completa - inicia teste normal a partir das notas de âncora
        self.quick_test_calibration_complete = True
        self.first_note_achieved = True
        self.phase = 'ascending'
        self.current_note_index = self.note_sequence.index(self.highest_note) + 1
        self.should_descend_after_ascending = True
        self._update_ui(
            status="Calibração completa! Iniciando teste...",
            status_color='#27AE60'
        )
        time.sleep(1)

        # Continua como teste normal a partir das notas de âncora
        self.run_test()

    def calibrate_highest_note(self):
        """Captura a nota mais aguda que o usuário consegue fazer - com critério de 3 segundos de manutenção da MESMA nota"""
        self._update_ui(
            status=f"Cante a nota MAIS AGUDA que conseguir! Mantenha por {self._testing_time} segundos.",
            status_color='#F39C12',
            expected_note="AGUDO",
            expected_freq="Sua nota mais aguda",
            too_high_button='normal',
            too_low_button='disabled'
        )
        time.sleep(0.1)

        self.correct_time = 0
        self.frequency_buffer.clear()
        self.is_listening = True
        self.max_amplitude = 1e-6
        self.silence_break_time = 0.0
        last_stable_note = None  # MUDANÇA: rastreia a nota estável atual

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                blocksize=self.chunk_size)
        stream.start()

        try:

            while self.is_testing and self.is_listening:
                audio_chunk, _ = stream.read(self.chunk_size)
                audio_chunk = audio_chunk.flatten()

                duration_per_chunk = self.chunk_size / float(self.sample_rate)


                if audio_chunk is not None and len(audio_chunk) > 0:
                    rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64)))))

                    # Noise Gate: se habilitado e RMS abaixo do limiar, treat como silêncio

                    if self.NOISE_GATE_ENABLED and rms < self.NOISE_GATE_THRESHOLD:
                        self.silence_break_time += duration_per_chunk
                        detected_freq = None
                    else:

                        if rms > self.max_amplitude:
                            self.max_amplitude = rms if rms > 0 else self.max_amplitude
                        if rms < 0.5 * max(self.max_amplitude, 1e-9):
                            self.silence_break_time += duration_per_chunk
                        else:
                            self.silence_break_time = 0.0

                        detected_freq = self.detect_pitch(audio_chunk)

                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

                    # Envio imediato do pitch em Hz para a UI (para plotar)
                    self._update_ui(pitch_hz=detected_freq)

                    if len(self.frequency_buffer) >= 20:
                        average_freq = np.mean(list(self.frequency_buffer))
                        average_note, _ = self.frequency_to_note(average_freq)

                        # MUDANÇA CRÍTICA: usa nota média como referência, não a primeira detectada
                        if last_stable_note is None:
                            # Primeira nota estável detectada
                            last_stable_note = average_note
                            target_freq_calibration = self.notes[average_note]
                        else:
                            # Se a nota média mudou, reinicia a contagem
                            if average_note != last_stable_note:
                                self.correct_time = 0
                                last_stable_note = average_note
                                target_freq_calibration = self.notes[average_note]
                                self._update_ui(
                                    status=f"Nota mudou para {average_note}. Reiniciando contagem!",
                                    status_color='#F39C12',
                                    detected_note=average_note if average_note else "--",
                                    detected_freq=f"{average_freq:.2f} Hz"
                                )
                            else:
                                target_freq_calibration = self.notes[last_stable_note]

                        cents_diff_average = abs(self.frequency_to_cents(average_freq, target_freq_calibration))
                        is_average_correct = cents_diff_average <= self.tolerance_cents

                        if is_average_correct:
                            self.correct_time += 0.1
                            self._update_ui(
                                status=f"✓ Mantendo {average_note} (média)!",
                                status_color='#27AE60',
                                detected_note=average_note if average_note else "--",
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time}.0s",
                                time=min(100, (self.correct_time / self._testing_time) * 100)
                            )

                            if self.correct_time >= self._testing_time:
                                self.highest_note = average_note
                                self._update_ui(
                                    status=f"✓ Nota aguda capturada: {self.highest_note}!",
                                    status_color='#27AE60',
                                    detected_note=average_note if average_note else "--"
                                )
                                self.is_listening = False
                                break
                        else:
                            self.correct_time = 0
                            self._update_ui(
                                status=f"Nota {average_note} fora da tolerância, aguardando estabilização!",
                                status_color='#E74C3C',
                                detected_note=average_note if average_note else "--",
                                detected_freq=f"{average_freq:.2f} Hz"
                            )

                        progress = min(100, (self.correct_time / self._testing_time) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time}.0s"
                    )
                    self.correct_time = 0
                    self.frequency_buffer.clear()
                    last_stable_note = None  # MUDANÇA: reseta nota estável

                time.sleep(0.1)

        finally:
            stream.stop()
            stream.close()

        self._update_ui(too_high_button='disabled')
        time.sleep(1)

    def calibrate_lowest_note(self):
        """Captura a nota mais grave que o usuário consegue fazer - com critério de 3 segundos de manutenção da MESMA nota"""
        self._update_ui(
            status=f"Cante a nota MAIS GRAVE que conseguir! Mantenha por {self._testing_time} segundos.",
            status_color='#F39C12',
            expected_note="GRAVE",
            expected_freq="Sua nota mais grave",
            too_low_button='normal',
            too_high_button='disabled'
        )

        self.correct_time = 0
        self.frequency_buffer.clear()
        self.is_listening = True
        self.max_amplitude = 1e-6
        self.silence_break_time = 0.0
        last_stable_note = None  # MUDANÇA: rastreia a nota estável atual

        time.sleep(0.1)

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                blocksize=self.chunk_size)
        stream.start()

        try:
            while self.is_testing and self.is_listening:
                audio_chunk, _ = stream.read(self.chunk_size)
                audio_chunk = audio_chunk.flatten()

                duration_per_chunk = self.chunk_size / float(self.sample_rate)

                if audio_chunk is not None and len(audio_chunk) > 0:
                    rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64)))))

                    # Noise Gate: se habilitado e RMS abaixo do limiar, trate como silêncio

                    if self.NOISE_GATE_ENABLED and rms < self.NOISE_GATE_THRESHOLD:
                        self.silence_break_time += duration_per_chunk
                        detected_freq = None
                    else:

                        if rms > self.max_amplitude:
                            self.max_amplitude = rms if rms > 0 else self.max_amplitude

                        if rms < 0.5 * max(self.max_amplitude, 1e-9):
                            self.silence_break_time += duration_per_chunk
                        else:
                            self.silence_break_time = 0.0

                        detected_freq = self.detect_pitch(audio_chunk)

                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

                    # Envio imediato do pitch em Hz para a UI (para plotar)
                    self._update_ui(pitch_hz=detected_freq)

                    if len(self.frequency_buffer) >= 20:
                        average_freq = np.mean(list(self.frequency_buffer))
                        average_note, _ = self.frequency_to_note(average_freq)

                        # MUDANÇA CRÍTICA: usa nota média como referência, não a primeira detectada
                        if last_stable_note is None:
                            # Primeira nota estável detectada
                            last_stable_note = average_note
                            target_freq_calibration = self.notes[average_note]
                        else:
                            # Se a nota média mudou, reinicia a contagem
                            if average_note != last_stable_note:
                                self.correct_time = 0
                                last_stable_note = average_note
                                target_freq_calibration = self.notes[average_note]
                                self._update_ui(
                                    status=f"Nota mudou para {average_note}. Reiniciando contagem!",
                                    status_color='#F39C12',
                                    detected_note=average_note if average_note else "--",
                                    detected_freq=f"{average_freq:.2f} Hz"
                                )
                            else:
                                target_freq_calibration = self.notes[last_stable_note]

                        cents_diff_average = abs(self.frequency_to_cents(average_freq, target_freq_calibration))
                        is_average_correct = cents_diff_average <= self.tolerance_cents

                        if is_average_correct:
                            self.correct_time += 0.1
                            self._update_ui(
                                status=f"✓ Mantendo {average_note} (média)!",
                                status_color='#27AE60',
                                detected_note=average_note if average_note else "--",
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time}.0s",
                                time=min(100, (self.correct_time / self._testing_time) * 100)
                            )

                            if self.correct_time >= self._testing_time:
                                self.lowest_note = average_note
                                self._update_ui(
                                    status=f"✓ Nota grave capturada: {self.lowest_note}!",
                                    status_color='#27AE60',
                                    detected_note=average_note if average_note else "--"
                                )
                                self.is_listening = False
                                break
                        else:
                            self.correct_time = 0
                            self._update_ui(
                                status=f"Nota {average_note} fora da tolerância, aguardando estabilização!",
                                status_color='#E74C3C',
                                detected_note=average_note if average_note else "--",
                                detected_freq=f"{average_freq:.2f} Hz"
                            )

                        progress = min(100, (self.correct_time / self._testing_time) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time}.0s"
                    )
                    self.correct_time = 0
                    self.frequency_buffer.clear()
                    last_stable_note = None  # MUDANÇA: reseta nota estável

                time.sleep(0.1)

        finally:
            stream.stop()
            stream.close()

        self._update_ui(too_low_button='disabled')
        time.sleep(1)

    def mark_too_low(self):
        """Marca como grave demais - sobe ignorando"""
        if not self.first_note_achieved:
            # Primeira vez em C4 (teste normal)
            if self.current_note_index == self.note_sequence.index('C4') and not self.c4_skipped_as_low:
                self.c4_skipped_as_low = True
                self.should_descend_after_ascending = False
                self._update_ui(
                    status="C4 ignorado! Subindo...",
                    status_color='#F39C12',
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.current_note_index += 1
            else:
                # Continuando a subir
                self._update_ui(
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.current_note_index += 1

        else:
            # Já conseguiu a primeira nota - é o limite grave final
            self.finish_test()

        self.is_listening = False

    def mark_too_high(self):
        """Marca como agudo demais - desce ignorando"""
        if not self.first_note_achieved:
            # Primeira vez em C4 (teste normal)
            if self.current_note_index == self.note_sequence.index('C4') and not self.c4_skipped_as_high:
                self.c4_skipped_as_high = True
                self.should_descend_after_ascending = False
                self._update_ui(
                    status="C4 ignorado! Descendendo...",
                    status_color='#F39C12',
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.phase = 'descending'
                # Inicia descendente a partir de B3 (conforme requisito)
                self.current_note_index = self.note_sequence.index('B3')
            else:
                # Continua a subir/descendo conforme lógica atual
                self._update_ui(
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.current_note_index += 1

        else:
            # Se começou com "Grave demais", termina aqui
            if self.c4_skipped_as_low:
                self.finish_test()
            else:
                # Caso contrário, desce para testar graves
                self.start_descending_phase()

        self.is_listening = False

    def stop_test(self):
        """Para o teste"""
        self.is_testing = False
        self.is_listening = False
        self._update_ui(
            status="Teste cancelado",
            status_color='#666666',
            start_button='normal',
            start_quick_button='normal',
            too_low_button='disabled',
            too_high_button='disabled',
            stop_button='disabled'
        )

    def run_test(self):
        """Loop principal do teste"""
        while self.is_testing:
            current_note = self.note_sequence[self.current_note_index]
            target_frequency = self.notes[current_note]

            # Rastreia a nota atual para repetição
            self.current_playing_note = current_note
            self.current_playing_frequency = target_frequency
            self._update_ui(
                status=f"Reproduzindo {current_note}... prepare-se!",
                status_color='#666666',
                expected_note=current_note,
                expected_freq=f"{target_frequency:.2f} Hz",
                repeat_button='normal'
            )

            # Novo: tocar a nota atual por 2 segundos ao iniciar cada nota nova
            try:
                self.play_note(target_frequency, duration=2)
            except Exception:
                # Em caso de falha ao tocar o som, continuar com a detecção
                pass

            self.listen_and_detect(current_note, target_frequency)

    def play_note(self, frequency, duration=2):
        """Reproduz uma nota com envelope de piano"""
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)

        # Envelope ADSR de piano
        attack_time = 0.05  # 50ms - ataque rápido
        decay_time = 0.3  # 300ms - decay rápido
        sustain_level = 0.3  # nível de sustain
        release_time = 0.3  # release suave

        attack_samples = int(self.sample_rate * attack_time)
        decay_samples = int(self.sample_rate * decay_time)
        sustain_samples = int(self.sample_rate * (duration - attack_time - decay_time - release_time))
        release_samples = int(self.sample_rate * release_time)

        envelope = np.ones_like(t)

        # Attack
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        # Decay
        decay_start = attack_samples
        decay_end = decay_start + decay_samples
        if decay_end < len(envelope):
            envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_samples)

        # Sustain
        sustain_start = decay_end
        sustain_end = sustain_start + sustain_samples
        if sustain_end < len(envelope):
            envelope[sustain_start:sustain_end] = sustain_level

        # Release
        release_start = sustain_end
        if release_start < len(envelope):
            release_samples_actual = len(envelope) - release_start
            envelope[release_start:] = np.linspace(sustain_level, 0, release_samples_actual)

        # Gera tom puro com harmônicos para simular piano
        signal_audio = 0.25 * np.sin(2 * np.pi * frequency * t) * envelope

        # Adiciona harmônicos para enriquecer o som
        signal_audio += 0.08 * np.sin(2 * np.pi * frequency * 2 * t) * envelope
        signal_audio += 0.04 * np.sin(2 * np.pi * frequency * 3 * t) * envelope

        sd.play(signal_audio, self.sample_rate)
        sd.wait()

    def listen_and_detect(self, current_note, target_frequency):
        """Captura áudio e detecta pitch em tempo real com média móvel"""
        self.correct_time = 0
        self.frequency_buffer.clear()
        self.is_listening = True

        # Rastreia a nota atual
        self.current_playing_note = current_note
        self.current_playing_frequency = target_frequency

        # Determina quais botões devem estar disponíveis
        if current_note == 'C4' and not self.c4_skipped_as_low and not self.c4_skipped_as_high:
            # Primeira tentativa em C4 - ambos os botões
            self._update_ui(
                too_low_button='normal',
                too_high_button='normal')
        elif self.c4_skipped_as_low and not self.first_note_achieved and self.phase == 'ascending':
            # Subindo após pular C4 por ser grave - apenas "Grave Demais"
            self._update_ui(
                too_low_button='normal',
                too_high_button='disabled')
        elif self.c4_skipped_as_high and not self.first_note_achieved and self.phase == 'descending':
            # Descendo após pular C4 por ser agudo - apenas "Agudo Demais"
            self._update_ui(
                too_low_button='disabled',
                too_high_button='normal')
        elif self.first_note_achieved and self.phase == 'ascending':
            # Depois de conseguir a primeira nota, subindo - apenas "Agudo Demais"
            self._update_ui(
                too_low_button='disabled',
                too_high_button='normal')
        elif self.first_note_achieved and self.phase == 'descending':
            # Descendo na segunda fase - apenas "Grave Demais"
            self._update_ui(
                too_low_button='normal',
                too_high_button='disabled')

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                blocksize=self.chunk_size)
        stream.start()

        try:
            while self.is_testing and self.is_listening:
                audio_chunk, _ = stream.read(self.chunk_size)
                audio_chunk = audio_chunk.flatten()

                duration_per_chunk = self.chunk_size / float(self.sample_rate)


                if audio_chunk is not None and len(audio_chunk) > 0:
                    rms = float(
                    np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64)))))

                    # Gate de ruído para detecção de pitch

                    if self.NOISE_GATE_ENABLED and rms < self.NOISE_GATE_THRESHOLD:
                        detected_freq = None
                    else:
                        if rms > self.max_amplitude:
                            self.max_amplitude = rms if rms > 0 else self.max_amplitude
                        if rms < 0.5 * max(self.max_amplitude, 1e-9):
                            self.silence_break_time += duration_per_chunk
                        else:
                            self.silence_break_time = 0.0

                        detected_freq = self.detect_pitch(audio_chunk)

                # Dentro de listen_and_detect, logo após:
                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

                    # Envio imediato do pitch em Hz para a UI (para plotar)
                    self._update_ui(pitch_hz=detected_freq)

                    # Novo: calcular offset em cents e enviar para a UI
                    detected_note_tmp, _ = self.frequency_to_note(detected_freq)
                    try:
                        offset_cents = int(round(self.frequency_to_cents(detected_freq, target_frequency)))
                    except Exception:
                        offset_cents = 0

                    # Atualiza a UI com o offset (mantém outros campos já existentes)
                    self._update_ui(
                        offset_cents=offset_cents,
                        detected_note=detected_note_tmp if detected_note_tmp else "--",
                        detected_freq=f"{detected_freq:.2f} Hz"
                    )

                    average_freq = np.mean(list(self.frequency_buffer))

                    cents_diff_current = abs(self.frequency_to_cents(detected_freq, target_frequency))
                    cents_diff_average = abs(self.frequency_to_cents(average_freq, target_frequency))

                    detected_note, _ = self.frequency_to_note(detected_freq)
                    average_note, _ = self.frequency_to_note(average_freq)

                    is_average_correct = cents_diff_average <= self.tolerance_cents

                    if is_average_correct:
                        self.correct_time += 0.1

                        if self.correct_time >= self._testing_time:
                            self.on_note_success(current_note)
                            break

                        self._update_ui(
                            status=f"✓ Mantendo {current_note} (média)!",
                            status_color='#27AE60',
                            detected_note=detected_note if detected_note else "--",
                            time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time}.0s",
                            time=min(100, (self.correct_time / self._testing_time) * 100)
                        )
                    else:
                        self.correct_time = 0
                        self._update_ui(
                            status=f"Média em {average_note}, esperado: {current_note}",
                            status_color='#E74C3C',
                            detected_note=detected_note if detected_note else "--"
                        )

                    progress = min(100, (self.correct_time / self._testing_time) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time}.0s"
                    )
                    self.correct_time = 0

                time.sleep(0.1)

        finally:
            stream.stop()
            stream.close()

    def on_note_success(self, note):
        """Chamado quando uma nota é conquistada automaticamente"""
        if not self.first_note_achieved:
            self.first_note_achieved = True

            if self.phase == 'ascending':
                self.lowest_note = note
            else:
                self.highest_note = note
        else:
            if self.phase == 'ascending':
                self.highest_note = note
            else:
                self.lowest_note = note

        self._update_ui(
            status=f"✓ {note} conquistado!",
            status_color='#27AE60'
        )

        if self.phase == 'ascending':
            self.current_note_index += 1

            if self.current_note_index >= len(self.note_sequence):
                if self.c4_skipped_as_low:
                    self.finish_test()
                    return
                if self.should_descend_after_ascending:
                    self.start_descending_phase()
                    return
                self.finish_test()
                return
        else:
            self.current_note_index -= 1

            if self.current_note_index < 0:
                self.finish_test()
                return

        time.sleep(1)

    def start_descending_phase(self):
        """Inicia a fase descendente"""
        self.phase = 'descending'
        self.current_note_index = self.note_sequence.index(self.lowest_note) - 1

        self._update_ui(
            status="Fase descendente! Preparando...",
            status_color='#F39C12'
        )
        time.sleep(0.1)
        time.sleep(1)

    def finish_test(self):
        self.is_testing = False
        self.is_listening = False
        self._update_ui(
            start_button="normal",
            start_quick_button="normal",
            too_low_button="disabled",
            too_high_button='disabled',
            stop_button='disabled',
            repeat_button='disabled'
        )

        # Invoca callback com resultado
        self._test_complete()

class RangeVisualizer:
    ROW_HEIGHT = 32
    BAR_HEIGHT = 14
    LEFT_PAD = 60
    RIGHT_PAD = 20
    CANVAS_WIDTH = 800
    CANVAS_HEIGHT = ROW_HEIGHT * 6 + 40

    def __init__(self, master, voices=None, base_ranges=None, coristas=None):
        self.master = master
        self.voices = voices or VOICES
        self.base_ranges = base_ranges or VOICE_BASE_RANGES
        self.group_ranges = None
        self.coristas = coristas or []
        self.coristas_mgr = CoristasManager()

        # Define o range de notas a exibir (C2 = 36, C6 = 84)
        self.MIDI_MIN = 36  # C2
        self.MIDI_MAX = 84  # C6
        self.MIDI_RANGE = self.MIDI_MAX - self.MIDI_MIN

        # Frame container para o canvas
        canvas_frame = ttk.LabelFrame(master, text="Visualização de Ranges", padding=5)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(canvas_frame, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
                                bg="white", highlightthickness=1, highlightbackground="black")
        self.canvas.pack(fill="both", expand=True, pady=10)

        self.scale = (self.CANVAS_WIDTH - self.LEFT_PAD - self.RIGHT_PAD) / self.MIDI_RANGE
        self.draw_grid()

    def set_group_ranges(self, group_ranges):
        """
        group_ranges: dict[str, tuple[str, str]] com (min_note, max_note) por voz
        """

        self.group_ranges = group_ranges

    def draw_grid(self):
        for i, v in enumerate(self.voices):
            y = 10 + i * self.ROW_HEIGHT
            self.canvas.create_line(0, y, self.CANVAS_WIDTH + 120, y, fill="#f0f0f0")

        # Offsets das notas naturais dentro de uma oitava (em semitons a partir de C)
        natural_notes_offsets = [0, 2, 4, 5, 7, 9, 11]  # C, D, E, F, G, A, B

        # Gera todos os MIDI das notas naturais no range
        natural_midis = []
        for octave in range(self.MIDI_MIN // 12, (self.MIDI_MAX // 12) + 2):
            for offset in natural_notes_offsets:
                midi = octave * 12 + offset
                if self.MIDI_MIN <= midi <= self.MIDI_MAX:
                    natural_midis.append(midi)

        # Desenha linhas e labels apenas para notas naturais
        for s in natural_midis:
            x = int(self.LEFT_PAD + (s - self.MIDI_MIN) * self.scale) + 100
            self.canvas.create_line(x, 0, x, self.CANVAS_HEIGHT, fill="#e6e6e6", dash=(2, 4))
            try:
                note = midi_to_note(s)
                self.canvas.create_text(x + 2, 8, anchor="nw", text=note, fill="#888888", font=("Arial", 8))
            except Exception:
                pass

    def _x(self, midi_note):
        # Ajusta a coordenada X subtraindo MIDI_MIN
        return int(self.LEFT_PAD + (midi_note - self.MIDI_MIN) * self.scale) + 100

    def update(self, piece_ranges, T, Os, group_ranges=None, group_extension=None, voice_scores=None):
        self.canvas.delete("all")
        self.draw_grid()

        for idx, v in enumerate(group_ranges if group_ranges else self.voices):
            y = 30 + idx * self.ROW_HEIGHT
            bar_y = y - 10 + (self.ROW_HEIGHT - self.BAR_HEIGHT) / 2

            # Determinar o range base para validação de transposição
            if group_ranges:
                g_min_m = note_to_midi(group_ranges[v][0])
                g_max_m = note_to_midi(group_ranges[v][1])
            else:
                g_min_m = note_to_midi(VOICE_BASE_RANGES[v][0])
                g_max_m = note_to_midi(VOICE_BASE_RANGES[v][1])

            # Desenhar barras de grupo se existirem
            if group_ranges is not None and group_extension is not None:
                # Desenhar barra de group_extension (com opacidade 50%) se aplicável
                if v in group_extension and v in group_ranges:
                    # Só desenha group_extension se tem valores diferentes de group_ranges
                    if group_extension[v] != group_ranges[v]:
                        ext_min_m = note_to_midi(group_extension[v][0])
                        ext_max_m = note_to_midi(group_extension[v][1])
                        ext_x1 = self._x(ext_min_m)
                        ext_x2 = self._x(ext_max_m)

                        # Desenha com opacidade 50% (usando stipple)
                        self.canvas.create_rectangle(ext_x1, bar_y, ext_x2, bar_y + self.BAR_HEIGHT,
                                                     fill="#4169E1", outline="#000080", stipple="gray50")

                # Desenhar barra de group_ranges (sólida)
                if v in group_ranges:
                    gr_min_m = note_to_midi(group_ranges[v][0])
                    gr_max_m = note_to_midi(group_ranges[v][1])
                    gr_x1 = self._x(gr_min_m)
                    gr_x2 = self._x(gr_max_m)

                    self.canvas.create_rectangle(gr_x1, bar_y, gr_x2, bar_y + self.BAR_HEIGHT,
                                                 fill="#4169E1", outline="#000080")
            else:
                # Comportamento padrão quando não há group_ranges/group_extension
                base_min_m = note_to_midi(VOICE_BASE_RANGES[v][0])
                base_max_m = note_to_midi(VOICE_BASE_RANGES[v][1])
                x1 = self._x(base_min_m)
                x2 = self._x(base_max_m)
                # fill = "#90ee90", outline = "#2e8b57"
                self.canvas.create_rectangle(x1, bar_y, x2, bar_y + self.BAR_HEIGHT,
                                             fill="#4169E1", outline="#000080")

            # Resto da lógica (piece_ranges e transposição)
            if v in {k: y for k, y in piece_ranges.items() if y != ('', '')}:
                piece_min_str, piece_max_str = piece_ranges[v]
                piece_min_m = note_to_midi(piece_min_str)
                piece_max_m = note_to_midi(piece_max_str)

                O = Os.get(v, 0)
                trans_min = piece_min_m + T + 12 * O
                trans_max = piece_max_m + T + 12 * O

                # Nova lógica para escolher a transposição mais "confortável"
                best_score = None
                best_tmin = trans_min
                best_tmax = trans_max
                best_Op = O

                # Tenta variações de O em small steps (±2) para achar posição mais distante das bordas
                for delta in range(-2, 3):  # -2, -1, 0, 1, 2
                    Op = O + delta
                    tmin = piece_min_m + T + 12 * Op
                    tmax = piece_max_m + T + 12 * Op

                    inside = (tmin >= g_min_m) and (tmax <= g_max_m)
                    if inside:
                        dist_left = tmin - g_min_m
                        dist_right = g_max_m - tmax
                        min_dist = min(dist_left, dist_right)
                        score = (1, min_dist, dist_left, dist_right)  # prioridade: dentro, maior min_dist
                    else:
                        left_excess = max(0, g_min_m - tmin)
                        right_excess = max(0, tmax - g_max_m)
                        outside_excess = left_excess + right_excess
                        score = (0, -outside_excess, 0, 0)  # fora: minimizar extrapolação

                    if best_score is None or score > best_score:
                        best_score = score
                        best_Op = Op
                        best_tmin = tmin
                        best_tmax = tmax

                # Use a melhor transposição encontrada
                trans_min = best_tmin
                trans_max = best_tmax

                tx1 = self._x(trans_min)
                tx2 = self._x(trans_max)

                red_thick = int(self.BAR_HEIGHT * 0.5)
                red_top = bar_y + (self.BAR_HEIGHT - red_thick) / 2
                red_bottom = red_top + red_thick
                self.canvas.create_rectangle(tx1, red_top, tx2, red_bottom,
                                             fill="#f7a40a", outline="#6e4b0b")

                # Exibir score no meio do retângulo red_thick
                if voice_scores and v in voice_scores and T in voice_scores[v]:
                    score_value = voice_scores[v][T]
                    score_text = f"{score_value:.2f}"

                    # Centralizar o texto no retângulo
                    text_x = (tx1 + tx2) / 2
                    text_y = (red_top + red_bottom) / 2

                    self.canvas.create_text(text_x, text_y, text=score_text,
                                            font=("Arial", 9, "bold"), fill="#FFFFFF")

            self.canvas.create_text(5, y + 6, anchor="w", text=v, font=("Arial", 10, "bold"))

        self.master.update_idletasks()

class KeyboardVisualizer:
    """Visualiza as notas no teclado com cores conforme o range do corista vs voz"""

    # Dimensões
    CANVAS_WIDTH = 100
    CANVAS_HEIGHT = 100
    WHITE_KEY_WIDTH = 20
    WHITE_KEY_HEIGHT = 80
    BLACK_KEY_WIDTH = 10
    BLACK_KEY_HEIGHT = 50

    # Notas brancas e pretas por oitava
    WHITE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
    BLACK_NOTES_POS = {  # posição relativa dentro da oitava
        'C#': 0.5, 'D#': 1.5, 'F#': 3.5, 'G#': 4.5, 'A#': 5.5
    }

    def __init__(self, master):
        self.master = master

        # Frame com label
        frame = ttk.LabelFrame(master, text="Visualização de Notas no Teclado", padding=5)
        frame.pack(fill="both", expand=False, padx=10, pady=10)

        self.canvas = tk.Canvas(frame, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
                                bg="white", highlightthickness=1, highlightbackground="black")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)

        # Legenda
        legend_frame = ttk.Frame(master)
        legend_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(legend_frame, text="●", foreground="green", font=("Arial", 16)).pack(side="left", padx=5)
        ttk.Label(legend_frame, text="Alcance exigido (consegue fazer)").pack(side="left", padx=2)

        ttk.Label(legend_frame, text="●", foreground="red", font=("Arial", 16)).pack(side="left", padx=15)
        ttk.Label(legend_frame, text="Alcance exigido (NÃO consegue)").pack(side="left", padx=2)

        ttk.Label(legend_frame, text="●", foreground="blue", font=("Arial", 16)).pack(side="left", padx=15)
        ttk.Label(legend_frame, text="Alcance extra (além do exigido)").pack(side="left", padx=2)

    def note_to_midi(self, note_str):
        """Converte nota para MIDI"""
        s = note_str.strip().replace(' ', '')
        m = re.match(r'^([A-Ga-g])([#b]?)(-?\d+)$', s)
        if not m:
            raise ValueError(f"Nota inválida: '{note_str}'")

        note = m.group(1).upper()
        acc = m.group(2)
        octa = int(m.group(3))

        note_to_semitone = {
            'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
        }

        semitone = note_to_semitone[note]
        if acc == '#' or acc == 'b':
            if acc == '#':
                semitone += 1
            else:
                semitone -= 1

        midi = 12 * (octa + 1) + semitone
        return midi

    def update(self, corista_min_str, corista_max_str, voice_min_str, voice_max_str):
        """Atualiza o teclado com as cores"""
        try:
            corista_min = self.note_to_midi(corista_min_str)
            corista_max = self.note_to_midi(corista_max_str)
            voice_min = self.note_to_midi(voice_min_str)
            voice_max = self.note_to_midi(voice_max_str)

            self.canvas.delete("all")
            self.draw_keyboard(corista_min, corista_max, voice_min, voice_max)
        except Exception as e:
            print(f"Erro ao atualizar teclado: {e}")

    def draw_keyboard(self, corista_min, corista_max, voice_min, voice_max):
        """Desenha o teclado com as cores"""

        # Define o range de oitavas a exibir (C2 até C7)
        start_midi = self.note_to_midi("C2")
        end_midi = self.note_to_midi("C7")

        x = 10
        white_key_index = 0

        for midi in range(start_midi, end_midi + 1):
            octave = (midi // 12) - 1
            note_pc = midi % 12

            # Mapeia MIDI para nota
            semitone_to_note = {
                0: 'C', 1: 'C#', 2: 'D', 3: 'D#', 4: 'E', 5: 'F',
                6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'A#', 11: 'B'
            }
            note_name = semitone_to_note[note_pc]

            # Determina a cor
            if '#' not in note_name:  # Tecla branca
                # Verifica a categoria
                if voice_min <= midi <= voice_max:
                    if corista_min <= midi <= corista_max:
                        color = "#90EE90"  # Verde - consegue cantar e é exigido
                    else:
                        color = "#FF6B6B"  # Vermelho - é exigido mas não consegue
                else:
                    if corista_min <= midi <= corista_max:
                        color = "#87CEEB"  # Azul - consegue cantar mas não é exigido
                    else:
                        color = "white"  # Branco - normal

                # Desenha tecla branca
                self.canvas.create_rectangle(
                    x, 10, x + self.WHITE_KEY_WIDTH, 10 + self.WHITE_KEY_HEIGHT,
                    fill=color, outline="black", width=2
                )

                # Label com a nota
                self.canvas.create_text(
                    x + self.WHITE_KEY_WIDTH // 2,
                    10 + self.WHITE_KEY_HEIGHT - 10,
                    text=f"{note_name}\n{octave}", font=("Arial", 8), anchor="center"
                )

                x += self.WHITE_KEY_WIDTH
            else:  # Tecla preta
                # Verifica a cor
                if voice_min <= midi <= voice_max:
                    if corista_min <= midi <= corista_max:
                        color = "#228B22"  # Verde escuro
                    else:
                        color = "#CC0000"  # Vermelho escuro
                else:
                    if corista_min <= midi <= corista_max:
                        color = "#0066CC"  # Azul escuro
                    else:
                        color = "black"  # Preto normal

                # Posição X (entre as teclas brancas)
                black_x = x - self.WHITE_KEY_WIDTH + (self.WHITE_KEY_WIDTH * 0.7)

                # Desenha tecla preta
                self.canvas.create_rectangle(
                    black_x - self.BLACK_KEY_WIDTH // 2,
                    10,
                    black_x + self.BLACK_KEY_WIDTH // 2,
                    10 + self.BLACK_KEY_HEIGHT,
                    fill=color, outline="black", width=1
                )

                # Label
                self.canvas.create_text(
                    black_x,
                    10 + self.BLACK_KEY_HEIGHT - 8,
                    text=note_name, font=("Arial", 7), anchor="center", fill="white"
                )

class AudioAnalyzer:
    """
    Encapsula o fluxo de análise de áudio por voz em uma classe.
    Ao chamar process_music(mp3_path, music_name), cria a estrutura
    root/musicas/{music_name} com os arquivos de saída:
      - {music_name}_notes_detected.json
      - {music_name}_normalized.json
      - {music_name}_midi.mid
    """
    def __init__(self, root_dir: str = "root"):
        self.root_dir = Path(root_dir)

    # -----------------------------
    # Helpers (reproduzem o seu pipeline)
    # -----------------------------
    @staticmethod
    def hz_to_midi_round(freq_hz):
        if freq_hz is None or freq_hz <= 0:
            return None
        try:
            midi = int(round(librosa.hz_to_midi(freq_hz)))
            if midi < 0:
                return None
            if midi > 127:
                return 127
            return midi
        except Exception:
            return None

    @staticmethod
    def midi_to_freq_hz(midi):
        if midi is None:
            return None
        try:
            return pretty_midi.note_number_to_hz(int(midi))
        except AttributeError:
            return 440.0 * (2.0 ** ((int(midi) - 69) / 12.0))

    @staticmethod
    def midi_to_name(midi):
        if midi is None:
            return None
        try:
            return pretty_midi.note_number_to_name(int(midi))
        except Exception:
            return None

    @staticmethod
    def save_notes_json(notes, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_notes_json(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def normalize_and_filter_notes(
            detected_notes,
            min_dur=0.1,
            max_gap_merge=2,
            return_extrema=False,
            normalize_population=0.95
    ):
        frames = []
        for n in detected_notes:
            f_hz = float(n.get('frequency_hz')) if 'frequency_hz' in n else None
            t0 = float(n.get('start_sec'))
            dur = float(n.get('duration_sec'))
            midi = AudioAnalyzer.hz_to_midi_round(f_hz)
            freq_norm = AudioAnalyzer.midi_to_freq_hz(midi)
            name = AudioAnalyzer.midi_to_name(midi)

            frames.append({
                'start_sec': t0,
                'duration_sec': max(dur, 0.0),
                'pitch_midi': int(midi) if midi is not None else None,
                'frequency_hz': freq_norm,
                'note_name': name
            })

        frames = [f for f in frames if f['pitch_midi'] is not None]

        # Passo 2: agrupar frames em notas contínuas da mesma pitch
        grouped = []
        current = None  # {'start': ..., 'end': ..., 'midi': ...}
        for f in frames:
            s = float(f['start_sec'])
            e = s + float(f['duration_sec'])
            midi = int(f['pitch_midi'])

            if current is None:
                current = {'start': s, 'end': e, 'midi': midi}
            else:
                if midi == current['midi']:
                    current['end'] = max(current['end'], e)
                else:
                    duration = current['end'] - current['start']
                    if duration >= min_dur:
                        grouped.append({
                            'start_sec': current['start'],
                            'duration_sec': duration,
                            'pitch_midi': int(current['midi']),
                            'frequency_hz': AudioAnalyzer.midi_to_freq_hz(current['midi']),
                            'note_name': AudioAnalyzer.midi_to_name(current['midi'])
                        })
                    current = {'start': s, 'end': e, 'midi': midi}

        if current is not None:
            duration = current['end'] - current['start']
            if duration >= min_dur:
                grouped.append({
                    'start_sec': current['start'],
                    'duration_sec': duration,
                    'pitch_midi': int(current['midi']),
                    'frequency_hz': AudioAnalyzer.midi_to_freq_hz(current['midi']),
                    'note_name': AudioAnalyzer.midi_to_name(current['midi'])
                })

        # Mesclar notas adjacentes da mesma pitch com gaps pequenos
        if not grouped:
            return []

        merged = [grouped[0]]
        for i in range(1, len(grouped)):
            prev = merged[-1]
            cur = grouped[i]
            gap = cur['start_sec'] - (prev['start_sec'] + prev['duration_sec'])
            if cur['pitch_midi'] == prev['pitch_midi'] and gap <= max_gap_merge:
                new_start = prev['start_sec']
                new_end = max(prev['start_sec'] + prev['duration_sec'], cur['start_sec'] + cur['duration_sec'])
                merged[-1] = {
                    'start_sec': new_start,
                    'duration_sec': new_end - new_start,
                    'pitch_midi': int(cur['pitch_midi']),
                    'frequency_hz': AudioAnalyzer.midi_to_freq_hz(cur['pitch_midi']),
                    'note_name': AudioAnalyzer.midi_to_name(cur['pitch_midi'])
                }
            else:
                merged.append(cur)

        final_notes = [m for m in merged if m['duration_sec'] >= min_dur]

        if normalize_population and final_notes:
            freqs = [n['frequency_hz'] for n in final_notes if n.get('frequency_hz') is not None]
            if freqs:
                freqs_sorted = sorted(freqs)

                def percentile(p):
                    if not freqs_sorted:
                        return None
                    idx = int(p * (len(freqs_sorted) - 1))
                    return freqs_sorted[idx]

                lower_p = (1.0 - normalize_population) / 2.0
                upper_p = 1.0 - lower_p
                central_lower = percentile(lower_p)
                central_upper = percentile(upper_p)

                semitone_ratio = 2 ** (1.0 / 12.0)
                four_semitones = semitone_ratio ** 4

                safe_min = None
                safe_max = None
                if central_lower is not None:
                    safe_min = central_lower / four_semitones
                if central_upper is not None:
                    safe_max = central_upper * four_semitones

                MIN_ALLOWED = NOTES_FREQUENCY_HZ['C2']
                MAX_ALLOWED = NOTES_FREQUENCY_HZ['E5']

                if safe_min is not None:
                    safe_min = max(safe_min, MIN_ALLOWED)
                if safe_max is not None:
                    safe_max = min(safe_max, MAX_ALLOWED)

                if safe_min is not None and safe_max is not None:
                    exclused_notes = [n.get('note_name') for n in [
                        n for n in final_notes
                        if not safe_min <= n['frequency_hz'] <= safe_max
                    ]]
                    final_notes = [
                        n for n in final_notes
                        if safe_min <= n['frequency_hz'] <= safe_max
                    ]
                    print(exclused_notes)

        if return_extrema:
            if final_notes:
                lowest_midi = min(n['pitch_midi'] for n in final_notes)
                highest_midi = max(n['pitch_midi'] for n in final_notes)
                extrema = [AudioAnalyzer.midi_to_name(lowest_midi),
                           AudioAnalyzer.midi_to_name(highest_midi)]
            else:
                extrema = None
            return {'notes': final_notes, 'extrema': extrema}
        else:
            return final_notes

    @staticmethod
    def notes_to_midi(normalized_notes, transpose_semitones=0, instrument_program=0):
        pm = pretty_midi.PrettyMIDI()
        piano = pretty_midi.Instrument(program=instrument_program, name="Detected Piano (normalized)")

        for n in (normalized_notes if not isinstance(normalized_notes, dict) else normalized_notes.get('notes', [])):
            midi = int(n['pitch_midi']) + int(transpose_semitones)
            if midi < 0 or midi > 127:
                continue
            start = float(n['start_sec'])
            end = start + float(n['duration_sec'])
            vel = 100
            note = pretty_midi.Note(velocity=vel, pitch=int(midi), start=start, end=end)
            piano.notes.append(note)

        pm.instruments.append(piano)
        return pm

    @staticmethod
    def save_midi(pm, midi_path):
        pm.write(str(midi_path))

    # -----------------------------
    # Novo: geração de HTML de Pitch History
    # -----------------------------
    @staticmethod
    def _generate_pitch_html(final_notes, music_dir: Path, music_name: str):
        """
        Gera um HTML com Pitch History em estilo "step/linha" onde cada nota
        é representada por um segmento horizontal ao longo do tempo.
        Eixo Y mostra as notas (labels vindas de NOTES_FREQUENCY_HZ).
        """
        html_path = music_dir / f"{music_name}_pitch_history.html"

        # Ordem das notas conforme NOTES_FREQUENCY_HZ (preserva ordem ascendente)
        note_order = list(NOTES_FREQUENCY_HZ.keys())
        name_to_index = {name: idx for idx, name in enumerate(note_order)}

        # Construção de pontos: cada nota gera dois pontos (início e fim),
        # e há um ponto adicional na transição para a próxima nota para
        # criar o salto vertical.
        data_points = []
        if isinstance(final_notes, list):
            for i, n in enumerate(final_notes):
                start = float(n.get('start_sec', 0.0))
                dur = float(n.get('duration_sec', 0.0))

                # Obter o nome da nota
                name = n.get('note_name')
                if name is None:
                    midi = n.get('pitch_midi')
                    if midi is not None:
                        name = AudioAnalyzer.midi_to_name(int(midi))

                idx = name_to_index.get(name)
                if idx is None:
                    continue

                end = start + max(dur, 0.0)

                # Segmento da nota atual
                data_points.append({'x': start, 'y': idx})
                data_points.append({'x': end, 'y': idx})

                # Salto vertical para a próxima nota (se houver)
                if i + 1 < len(final_notes):
                    next_n = final_notes[i + 1]
                    next_name = next_n.get('note_name')
                    if next_name is None:
                        m = next_n.get('pitch_midi')
                        if m is not None:
                            next_name = AudioAnalyzer.midi_to_name(int(m))
                    next_idx = name_to_index.get(next_name)
                    if next_idx is not None:
                        data_points.append({'x': end, 'y': next_idx})

        # HTML com Chart.js (CDN)

        html_lines = []
        html_lines.append('<!DOCTYPE html>')
        html_lines.append('<html lang="pt-BR">')
        html_lines.append('<head>')
        html_lines.append('  <meta charset="UTF-8">')
        html_lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_lines.append(f'  <title>Pitch History - {music_name}</title>')
        html_lines.append('  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>')
        html_lines.append('</head>')
        html_lines.append('<body>')
        html_lines.append(f'  <h2>Pitch History: {music_name}</h2>')
        html_lines.append('  <div style="width:100%; height:500px; position: relative;">')
        html_lines.append('    <canvas id="pitchChart" style="width:100%; height:100%;"></canvas>')
        html_lines.append('  </div>')

        # Embarcar variáveis para renderização
        html_lines.append('  <script>')
        html_lines.append('    const NOTE_ORDER = ' + json.dumps(note_order) + ';')
        html_lines.append('    const dataPoints = ' + json.dumps(data_points) + ';')
        html_lines.append('    const ctx = document.getElementById("pitchChart").getContext("2d");')
        html_lines.append("    new Chart(ctx, {")
        html_lines.append("      type: 'line',")
        html_lines.append("      data: {")
        html_lines.append("        datasets: [{")
        html_lines.append("          label: 'Pitch (Note)',")
        html_lines.append("          data: dataPoints,")
        html_lines.append("          borderColor: 'rgb(75, 192, 192)',")
        html_lines.append("          backgroundColor: 'rgba(75,192,192,0.2)',")
        html_lines.append("          fill: false,")
        html_lines.append("          pointRadius: 0,")
        html_lines.append("          lineTension: 0,")
        html_lines.append("          stepped: true")
        html_lines.append("        }]")
        html_lines.append("      },")
        html_lines.append("      options: {")
        html_lines.append("        scales: {")
        html_lines.append(
            "          x: { type: 'linear', position: 'bottom', title: { display: true, text: 'Tempo (s)' }, min: 0 },")
        html_lines.append("          y: {")
        html_lines.append("            type: 'linear',")
        html_lines.append("            min: 0,")
        html_lines.append("            max: " + str(len(note_order) - 1) + ",")
        html_lines.append("            ticks: {")
        html_lines.append("              callback: function(value) {")
        html_lines.append("                const idx = Math.round(value);")
        html_lines.append("                return (idx >= 0 && idx < NOTE_ORDER.length) ? NOTE_ORDER[idx] : '';")
        html_lines.append("              }")
        html_lines.append("            },")
        html_lines.append("            title: { display: true, text: 'Nota' }")
        html_lines.append("          }")
        html_lines.append("        },")
        html_lines.append("        responsive: true,")
        html_lines.append("        maintainAspectRatio: false,")
        html_lines.append("        plugins: { legend: { display: false } }")
        html_lines.append("      }")
        html_lines.append("    });")
        html_lines.append("  </script>")
        html_lines.append('</body>')
        html_lines.append('</html>')

        html_content = "\n".join(html_lines)

        # Escreve o HTML
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(html_path)

    # -----------------------------
    # Fluxo público
    # -----------------------------
    def process_music(self, mp3_path: str, music_name: str):
        """
        Processa um mp3 e salva output em root/musicas/{music_name}/
        Retorna um dict com caminhos e informações de alcance da voz.
        """
        mp3_path = Path(mp3_path)
        # 1) Análise para notas detectadas
        notes, sr = self._analyze_mp3_to_notes(str(mp3_path))
        # 2) Normalização/Filtragem
        normalized = self.normalize_and_filter_notes(notes, return_extrema=True)

        final_notes = normalized.get('notes', []) if isinstance(normalized, dict) else normalized
        # 3) Determinar min/max da voz selecionada a partir dos resultados
        if final_notes:
            min_hz = min(
                n['frequency_hz'] for n in final_notes if 'frequency_hz' in n and n['frequency_hz'] is not None)
            max_hz = max(
                n['frequency_hz'] for n in final_notes if 'frequency_hz' in n and n['frequency_hz'] is not None)
        else:
            min_hz, max_hz = None, None

        # 4) Preparar diretório de saída
        music_dir = self.root_dir / "musicas" / music_name
        music_dir.mkdir(parents=True, exist_ok=True)

        # 5) Salvar outputs
        notes_path = music_dir / f"{music_name}_notes_detected.json"
        with open(notes_path, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

        normalized_path = music_dir / f"{music_name}_normalized.json"
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)

        pm = self.notes_to_midi(normalized)
        midi_path = music_dir / f"{music_name}_midi.mid"
        self.save_midi(pm, midi_path)

        # Novo: gerar HTML de Pitch History (Pitch Line)
        pitch_html_path = self._generate_pitch_html(final_notes, music_dir, music_name)

        return {
            "notes_detected_path": str(notes_path),
            "normalized_path": str(normalized_path),
            "midi_path": str(midi_path),
            "pitch_history_html_path": pitch_html_path,
            "voice_min_hz": min_hz,
            "voice_max_hz": max_hz,
            "extrema": normalized.get('extrema') if isinstance(normalized, dict) else None
        }

    def _analyze_mp3_to_notes(self, mp3_path: str, sr=22050, fmin=55.0, fmax=2000.0,
                              hop_length=512, frame_length=2048):
        """
        Wrapper próprio que reproduz seu fluxo de análise original.
        Retorna (notes, sr).
        """
        # Carrega o áudio
        y, sr = librosa.load(mp3_path, sr=sr, mono=True)

        # Estima pitch por frame (fundamental)
        f0, voiced_flag, _ = librosa.pyin(y,
                                          fmin=fmin,
                                          fmax=fmax,
                                          sr=sr,
                                          frame_length=frame_length,
                                          hop_length=hop_length)

        times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)

        notes = []
        current_midi = None
        onset = None

        for i, freq in enumerate(f0):
            t = times[i]
            if np.isnan(freq):
                if current_midi is not None:
                    duration = t - onset
                    hz = librosa.midi_to_hz(current_midi)
                    notes.append({
                        "frequency_hz": hz,
                        "start_sec": onset,
                        "duration_sec": duration,
                        "pitch_midi": int(current_midi)
                    })
                    current_midi = None
            else:
                midi = librosa.hz_to_midi(freq)
                if current_midi is None:
                    current_midi = midi
                    onset = t
                else:
                    if abs(midi - current_midi) >= 0.5:
                        duration = t - onset
                        hz = librosa.midi_to_hz(current_midi)
                        notes.append({
                            "frequency_hz": hz,
                            "start_sec": onset,
                            "duration_sec": duration,
                            "pitch_midi": int(current_midi)
                        })
                        current_midi = midi
                        onset = t

        if current_midi is not None:
            duration = times[-1] - onset
            hz = librosa.midi_to_hz(current_midi)
            notes.append({
                "frequency_hz": hz,
                "start_sec": onset,
                "duration_sec": duration,
                "pitch_midi": int(current_midi)
            })

        return notes, sr

def main():
    root = tk.Tk()
    app = VoiceRangeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

# pyinstaller --onefile --windowed Gerenciador_Grupo_Vocal.py
# pyinstaller --onefile --windowed Main.py --add-data "C:\Users\Sérgio\PycharmProjects\Gerenciador de Coral;."