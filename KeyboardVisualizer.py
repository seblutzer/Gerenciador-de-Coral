import tkinter as tk
from tkinter import ttk
import re


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

# ===== VISUALIZADOR DE TECLADO =====
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