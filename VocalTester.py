import json
import numpy as np
import sounddevice as sd
import threading
import librosa
import time
from collections import deque
import math
import tkinter as tk

class BeltIndicator(tk.Canvas):
    """
    BeltIndicator self-contained:
    - Semitons na faixa [semitone_min, semitone_max] com espaçamento não-linear
      (centrado em 0, controlado por sigma).
    - O marcador vermelho posiciona-se no semitomo atual correspondente ao offset.
    - O cent-line (indicação de cents) fica dentro do semitomo atual.
    - Fácil de copiar/colar entre arquivos sem dependências externas.
    """

    def __init__(self, master, width=320, height=60,
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


class VocalTestCore:
    """Núcleo de teste vocal sem interface gráfica - retorna dados apenas"""

    def __init__(self):
        # Notas musicais...
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

        # Callbacks para UI (serão fornecidos por VoiceRangeApp)
        self.on_update_ui = None
        self.on_test_complete = None
        self.on_request_button_state = None

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
        self.current_note_index = self.note_sequence.index(self.highest_note)
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
            status="Cante a nota MAIS AGUDA que conseguir! Mantenha por 3 segundos.",
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
                        self.silence_break_time = 0.0
                        self._update_ui(
                            status="Pausa de silêncio detectada. Reiniciando contagem...",
                            status_color='#F39C12',
                            time_text=f"Tempo mantendo a nota: 0.0s / 3.0s"
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
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s",
                                time=min(100, (self.correct_time / 3.0) * 100)
                            )

                            if self.correct_time >= 3.0:
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

                        progress = min(100, (self.correct_time / 3.0) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text="Tempo mantendo a nota: 0.0s / 3.0s"
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
            status="Cante a nota MAIS GRAVE que conseguir! Mantenha por 3 segundos.",
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
                        self.silence_break_time = 0.0
                        self._update_ui(
                            status="Pausa de silêncio detectada. Reiniciando contagem...",
                            status_color='#F39C12',
                            time_text=f"Tempo mantendo a nota: 0.0s / 3.0s"
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
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s",
                                time=min(100, (self.correct_time / 3.0) * 100)
                            )

                            if self.correct_time >= 3.0:
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

                        progress = min(100, (self.correct_time / 3.0) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text="Tempo mantendo a nota: 0.0s / 3.0s"
                    )
                    self.correct_time = 0
                    self.frequency_buffer.clear()
                    last_stable_note = None  # MUDANÇA: reseta nota estável

                time.sleep(0.1)
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
                self._update_ui(
                    status="C4 ignorado! Descendo...",
                    status_color='#F39C12',
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.phase = 'descending'
                self.current_note_index = self.note_sequence.index('B3')
            else:
                # Continuando a descer
                self._update_ui(
                    too_low_button='disabled',
                    too_high_button='disabled'
                )
                self.current_note_index -= 1
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

                        self.silence_break_time = 0.0
                        self._update_ui(
                            status="Pausa de silêncio detectada. Reiniciando contagem da média...",
                            status_color='#F39C12',
                            time_text=f"Tempo mantendo a nota: 0.0s / 3.0s"
                        )

                detected_freq = self.detect_pitch(audio_chunk)

                # Dentro de listen_and_detect, logo após:
                if detected_freq is not None and detected_freq > 0:
                    self.frequency_buffer.append(detected_freq)

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

                        if self.correct_time >= 3.0:
                            self.on_note_success(current_note)
                            break

                        self._update_ui(
                            status=f"✓ Mantendo {current_note} (média)!",
                            status_color='#27AE60',
                            detected_note=detected_note if detected_note else "--",
                            time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / 3.0s",
                            time=min(100, (self.correct_time / 3.0) * 100)
                        )
                    else:
                        self.correct_time = 0
                        self._update_ui(
                            status=f"Média em {average_note}, esperado: {current_note}",
                            status_color='#E74C3C',
                            detected_note=detected_note if detected_note else "--"
                        )

                    progress = min(100, (self.correct_time / 3.0) * 100)
                else:
                    self._update_ui(
                        status="Nenhuma nota detectada. Cante!",
                        status_color='#E74C3C',
                        detected_note="--",
                        detected_freq="-- Hz",
                        time_text="Tempo mantendo a nota: 0.0s / 3.0s"
                    )
                    self.correct_time = 0

                time.sleep(0.1)
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
        self.current_note_index = self.note_sequence.index(self.lowest_note)

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
