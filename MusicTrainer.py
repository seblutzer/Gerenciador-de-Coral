import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import threading
from collections import deque
import numpy as np
import sounddevice as sd

try:
    import music21

    MUSICXML_AVAILABLE = True
except ImportError:
    MUSICXML_AVAILABLE = False
    print("Aviso: music21 não instalado. Use: pip install music21")


class KaraokeNote:
    """Representa uma nota no jogo de karaokê"""

    def __init__(self, midi_note, start_time, duration, note_name, lyric=None):
        self.midi_note = midi_note
        self.start_time = start_time
        self.duration = duration
        self.note_name = note_name
        self.lyric = lyric  # Letra da música (se disponível)
        self.hit_time = 0.0  # Tempo que o usuário acertou a nota
        self.total_checked_time = 0.0  # Tempo total verificado

    def get_display_text(self):
        """Retorna o texto a ser exibido (letra ou nome da nota)"""
        return self.lyric if self.lyric else self.note_name

    def get_accuracy(self):
        """Retorna a precisão (0.0 a 1.0) baseado no tempo acertado"""
        if self.total_checked_time == 0:
            return 0.0
        return min(1.0, self.hit_time / self.total_checked_time)

    def is_passed(self, current_time):
        """Verifica se a nota já passou"""
        return current_time > (self.start_time + self.duration)


class PhraseSection:
    """Representa uma seção/frase da música para aprendizado"""

    def __init__(self, notes, phrase_number):
        self.notes = notes  # Lista de KaraokeNote
        self.phrase_number = phrase_number
        self.duration = sum(n.duration for n in notes)
        self.start_time = notes[0].start_time if notes else 0
        self.end_time = notes[-1].start_time + notes[-1].duration if notes else 0

    def get_note_names(self):
        """Retorna string com os nomes das notas ou letras"""
        return "-".join(n.get_display_text() for n in self.notes)


class KaraokeTrack:
    """Representa uma faixa musical para o jogo"""

    def __init__(self, name, notes):
        self.name = name
        self.notes = notes  # Lista de KaraokeNote
        self.duration = max(n.start_time + n.duration for n in notes) if notes else 0
        self.phrases = []  # Será preenchido por split_into_phrases()
        self.time_scale = 1.0  # Multiplicador de tempo (1.0 = normal)
        self.original_duration = self.duration  # Guardar duração original

    def apply_time_scale(self, scale):
        """
        Aplica um fator de escala de tempo a todas as notas.
        scale < 1.0 = mais rápido
        scale > 1.0 = mais lento
        """
        self.time_scale = scale

        # Recalcular todas as durações e posições
        for note in self.notes:
            # Voltar ao tempo original primeiro
            original_start = note.start_time / self.time_scale if self.time_scale != 0 else note.start_time
            original_duration = note.duration / self.time_scale if self.time_scale != 0 else note.duration

            # Aplicar nova escala
            note.start_time = original_start * scale
            note.duration = original_duration * scale

        # Recalcular duração total
        self.duration = max(n.start_time + n.duration for n in self.notes) if self.notes else 0

        # Re-dividir em frases com as novas durações
        self.split_into_phrases()

    def set_target_duration(self, target_seconds):
        """
        Ajusta o tempo para que a música tenha a duração desejada.
        target_seconds: duração desejada em segundos
        """
        if self.original_duration <= 0:
            return

        scale = target_seconds / self.original_duration
        self.apply_time_scale(scale)

    def split_into_phrases(self, max_notes_per_phrase=6):
        """Divide a música em frases menores para aprendizado"""
        self.phrases = []

        if not self.notes:
            return

        current_phrase = []
        phrase_num = 1

        for i, note in enumerate(self.notes):
            current_phrase.append(note)

            # Criar nova frase quando:
            # 1. Atingir o máximo de notas
            # 2. Houver pausa longa (>1s) até a próxima nota
            # 3. For a última nota
            should_break = False

            if len(current_phrase) >= max_notes_per_phrase:
                should_break = True
            elif i < len(self.notes) - 1:
                next_note = self.notes[i + 1]
                gap = next_note.start_time - (note.start_time + note.duration)
                if gap > 1.0:  # Pausa maior que 1 segundo
                    should_break = True
            else:  # Última nota
                should_break = True

            if should_break:
                self.phrases.append(PhraseSection(current_phrase[:], phrase_num))
                current_phrase = []
                phrase_num += 1

        return self.phrases

    @classmethod
    def from_musicxml(cls, part, part_name="Parte"):
        """Cria uma faixa a partir de uma parte do MusicXML"""
        notes = []
        current_time = 0.0

        for element in part.flatten().notesAndRests:
            if element.isNote:
                midi = element.pitch.midi
                duration = element.duration.quarterLength
                note_name = f"{element.pitch.name}{element.pitch.octave}"

                # Extrair letra (lyric) se disponível
                lyric = None
                if hasattr(element, 'lyrics') and element.lyrics:
                    # Pegar a primeira letra disponível
                    lyric_obj = element.lyrics[0]
                    if hasattr(lyric_obj, 'text') and lyric_obj.text:
                        lyric = lyric_obj.text.strip()

                notes.append(KaraokeNote(midi, current_time, duration, note_name, lyric))
            current_time += element.duration.quarterLength

        track = cls(part_name, notes)
        track.split_into_phrases()
        return track

    @classmethod
    def create_test_melody(cls):
        """Cria uma melodia de teste simples"""
        # Criando uma melodia: "Parabéns pra você" simplificada COM LETRAS
        melody = [
            # (MIDI, início, duração, nome, letra)
            (60, 0.0, 0.5, "C4", "Pa"),
            (60, 0.5, 0.5, "C4", "ra"),
            (62, 1.0, 1.0, "D4", "béns"),
            (60, 2.0, 1.0, "C4", "pra"),
            (65, 3.0, 1.0, "F4", "vo"),
            (64, 4.0, 2.0, "E4", "cê"),

            (60, 6.0, 0.5, "C4", "Pa"),
            (60, 6.5, 0.5, "C4", "ra"),
            (62, 7.0, 1.0, "D4", "béns"),
            (60, 8.0, 1.0, "C4", "pra"),
            (67, 9.0, 1.0, "G4", "vo"),
            (65, 10.0, 2.0, "F4", "cê"),

            (60, 12.0, 0.5, "C4", "Pa"),
            (60, 12.5, 0.5, "C4", "ra"),
            (72, 13.0, 1.0, "C5", "béns"),
            (69, 14.0, 1.0, "A4", "que"),
            (65, 15.0, 1.0, "F4", "ri"),
            (64, 16.0, 1.0, "E4", "do"),
            (62, 17.0, 1.0, "D4", "a"),

            (70, 18.0, 0.5, "A#4", "mi"),
            (70, 18.5, 0.5, "A#4", "go"),
            (69, 19.0, 1.0, "A4", "Pa"),
            (65, 20.0, 1.0, "F4", "ra"),
            (67, 21.0, 1.0, "G4", "béns"),
            (65, 22.0, 2.0, "F4", "pra você"),
        ]

        notes = [KaraokeNote(midi, start, dur, name, lyric)
                 for midi, start, dur, name, lyric in melody]

        track = cls("Parabéns pra Você (Teste)", notes)
        track.split_into_phrases()
        return track


class AudioSynthesizer:
    """Sintetiza e reproduz notas musicais"""

    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

    def midi_to_freq(self, midi):
        """Converte nota MIDI para frequência em Hz"""
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))

    def generate_tone(self, frequency, duration, volume=0.3):
        """Gera um tom simples com envelope ADSR"""
        samples = int(duration * self.sample_rate)
        t = np.linspace(0, duration, samples, False)

        # Onda senoidal
        wave = np.sin(2 * np.pi * frequency * t)

        # Envelope ADSR simples
        attack = int(0.01 * self.sample_rate)  # 10ms
        decay = int(0.05 * self.sample_rate)  # 50ms
        release = int(0.1 * self.sample_rate)  # 100ms

        envelope = np.ones(samples)

        # Attack
        if attack > 0:
            envelope[:attack] = np.linspace(0, 1, attack)

        # Decay
        if decay > 0 and attack + decay < samples:
            envelope[attack:attack + decay] = np.linspace(1, 0.7, decay)

        # Release
        if release > 0:
            envelope[-release:] = np.linspace(envelope[-release], 0, release)

        # Aplicar envelope e volume
        wave = wave * envelope * volume

        return wave.astype(np.float32)

    def play_note(self, midi, duration):
        """Toca uma nota MIDI por uma duração específica"""
        freq = self.midi_to_freq(midi)
        tone = self.generate_tone(freq, duration)
        sd.play(tone, self.sample_rate)
        sd.wait()

    def play_phrase(self, notes):
        """Toca uma sequência de notas"""
        for note in notes:
            self.play_note(note.midi_note, note.duration)


class KaraokeVisualizer(tk.Canvas):
    """
    Visualizador de notas estilo Guitar Hero.
    As notas se aproximam da esquerda para a direita.
    """

    def __init__(self, master, width=800, height=400, **kwargs):
        super().__init__(master, width=width, height=height,
                         bg='#1a1a2e', highlightthickness=0, **kwargs)
        self.width = width
        self.height = height

        # Configurações de visualização
        self.lookahead_time = 5.0  # Mostrar 5 segundos à frente
        self.hit_zone_x = 150  # Posição X da zona de acerto
        self.min_midi = 48  # C3
        self.max_midi = 84  # C6

        # Estado do jogo
        self.current_time = 0.0
        self.track = None
        self.detected_midi = None
        self.tolerance_cents = 50  # Tolerância para considerar nota correta

        # Modo de aprendizado
        self.learn_mode = False
        self.current_phrase = None

        self.draw_static_elements()

    def set_track(self, track):
        """Define a faixa a ser tocada"""
        self.track = track
        if track and track.notes:
            midis = [n.midi_note for n in track.notes]
            self.min_midi = min(midis) - 2
            self.max_midi = max(midis) + 2

    def set_learn_phrase(self, phrase):
        """Define a frase atual no modo de aprendizado"""
        self.current_phrase = phrase

    def midi_to_y(self, midi):
        """Converte nota MIDI para coordenada Y"""
        span = max(1, self.max_midi - self.min_midi)
        normalized = (midi - self.min_midi) / span
        return self.height - 80 - (normalized * (self.height - 160))

    def time_to_x(self, note_time):
        """Converte tempo da nota para coordenada X"""
        time_diff = note_time - self.current_time
        if time_diff < 0:
            # Nota já passou
            return self.hit_zone_x - 200
        elif time_diff > self.lookahead_time:
            # Nota muito à frente
            return self.width + 100
        else:
            # Interpolar entre hit_zone_x e largura do canvas
            progress = time_diff / self.lookahead_time
            return self.hit_zone_x + progress * (self.width - self.hit_zone_x - 50)

    def draw_static_elements(self):
        """Desenha elementos estáticos da interface"""
        # Linha da zona de acerto
        self.create_line(self.hit_zone_x, 60, self.hit_zone_x, self.height - 60,
                         fill='#ff4757', width=4, tags='static')

        # Texto da zona de acerto
        self.create_text(self.hit_zone_x, 30, text="♪ ZONA DE ACERTO ♪",
                         fill='#ff4757', font=('Arial', 12, 'bold'),
                         tags='static')

    def update_time(self, current_time):
        """Atualiza o tempo atual do jogo"""
        self.current_time = current_time
        self.draw()

    def update_detected_pitch(self, midi_float):
        """Atualiza o pitch detectado do microfone"""
        self.detected_midi = midi_float

    def draw(self):
        """Redesenha o canvas"""
        # Remove tudo exceto elementos estáticos
        self.delete('dynamic')

        # Determinar quais notas mostrar
        notes_to_show = []
        if self.learn_mode and self.current_phrase:
            notes_to_show = self.current_phrase.notes
        elif self.track:
            notes_to_show = self.track.notes

        if not notes_to_show:
            return

        # Desenhar linhas de referência das notas
        drawn_midis = set()
        for note in notes_to_show:
            if note.midi_note not in drawn_midis:
                y = self.midi_to_y(note.midi_note)
                self.create_line(0, y, self.width, y,
                                 fill='#353535', width=1, tags='dynamic')
                # Nome da nota (sempre mostrar na lateral)
                self.create_text(20, y, text=note.note_name,
                                 fill='#666', font=('Arial', 9),
                                 anchor='w', tags='dynamic')
                drawn_midis.add(note.midi_note)

        # Desenhar notas
        for note in notes_to_show:
            # Verificar se a nota está visível
            start_x = self.time_to_x(note.start_time)
            end_x = self.time_to_x(note.start_time + note.duration)

            if end_x < -50 or start_x > self.width + 50:
                continue

            y = self.midi_to_y(note.midi_note)
            note_height = 30

            # Determinar cor baseado no estado da nota
            if note.is_passed(self.current_time):
                # Nota já passou - colorir baseado na precisão
                accuracy = note.get_accuracy()
                if accuracy >= 0.5:
                    color = '#2ecc71'  # Verde - acertou
                elif accuracy > 0:
                    color = '#f39c12'  # Laranja - acertou parcialmente
                else:
                    color = '#e74c3c'  # Vermelho - errou
                outline_color = color
            else:
                # Nota ainda não passou
                color = '#3498db'  # Azul
                outline_color = '#2980b9'

            # Desenhar retângulo "gordo" da nota
            self.create_rectangle(start_x, y - note_height / 2,
                                  end_x, y + note_height / 2,
                                  fill=color, outline=outline_color,
                                  width=2, tags='dynamic')

            # Texto da nota: mostrar LETRA se disponível, senão nome da nota
            display_text = note.get_display_text()

            # Determinar tamanho da fonte baseado no comprimento do texto
            text_length = len(display_text)
            note_width = end_x - start_x

            # Ajustar fonte dinamicamente
            if text_length <= 3 and note_width > 30:
                font_size = 11
                font_weight = 'bold'
            elif text_length <= 6 and note_width > 40:
                font_size = 10
                font_weight = 'bold'
            elif note_width > 50:
                font_size = 9
                font_weight = 'normal'
            else:
                font_size = 8
                font_weight = 'normal'

            # Só desenhar texto se houver espaço mínimo
            if note_width > 25:
                text_x = (start_x + end_x) / 2
                self.create_text(text_x, y, text=display_text,
                                 fill='white', font=('Arial', font_size, font_weight),
                                 tags='dynamic')

        # Desenhar indicador de pitch detectado
        if self.detected_midi is not None:
            y = self.midi_to_y(self.detected_midi)
            # Círculo na zona de acerto
            self.create_oval(self.hit_zone_x - 15, y - 15,
                             self.hit_zone_x + 15, y + 15,
                             fill='#ffd700', outline='#ffaa00',
                             width=3, tags='dynamic')

            # Linha horizontal mostrando o pitch
            self.create_line(self.hit_zone_x + 20, y,
                             self.hit_zone_x + 100, y,
                             fill='#ffd700', width=3,
                             arrow=tk.LAST, tags='dynamic')


class KaraokeGame:
    """Classe principal do jogo de karaokê"""

    def __init__(self, master, pitch_detector=None):
        self.master = master
        self.pitch_detector = pitch_detector  # Referência ao VocalRangeTest ou similar

        self.track = None
        self.is_playing = False
        self.start_time = None
        self.current_time = 0.0

        # Modo de aprendizado
        self.learn_mode = False
        self.current_phrase_index = 0
        self.phrase_state = 'waiting'  # 'playing', 'pause', 'recording', 'evaluating'
        self.synthesizer = AudioSynthesizer()

        self.setup_ui()

    def setup_ui(self):
        """Configura a interface do usuário"""
        # Frame principal
        main_frame = ttk.Frame(self.master)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame superior - controles
        control_frame = ttk.LabelFrame(main_frame, text="Controles", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # Botões de carregamento
        load_frame = ttk.Frame(control_frame)
        load_frame.pack(fill=tk.X)

        if MUSICXML_AVAILABLE:
            ttk.Button(load_frame, text="📁 Carregar MusicXML",
                       command=self.load_musicxml).pack(side=tk.LEFT, padx=5)

        ttk.Button(load_frame, text="🎵 Melodia de Teste",
                   command=self.load_test_melody).pack(side=tk.LEFT, padx=5)

        # Separador
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Frame de modo de jogo
        mode_frame = ttk.LabelFrame(control_frame, text="Modo de Jogo", padding=5)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_learn = ttk.Button(mode_frame, text="📚 Aprender",
                                    command=self.start_learn_mode, state='disabled')
        self.btn_learn.pack(side=tk.LEFT, padx=5)

        self.btn_play = ttk.Button(mode_frame, text="▶ Cantar",
                                   command=self.start_game, state='disabled')
        self.btn_play.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(mode_frame, text="⏹ Parar",
                                   command=self.stop_game, state='disabled')
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Info da música
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X, pady=(0, 0))

        ttk.Label(info_frame, text="Música:").pack(side=tk.LEFT)
        self.lbl_track = ttk.Label(info_frame, text="Nenhuma música carregada",
                                   font=('Arial', 10, 'bold'))
        self.lbl_track.pack(side=tk.LEFT, padx=10)

        # ===== NOVO: Controle de tempo =====
        time_control_frame = ttk.LabelFrame(control_frame, text="⏱️ Ajuste de Tempo", padding=5)
        time_control_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(time_control_frame, text="Duração atual:").pack(side=tk.LEFT, padx=5)
        self.lbl_current_duration = ttk.Label(time_control_frame, text="--:--",
                                              font=('Arial', 10, 'bold'),
                                              foreground='#3498db')
        self.lbl_current_duration.pack(side=tk.LEFT, padx=5)

        ttk.Label(time_control_frame, text="→ Ajustar para:").pack(side=tk.LEFT, padx=(20, 5))

        # Entry para minutos
        self.entry_minutes = ttk.Entry(time_control_frame, width=3, font=('Arial', 10))
        self.entry_minutes.pack(side=tk.LEFT)
        self.entry_minutes.insert(0, "0")

        ttk.Label(time_control_frame, text="min").pack(side=tk.LEFT, padx=2)

        # Entry para segundos
        self.entry_seconds = ttk.Entry(time_control_frame, width=3, font=('Arial', 10))
        self.entry_seconds.pack(side=tk.LEFT)
        self.entry_seconds.insert(0, "0")

        ttk.Label(time_control_frame, text="seg").pack(side=tk.LEFT, padx=2)

        # Botão aplicar
        self.btn_apply_time = ttk.Button(time_control_frame, text="✓ Aplicar",
                                         command=self.apply_time_adjustment,
                                         state='disabled')
        self.btn_apply_time.pack(side=tk.LEFT, padx=10)

        # Botão reset
        self.btn_reset_time = ttk.Button(time_control_frame, text="↺ Resetar",
                                         command=self.reset_time_adjustment,
                                         state='disabled')
        self.btn_reset_time.pack(side=tk.LEFT, padx=5)

        # Label de velocidade
        self.lbl_speed = ttk.Label(time_control_frame, text="",
                                   font=('Arial', 9),
                                   foreground='#7f8c8d')
        self.lbl_speed.pack(side=tk.LEFT, padx=10)

        # Visualizador
        viz_frame = ttk.LabelFrame(main_frame, text="Visualizador", padding=10)
        viz_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.visualizer = KaraokeVisualizer(viz_frame, width=900, height=400)
        self.visualizer.pack()

        # Frame de informações em tempo real
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding=10)
        status_frame.pack(fill=tk.X)

        # Modo de aprendizado - info da frase
        phrase_frame = ttk.Frame(status_frame)
        phrase_frame.pack(fill=tk.X, pady=5)

        self.lbl_phrase_info = ttk.Label(phrase_frame, text="",
                                         font=('Arial', 11, 'bold'),
                                         foreground='#3498db')
        self.lbl_phrase_info.pack(side=tk.LEFT)

        # Status do modo
        self.lbl_mode_status = ttk.Label(phrase_frame, text="",
                                         font=('Arial', 10),
                                         foreground='#e74c3c')
        self.lbl_mode_status.pack(side=tk.LEFT, padx=20)

        # Tempo
        time_frame = ttk.Frame(status_frame)
        time_frame.pack(fill=tk.X, pady=5)

        ttk.Label(time_frame, text="Tempo:").pack(side=tk.LEFT)
        self.lbl_time = ttk.Label(time_frame, text="0:00 / 0:00",
                                  font=('Arial', 12, 'bold'))
        self.lbl_time.pack(side=tk.LEFT, padx=10)

        # Barra de progresso
        self.progress = ttk.Progressbar(time_frame, length=300, mode='determinate')
        self.progress.pack(side=tk.LEFT, padx=10)

        # Precisão
        accuracy_frame = ttk.Frame(status_frame)
        accuracy_frame.pack(fill=tk.X, pady=5)

        ttk.Label(accuracy_frame, text="Precisão:").pack(side=tk.LEFT)
        self.lbl_accuracy = ttk.Label(accuracy_frame, text="0%",
                                      font=('Arial', 16, 'bold'),
                                      foreground='#3498db')
        self.lbl_accuracy.pack(side=tk.LEFT, padx=10)

        ttk.Label(accuracy_frame, text="Nota Detectada:").pack(side=tk.LEFT, padx=(20, 0))
        self.lbl_detected = ttk.Label(accuracy_frame, text="--",
                                      font=('Arial', 12, 'bold'))
        self.lbl_detected.pack(side=tk.LEFT, padx=10)

    def apply_time_adjustment(self):
        """Aplica o ajuste de tempo definido pelo usuário"""
        if not self.track:
            return

        try:
            minutes = int(self.entry_minutes.get())
            seconds = int(self.entry_seconds.get())
            target_duration = minutes * 60 + seconds

            if target_duration <= 0:
                messagebox.showwarning("Aviso", "Digite uma duração válida (maior que 0).")
                return

            # Aplicar ajuste
            self.track.set_target_duration(target_duration)

            # Atualizar UI
            self.update_duration_display()

            # Mostrar informação
            speed_percent = (self.track.time_scale * 100)
            if self.track.time_scale < 1.0:
                speed_text = f"⚡ {speed_percent:.1f}% (mais rápido)"
            elif self.track.time_scale > 1.0:
                speed_text = f"🐌 {speed_percent:.1f}% (mais lento)"
            else:
                speed_text = "✓ Velocidade original"

            self.lbl_speed.config(text=speed_text)

            messagebox.showinfo("Sucesso",
                                f"Tempo ajustado!\n"
                                f"Nova duração: {self.format_time(self.track.duration)}\n"
                                f"Velocidade: {speed_percent:.1f}%")

        except ValueError:
            messagebox.showerror("Erro", "Digite valores numéricos válidos para minutos e segundos.")

    def reset_time_adjustment(self):
        """Reseta o ajuste de tempo para o original"""
        if not self.track:
            return

        self.track.apply_time_scale(1.0)
        self.update_duration_display()
        self.lbl_speed.config(text="")

        messagebox.showinfo("Resetado", "Tempo restaurado para o original.")

    def update_duration_display(self):
        """Atualiza a exibição da duração atual"""
        if self.track:
            duration_str = self.format_time(self.track.duration)
            self.lbl_current_duration.config(text=duration_str)

            # Sugerir valores nos campos de entrada
            minutes = int(self.track.duration // 60)
            seconds = int(self.track.duration % 60)

            # Não sobrescrever se o usuário já digitou algo diferente de "0"
            if self.entry_minutes.get() == "0":
                self.entry_minutes.delete(0, tk.END)
                self.entry_minutes.insert(0, str(minutes))
            if self.entry_seconds.get() == "0":
                self.entry_seconds.delete(0, tk.END)
                self.entry_seconds.insert(0, str(seconds))

    def load_musicxml(self):
        """Carrega um arquivo MusicXML"""
        if not MUSICXML_AVAILABLE:
            messagebox.showerror("Erro", "music21 não está instalado.\n"
                                         "Instale com: pip install music21")
            return

        filename = filedialog.askopenfilename(
            title="Selecionar arquivo MusicXML",
            filetypes=[("MusicXML", "*.xml *.musicxml *.mxl"), ("Todos", "*.*")]
        )

        if not filename:
            return

        try:
            score = music21.converter.parse(filename)
            parts = score.parts

            if len(parts) == 0:
                messagebox.showerror("Erro", "Nenhuma parte encontrada no arquivo.")
                return

            # Se houver múltiplas partes, perguntar qual usar
            if len(parts) > 1:
                self.select_part_dialog(parts)
            else:
                track = KaraokeTrack.from_musicxml(parts[0], "Parte 1")
                self.set_track(track)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar arquivo:\n{str(e)}")

    def select_part_dialog(self, parts):
        """Diálogo para selecionar qual parte cantar"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Selecionar Faixa")
        dialog.geometry("400x300")
        dialog.transient(self.master)
        dialog.grab_set()

        ttk.Label(dialog, text="Selecione qual faixa você deseja cantar:",
                  font=('Arial', 11, 'bold')).pack(pady=10)

        listbox = tk.Listbox(dialog, font=('Arial', 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for i, part in enumerate(parts):
            part_name = part.partName if part.partName else f"Parte {i + 1}"
            instrument = part.getInstrument().instrumentName if part.getInstrument() else "?"
            notes_count = len([n for n in part.flatten().notes if n.isNote])
            listbox.insert(tk.END, f"{part_name} - {instrument} ({notes_count} notas)")

        listbox.selection_set(0)

        def on_select():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                part = parts[idx]
                part_name = part.partName if part.partName else f"Parte {idx + 1}"
                track = KaraokeTrack.from_musicxml(part, part_name)
                self.set_track(track)
                dialog.destroy()

        ttk.Button(dialog, text="Selecionar", command=on_select).pack(pady=10)

    def load_test_melody(self):
        """Carrega melodia de teste"""
        track = KaraokeTrack.create_test_melody()
        self.set_track(track)

    def set_track(self, track):
        """Define a faixa a ser tocada"""
        self.track = track
        self.visualizer.set_track(track)
        self.lbl_track.config(text=track.name)
        self.btn_play.config(state='normal')
        self.btn_learn.config(state='normal')

        # Habilitar controles de tempo
        self.btn_apply_time.config(state='normal')
        self.btn_reset_time.config(state='normal')
        self.update_duration_display()

        phrases_info = f"{len(track.phrases)} frases" if track.phrases else "nenhuma frase"

        # Verificar se tem letras
        has_lyrics = any(note.lyric for note in track.notes)
        lyrics_info = "✓ Com letras" if has_lyrics else "Sem letras"

        messagebox.showinfo("Sucesso",
                            f"Música carregada: {track.name}\n"
                            f"Duração detectada: {self.format_time(track.duration)}\n"
                            f"Notas: {len(track.notes)}\n"
                            f"Frases para aprender: {phrases_info}\n"
                            f"{lyrics_info}\n\n"
                            f"💡 Dica: Use 'Ajuste de Tempo' se a duração\n"
                            f"   estiver diferente da música real!")

    def start_learn_mode(self):
        """Inicia o modo de aprendizado"""
        if not self.track or not self.track.phrases:
            messagebox.showwarning("Aviso", "Nenhuma frase disponível para aprender.")
            return

        self.learn_mode = True
        self.is_playing = True
        self.current_phrase_index = 0
        self.phrase_state = 'waiting'

        self.visualizer.learn_mode = True

        self.btn_play.config(state='disabled')
        self.btn_learn.config(state='disabled')
        self.btn_stop.config(state='normal')

        # Iniciar loop de aprendizado
        threading.Thread(target=self.learn_loop, daemon=True).start()

    def learn_loop(self):
        """Loop principal do modo de aprendizado"""
        while self.is_playing and self.learn_mode:
            if self.current_phrase_index >= len(self.track.phrases):
                # Completou todas as frases!
                self.master.after(0, lambda: messagebox.showinfo(
                    "Parabéns!",
                    "Você completou todas as frases da música!\n"
                    "Agora tente cantar a música completa no modo 'Cantar'."
                ))
                self.master.after(0, self.stop_game)
                break

            phrase = self.track.phrases[self.current_phrase_index]
            self.visualizer.set_learn_phrase(phrase)

            # Atualizar UI
            phrase_notes = phrase.get_note_names()
            self.master.after(0, lambda: self.lbl_phrase_info.config(
                text=f"Frase {phrase.phrase_number}/{len(self.track.phrases)}: {phrase_notes}"
            ))

            # Fase 1: Tocar a frase
            self.phrase_state = 'playing'
            self.master.after(0, lambda: self.lbl_mode_status.config(
                text="🔊 Ouça atentamente...", foreground='#3498db'
            ))

            self.play_phrase_with_visual(phrase)

            # Fase 2: Pausa de 2 segundos
            self.phrase_state = 'pause'
            for i in range(2, 0, -1):
                if not self.is_playing:
                    return
                self.master.after(0, lambda cnt=i: self.lbl_mode_status.config(
                    text=f"⏳ Prepare-se... {cnt}", foreground='#f39c12'
                ))
                time.sleep(1)

            # Fase 3: Gravar o usuário
            self.phrase_state = 'recording'
            self.master.after(0, lambda: self.lbl_mode_status.config(
                text="🎤 CANTE AGORA!", foreground='#e74c3c'
            ))

            # Resetar notas da frase
            for note in phrase.notes:
                note.hit_time = 0.0
                note.total_checked_time = 0.0

            # Gravar por um tempo baseado na duração da frase + margem
            record_duration = phrase.duration + 1.0
            self.record_phrase(phrase, record_duration)

            # Fase 4: Avaliar
            self.phrase_state = 'evaluating'
            accuracy = self.evaluate_phrase(phrase)

            self.master.after(0, lambda acc=accuracy: self.lbl_accuracy.config(
                text=f"{acc:.1f}%"
            ))

            # Decidir se passa ou repete
            if accuracy >= 80.0:
                self.master.after(0, lambda: messagebox.showinfo(
                    "Muito bem!",
                    f"Você acertou {accuracy:.1f}% da frase!\n"
                    "Passando para a próxima..."
                ))
                self.current_phrase_index += 1
            else:
                self.master.after(0, lambda: messagebox.showwarning(
                    "Tente novamente",
                    f"Você acertou {accuracy:.1f}% da frase.\n"
                    "Precisa de pelo menos 80% para prosseguir.\n"
                    "Vamos tentar de novo!"
                ))

            time.sleep(0.5)

    def play_phrase_with_visual(self, phrase):
        """Toca a frase com visualização sincronizada"""
        # Iniciar thread de áudio
        audio_thread = threading.Thread(
            target=lambda: self.synthesizer.play_phrase(phrase.notes),
            daemon=True
        )
        audio_thread.start()

        # Simular tempo passando para visualização
        self.start_time = time.time()
        phrase_start = phrase.notes[0].start_time

        while audio_thread.is_alive():
            elapsed = time.time() - self.start_time
            self.current_time = phrase_start + elapsed
            self.visualizer.update_time(self.current_time)
            time.sleep(0.033)

        audio_thread.join()

    def record_phrase(self, phrase, duration):
        """Grava e avalia o usuário cantando a frase"""
        sr = 44100
        chunk = 2048
        gate_enabled = True
        gate_th = 0.01

        self.start_time = time.time()
        phrase_start = phrase.notes[0].start_time

        stream = sd.InputStream(samplerate=sr, channels=1, blocksize=chunk, dtype="float32")
        stream.start()

        try:
            end_time = time.time() + duration

            while time.time() < end_time and self.is_playing:
                elapsed = time.time() - self.start_time
                self.current_time = phrase_start + elapsed
                self.visualizer.update_time(self.current_time)

                audio_chunk, _ = stream.read(chunk)
                audio_chunk = audio_chunk.flatten()

                rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64))))) if len(audio_chunk) else 0.0

                if gate_enabled and rms < gate_th:
                    time.sleep(0.05)
                    continue

                # Detectar pitch
                if self.pitch_detector and hasattr(self.pitch_detector, 'detect_pitch'):
                    detected_freq = self.pitch_detector.detect_pitch(audio_chunk)
                else:
                    detected_freq = self.detect_pitch_simple(audio_chunk, sr)

                if not detected_freq or detected_freq < 70 or detected_freq > 1200:
                    time.sleep(0.05)
                    continue

                detected_midi = 69.0 + 12.0 * np.log2(detected_freq / 440.0)
                self.visualizer.update_detected_pitch(detected_midi)

                # Verificar notas da frase
                self.check_phrase_notes(phrase, detected_midi, elapsed)

                time.sleep(0.05)
        finally:
            stream.stop()
            stream.close()

    def check_phrase_notes(self, phrase, detected_midi, elapsed_time):
        """Verifica se o usuário acertou as notas da frase"""
        tolerance_semitones = 0.5

        for note in phrase.notes:
            # Calcular tempo relativo da nota dentro da frase
            note_relative_start = note.start_time - phrase.notes[0].start_time
            note_relative_end = note_relative_start + note.duration

            if note_relative_start <= elapsed_time <= note_relative_end:
                note.total_checked_time += 0.05

                midi_diff = abs(detected_midi - note.midi_note)
                if midi_diff <= tolerance_semitones:
                    note.hit_time += 0.05

    def evaluate_phrase(self, phrase):
        """Avalia a precisão do usuário na frase"""
        if not phrase.notes:
            return 0.0

        total_notes = len(phrase.notes)
        successful_notes = sum(1 for n in phrase.notes if n.get_accuracy() >= 0.5)

        return (successful_notes / total_notes) * 100

    def start_game(self):
        """Inicia o jogo (modo cantar)"""
        if not self.track:
            return

        self.learn_mode = False
        self.is_playing = True
        self.start_time = time.time()
        self.current_time = 0.0

        self.visualizer.learn_mode = False

        # Resetar estado das notas
        for note in self.track.notes:
            note.hit_time = 0.0
            note.total_checked_time = 0.0

        self.btn_play.config(state='disabled')
        self.btn_learn.config(state='disabled')
        self.btn_stop.config(state='normal')

        # Limpar labels do modo aprendizado
        self.lbl_phrase_info.config(text="")
        self.lbl_mode_status.config(text="")

        # Iniciar threads
        threading.Thread(target=self.game_loop, daemon=True).start()
        threading.Thread(target=self.audio_loop, daemon=True).start()

    def stop_game(self):
        """Para o jogo"""
        self.is_playing = False
        self.learn_mode = False

        self.btn_play.config(state='normal')
        self.btn_learn.config(state='normal')
        self.btn_stop.config(state='disabled')

        # Mostrar resultado final (apenas no modo cantar)
        if not self.learn_mode and self.track:
            self.show_final_score()

    def game_loop(self):
        """Loop principal do jogo (modo cantar)"""
        while self.is_playing and not self.learn_mode:
            self.current_time = time.time() - self.start_time

            # Atualizar visualizador
            self.visualizer.update_time(self.current_time)

            # Atualizar UI
            self.update_status_ui()

            # Verificar se a música acabou
            if self.current_time >= self.track.duration + 2.0:
                self.master.after(0, self.stop_game)
                break

            time.sleep(0.033)  # ~30 FPS

    def audio_loop(self):
        """Loop de captura de áudio (modo cantar)"""
        # Se tem detector customizado, usar suas configs
        if self.pitch_detector:
            sr = getattr(self.pitch_detector, "sample_rate", 44100)
            chunk = getattr(self.pitch_detector, "chunk_size", 2048)
            gate_enabled = getattr(self.pitch_detector, "NOISE_GATE_ENABLED", True)
            gate_th = getattr(self.pitch_detector, "NOISE_GATE_THRESHOLD", 0.01)
        else:
            # Configs padrão
            sr = 44100
            chunk = 2048
            gate_enabled = True
            gate_th = 0.01

        stream = sd.InputStream(samplerate=sr, channels=1, blocksize=chunk, dtype="float32")
        stream.start()

        try:
            while self.is_playing and not self.learn_mode:
                audio_chunk, _ = stream.read(chunk)
                audio_chunk = audio_chunk.flatten()

                rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64))))) if len(audio_chunk) else 0.0

                # Gate de ruído
                if gate_enabled and rms < gate_th:
                    time.sleep(0.05)
                    continue

                # Usar detector customizado OU fallback interno
                if self.pitch_detector and hasattr(self.pitch_detector, 'detect_pitch'):
                    detected_freq = self.pitch_detector.detect_pitch(audio_chunk)
                else:
                    detected_freq = self.detect_pitch_simple(audio_chunk, sr)

                # Validar frequência
                if not detected_freq or detected_freq < 70 or detected_freq > 1200:
                    time.sleep(0.05)
                    continue

                # Converter Hz -> MIDI
                detected_midi = 69.0 + 12.0 * np.log2(detected_freq / 440.0)

                self.visualizer.update_detected_pitch(detected_midi)
                self.check_notes(detected_midi)

                time.sleep(0.05)
        finally:
            stream.stop()
            stream.close()

    def detect_pitch_simple(self, audio_chunk, sample_rate):
        """Detecção simples de pitch - VOCÊ DEVE SUBSTITUIR PELO SEU MÉTODO"""
        if self.pitch_detector and hasattr(self.pitch_detector, 'detect_pitch'):
            return self.pitch_detector.detect_pitch(audio_chunk)

        # Implementação simples usando autocorrelação
        correlation = np.correlate(audio_chunk, audio_chunk, mode='full')
        correlation = correlation[len(correlation) // 2:]

        # Encontrar pico
        diff = np.diff(correlation)
        start = np.where(diff > 0)[0]
        if len(start) == 0:
            return None
        start = start[0]
        peak = np.argmax(correlation[start:]) + start

        if peak == 0:
            return None

        return sample_rate / peak

    def check_notes(self, detected_midi):
        """Verifica se o usuário acertou as notas atuais (modo cantar)"""
        tolerance_semitones = 0.5  # 50 cents

        for note in self.track.notes:
            # Verificar se a nota está ativa no momento
            if (note.start_time <= self.current_time <=
                    note.start_time + note.duration):

                note.total_checked_time += 0.05  # Incremento de tempo verificado

                # Verificar se o pitch está correto
                midi_diff = abs(detected_midi - note.midi_note)
                if midi_diff <= tolerance_semitones:
                    note.hit_time += 0.05

    def update_status_ui(self):
        """Atualiza a UI de status"""
        # Tempo
        current_str = self.format_time(self.current_time)
        total_str = self.format_time(self.track.duration)
        self.lbl_time.config(text=f"{current_str} / {total_str}")

        # Progresso
        progress = min(100, (self.current_time / self.track.duration) * 100)
        self.progress['value'] = progress

        # Calcular precisão geral
        accuracy = self.calculate_accuracy()
        self.lbl_accuracy.config(text=f"{accuracy:.1f}%")

        # Cor da precisão
        if accuracy >= 80:
            color = '#27ae60'
        elif accuracy >= 50:
            color = '#f39c12'
        else:
            color = '#e74c3c'
        self.lbl_accuracy.config(foreground=color)

    def calculate_accuracy(self):
        """Calcula a precisão geral"""
        if not self.track or not self.track.notes:
            return 0.0

        total_notes = 0
        successful_notes = 0

        for note in self.track.notes:
            if note.is_passed(self.current_time):
                total_notes += 1
                if note.get_accuracy() >= 0.5:  # 50% do tempo correto
                    successful_notes += 1

        if total_notes == 0:
            return 0.0

        return (successful_notes / total_notes) * 100

    def format_time(self, seconds):
        """Formata tempo em MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def show_final_score(self):
        """Mostra a pontuação final"""
        accuracy = self.calculate_accuracy()

        # Determinar classificação
        if accuracy >= 90:
            rating = "⭐⭐⭐ PERFEITO!"
            color = '#27ae60'
        elif accuracy >= 75:
            rating = "⭐⭐ MUITO BOM!"
            color = '#2ecc71'
        elif accuracy >= 50:
            rating = "⭐ BOM!"
            color = '#f39c12'
        else:
            rating = "Continue praticando!"
            color = '#e74c3c'

        # Estatísticas detalhadas
        total_notes = len(self.track.notes)
        perfect_notes = sum(1 for n in self.track.notes if n.get_accuracy() >= 0.9)
        good_notes = sum(1 for n in self.track.notes if 0.5 <= n.get_accuracy() < 0.9)
        missed_notes = sum(1 for n in self.track.notes if n.get_accuracy() < 0.5)

        message = (
            f"{rating}\n\n"
            f"Precisão Geral: {accuracy:.1f}%\n\n"
            f"Estatísticas:\n"
            f"  Notas Perfeitas (>90%): {perfect_notes}\n"
            f"  Notas Boas (50-90%): {good_notes}\n"
            f"  Notas Perdidas (<50%): {missed_notes}\n"
            f"  Total: {total_notes}"
        )

        messagebox.showinfo("Resultado Final", message)


def main():
    """Função principal para executar o jogo standalone"""
    root = tk.Tk()
    root.title("🎤 Jogo de Karaokê / Canto")
    root.geometry("1000x800")

    # Criar jogo
    game = KaraokeGame(root)

    # Instruções
    instructions = (
        "📋 INSTRUÇÕES:\n\n"
        "🎵 MODO CANTAR:\n"
        "- Cante a música completa seguindo as notas\n"
        "- As notas mostram as LETRAS da música (se disponível)\n"
        "- Verde = acertou, Laranja = parcial, Vermelho = errou\n\n"
        "📚 MODO APRENDER:\n"
        "- A música é dividida em frases pequenas\n"
        "- O sistema toca a frase no seu fone\n"
        "- Após 2 segundos, você deve repetir\n"
        "- Precisa de 80% de precisão para passar\n"
        "- Se errar, repete até acertar\n\n"
        "🎮 Carregue uma música e divirta-se!"
    )

    if not MUSICXML_AVAILABLE:
        instructions += "\n\n⚠️ Instale music21 para carregar arquivos MusicXML:\npip install music21"

    messagebox.showinfo("Bem-vindo!", instructions)

    root.mainloop()


if __name__ == "__main__":
    main()
