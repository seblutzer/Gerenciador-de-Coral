import json
import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk
import threading
import librosa
import time
from collections import deque

class VocalTestRealtime:
    def __init__(self):
        # Notas musicais e suas frequências (Hz)
        self.notes = {'C0': 16.35, 'C#0': 17.32, 'D0': 18.35, 'D#0': 19.45, 'E0': 20.6, 'F0': 21.83, 'F#0': 23.12,
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

        # Ordem das notas
        self.note_sequence = list(self.notes.keys())
        self.current_note_index = self.note_sequence.index('C4')

        # Break em caso de parar
        self.max_amplitude = 1e-6
        self.silence_break_time = 0.0

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

        # Modo do teste: 'normal' ou 'quick'
        self.test_mode = 'normal'
        self.quick_test_calibration_complete = False

        # Interface
        self.setup_ui()

    def setup_ui(self):
        self.window = tk.Tk()
        self.window.title("Teste Vocal Inteligente")
        self.window.geometry("1100x1000")
        self.window.configure(bg='#f0f0f0')

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')

        # Header
        header = ttk.Frame(self.window, height=100)
        header.pack(fill='x', padx=20, pady=20)

        ttk.Label(header, text="🎤 TESTE VOCAL INTELIGENTE",
                  font=('Arial', 28, 'bold')).pack()

        # Nota esperada vs detectada
        comparison_frame = ttk.Frame(self.window)
        comparison_frame.pack(pady=20)

        # Nota esperada
        expected_box = ttk.LabelFrame(comparison_frame, text="Nota Esperada",
                                      padding=15)
        expected_box.grid(row=0, column=0, padx=20)

        self.expected_note_label = ttk.Label(expected_box, text="C4",
                                             font=('Arial', 48, 'bold'),
                                             foreground='#2E86AB')
        self.expected_note_label.pack()

        self.expected_freq_label = ttk.Label(expected_box, text="261.63 Hz",
                                             font=('Arial', 14))
        self.expected_freq_label.pack()

        # Seta central
        ttk.Label(comparison_frame, text="→", font=('Arial', 32)).grid(row=0, column=1, padx=20)

        # Nota detectada
        detected_box = ttk.LabelFrame(comparison_frame, text="Nota Detectada (Atual)",
                                      padding=15)
        detected_box.grid(row=0, column=2, padx=20)

        self.detected_note_label = ttk.Label(detected_box, text="--",
                                             font=('Arial', 48, 'bold'),
                                             foreground='#888888')
        self.detected_note_label.pack()

        self.detected_freq_label = ttk.Label(detected_box, text="-- Hz",
                                             font=('Arial', 14))
        self.detected_freq_label.pack()

        # Nota média
        average_box = ttk.LabelFrame(comparison_frame, text="Média (Últimos 3s)",
                                     padding=15)
        average_box.grid(row=1, column=2, padx=20, pady=15)

        self.average_note_label = ttk.Label(average_box, text="--",
                                            font=('Arial', 32, 'bold'),
                                            foreground='#27AE60')
        self.average_note_label.pack()

        self.average_freq_label = ttk.Label(average_box, text="-- Hz",
                                            font=('Arial', 12))
        self.average_freq_label.pack()

        # Status
        self.status_label = ttk.Label(self.window, text="Aguardando...",
                                      font=('Arial', 14), foreground='#666666')
        self.status_label.pack(pady=10)

        # Diferença em cents
        self.difference_label = ttk.Label(self.window, text="Diferença (atual): -- cents",
                                          font=('Arial', 12))
        self.difference_label.pack(pady=5)

        self.average_difference_label = ttk.Label(self.window, text="Diferença (média): -- cents",
                                                  font=('Arial', 12, 'bold'), foreground='#27AE60')
        self.average_difference_label.pack(pady=5)

        # Progresso circular (tempo correto)
        self.time_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.window, variable=self.time_var,
                                        maximum=100, length=500, mode='determinate')
        self.progress.pack(pady=15)

        self.time_label = ttk.Label(self.window, text="Tempo mantendo a nota: 0.0s / 3.0s",
                                    font=('Arial', 12, 'bold'))
        self.time_label.pack()

        # Botões
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=15)

        self.start_button = ttk.Button(button_frame, text="Iniciar Teste",
                                       command=self.start_test)
        self.start_button.grid(row=0, column=0, padx=10)

        self.start_quick_button = ttk.Button(button_frame, text="⚡ Teste Rápido",
                                             command=self.start_quick_test)
        self.start_quick_button.grid(row=0, column=1, padx=10)

        self.too_low_button = ttk.Button(button_frame, text="⬇️ Grave Demais",
                                         command=self.mark_too_low, state='disabled')
        self.too_low_button.grid(row=0, column=2, padx=10)

        self.too_high_button = ttk.Button(button_frame, text="⬆️ Agudo Demais",
                                          command=self.mark_too_high, state='disabled')
        self.too_high_button.grid(row=0, column=3, padx=10)

        self.stop_button = ttk.Button(button_frame, text="Parar Teste",
                                      command=self.stop_test, state='disabled')
        self.stop_button.grid(row=0, column=4, padx=10)

        self.repeat_button = ttk.Button(button_frame, text="🔄 Repetir Nota",
                                        command=self.repeat_current_note, state='disabled')
        self.repeat_button.grid(row=0, column=5, padx=10)

        # Info com SCROLL
        info_frame = ttk.LabelFrame(self.window, text="Informações", padding=10)
        info_frame.pack(fill='both', expand=True, padx=20, pady=15)

        # Canvas com scrollbar
        canvas = tk.Canvas(info_frame, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(info_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Conteúdo do info
        self.info_label = ttk.Label(scrollable_frame,
                                    text="🎤 TESTE VOCAL INTELIGENTE:\n\n"
                                         "Este teste detecta automaticamente seu range vocal!\n\n"
                                         "📌 TESTE NORMAL (Começando em C4):\n\n"
                                         "CENÁRIO 1 - Consegue fazer C4:\n"
                                         "   • C4 é conquistado automaticamente\n"
                                         "   • Sobe: C#4, D4, E4... (até não conseguir)\n"
                                         "   • Clique '⬆️ Agudo Demais' quando atingir seu limite\n"
                                         "   • Desce: B3, A#3, A3... (até não conseguir)\n"
                                         "   • Clique '⬇️ Grave Demais' quando atingir seu limite\n"
                                         "   • Pronto! Range vocal identificado!\n\n"
                                         "CENÁRIO 2 - C4 é GRAVE DEMAIS:\n"
                                         "   • Clique '⬇️ Grave Demais' em C4\n"
                                         "   • C4 é IGNORADO (não entra no range)\n"
                                         "   • Sobe: C#4, D4, E4...\n"
                                         "   • '⬇️ Grave Demais' continua disponível\n"
                                         "   • Clique novamente para continuar subindo se ainda estiver grave\n"
                                         "   • Quando CONSEGUIR uma nota:\n"
                                         "      → Essa é sua nota mais GRAVE\n"
                                         "      → '⬇️ Grave Demais' DESABILITA\n"
                                         "      → '⬆️ Agudo Demais' ATIVA\n"
                                         "   • Continue subindo até apertar '⬆️ Agudo Demais'\n"
                                         "   • FIM! Essa será sua nota mais AGUDA!\n\n"
                                         "CENÁRIO 3 - C4 é AGUDO DEMAIS:\n"
                                         "   • Clique '⬆️ Agudo Demais' em C4\n"
                                         "   • C4 é IGNORADO (não entra no range)\n"
                                         "   • Desce: B3, A#3, A3...\n"
                                         "   • '⬆️ Agudo Demais' continua disponível\n"
                                         "   • Clique novamente para continuar descendo se ainda estiver agudo\n"
                                         "   • Quando CONSEGUIR uma nota:\n"
                                         "      → Essa é sua nota mais AGUDA\n"
                                         "      → '⬆️ Agudo Demais' DESABILITA\n"
                                         "      → '⬇️ Grave Demais' ATIVA\n"
                                         "   • Continue descendo até apertar '⬇️ Grave Demais'\n"
                                         "   • FIM! Essa será sua nota mais GRAVE!\n\n"
                                         "⚡ TESTE RÁPIDO:\n\n"
                                         "   1. Cante a nota MAIS AGUDA que conseguir\n"
                                         "   2. Mantenha por 3 segundos para que o sistema identifique\n"
                                         "   3. Clique '⬆️ Agudo Demais' quando terminar a nota aguda\n"
                                         "   4. Cante a nota MAIS GRAVE que conseguir\n"
                                         "   5. Mantenha por 3 segundos para que o sistema identifique\n"
                                         "   6. Clique '⬇️ Grave Demais' quando terminar a nota grave\n"
                                         "   7. O teste continua a partir dessas 2 notas de âncora!\n\n"
                                         "Este modo é mais rápido pois inicia direto nos seus extremos.",
                                    font=('Arial', 10), justify='left', wraplength=900)
        self.info_label.pack(anchor='w', pady=10, padx=10)

        self.result_label = ttk.Label(scrollable_frame, text="", font=('Arial', 12, 'bold'),
                                      foreground='#27AE60')
        self.result_label.pack(anchor='w', pady=10, padx=10)

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

        self.start_button.config(state='disabled')
        self.start_quick_button.config(state='disabled')
        self.too_low_button.config(state='disabled')
        self.too_high_button.config(state='disabled')
        self.stop_button.config(state='normal')

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

        self.start_button.config(state='disabled')
        self.start_quick_button.config(state='disabled')
        self.stop_button.config(state='normal')

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
        self.current_note_index = self.note_sequence.index(self.highest_note)
        self.should_descend_after_ascending = True

        self.status_label.config(text="Calibração completa! Iniciando teste...", foreground='#27AE60')
        self.window.update()
        time.sleep(1)

        # Continua como teste normal a partir das notas de âncora
        self.run_test()

    def calibrate_highest_note(self):
        """Captura a nota mais aguda que o usuário consegue fazer - com critério de 3 segundos de manutenção da MESMA nota"""
        self.expected_note_label.config(text="AGUDO")
        self.expected_freq_label.config(text="Sua nota mais aguda")
        self.status_label.config(text="Cante a nota MAIS AGUDA que conseguir! Mantenha por 3 segundos.",
                                 foreground='#F39C12')
        self.too_high_button.config(state='normal')
        self.too_low_button.config(state='disabled')
        self.window.update()

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

                    if rms > self.max_amplitude:
                        self.max_amplitude = rms if rms > 0 else self.max_amplitude

                    if rms < 0.5 * max(self.max_amplitude, 1e-9):
                        self.silence_break_time += duration_per_chunk
                    else:
                        self.silence_break_time = 0.0

                    if self.silence_break_time >= 0.5:
                        self.frequency_buffer.clear()
                        self.correct_time = 0.0
                        last_stable_note = None  # MUDANÇA: reseta nota estável
                        self.time_var.set(0)
                        self.time_label.config(text=f"Tempo mantendo a nota: 0.0s / 3.0s")
                        self.silence_break_time = 0.0
                        self.status_label.config(
                            text="Pausa de silêncio detectada. Reiniciando contagem...",
                            foreground='#F39C12'
                        )

                detected_freq = self.detect_pitch(audio_chunk)

                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

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
                                self.status_label.config(
                                    text=f"Nota mudou para {average_note}. Reiniciando contagem!",
                                    foreground='#F39C12'
                                )
                            else:
                                target_freq_calibration = self.notes[last_stable_note]

                        cents_diff_average = abs(self.frequency_to_cents(average_freq, target_freq_calibration))
                        is_average_correct = cents_diff_average <= self.tolerance_cents

                        self.detected_note_label.config(text=average_note if average_note else "--",
                                                        foreground='#27AE60' if is_average_correct else '#E74C3C')
                        self.detected_freq_label.config(text=f"{average_freq:.2f} Hz")
                        self.average_difference_label.config(
                            text=f"Diferença (média): {cents_diff_average:.1f} cents {'✓' if is_average_correct else '✗'}",
                            foreground='#27AE60' if is_average_correct else '#E74C3C'
                        )

                        if is_average_correct:
                            self.correct_time += 0.1
                            self.status_label.config(
                                text=f"✓ Mantendo {average_note} (média)!",
                                foreground='#27AE60'
                            )

                            if self.correct_time >= 3.0:
                                self.highest_note = average_note
                                self.status_label.config(
                                    text=f"✓ Nota aguda capturada: {self.highest_note}!",
                                    foreground='#27AE60'
                                )
                                self.is_listening = False
                                break
                        else:
                            self.correct_time = 0
                            self.status_label.config(
                                text=f"Nota {average_note} fora da tolerância, aguardando estabilização!",
                                foreground='#E74C3C'
                            )

                        progress = min(100, (self.correct_time / 3.0) * 100)
                        self.time_var.set(progress)
                        self.time_label.config(text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s")
                else:
                    self.detected_note_label.config(text="--", foreground='#888888')
                    self.detected_freq_label.config(text="-- Hz")
                    self.average_difference_label.config(text="Diferença (média): -- cents")
                    self.status_label.config(text="Nenhuma nota detectada. Cante!", foreground='#E74C3C')
                    self.correct_time = 0
                    self.frequency_buffer.clear()
                    last_stable_note = None  # MUDANÇA: reseta nota estável
                    self.time_var.set(0)
                    self.time_label.config(text="Tempo mantendo a nota: 0.0s / 3.0s")

                self.window.update()
                time.sleep(0.1)

        finally:
            stream.stop()
            stream.close()

        self.too_high_button.config(state='disabled')
        self.window.update()
        time.sleep(1)

    def calibrate_lowest_note(self):
        """Captura a nota mais grave que o usuário consegue fazer - com critério de 3 segundos de manutenção da MESMA nota"""
        self.expected_note_label.config(text="GRAVE")
        self.expected_freq_label.config(text="Sua nota mais grave")
        self.status_label.config(text="Cante a nota MAIS GRAVE que conseguir! Mantenha por 3 segundos.",
                                 foreground='#F39C12')
        self.too_low_button.config(state='normal')
        self.too_high_button.config(state='disabled')

        self.correct_time = 0
        self.frequency_buffer.clear()
        self.is_listening = True
        self.max_amplitude = 1e-6
        self.silence_break_time = 0.0
        last_stable_note = None  # MUDANÇA: rastreia a nota estável atual

        self.window.update()

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

                    if rms > self.max_amplitude:
                        self.max_amplitude = rms if rms > 0 else self.max_amplitude

                    if rms < 0.5 * max(self.max_amplitude, 1e-9):
                        self.silence_break_time += duration_per_chunk
                    else:
                        self.silence_break_time = 0.0

                    if self.silence_break_time >= 0.5:
                        self.frequency_buffer.clear()
                        self.correct_time = 0.0
                        last_stable_note = None  # MUDANÇA: reseta nota estável
                        self.time_var.set(0)
                        self.time_label.config(text=f"Tempo mantendo a nota: 0.0s / 3.0s")
                        self.silence_break_time = 0.0
                        self.status_label.config(
                            text="Pausa de silêncio detectada. Reiniciando contagem...",
                            foreground='#F39C12'
                        )

                detected_freq = self.detect_pitch(audio_chunk)

                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

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
                                self.status_label.config(
                                    text=f"Nota mudou para {average_note}. Reiniciando contagem!",
                                    foreground='#F39C12'
                                )
                            else:
                                target_freq_calibration = self.notes[last_stable_note]

                        cents_diff_average = abs(self.frequency_to_cents(average_freq, target_freq_calibration))
                        is_average_correct = cents_diff_average <= self.tolerance_cents

                        self.detected_note_label.config(text=average_note if average_note else "--",
                                                        foreground='#27AE60' if is_average_correct else '#E74C3C')
                        self.detected_freq_label.config(text=f"{average_freq:.2f} Hz")
                        self.average_difference_label.config(
                            text=f"Diferença (média): {cents_diff_average:.1f} cents {'✓' if is_average_correct else '✗'}",
                            foreground='#27AE60' if is_average_correct else '#E74C3C'
                        )

                        if is_average_correct:
                            self.correct_time += 0.1
                            self.status_label.config(
                                text=f"✓ Mantendo {average_note} (média)!",
                                foreground='#27AE60'
                            )

                            if self.correct_time >= 3.0:
                                self.lowest_note = average_note
                                self.status_label.config(
                                    text=f"✓ Nota grave capturada: {self.lowest_note}!",
                                    foreground='#27AE60'
                                )
                                self.is_listening = False
                                break
                        else:
                            self.correct_time = 0
                            self.status_label.config(
                                text=f"Nota {average_note} fora da tolerância, aguardando estabilização!",
                                foreground='#E74C3C'
                            )

                        progress = min(100, (self.correct_time / 3.0) * 100)
                        self.time_var.set(progress)
                        self.time_label.config(text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s")
                else:
                    self.detected_note_label.config(text="--", foreground='#888888')
                    self.detected_freq_label.config(text="-- Hz")
                    self.average_difference_label.config(text="Diferença (média): -- cents")
                    self.status_label.config(text="Nenhuma nota detectada. Cante!", foreground='#E74C3C')
                    self.correct_time = 0
                    self.frequency_buffer.clear()
                    last_stable_note = None  # MUDANÇA: reseta nota estável
                    self.time_var.set(0)
                    self.time_label.config(text="Tempo mantendo a nota: 0.0s / 3.0s")

                self.window.update()
                time.sleep(0.1)

        finally:
            stream.stop()
            stream.close()

        self.too_low_button.config(state='disabled')
        self.window.update()
        time.sleep(1)

    def mark_too_low(self):
        """Marca como grave demais - sobe ignorando"""
        if not self.first_note_achieved:
            # Primeira vez em C4 (teste normal)
            if self.current_note_index == self.note_sequence.index('C4') and not self.c4_skipped_as_low:
                self.c4_skipped_as_low = True
                self.should_descend_after_ascending = False
                self.status_label.config(text="C4 ignorado! Subindo...", foreground='#F39C12')
                self.current_note_index += 1
                self.too_low_button.config(state='disabled')
                self.too_high_button.config(state='disabled')
            else:
                # Continuando a subir
                self.current_note_index += 1
                self.too_low_button.config(state='disabled')
                self.too_high_button.config(state='disabled')
        else:
            # Já conseguiu a primeira nota - é o limite grave final
            self.lowest_note = self.note_sequence[self.current_note_index]
            self.finish_test()

        self.is_listening = False

    def mark_too_high(self):
        """Marca como agudo demais - desce ignorando"""
        if not self.first_note_achieved:
            # Primeira vez em C4 (teste normal)
            if self.current_note_index == self.note_sequence.index('C4') and not self.c4_skipped_as_high:
                self.c4_skipped_as_high = True
                self.should_descend_after_ascending = False
                self.status_label.config(text="C4 ignorado! Descendo...", foreground='#F39C12')
                self.phase = 'descending'
                self.current_note_index = self.note_sequence.index('B3')
                self.too_low_button.config(state='disabled')
                self.too_high_button.config(state='disabled')
            else:
                # Continuando a descer
                self.current_note_index -= 1
                self.too_low_button.config(state='disabled')
                self.too_high_button.config(state='disabled')
        else:
            # Já conseguiu a primeira nota - é o limite agudo final
            self.highest_note = self.note_sequence[self.current_note_index]

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
        self.start_button.config(state='normal')
        self.start_quick_button.config(state='normal')
        self.too_low_button.config(state='disabled')
        self.too_high_button.config(state='disabled')
        self.stop_button.config(state='disabled')

        self.status_label.config(text="Teste cancelado")
        self.result_label.config(text="")

    def run_test(self):
        """Loop principal do teste"""
        while self.is_testing:
            current_note = self.note_sequence[self.current_note_index]
            target_frequency = self.notes[current_note]

            # Rastreia a nota atual para repetição
            self.current_playing_note = current_note
            self.current_playing_frequency = target_frequency

            self.expected_note_label.config(text=current_note)
            self.expected_freq_label.config(text=f"{target_frequency:.2f} Hz")
            self.status_label.config(text=f"Reproduzindo {current_note}... prepare-se!")
            self.result_label.config(text="")
            self.repeat_button.config(state='normal')  # Habilita repetição
            self.window.update()

            self.play_note(target_frequency)
            time.sleep(0.3)

            self.listen_and_detect(current_note, target_frequency)

    def repeat_current_note(self):
        """Repete a nota atual tocando novamente"""
        if self.current_playing_frequency is not None:
            self.play_note(self.current_playing_frequency)

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
            self.too_low_button.config(state='normal')
            self.too_high_button.config(state='normal')
        elif self.c4_skipped_as_low and not self.first_note_achieved and self.phase == 'ascending':
            # Subindo após pular C4 por ser grave - apenas "Grave Demais"
            self.too_low_button.config(state='normal')
            self.too_high_button.config(state='disabled')
        elif self.c4_skipped_as_high and not self.first_note_achieved and self.phase == 'descending':
            # Descendo após pular C4 por ser agudo - apenas "Agudo Demais"
            self.too_low_button.config(state='disabled')
            self.too_high_button.config(state='normal')
        elif self.first_note_achieved and self.phase == 'ascending':
            # Depois de conseguir a primeira nota, subindo - apenas "Agudo Demais"
            self.too_low_button.config(state='disabled')
            self.too_high_button.config(state='normal')
        elif self.first_note_achieved and self.phase == 'descending':
            # Descendo na segunda fase - apenas "Grave Demais"
            self.too_low_button.config(state='normal')
            self.too_high_button.config(state='disabled')

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

                    if rms > self.max_amplitude:
                        self.max_amplitude = rms if rms > 0 else self.max_amplitude

                    if rms < 0.5 * max(self.max_amplitude, 1e-9):
                        self.silence_break_time += duration_per_chunk
                    else:
                        self.silence_break_time = 0.0

                    if self.silence_break_time >= 0.5:
                        self.frequency_buffer.clear()
                        self.correct_time = 0.0

                        self.time_var.set(0)
                        self.time_label.config(text=f"Tempo mantendo a nota: 0.0s / 3.0s")
                        self.silence_break_time = 0.0

                        self.status_label.config(
                            text="Pausa de silêncio detectada. Reiniciando contagem da média...",
                            foreground='#F39C12'
                        )

                detected_freq = self.detect_pitch(audio_chunk)

                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

                    average_freq = np.mean(list(self.frequency_buffer))

                    cents_diff_current = abs(self.frequency_to_cents(detected_freq, target_frequency))
                    cents_diff_average = abs(self.frequency_to_cents(average_freq, target_frequency))

                    detected_note, _ = self.frequency_to_note(detected_freq)
                    average_note, _ = self.frequency_to_note(average_freq)

                    is_average_correct = cents_diff_average <= self.tolerance_cents

                    self.detected_note_label.config(
                        text=detected_note if detected_note else "--",
                        foreground='#27AE60' if cents_diff_current <= self.tolerance_cents else '#E74C3C'
                    )
                    self.detected_freq_label.config(text=f"{detected_freq:.2f} Hz")
                    self.difference_label.config(
                        text=f"Diferença (atual): {cents_diff_current:.1f} cents"
                    )

                    self.average_note_label.config(
                        text=average_note if average_note else "--",
                        foreground='#27AE60' if is_average_correct else '#E74C3C'
                    )
                    self.average_freq_label.config(text=f"{average_freq:.2f} Hz")
                    self.average_difference_label.config(
                        text=f"Diferença (média): {cents_diff_average:.1f} cents {'✓' if is_average_correct else '✗'}",
                        foreground='#27AE60' if is_average_correct else '#E74C3C'
                    )

                    if is_average_correct:
                        self.correct_time += 0.1

                        if self.correct_time >= 3.0:
                            self.on_note_success(current_note)
                            break

                        self.status_label.config(
                            text=f"✓ Mantendo {current_note} (média)!",
                            foreground='#27AE60'
                        )
                    else:
                        self.correct_time = 0
                        self.status_label.config(
                            text=f"Média em {average_note}, esperado: {current_note}",
                            foreground='#E74C3C'
                        )

                    progress = min(100, (self.correct_time / 3.0) * 100)
                    self.time_var.set(progress)
                    self.time_label.config(text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s")
                else:
                    self.detected_note_label.config(text="--", foreground='#888888')
                    self.detected_freq_label.config(text="-- Hz")
                    self.difference_label.config(text="Diferença (atual): -- cents")
                    self.average_note_label.config(text="--", foreground='#888888')
                    self.average_freq_label.config(text="-- Hz")
                    self.average_difference_label.config(text="Diferença (média): -- cents")
                    self.status_label.config(text="Nenhuma nota detectada. Cante!", foreground='#E74C3C')
                    self.correct_time = 0
                    self.time_var.set(0)
                    self.time_label.config(text="Tempo mantendo a nota: 0.0s / 3.0s")

                self.window.update()
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

        self.status_label.config(text=f"✓ {note} conquistado!", foreground='#27AE60')

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

        self.result_label.config(text="")
        self.window.update()
        time.sleep(1)

    def start_descending_phase(self):
        """Inicia a fase descendente"""
        self.phase = 'descending'
        self.current_note_index = self.note_sequence.index(self.lowest_note)

        self.status_label.config(text="Fase descendente! Preparando...", foreground='#F39C12')
        self.window.update()
        time.sleep(1)

    def finish_test(self):
        """Finaliza o teste"""
        self.is_testing = False
        self.is_listening = False

        result_text = "🎉 TESTE CONCLUÍDO!\n\n"
        if self.highest_note:
            result_text += f"✓ Nota mais aguda: {self.highest_note}\n"
        if self.lowest_note:
            result_text += f"✓ Nota mais grave: {self.lowest_note}\n"

        if self.highest_note and self.lowest_note:
            result_text += f"\n🎵 SEU RANGE VOCAL: {self.lowest_note} até {self.highest_note}"

            # ===== NOVO: Salva resultado para integração com programa de coral =====
            result_data = {
                'range_min': self.lowest_note,
                'range_max': self.highest_note
            }
            try:
                with open('vocal_test_result.json', 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Erro ao salvar resultado: {e}")

        self.result_label.config(text=result_text, foreground='#27AE60')
        self.status_label.config(text="Teste finalizado!")

        self.start_button.config(state='normal')
        self.start_quick_button.config(state='normal')
        self.too_low_button.config(state='disabled')
        self.too_high_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.repeat_button.config(state='disabled')

    def run(self):
        self.window.mainloop()