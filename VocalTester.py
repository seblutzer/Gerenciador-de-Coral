import numpy as np
import sounddevice as sd
import librosa
import time
from collections import deque
import math
from Constants import NOTES_FREQUENCY_HZ
import pretty_midi
import tkinter as tk
from tkinter import ttk, simpledialog
import threading

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
        self.current_note = None

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

        # Desenhar a faixa sombreada e a linha atual (se houver current_note)
        if getattr(self, "current_note", None) is not None:
            y_curr = midi_to_y(self.current_note)
            y_down = midi_to_y(self.current_note - 1)
            y_up = midi_to_y(self.current_note + 1)

            # Pontos intermediários entre current_note e os adjacentes
            y_mid_down = (y_curr + y_down) / 2.0  # entre current e o semitom abaixo
            y_mid_up = (y_curr + y_up) / 2.0  # entre current e o semitom acima

            top = min(y_mid_up, y_mid_down)
            bottom = max(y_mid_up, y_mid_down)

            # Faixa sombreada (pode ajustar a cor ou usar stippling para transparência)
            self.create_rectangle(pad, top, w - pad, bottom, fill='#ffcccc', outline='')

        # Desenhar grade de semitons visíveis (na faixa atual)
        # Mostrar apenas inteiros dentro da faixa visível
        min_int = int(math.floor(self.plot_min_midi))
        max_int = int(math.ceil(self.plot_max_midi))
        for m in range(min_int, max_int + 1):
            y = midi_to_y(float(m))
            if self.current_note and m == self.current_note:
                self.create_line(pad, y, w - pad, y, fill='#e74c3c', width=4)
            else:
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

        # Novo: log de pitches capturados durante a gravação
        self._pitch_log = []  # lista de {'time': float, 'freq': float, 'note': str}
        self._record_pitch = False  # está gravando pitch?
        self._pitch_log_start_time = None  # tempo de início da gravação
        self._pitch_orig_update_ui = None  # salva callback original de UI

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

    def filter_pitch_log(self, raw_log):
        """
        Filtra oscilações e artefatos do log de pitch.

        Filtros aplicados:
        1. Remove notas fora do range C2-E6 (65.41 Hz - 659.25 Hz)
        2. Remove variações >20 semitons entre amostras consecutivas
        3. Remove picos isolados de 1 semitom entre notas iguais
        4. Remove picos isolados no início/fim de sequências constantes
        5. Suaviza variações >3 semitons em <0.2s

        Adições:
        - Filtro de repetição: elimina pitches isolados, mantendo apenas pitches que apareçam
          pelo menos duas vezes consecutivas. Caso a sequência seja ABAB (duas notas alternadas),
          transforma em pares duplicados (A3-A3-C4-C4).
        - Integração de filtros adicionais (vibrato, portamento e mediana) já existentes
          fica dentro do mesmo método.

        Args:
            raw_log: Lista de {'time': float, 'freq': float, 'note': str}

        Returns:
            Lista filtrada com mesmo formato
        """
        if not raw_log or len(raw_log) < 3:
            return raw_log

        # Constantes
        MIN_FREQ = 65.41  # C2
        MAX_FREQ = 659.25  # E6
        MAX_SEMITONE_JUMP = 20
        RAPID_CHANGE_SEMITONES = 3
        RAPID_CHANGE_TIME = 0.2
        DUP_TIME = 1e-6  # pequeno delta de tempo para duplicar amostras (ABAB)

        # Filtro 1 e 2: Range válido e saltos absurdos
        filtered = []
        for i, entry in enumerate(raw_log):
            freq = entry['freq']

            # Filtro 1: Range C2-E6
            if freq < MIN_FREQ or freq > MAX_FREQ:
                continue

            # Filtro 2: Variação >20 semitons
            if filtered:
                prev_midi = pretty_midi.hz_to_note_number(filtered[-1]['freq'])
                curr_midi = pretty_midi.hz_to_note_number(freq)
                if abs(curr_midi - prev_midi) > MAX_SEMITONE_JUMP:
                    continue

            filtered.append(entry.copy())

        if len(filtered) < 3:
            return filtered

        # Filtro 3: Picos isolados de 1 semitom (X-X-Y-X-X)
        cleaned = []
        i = 0
        while i < len(filtered):
            if i == 0 or i >= len(filtered) - 1:
                cleaned.append(filtered[i])
                i += 1
                continue

            prev_note = filtered[i - 1]['note']
            curr_note = filtered[i]['note']
            next_note = filtered[i + 1]['note']

            # Se nota atual difere de ambos vizinhos iguais, é pico
            if prev_note == next_note and curr_note != prev_note:
                prev_midi = pretty_midi.hz_to_note_number(filtered[i - 1]['freq'])
                curr_midi = pretty_midi.hz_to_note_number(filtered[i]['freq'])

                # Apenas remove se for variação de 1 semitom
                if abs(curr_midi - prev_midi) <= 1:
                    i += 1  # Pula este pico
                    continue

            cleaned.append(filtered[i])
            i += 1

        if len(cleaned) < 3:
            return cleaned

        # Filtro 4: Picos isolados no início/fim de sequências constantes
        # Detecta sequências de 3+ notas iguais
        final = []
        i = 0
        while i < len(cleaned):
            curr_note = cleaned[i]['note']

            # Verifica se próximos 3+ são iguais
            sequence_length = 1
            j = i + 1
            while j < len(cleaned) and cleaned[j]['note'] == cleaned[i]['note']:
                sequence_length += 1
                j += 1

            # Se temos sequência de 4+, verificamos vizinhos
            if sequence_length >= 4:
                # Verifica nota anterior (pico antes da sequência)
                if i > 0:
                    prev_note = cleaned[i - 1]['note']
                    if prev_note != curr_note:
                        prev_midi = pretty_midi.hz_to_note_number(cleaned[i - 1]['freq'])
                        curr_midi = pretty_midi.hz_to_note_number(cleaned[i]['freq'])
                        # Se é pico pequeno isolado, remove retrospectivamente
                        if abs(curr_midi - prev_midi) <= 3 and len(final) > 0:
                            final.pop()  # Remove o pico que já adicionamos

                # Adiciona toda a sequência
                for k in range(i, j):
                    final.append(cleaned[k])

                # Verifica nota posterior (pico depois da sequência)
                if j < len(cleaned):
                    next_note = cleaned[j]['note']
                    if next_note != curr_note:
                        next_midi = pretty_midi.hz_to_note_number(cleaned[j]['freq'])
                        curr_midi = pretty_midi.hz_to_note_number(cleaned[j - 1]['freq'])
                        # Se próxima é pico pequeno, pula ela
                        if abs(next_midi - curr_midi) <= 3:
                            i = j + 1
                            continue

                i = j
            else:
                final.append(cleaned[i])
                i += 1

        if len(final) < 3:
            return final

        # Novo filtro de repetição integrado:
        # Remove pitches isolados; trata ABAB (A,B,A,B,...) duplicando cada pitch para formar pares A,A,B,B ...
        rep = []
        i = 0
        while i < len(final):
            # Checa padrão ABAB (alternância entre dois pitches)
            if i + 1 < len(final) and final[i]['note'] != final[i + 1]['note']:
                a = final[i]['note']
                b = final[i + 1]['note']
                s = i + 2
                # expande enquanto pertence a {a,b}
                while s < len(final) and final[s]['note'] in (a, b):
                    s += 1
                length = s - i
                # verifica se é estritamente alternante para pelo menos 4 elementos
                if length >= 4 and all(final[i + t]['note'] == (a if t % 2 == 0 else b) for t in range(length)):
                    # substitui por duplicatas (A,A,B,B,...)
                    seg = final[i:s]
                    for ent in seg:
                        # primeira ocorrência
                        rep.append({'time': ent['time'], 'freq': ent['freq'], 'note': ent['note']})
                        # duplicata com pequeno deslocamento temporal
                        rep.append({'time': ent['time'] + DUP_TIME, 'freq': ent['freq'], 'note': ent['note']})
                    i = s
                    continue
            # Sem ABAB: aplicar regra de repetição simples (padrão: manter runs de >=2)
            if i < len(final):
                run_note = final[i]['note']
                j = i + 1
                while j < len(final) and final[j]['note'] == run_note:
                    j += 1
                run_len = j - i
                if run_len >= 2:
                    rep.extend(final[i:j])
                # Se run_len == 1, drop(single)
                i = j

        if len(rep) < 3:
            return rep

        # Filtro 5: Variações rápidas >3 semitons em <0.2s
        smoothed = [rep[0]]

        i = 1
        while i < len(rep):
            time_diff = rep[i]['time'] - smoothed[-1]['time']

            if time_diff < RAPID_CHANGE_TIME:
                curr_midi = pretty_midi.hz_to_note_number(rep[i]['freq'])
                prev_midi = pretty_midi.hz_to_note_number(smoothed[-1]['freq'])

                if abs(curr_midi - prev_midi) > RAPID_CHANGE_SEMITONES:
                    # Variação rápida detectada
                    # Procura nota "longa" próxima (antes ou depois)

                    # Verifica se há sequência longa antes
                    long_before = None
                    if len(smoothed) >= 3:
                        # Últimas 3 notas iguais?
                        if (smoothed[-1]['note'] == smoothed[-2]['note'] ==
                                smoothed[-3]['note']):
                            long_before = smoothed[-1]['note']

                    # Verifica se há sequência longa depois
                    long_after = None
                    if i + 2 < len(rep):
                        if (rep[i]['note'] == rep[i + 1]['note'] ==
                                rep[i + 2]['note']):
                            long_after = rep[i]['note']

                    # Decide: nota longa ou média
                    if long_before:
                        # Usa nota longa anterior
                        smoothed.append({
                            'time': rep[i]['time'],
                            'freq': smoothed[-1]['freq'],
                            'note': long_before
                        })
                    elif long_after:
                        # Usa nota longa posterior
                        smoothed.append(rep[i])
                    else:
                        # Calcula média entre as duas
                        avg_freq = (smoothed[-1]['freq'] + rep[i]['freq']) / 2.0
                        avg_note, _ = self.frequency_to_note(avg_freq)
                        smoothed.append({
                            'time': rep[i]['time'],
                            'freq': avg_freq,
                            'note': avg_note
                        })

                    i += 1
                    continue

            smoothed.append(rep[i])
            i += 1

        # Filtro 6: Vibrato excessivo
        # Conta oscilações em uma janela de 1s
        def count_oscillations(sequence, window_notes=None):
            changes = 0
            for idx in range(1, len(sequence)):
                if sequence[idx]['note'] != sequence[idx - 1]['note']:
                    changes += 1
            return changes

        vibrato_filtered = [smoothed[0]]
        for idx in range(1, len(smoothed)):
            window_start_time = smoothed[idx]['time'] - 1.0
            window = [s for s in vibrato_filtered if s['time'] >= window_start_time]

            if len(window) > 1 and count_oscillations(window) > 6:
                avg_freq = sum(s['freq'] for s in window) / len(window)
                avg_note, _ = self.frequency_to_note(avg_freq)
                vibrato_filtered.append({
                    'time': smoothed[idx]['time'],
                    'freq': avg_freq,
                    'note': avg_note
                })
            else:
                vibrato_filtered.append(smoothed[idx])

        # Filtro 7: Portamento
        portamento_filtered = []
        i = 0
        while i < len(vibrato_filtered):
            curr_note = vibrato_filtered[i]['note']

            # Verifica se há progressão gradual (C-C#-D-D#-E em <0.5s)
            progression = [vibrato_filtered[i]]
            j = i + 1
            while j < len(vibrato_filtered):
                time_diff = vibrato_filtered[j]['time'] - progression[0]['time']
                if time_diff > 0.5:
                    break

                curr_midi = pretty_midi.hz_to_note_number(progression[-1]['freq'])
                next_midi = pretty_midi.hz_to_note_number(vibrato_filtered[j]['freq'])

                # Se próxima nota é exatamente 1 semitom acima/abaixo
                if abs(next_midi - curr_midi) == 1:
                    progression.append(vibrato_filtered[j])
                    j += 1
                else:
                    break

            # Se detectou progressão de 4+ notas, é portamento
            if len(progression) >= 4:
                # Usa última nota da progressão (destino)
                portamento_filtered.append(progression[-1])
                i = j
            else:
                portamento_filtered.append(vibrato_filtered[i])
                i += 1

        # Filtro 8: Median filter (3)
        def median_of(nums):
            nums = sorted(nums)
            n = len(nums)
            return nums[n // 2]

        median_filtered = []
        for idx, ent in enumerate(portamento_filtered):
            if idx < 1 or idx >= len(portamento_filtered) - 1:
                median_filtered.append(ent)
            else:
                # janela de 3 centrada em idx
                w_start = max(0, idx - 1)
                w_end = min(len(portamento_filtered), idx + 2)
                window_freqs = [portamento_filtered[k]['freq'] for k in range(w_start, w_end)]
                med = median_of(window_freqs)
                med_note, _ = self.frequency_to_note(med)
                median_filtered.append({'time': ent['time'], 'freq': med, 'note': med_note})

        return median_filtered

    def start_test(self):
        """Inicia o teste normal"""
        self._pitch_log = []
        self._pitch_log_start_time = None
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
        self._pitch_log = []
        self._pitch_log_start_time = None
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
                        stop_button='normal',
                        repeat_button='disabled')

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
            status=f"Cante a nota MAIS AGUDA que conseguir! Mantenha por {self._testing_time:.1f} segundos.",
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

                        self._update_ui(current_note=round(pretty_midi.hz_to_note_number(average_freq)))

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
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time:.1f}s",
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
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time:.1f}s"
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
            status=f"Cante a nota MAIS GRAVE que conseguir! Mantenha por {self._testing_time:.1f} segundos.",
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
                        self._update_ui(current_note=round(pretty_midi.hz_to_note_number(average_freq)))

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
                                time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time:.1f}s",
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
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time:.1f}s"
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

    def start_pitch_recording(self, mode='normal'):
        """
        Inicia uma sessão de gravação de pitches.
        mode: 'normal' ou 'quick' (usa start_test ou start_quick_test)
        export_path: caminho opcional para exportar o HTML no fim
        """
        # reset/log
        self._pitch_log = []
        self._pitch_log_start_time = None
        self._record_pitch = True
        self._pitch_orig_update_ui = self.on_update_ui

        # wrapper de UI para logar sem perder a UI existente
        def recording_update_ui(**kwargs):
            # delega para a UI original (se existir)
            if self._pitch_orig_update_ui:
                self._pitch_orig_update_ui(**kwargs)

            # Log somente pitches quando disponíveis
            if self._record_pitch and 'pitch_hz' in kwargs and kwargs['pitch_hz'] is not None:
                if self._pitch_log_start_time is None:
                    self._pitch_log_start_time = time.time()
                t = time.time() - self._pitch_log_start_time
                freq = float(kwargs['pitch_hz'])
                note_tmp, _ = self.frequency_to_note(freq)
                self._pitch_log.append({'time': t, 'freq': freq, 'note': note_tmp})

        # aplica wrapper
        self.on_update_ui = recording_update_ui

        # inicia o teste conforme o modo solicitado
        if mode == 'normal':
            self.start_test()
        elif mode == 'quick':
            self.start_quick_test()
        else:
            raise ValueError("modo inválido. Use 'normal' ou 'quick'.")

    def stop_pitch_recording(self):
        """
        Para a gravação de pitches e restaura callbacks.
        Se export_path for fornecido, exporta o HTML para esse caminho.
        """
        self._record_pitch = False
        # restaura callback original
        if self._pitch_orig_update_ui is not None:
            self.on_update_ui = self._pitch_orig_update_ui
            self._pitch_orig_update_ui = None

        self.export_pitch_log_to_html()

    def export_pitch_log_to_html(self):
        """Exporta o log de pitches para um HTML com gráfico de linha (Plotly)."""
        if not self._pitch_log:
            print("Nada para exportar no pitch log.")
            return

        # NOVO: Aplica filtragem antes de exportar
        filtered_log = self.filter_pitch_log(self._pitch_log)

        if not filtered_log:
            print("Nenhum pitch válido após filtragem.")
            return

        times = [entry['time'] for entry in filtered_log]
        notes = [entry['note'] if entry['note'] else "--" for entry in filtered_log]

        # Estatísticas para incluir no HTML
        total_raw = len(self._pitch_log)
        total_filtered = len(filtered_log)
        removed = total_raw - total_filtered
        # Prepara estatísticas
        stats = {
            'raw': total_raw,
            'filtered': total_filtered,
            'removed': removed
        }

        html = self._build_html_plot(times, notes, stats)

        file_name = simpledialog.askstring("Nomear Arquivo", "Nome do Arquivo:")
        if file_name and file_name.strip():
            with open(f"{file_name}.html", 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Pitch log exportado para {file_name}.html")

    def _build_html_plot(self, times, notes, stats=None):
        import json
        times_json = json.dumps(times)
        notes_json = json.dumps(notes)

        # Estatísticas (se fornecidas)
        stats_html = ""
        if stats:
            stats_html = f"""
        <div style="padding: 20px; background: #f5f5f5; margin-bottom: 10px; border-radius: 5px;">
          <h3 style="margin-top: 0;">Estatísticas de Filtragem</h3>
          <p><strong>Amostras brutas:</strong> {stats['raw']}</p>
          <p><strong>Amostras filtradas:</strong> {stats['filtered']}</p>
          <p><strong>Removidas (oscilações):</strong> {stats['removed']} ({stats['removed'] / stats['raw'] * 100:.1f}%)</p>
        </div>
        """


        # HTML com Plotly (usando CDN)
        html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    </head>
    <body>
      {stats_html}
      <div id="plot" style="width:100%; height:600px;"></div>"""

        # Ordem de semitons dentro de uma oitava, conforme você definiu
        SEMITONE_TO_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        # Converte uma nota tipo "D#3" em um valor numérico de pitch para ordenação
        def note_to_pitch(nota):
            # extrai o nome da nota (inclui # se houver) e o octavo
            i = 0
            while i < len(nota) and (nota[i].isalpha() or nota[i] == '#'):
                i += 1
            name = nota[:i]  # exemplo: "D#" ou "E"
            octave = int(nota[i:])  # exemplo: 3

            idx = SEMITONE_TO_SHARP.index(name)
            return octave * 12 + idx

        # Cria a lista de notas únicas presentes, ordenadas por pitch
        unique_notes = sorted(set(notes), key=note_to_pitch)
        order_json = json.dumps(unique_notes)  # será inserido no JS como array

        # HTML com Plotly (usando CDN)
        html = f"""
            <!doctype html>
            <html>
              <head>
                <meta charset="utf-8" />
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
              </head>
              <body>
                <div id="plot" style="width:100%; height:600px;"></div>
                <script>
                  var times = {times_json};
                  var notes = {notes_json};
                  var data = [{{
                    x: times,
                    y: notes,
                    mode: 'lines+markers',
                    type: 'scatter',
                    line: {{shape: 'linear'}},
                    hovertemplate: 'Tempo: %{{x:.2f}}s, Nota: %{{y}}<extra></extra>',
                  }}];
                  var layout = {{
                    title: 'Log de Pitch (tempo x nota)',
                    xaxis: {{ title: 'Tempo (s)' }},
                    yaxis: {{
                      title: 'Nota',
                      type: 'category',
                      categoryorder: 'array',
                      categoryarray: {order_json}
                    }},
                    margin: {{ t: 30 }},
                    height: 600
                  }};
                  Plotly.newPlot('plot', data, layout);
                </script>
              </body>
            </html>
            """

        return html


    def listen_and_detect(self, current_note, target_frequency):
        """Captura áudio e detecta pitch em tempo real com média móvel"""
        self.correct_time = 0
        self.frequency_buffer.clear()
        self.is_listening = True

        # Rastreia a nota atual
        self.current_playing_note = current_note

        self._update_ui(current_note=self.current_note_index+12)

        self.current_playing_frequency = target_frequency

        # Determina quais botões devem estar disponíveis
        if current_note == 'C4' and not self.c4_skipped_as_low and not self.c4_skipped_as_high and not self.lowest_note:
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

                    # Log de pitch se gravação ativa
                    if self._record_pitch:
                        if self._pitch_log_start_time is None:
                            self._pitch_log_start_time = time.time()
                        t = time.time() - self._pitch_log_start_time
                        note_tmp, _ = self.frequency_to_note(detected_freq)
                        self._pitch_log.append({'time': t, 'freq': detected_freq, 'note': note_tmp})

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
                            time_text=f"Tempo mantendo a nota: {self.correct_time:.1f}s / {self._testing_time:.1f}s",
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
                        time_text=f"Tempo mantendo a nota: 0.0s / {self._testing_time:.1f}s"
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

    def run_pitch_recording_only(self):
        """
        Modo de gravação pura de pitch - apenas captura e loga pitches
        sem tocar notas de referência ou verificar acertos.
        """
        self._pitch_log = []
        self._pitch_log_start_time = None
        self._record_pitch = True

        self.is_testing = True
        self.is_listening = True

        self._update_ui(
            status="Gravando pitch... Cante livremente!",
            status_color='#E74C3C',
            expected_note="LIVRE",
            expected_freq="Gravação livre",
            start_button='disabled',
            start_quick_button='disabled',
            recording_button='normal',
            too_low_button='disabled',
            too_high_button='disabled',
            repeat_button='disabled'
        )

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                blocksize=self.chunk_size)
        stream.start()

        try:
            while self.is_testing and self.is_listening:
                audio_chunk, _ = stream.read(self.chunk_size)
                audio_chunk = audio_chunk.flatten()

                if audio_chunk is not None and len(audio_chunk) > 0:
                    rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64)))))

                    # Noise Gate
                    if self.NOISE_GATE_ENABLED and rms < self.NOISE_GATE_THRESHOLD:
                        detected_freq = None
                    else:
                        detected_freq = self.detect_pitch(audio_chunk)

                    if detected_freq is not None and detected_freq > 0:
                        # Envia para UI
                        self._update_ui(pitch_hz=detected_freq)

                        # Log do pitch
                        if self._pitch_log_start_time is None:
                            self._pitch_log_start_time = time.time()

                        t = time.time() - self._pitch_log_start_time
                        note_tmp, _ = self.frequency_to_note(detected_freq)
                        self._pitch_log.append({'time': t, 'freq': detected_freq, 'note': note_tmp})

                        # Atualiza UI com nota detectada
                        self._update_ui(
                            detected_note=note_tmp if note_tmp else "--",
                            detected_freq=f"{detected_freq:.2f} Hz",
                            status=f"Gravando: {len(self._pitch_log)} amostras ({t:.1f}s)",
                            status_color='#E74C3C'
                        )
                    else:
                        self._update_ui(
                            detected_note="--",
                            detected_freq="-- Hz"
                        )

                time.sleep(0.05)

        finally:
            stream.stop()
            stream.close()

        self._record_pitch = False

"""
VocalTestManager - Responsável por gerenciar testes vocais
Responsabilidades:
- Iniciar/parar testes vocais
- Gerenciar estado do teste (normal/rápido)
- Controlar marcações (grave/agudo demais)
- Atualizar UI durante o teste
- Processar resultados do teste
"""

class VocalTestManager:
    def __init__(self, ui_callbacks):
        """
        Args:
            ui_callbacks: Dicionário com callbacks da UI:
                - update_ui: função para atualizar elementos visuais
                - on_complete: função chamada ao completar teste
                - update_buttons: função para atualizar estado dos botões
        """
        self.vocal_tester = None
        self.ui_callbacks = ui_callbacks
        self.testing_time = VocalTestCore.DEFAULT_TESTING_TIME

    def start_test(self, test_type='normal'):
        """
        Inicia um teste vocal.

        Args:
            test_type: 'normal' ou 'quick'

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester is not None:
            return False, "Um teste já está em andamento!"

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.ui_callbacks['update_ui'],
            complete_callback=self._on_test_complete_internal,
            button_callback=self.ui_callbacks['update_buttons']
        )

        if test_type == 'quick':
            threading.Thread(target=self.vocal_tester.start_quick_test, daemon=True).start()
            return True, "Teste rápido iniciado"
        else:
            threading.Thread(target=self.vocal_tester.start_test, daemon=True).start()
            return True, "Teste normal iniciado"

    def stop_test(self):
        """
        Para o teste vocal em andamento.

        Returns:
            bool: True se havia teste rodando
        """
        if self.vocal_tester:
            self.vocal_tester.stop_test()
            self.vocal_tester = None
            return True
        return False

    def mark_too_low(self):
        """Marca a nota atual como grave demais."""
        if self.vocal_tester:
            self.vocal_tester.mark_too_low()
            return True
        return False

    def mark_too_high(self):
        """Marca a nota atual como agudo demais."""
        if self.vocal_tester:
            self.vocal_tester.mark_too_high()
            return True
        return False

    def repeat_current_tone(self):
        """
        Reproduz o tom atual novamente.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            freq = self.vocal_tester.current_playing_frequency
            if freq and freq > 0:
                threading.Thread(
                    target=self.vocal_tester.play_note,
                    args=(freq, 2),
                    daemon=True
                ).start()
                return True, "Reproduzindo tom atual..."
        return False, "Nenhum tom atual para repetir"

    def update_testing_time(self, new_time):
        """
        Atualiza o tempo de teste.

        Args:
            new_time: Novo tempo em segundos (int)
        """
        self.testing_time = new_time
        VocalTestCore.DEFAULT_TESTING_TIME = new_time

        if self.vocal_tester is not None:
            self.vocal_tester.testing_time = new_time

    def update_noise_gate(self, threshold):
        """
        Atualiza o threshold do noise gate.

        Args:
            threshold: Novo threshold (float)
        """
        VocalTestCore.NOISE_GATE_THRESHOLD = threshold

        if self.vocal_tester is not None:
            self.vocal_tester.NOISE_GATE_THRESHOLD = threshold

    def is_testing(self):
        """Retorna True se há um teste em andamento."""
        return self.vocal_tester is not None

    def _on_test_complete_internal(self, range_min, range_max):
        """
        Callback interno para processar conclusão do teste.
        Delega para o callback da UI.

        Args:
            range_min: Nota mínima detectada
            range_max: Nota máxima detectada
        """
        # Limpa a instância do teste
        self.vocal_tester = None

        # Chama o callback da UI
        if 'on_complete' in self.ui_callbacks:
            self.ui_callbacks['on_complete'](range_min, range_max)

    def get_current_frequency(self):
        """
        Retorna a frequência atual sendo tocada (se houver).

        Returns:
            float ou None
        """
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            return self.vocal_tester.current_playing_frequency
        return None

    def start_pitch_recording(self):
        """
        Inicia gravação pura de pitch sem teste de notas.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester is not None:
            return False, "Um teste ou gravação já está em andamento!"

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.ui_callbacks['update_ui'],
            complete_callback=self._on_recording_complete_internal,
            button_callback=self.ui_callbacks['update_buttons']
        )

        # Inicia thread de gravação pura
        threading.Thread(target=self.vocal_tester.run_pitch_recording_only, daemon=True).start()
        return True, "Gravação de pitch iniciada"

    def stop_pitch_recording(self):
        """
        Para a gravação de pitch e gera o HTML.

        Returns:
            (sucesso: bool, caminho_html: str ou None)
        """
        if self.vocal_tester and hasattr(self.vocal_tester, '_record_pitch'):
            # Para a gravação
            self.vocal_tester.is_testing = False
            self.vocal_tester.is_listening = False


            self.vocal_tester.export_pitch_log_to_html()
            self.vocal_tester = None

            return True
        return False

    def _on_recording_complete_internal(self, range_min, range_max):
        """
        Callback interno para conclusão de gravação.
        Gravação pura não retorna ranges, então apenas limpa.
        """
        self.vocal_tester = None

"""
VocalTestUIBuilder - Responsável por construir a UI de teste vocal
Responsabilidades:
- Criar todos os widgets do teste vocal
- Organizar layout da UI de teste
- Gerenciar referências aos widgets
"""

class VocalTestUIBuilder:
    def __init__(self, parent_frame, testing_time_values, default_testing_time):
        self.parent_frame = parent_frame
        self.testing_time_values = testing_time_values
        self.testing_time = default_testing_time

        # Widgets
        self.testing_time_cb = None
        self.btn_repeat_tone = None
        self.btn_start_test = None
        self.btn_quick_test = None
        self.btn_rec = None
        self.btn_too_low = None
        self.btn_too_high = None
        self.btn_stop_test = None
        self.noise_gate_slider = None
        self.noise_gate_value_label = None
        self.belt_indicator = None
        self.pitch_line_chart = None
        self.time_var = None
        self.progress_bar = None
        self.time_label = None
        self.expected_note_label = None
        self.detected_note_label = None
        self.status_label = None

    def build(self):
        """Constrói toda a UI de teste vocal."""
        # Estado e repetição
        state_row = ttk.Frame(self.parent_frame)
        state_row.pack(anchor="w", pady=(0, 5))

        ttk.Label(state_row, text="Tempo de teste (s):").pack(side="left", padx=(8, 0))
        self.testing_time_cb = ttk.Combobox(
            state_row,
            values=self.testing_time_values,
            state="readonly",
            width=5
        )
        self.testing_time_cb.pack(side="left", padx=(8, 0))
        self.testing_time_cb.current(self.testing_time_values.index(self.testing_time))

        self.btn_repeat_tone = ttk.Button(
            state_row,
            text="🔁 Repetir Tom",
            state='disabled'
        )
        self.btn_repeat_tone.pack(side="left", padx=(8, 0))

        # Botões de teste
        buttons_row = ttk.Frame(self.parent_frame)
        buttons_row.pack(fill="x", pady=5)

        self.btn_start_test = ttk.Button(buttons_row, text="🏁 Iniciar Teste")
        self.btn_start_test.grid(row=0, column=0, padx=3, sticky="ew")

        self.btn_quick_test = ttk.Button(buttons_row, text="⚡ Teste Rápido")
        self.btn_quick_test.grid(row=0, column=1, padx=3, sticky="ew")

        self.btn_rec = ttk.Button(buttons_row, text="🔴REC Pitch")
        self.btn_rec.grid(row=0, column=2, padx=3, sticky="ew")

        ##########################################

        buttons_row.columnconfigure(0, weight=1)
        buttons_row.columnconfigure(1, weight=1)
        buttons_row.columnconfigure(2, weight=1)

        # Botões de marcação
        marking_row = ttk.Frame(self.parent_frame)
        marking_row.pack(fill="x", pady=5)

        self.btn_too_low = ttk.Button(
            marking_row,
            text="🔽️ Grave D.",
            state='disabled'
        )
        self.btn_too_low.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_too_high = ttk.Button(
            marking_row,
            text="🔼 Agudo D.",
            state='disabled'
        )
        self.btn_too_high.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_stop_test = ttk.Button(
            marking_row,
            text="🛑 Parar",
            state='disabled'
        )
        self.btn_stop_test.grid(row=0, column=2, padx=2, sticky="ew")

        marking_row.columnconfigure(0, weight=1)
        marking_row.columnconfigure(1, weight=1)
        marking_row.columnconfigure(2, weight=1)

        # Controle de noise gate
        noise_gate_frame = ttk.LabelFrame(
            self.parent_frame,
            text="Controle de Abafamento",
            padding=8
        )
        noise_gate_frame.pack(fill="x", pady=5)

        ttk.Label(
            noise_gate_frame,
            text="Nível de abafamento do microfone:",
            font=("Arial", 9)
        ).pack(anchor="w", padx=5)

        slider_frame = ttk.Frame(noise_gate_frame)
        slider_frame.pack(fill="x", padx=5, pady=5)

        self.noise_gate_slider = tk.Scale(
            slider_frame,
            from_=0,
            to=0.02,
            resolution=0.0001,
            orient="horizontal",
            length=300
        )
        self.noise_gate_slider.set(VocalTestCore.NOISE_GATE_THRESHOLD)
        self.noise_gate_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.noise_gate_value_label = ttk.Label(
            slider_frame,
            text=f"{VocalTestCore.NOISE_GATE_THRESHOLD:.4f}",
            font=("Arial", 9, "bold"),
            foreground="#2E86AB",
            width=8
        )
        self.noise_gate_value_label.pack(side="left")

        # Indicador visual (belt)
        self.belt_indicator = BeltIndicator(self.parent_frame, width=300, height=50)
        self.belt_indicator.set_range(-12, 12)
        self.belt_indicator.pack(pady=5)

        # Progresso de tempo
        self.time_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.parent_frame,
            variable=self.time_var,
            maximum=100,
            length=300,
            mode='determinate'
        )
        self.progress_bar.pack(pady=3)

        self.time_label = ttk.Label(
            self.parent_frame,
            text=f"Tempo: 0.0s / {self.testing_time}.0s",
            font=("Arial", 8)
        )
        self.time_label.pack(pady=(0, 5))

        # Notas esperada e detectada
        notes_frame = ttk.Frame(self.parent_frame)
        notes_frame.pack(fill="x", pady=5)

        ttk.Label(notes_frame, text="Esperada:", font=("Arial", 8, "bold")).pack(
            side="left", padx=2
        )
        self.expected_note_label = ttk.Label(
            notes_frame,
            text="--",
            font=("Arial", 9),
            foreground="#2E86AB"
        )
        self.expected_note_label.pack(side="left", padx=2)

        ttk.Label(notes_frame, text="→", font=("Arial", 10)).pack(side="left", padx=5)

        ttk.Label(notes_frame, text="Detectada:", font=("Arial", 8, "bold")).pack(
            side="left", padx=2
        )
        self.detected_note_label = ttk.Label(
            notes_frame,
            text="--",
            font=("Arial", 9),
            foreground="#888"
        )
        self.detected_note_label.pack(side="left", padx=2)

        # Status
        self.status_label = ttk.Label(
            self.parent_frame,
            text="Aguardando...",
            font=("Arial", 9),
            foreground="#666"
        )
        self.status_label.pack(pady=5)

    def add_pitch_chart(self, parent_frame):
        """Adiciona o gráfico de pitch à UI (separado pois vai em outro frame)."""
        self.pitch_line_chart = PitchLineChart(
            parent_frame,
            width=640,
            height=300,
            min_midi=40,
            max_midi=84
        )
        return self.pitch_line_chart

    def get_widgets(self):
        """Retorna todos os widgets criados."""
        return {
            'testing_time_cb': self.testing_time_cb,
            'btn_repeat_tone': self.btn_repeat_tone,
            'btn_start_test': self.btn_start_test,
            'btn_quick_test': self.btn_quick_test,
            'btn_rec': self.btn_rec,
            'btn_too_low': self.btn_too_low,
            'btn_too_high': self.btn_too_high,
            'btn_stop_test': self.btn_stop_test,
            'noise_gate_slider': self.noise_gate_slider,
            'noise_gate_value_label': self.noise_gate_value_label,
            'belt_indicator': self.belt_indicator,
            'pitch_line_chart': self.pitch_line_chart,
            'time_var': self.time_var,
            'progress_bar': self.progress_bar,
            'time_label': self.time_label,
            'expected_note_label': self.expected_note_label,
            'detected_note_label': self.detected_note_label,
            'status_label': self.status_label
        }
