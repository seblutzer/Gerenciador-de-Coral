"""
Jogo de Karaokê - Sistema de canto com avaliação de precisão
Integra com sistema Coral existente para detecção de pitch
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import threading
from collections import deque
import numpy as np
import librosa
import sounddevice as sd
from typing import List, Dict, Optional, Tuple
import xml.etree.ElementTree as ET


class MusicNote:
    """Representa uma nota musical no karaoke"""

    def __init__(self, pitch: str, midi: int, duration: float,
                 start_time: float, lyric: str = ""):
        self.pitch = pitch  # Ex: "C4", "D#5"
        self.midi = midi
        self.duration = duration  # em segundos
        self.start_time = start_time  # em segundos
        self.lyric = lyric
        self.end_time = start_time + duration

        # Avaliação
        self.achieved = False
        self.time_correct = 0.0  # Tempo total cantado corretamente (em segundos)
        self.was_evaluated = False  # Se já foi avaliada ao terminar
        self.score = 0.0  # Pontuação final (0 a 1)
        self.rating = ""  # "Perfeito!", "Ótimo", "Bom", "Errou"


class MusicXMLParser:
    """Parser para arquivos MusicXML"""

    @staticmethod
    def parse(filepath: str) -> Tuple[List[MusicNote], float, List[List[MusicNote]]]:
        """
        Parseia arquivo MusicXML e retorna notas, duração total e partes/vozes
        Returns: (todas_notas, duracao_total, lista_de_vozes)
        """
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Encontrar todas as partes (vozes)
        parts = root.findall('.//part')
        all_voices = []
        max_duration = 0.0

        # Tempo padrão (pode ser lido do XML)
        divisions = 1
        tempo = 120  # BPM padrão

        for part in parts:
            voice_notes = []
            current_time = 0.0

            # Tentar encontrar divisions e tempo
            for measure in part.findall('.//measure'):
                attributes = measure.find('.//attributes')
                if attributes is not None:
                    div = attributes.find('.//divisions')
                    if div is not None:
                        divisions = int(div.text)

                direction = measure.find('.//direction')
                if direction is not None:
                    sound = direction.find('.//sound')
                    if sound is not None and 'tempo' in sound.attrib:
                        tempo = float(sound.attrib['tempo'])

                # Processar notas
                for note in measure.findall('.//note'):
                    # Verificar se é pausa
                    if note.find('.//rest') is not None:
                        duration_elem = note.find('.//duration')
                        if duration_elem is not None:
                            duration_divisions = int(duration_elem.text)
                            duration_seconds = (duration_divisions / divisions) * (60.0 / tempo)
                            current_time += duration_seconds
                        continue

                    # Extrair pitch
                    pitch_elem = note.find('.//pitch')
                    if pitch_elem is None:
                        continue

                    step = pitch_elem.find('.//step').text
                    octave = int(pitch_elem.find('.//octave').text)
                    alter_elem = pitch_elem.find('.//alter')
                    alter = int(alter_elem.text) if alter_elem is not None else 0

                    # Construir nome da nota
                    pitch_name = step
                    if alter == 1:
                        pitch_name += "#"
                    elif alter == -1:
                        pitch_name += "b"
                    pitch_name += str(octave)

                    # Calcular MIDI
                    note_values = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
                    midi = (octave + 1) * 12 + note_values[step] + alter

                    # Duração
                    duration_elem = note.find('.//duration')
                    duration_divisions = int(duration_elem.text) if duration_elem is not None else divisions
                    duration_seconds = (duration_divisions / divisions) * (60.0 / tempo)

                    # Letra
                    lyric_elem = note.find('.//lyric/text')
                    lyric = lyric_elem.text if lyric_elem is not None else ""

                    # Criar nota
                    music_note = MusicNote(pitch_name, midi, duration_seconds,
                                           current_time, lyric)
                    voice_notes.append(music_note)

                    # Avançar tempo se não for acorde
                    if note.find('.//chord') is None:
                        current_time += duration_seconds

            if voice_notes:
                all_voices.append(voice_notes)
                max_duration = max(max_duration, voice_notes[-1].end_time)

        # Retornar todas as notas combinadas, duração e vozes separadas
        all_notes = []
        for voice in all_voices:
            all_notes.extend(voice)
        all_notes.sort(key=lambda n: n.start_time)

        return all_notes, max_duration, all_voices


class NoteScrollCanvas(tk.Canvas):
    """Canvas com rolagem de notas estilo karaokê"""

    def __init__(self, master, width=800, height=300, **kwargs):
        super().__init__(master, width=width, height=height,
                         bg='#1a1a2e', highlightthickness=0, **kwargs)
        self.width = width
        self.height = height

        # Configurações visuais
        self.note_height = 20
        self.pixels_per_second = 100  # Quantos pixels = 1 segundo
        self.current_time = 0.0
        self.window_time = 8.0  # Mostrar 8 segundos à frente

        # MIDI range para escala vertical
        self.min_midi = 48  # C3
        self.max_midi = 84  # C6

        self.notes: List[MusicNote] = []
        self.current_pitch_midi: Optional[int] = None

        # Linha vertical onde as notas devem ser cantadas
        self.hit_line_x = 150

        self.draw()

    def set_notes(self, notes: List[MusicNote]):
        """Define as notas a serem exibidas"""
        self.notes = notes
        if notes:
            # Ajustar range MIDI baseado nas notas
            midis = [n.midi for n in notes]
            self.min_midi = min(midis) - 2
            self.max_midi = max(midis) + 2

    def update_time(self, current_time: float):
        """Atualiza o tempo atual e redesenha"""
        self.current_time = current_time
        self.draw()

    def update_pitch(self, midi: Optional[int]):
        """Atualiza o pitch atual cantado"""
        self.current_pitch_midi = midi
        self.draw()

    def _midi_to_y(self, midi: int) -> float:
        """Converte MIDI para posição Y no canvas"""
        span = max(1, self.max_midi - self.min_midi)
        normalized = (midi - self.min_midi) / span
        # Inverter para que notas mais altas fiquem no topo
        return self.height * (1 - normalized) * 0.8 + self.height * 0.1

    def _time_to_x(self, time: float) -> float:
        """Converte tempo para posição X no canvas"""
        # Notas aparecem à direita e movem para esquerda
        relative_time = time - self.current_time
        return self.hit_line_x + (relative_time * self.pixels_per_second)

    def draw(self):
        """Desenha o canvas completo"""
        self.delete("all")

        # Fundo
        self.create_rectangle(0, 0, self.width, self.height,
                              fill='#1a1a2e', outline='')

        # Linha de referência (onde cantar)
        self.create_line(self.hit_line_x, 0, self.hit_line_x, self.height,
                         fill='#00ff00', width=3, dash=(5, 5))

        # Desenhar grade de notas (linhas horizontais)
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        for midi in range(self.min_midi, self.max_midi + 1):
            y = self._midi_to_y(midi)
            # Linhas mais visíveis para notas naturais (sem #)
            note_name = note_names[midi % 12]
            if '#' not in note_name:
                self.create_line(0, y, self.width, y, fill='#2a2a3e', width=1)

            # Nome da nota no lado esquerdo
            octave = (midi // 12) - 1
            self.create_text(10, y, text=f"{note_name}{octave}",
                             fill='#888', anchor='w', font=('Arial', 8))

        # Desenhar notas da música
        time_end = self.current_time + self.window_time
        for note in self.notes:
            # Só desenhar notas visíveis
            if note.end_time < self.current_time - 2.0 or note.start_time > time_end:
                continue

            x_start = self._time_to_x(note.start_time)
            x_end = self._time_to_x(note.end_time)
            y = self._midi_to_y(note.midi)

            # Cor baseada no estado
            if note.was_evaluated:
                # Nota já avaliada - mostrar cor baseada no rating
                if note.rating == "Perfeito!":
                    color = '#FFD700'  # Dourado
                elif note.rating == "Ótimo":
                    color = '#27ae60'  # Verde
                elif note.rating == "Bom":
                    color = '#3498db'  # Azul
                else:
                    color = '#e74c3c'  # Vermelho (errou)
            elif note.end_time < self.current_time:
                color = '#e74c3c'  # Vermelho se passou e não foi avaliada
            else:
                color = '#9b59b6'  # Roxo se ainda não chegou

            # Desenhar "nota gorda"
            note_h = self.note_height
            self.create_rectangle(x_start, y - note_h / 2, x_end, y + note_h / 2,
                                  fill=color, outline='white', width=2)

            # Texto (letra ou nome da nota)
            text = note.lyric if note.lyric else note.pitch
            text_x = (x_start + x_end) / 2
            self.create_text(text_x, y, text=text, fill='white',
                             font=('Arial', 10, 'bold'))

            # NOVO: Mostrar ícone de feedback após a nota
            if note.was_evaluated and note.end_time < self.current_time:
                icon_x = x_end + 30
                icon_y = y

                # Desenhar ícone baseado no rating
                if note.rating == "Perfeito!":
                    # Estrela dourada
                    self.create_text(icon_x, icon_y, text="⭐",
                                     font=('Arial', 20), fill='#FFD700')
                elif note.rating == "Ótimo":
                    # Check verde
                    self.create_text(icon_x, icon_y, text="✓",
                                     font=('Arial', 24, 'bold'), fill='#27ae60')
                elif note.rating == "Bom":
                    # Thumbs up
                    self.create_text(icon_x, icon_y, text="👍",
                                     font=('Arial', 18), fill='#3498db')
                else:
                    # X vermelho
                    self.create_text(icon_x, icon_y, text="✗",
                                     font=('Arial', 24, 'bold'), fill='#e74c3c')

        # Desenhar pitch atual (linha horizontal do usuário)
        if self.current_pitch_midi is not None:
            y_user = self._midi_to_y(self.current_pitch_midi)
            # Barra horizontal vermelha mostrando onde está cantando
            self.create_rectangle(self.hit_line_x - 30, y_user - 3,
                                  self.hit_line_x + 30, y_user + 3,
                                  fill='#ff0000', outline='#ffffff', width=1)


class AudioDetector:
    """Sistema de detecção de áudio em tempo real"""

    def __init__(self, sample_rate=22050, chunk_size=2048, tolerance_cents=50):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.tolerance_cents = tolerance_cents

        self.is_listening = False
        self.current_freq = None
        # CORREÇÃO: Buffer menor para reduzir latência (de 10 para 3)
        self.frequency_buffer = deque(maxlen=3)

        self.stream = None
        self.listener_thread = None

        # NOVO: Lock para thread-safety
        self.freq_lock = threading.Lock()

    def start_listening(self):
        """Inicia captura de áudio"""
        if self.is_listening:
            return

        self.is_listening = True
        self.listener_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.listener_thread.start()

    def stop_listening(self):
        """Para captura de áudio"""
        self.is_listening = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _audio_loop(self):
        """Loop de captura de áudio"""
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.chunk_size
        )
        self.stream.start()

        try:
            while self.is_listening:
                audio_chunk, _ = self.stream.read(self.chunk_size)
                audio_chunk = audio_chunk.flatten()

                if len(audio_chunk) > 0:
                    rms = float(np.sqrt(np.mean(np.square(audio_chunk.astype(np.float64)))))

                    # CORREÇÃO: Threshold mais baixo para captar melhor
                    if rms > 0.005:  # Era 0.01
                        detected_freq = self._detect_pitch(audio_chunk)

                        if detected_freq and detected_freq > 0:
                            with self.freq_lock:
                                self.current_freq = detected_freq
                                self.frequency_buffer.append(detected_freq)
                    else:
                        with self.freq_lock:
                            self.current_freq = None

                # CORREÇÃO: Reduzir sleep para captura mais frequente
                time.sleep(0.02)  # Era 0.05
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()

    def _detect_pitch(self, audio_chunk):
        """Detecta pitch do chunk de áudio"""
        try:
            # Autocorrelação para detecção de pitch
            pitches, magnitudes = librosa.piptrack(
                y=audio_chunk,
                sr=self.sample_rate,
                hop_length=self.chunk_size // 4,
                fmin=80,
                fmax=1000
            )

            # Pegar o pitch mais forte
            pitch = pitches[:, 0]
            magnitude = magnitudes[:, 0]

            if len(magnitude) > 0:
                max_idx = magnitude.argmax()
                detected_freq = pitch[max_idx]

                if detected_freq > 0:
                    return detected_freq
        except Exception as e:
            pass

        return None

    def get_average_freq(self):
        """Retorna frequência média do buffer"""
        with self.freq_lock:
            if len(self.frequency_buffer) > 0:
                return np.mean(list(self.frequency_buffer))
        return None

    def get_current_midi(self):
        """Retorna nota MIDI atual"""
        freq = self.get_average_freq()
        if freq:
            try:
                return int(round(librosa.hz_to_midi(freq)))
            except:
                pass
        return None

    @staticmethod
    def frequency_to_cents(freq1, freq2):
        """Calcula diferença em cents entre duas frequências"""
        if freq1 <= 0 or freq2 <= 0:
            return 0
        return 1200 * np.log2(freq1 / freq2)

class KaraokeGameMode:
    """Modo Jogo - canta a música completa e recebe pontuação"""

    def __init__(self, notes: List[MusicNote], audio_detector: AudioDetector,
                 canvas: NoteScrollCanvas, score_callback, time_scale: float = 1.0):
        self.notes = notes
        self.audio_detector = audio_detector
        self.canvas = canvas
        self.score_callback = score_callback
        self.time_scale = time_scale

        self.is_playing = False
        self.start_real_time = 0.0
        self.current_note_index = 0

        # Estatísticas
        self.total_notes = len(notes)
        self.notes_perfect = 0
        self.notes_great = 0
        self.notes_good = 0
        self.notes_missed = 0
        self.total_score = 0.0

        # Thread de jogo
        self.game_thread = None

        # CORREÇÃO: Intervalo menor para verificação mais precisa
        self.check_interval = 0.02  # Era 0.05 (50ms), agora 20ms

        # NOVO: Rastreamento de tempo anterior para cálculo preciso
        self.last_check_time = 0.0

    def start(self):
        """Inicia o modo jogo"""
        self.is_playing = True
        self.start_real_time = time.time()
        self.current_note_index = 0
        self.last_check_time = 0.0

        # Aplicar escala de tempo
        for note in self.notes:
            note.start_time *= self.time_scale
            note.duration *= self.time_scale
            note.end_time = note.start_time + note.duration

        self.canvas.set_notes(self.notes)
        self.audio_detector.start_listening()

        # Thread de detecção
        self.game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_thread.start()

    def stop(self):
        """Para o jogo"""
        self.is_playing = False
        self.audio_detector.stop_listening()

    def _game_loop(self):
        """Loop principal do jogo - CORRIGIDO"""
        self.last_check_time = time.time()

        while self.is_playing:
            current_time = time.time() - self.start_real_time

            # CORREÇÃO: Calcular delta time real
            now = time.time()
            delta_time = now - self.last_check_time
            self.last_check_time = now

            # Atualizar canvas
            self.canvas.update_time(current_time)

            # Atualizar pitch visual
            current_midi = self.audio_detector.get_current_midi()
            if current_midi:
                self.canvas.update_pitch(current_midi)

            # Verificar e avaliar notas
            for note in self.notes:
                # Nota ativa - verificar se está cantando corretamente
                if note.start_time <= current_time <= note.end_time and not note.was_evaluated:
                    # CORREÇÃO: Passar delta_time real em vez de intervalo fixo
                    self._check_note_singing(note, current_time, delta_time)

                # Nota terminou - avaliar resultado final
                elif current_time > note.end_time and not note.was_evaluated:
                    self._finalize_note_evaluation(note)

            # Atualizar placar
            self._update_score_display()

            # Verificar fim
            if current_time > self.notes[-1].end_time + 2.0:
                self.is_playing = False
                self._show_results()
                break

            time.sleep(self.check_interval)

    def _check_note_singing(self, note: MusicNote, current_time: float, delta_time: float):
        """
        Verifica se o usuário está cantando a nota correta no momento
        CORREÇÃO: Usa delta_time real em vez de intervalo fixo
        """
        detected_freq = self.audio_detector.get_average_freq()

        if detected_freq and detected_freq > 0:
            # Calcular diferença em cents
            target_freq = librosa.midi_to_hz(note.midi)
            cents_diff = abs(AudioDetector.frequency_to_cents(detected_freq, target_freq))

            # CORREÇÃO: Debug detalhado
            print(f"[DEBUG] Nota: {note.pitch} ({target_freq:.2f}Hz) | "
                  f"Detectado: {detected_freq:.2f}Hz | "
                  f"Diff: {cents_diff:.1f} cents | "
                  f"Delta: {delta_time*1000:.1f}ms")

            # Se está dentro da tolerância, incrementar tempo correto
            if cents_diff <= self.audio_detector.tolerance_cents:
                # CORREÇÃO: Usar delta_time real
                note.time_correct += delta_time
                print(f"  ✓ CORRETO! Tempo acumulado: {note.time_correct:.3f}s / {note.duration:.3f}s")
            else:
                print(f"  ✗ Fora da tolerância ({self.audio_detector.tolerance_cents} cents)")
        else:
            print(f"[DEBUG] Nenhuma frequência detectada")

    def _finalize_note_evaluation(self, note: MusicNote):
        """Avalia a nota após ela terminar e atribui pontuação - CORRIGIDO"""
        if note.was_evaluated:
            return

        note.was_evaluated = True

        # CORREÇÃO: Calcular porcentagem de forma mais precisa
        # Limitar time_correct à duração da nota (pode ultrapassar por imprecisão)
        note.time_correct = min(note.time_correct, note.duration)
        percentage = (note.time_correct / note.duration) * 100 if note.duration > 0 else 0

        print(f"\n[AVALIAÇÃO] Nota {note.pitch}:")
        print(f"  Tempo correto: {note.time_correct:.3f}s")
        print(f"  Duração total: {note.duration:.3f}s")
        print(f"  Porcentagem: {percentage:.1f}%")

        # CORREÇÃO: Ajustar thresholds para serem mais justos
        if percentage >= 90:  # Era 100
            note.score = 1.0
            note.rating = "Perfeito!"
            note.achieved = True
            self.notes_perfect += 1
        elif percentage >= 70:  # Era 80
            note.score = 0.8
            note.rating = "Ótimo"
            note.achieved = True
            self.notes_great += 1
        elif percentage >= 40:  # Era 50
            note.score = 0.5
            note.rating = "Bom"
            note.achieved = True
            self.notes_good += 1
        else:
            note.score = 0.0
            note.rating = "Errou"
            note.achieved = False
            self.notes_missed += 1

        # Acumular pontuação total
        self.total_score += note.score

        print(f"  Rating: {note.rating} ({note.score} pontos)\n")

    def _update_score_display(self):
        """Atualiza o placar na interface"""
        if self.score_callback:
            notes_evaluated = self.notes_perfect + self.notes_great + self.notes_good + self.notes_missed

            if notes_evaluated > 0:
                precision = (self.total_score / notes_evaluated) * 100
            else:
                precision = 0.0

            score_data = {
                'perfect': self.notes_perfect,
                'great': self.notes_great,
                'good': self.notes_good,
                'missed': self.notes_missed,
                'total': self.total_notes,
                'evaluated': notes_evaluated,
                'score': self.total_score,
                'precision': precision
            }

            self.score_callback(score_data)

    def _show_results(self):
        """Mostra resultados finais"""
        precision = (self.total_score / max(1, self.total_notes)) * 100

        msg = f"""
🎤 RESULTADO FINAL 🎤

⭐ Perfeito: {self.notes_perfect}
✓ Ótimo: {self.notes_great}
👍 Bom: {self.notes_good}
✗ Errou: {self.notes_missed}

Total de notas: {self.total_notes}
Pontuação: {self.total_score:.2f}/{self.total_notes}
Precisão: {precision:.1f}%

{"🏆 EXCELENTE!" if precision >= 80 else "👍 BOM TRABALHO!" if precision >= 60 else "💪 CONTINUE PRATICANDO!"}
        """
        print(msg)
        messagebox.showinfo("Resultado Final", msg)

class LearningMode:
    """Modo Aprender - ensina pedaço por pedaço"""

    def __init__(self, notes: List[MusicNote], audio_detector: AudioDetector,
                 canvas: NoteScrollCanvas, time_scale: float = 1.0):
        self.notes = notes
        self.audio_detector = audio_detector
        self.canvas = canvas
        self.time_scale = time_scale

        # Dividir em frases
        self.phrases = self._split_into_phrases(notes)
        self.current_phrase_index = 0

        self.is_playing = False
        self.phrase_results = []

        # Para avaliação
        self.evaluation_thread = None

    def _split_into_phrases(self, notes: List[MusicNote]) -> List[List[MusicNote]]:
        """Divide notas em frases baseado em pausas ou notas longas"""
        phrases = []
        current_phrase = []

        for i, note in enumerate(notes):
            current_phrase.append(note)

            # Verificar se deve quebrar
            should_break = False

            # Pausa longa após a nota
            if i < len(notes) - 1:
                gap = notes[i + 1].start_time - note.end_time
                if gap > 0.5:  # Pausa > 0.5s
                    should_break = True

            # Nota longa (> 1.5s)
            if note.duration > 1.5:
                should_break = True

            # Máximo de 10 notas por frase
            if len(current_phrase) >= 10:
                should_break = True

            if should_break or i == len(notes) - 1:
                if current_phrase:
                    phrases.append(current_phrase[:])
                    current_phrase = []

        return phrases

    def start(self):
        """Inicia modo de aprendizado"""
        self.is_playing = True
        self.current_phrase_index = 0
        self.audio_detector.start_listening()
        self._teach_phrase()

    def stop(self):
        """Para o modo de aprendizado"""
        self.is_playing = False
        self.audio_detector.stop_listening()

    def _teach_phrase(self):
        """Ensina uma frase"""
        if self.current_phrase_index >= len(self.phrases):
            self._show_final_results()
            return

        phrase = self.phrases[self.current_phrase_index]
        print(f"\n📚 Frase {self.current_phrase_index + 1}/{len(self.phrases)}")
        print("🎵 Ouça...")

        # Aplicar escala de tempo
        for note in phrase:
            note.start_time *= self.time_scale
            note.duration *= self.time_scale
            note.end_time = note.start_time + note.duration

        self.canvas.set_notes(phrase)

        # Simula tempo de escuta (aqui você tocaria o áudio)
        time.sleep(2)

        print("🎤 Agora você! Repita...")
        self._evaluate_phrase(phrase)

    def _evaluate_phrase(self, phrase: List[MusicNote]):
        """Avalia a tentativa do usuário na frase"""
        phrase_duration = phrase[-1].end_time - phrase[0].start_time
        start_time = time.time()

        correct_time = 0
        total_checks = 0

        while time.time() - start_time < phrase_duration:
            elapsed = time.time() - start_time

            # Encontrar nota atual
            current_note = None
            for note in phrase:
                if note.start_time <= elapsed <= note.end_time:
                    current_note = note
                    break

            if current_note:
                detected_freq = self.audio_detector.get_average_freq()

                if detected_freq and detected_freq > 0:
                    target_freq = librosa.midi_to_hz(current_note.midi)
                    cents_diff = abs(AudioDetector.frequency_to_cents(detected_freq, target_freq))

                    if cents_diff <= self.audio_detector.tolerance_cents:
                        correct_time += 0.1

                    total_checks += 1

            # Atualizar canvas
            self.canvas.update_time(elapsed)
            current_midi = self.audio_detector.get_current_midi()
            if current_midi:
                self.canvas.update_pitch(current_midi)

            time.sleep(0.1)

        # Calcular precisão
        precision = (correct_time / phrase_duration) * 100 if phrase_duration > 0 else 0
        self.phrase_results.append(precision)

        print(f"✨ Precisão: {precision:.1f}%")

        if precision >= 70:
            print("✅ Ótimo! Próxima frase...")
            self.current_phrase_index += 1
            time.sleep(1)
            self._teach_phrase()
        else:
            print("🔄 Vamos tentar de novo!")
            time.sleep(1)
            self._teach_phrase()

    def _show_final_results(self):
        """Mostra resultados finais do aprendizado"""
        avg_precision = np.mean(self.phrase_results) if self.phrase_results else 0
        print(f"""
📖 APRENDIZADO COMPLETO 📖

Frases completadas: {len(self.phrase_results)}
Precisão geral: {avg_precision:.1f}%

🎓 Parabéns por completar o treino!
        """)


class KaraokeApp:
    """Aplicação principal do karaokê"""

    def __init__(self, master):
        self.master = master
        self.audio_detector = AudioDetector()

        master.title("🎤 Karaokê Game")
        master.geometry("900x750")
        master.configure(bg='#16213e')

        self.notes = []
        self.xml_duration = 0.0
        self.real_duration = 0.0
        self.selected_voice = 0
        self.all_voices = []

        self._create_widgets()

        self.current_mode = None

    def _create_widgets(self):
        """Cria interface"""
        # Frame superior - controles
        control_frame = tk.Frame(self.master, bg='#16213e')
        control_frame.pack(pady=10, padx=10, fill='x')

        # Botão carregar XML
        tk.Button(control_frame, text="📁 Carregar MusicXML",
                  command=self._load_xml, bg='#0f3460', fg='white',
                  font=('Arial', 12, 'bold'), padx=20, pady=10).pack(side='left', padx=5)

        # Seletor de voz
        tk.Label(control_frame, text="Voz:", bg='#16213e',
                 fg='white', font=('Arial', 10)).pack(side='left', padx=5)
        self.voice_combo = ttk.Combobox(control_frame, width=15, state='readonly')
        self.voice_combo.pack(side='left', padx=5)
        self.voice_combo.bind('<<ComboboxSelected>>', self._on_voice_change)

        # Ajuste de tempo
        tk.Label(control_frame, text="Duração real (min):", bg='#16213e',
                 fg='white', font=('Arial', 10)).pack(side='left', padx=5)
        self.duration_entry = tk.Entry(control_frame, width=8)
        self.duration_entry.pack(side='left', padx=5)
        self.duration_entry.insert(0, "0.0")

        tk.Button(control_frame, text="⏱️ Ajustar Tempo",
                  command=self._adjust_time, bg='#e94560', fg='white',
                  font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side='left', padx=5)

        # Info
        self.info_label = tk.Label(control_frame, text="Nenhum arquivo carregado",
                                   bg='#16213e', fg='#aaa', font=('Arial', 9))
        self.info_label.pack(side='left', padx=20)

        # NOVO: Painel de pontuação
        score_frame = tk.Frame(self.master, bg='#0f3460', relief='raised', borderwidth=2)
        score_frame.pack(pady=5, padx=10, fill='x')

        # Título do placar
        tk.Label(score_frame, text="📊 PLACAR", bg='#0f3460', fg='#FFD700',
                 font=('Arial', 14, 'bold')).pack(pady=5)

        # Frame para estatísticas
        stats_frame = tk.Frame(score_frame, bg='#0f3460')
        stats_frame.pack(pady=5)

        # Labels de estatísticas
        self.score_labels = {}

        stats_info = [
            ('perfect', '⭐ Perfeito:', '#FFD700'),
            ('great', '✓ Ótimo:', '#27ae60'),
            ('good', '👍 Bom:', '#3498db'),
            ('missed', '✗ Errou:', '#e74c3c')
        ]

        for i, (key, text, color) in enumerate(stats_info):
            frame = tk.Frame(stats_frame, bg='#0f3460')
            frame.grid(row=0, column=i, padx=15)

            tk.Label(frame, text=text, bg='#0f3460', fg='white',
                     font=('Arial', 10)).pack()
            label = tk.Label(frame, text='0', bg='#0f3460', fg=color,
                             font=('Arial', 16, 'bold'))
            label.pack()
            self.score_labels[key] = label

        # Precisão e pontuação total
        precision_frame = tk.Frame(score_frame, bg='#0f3460')
        precision_frame.pack(pady=5)

        self.precision_label = tk.Label(precision_frame, text="Precisão: 0.0%",
                                        bg='#0f3460', fg='#FFD700',
                                        font=('Arial', 14, 'bold'))
        self.precision_label.pack(side='left', padx=20)

        self.total_score_label = tk.Label(precision_frame, text="Pontos: 0.00 / 0",
                                          bg='#0f3460', fg='white',
                                          font=('Arial', 12))
        self.total_score_label.pack(side='left', padx=20)

        # Canvas de notas
        self.note_canvas = NoteScrollCanvas(self.master, width=880, height=300)
        self.note_canvas.pack(pady=10, padx=10)

        # Botões de modo
        mode_frame = tk.Frame(self.master, bg='#16213e')
        mode_frame.pack(pady=10)

        tk.Button(mode_frame, text="🎮 MODO JOGO", command=self._start_game_mode,
                  bg='#27ae60', fg='white', font=('Arial', 14, 'bold'),
                  padx=40, pady=15).pack(side='left', padx=10)

        tk.Button(mode_frame, text="📚 MODO APRENDER", command=self._start_learning_mode,
                  bg='#3498db', fg='white', font=('Arial', 14, 'bold'),
                  padx=40, pady=15).pack(side='left', padx=10)

        tk.Button(mode_frame, text="⏹️ PARAR", command=self._stop_mode,
                  bg='#e74c3c', fg='white', font=('Arial', 14, 'bold'),
                  padx=40, pady=15).pack(side='left', padx=10)

        # Status
        self.status_label = tk.Label(self.master, text="Aguardando...",
                                     bg='#16213e', fg='white',
                                     font=('Arial', 12, 'bold'))
        self.status_label.pack(pady=10)

    def _update_score_display(self, score_data):
        """Atualiza o display de pontuação"""
        self.score_labels['perfect'].config(text=str(score_data['perfect']))
        self.score_labels['great'].config(text=str(score_data['great']))
        self.score_labels['good'].config(text=str(score_data['good']))
        self.score_labels['missed'].config(text=str(score_data['missed']))

        self.precision_label.config(text=f"Precisão: {score_data['precision']:.1f}%")
        self.total_score_label.config(
            text=f"Pontos: {score_data['score']:.2f} / {score_data['total']}"
        )

    def _load_xml(self):
        """Carrega arquivo MusicXML"""
        filepath = filedialog.askopenfilename(
            title="Selecionar MusicXML",
            filetypes=[("MusicXML", "*.xml *.musicxml"), ("Todos", "*.*")]
        )

        if not filepath:
            return

        try:
            all_notes, duration, voices = MusicXMLParser.parse(filepath)
            self.notes = all_notes
            self.xml_duration = duration
            self.all_voices = voices

            # Atualizar combo de vozes
            voice_names = [f"Voz {i + 1} ({len(v)} notas)"
                           for i, v in enumerate(voices)]
            self.voice_combo['values'] = voice_names
            if voices:
                self.voice_combo.current(0)
                self.selected_voice = 0
                self.notes = voices[0]

            self.info_label.config(
                text=f"✓ {len(all_notes)} notas | Duração: {duration / 60:.1f} min | {len(voices)} vozes"
            )
            self.duration_entry.delete(0, 'end')
            self.duration_entry.insert(0, f"{duration / 60:.2f}")

            self.note_canvas.set_notes(self.notes)
            self.status_label.config(text="✓ Arquivo carregado! Escolha um modo.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar XML:\n{e}")

    def _on_voice_change(self, event):
        """Muda a voz selecionada"""
        idx = self.voice_combo.current()
        if 0 <= idx < len(self.all_voices):
            self.selected_voice = idx
            self.notes = self.all_voices[idx]
            self.note_canvas.set_notes(self.notes)
            self.status_label.config(text=f"Voz {idx + 1} selecionada")

    def _adjust_time(self):
        """Ajusta escala temporal"""
        try:
            real_min = float(self.duration_entry.get())
            self.real_duration = real_min * 60  # Converter para segundos
            self.status_label.config(text=f"⏱️ Tempo ajustado para {real_min:.2f} min")
        except ValueError:
            messagebox.showerror("Erro", "Duração inválida")

    def _start_game_mode(self):
        """Inicia modo jogo"""
        if not self.notes:
            messagebox.showwarning("Aviso", "Carregue um arquivo MusicXML primeiro!")
            return

        time_scale = 1.0
        if self.real_duration > 0 and self.xml_duration > 0:
            time_scale = self.real_duration / self.xml_duration

        # Fazer cópia das notas para não afetar original
        notes_copy = [MusicNote(n.pitch, n.midi, n.duration, n.start_time, n.lyric)
                      for n in self.notes]

        # Resetar placar
        self._update_score_display({
            'perfect': 0, 'great': 0, 'good': 0, 'missed': 0,
            'total': len(notes_copy), 'evaluated': 0,
            'score': 0.0, 'precision': 0.0
        })

        self.current_mode = KaraokeGameMode(
            notes_copy, self.audio_detector, self.note_canvas,
            self._update_score_display, time_scale
        )
        self.current_mode.start()
        self.status_label.config(text="🎮 JOGANDO! Cante junto!")

    def _start_learning_mode(self):
        """Inicia modo aprender"""
        if not self.notes:
            messagebox.showwarning("Aviso", "Carregue um arquivo MusicXML primeiro!")
            return

        time_scale = 1.0
        if self.real_duration > 0 and self.xml_duration > 0:
            time_scale = self.real_duration / self.xml_duration

        notes_copy = [MusicNote(n.pitch, n.midi, n.duration, n.start_time, n.lyric)
                      for n in self.notes]

        self.current_mode = LearningMode(notes_copy, self.audio_detector,
                                         self.note_canvas, time_scale)
        self.current_mode.start()
        self.status_label.config(text="📚 APRENDENDO! Siga as instruções.")

    def _stop_mode(self):
        """Para o modo atual"""
        if self.current_mode:
            self.current_mode.stop()
            self.current_mode = None
        self.status_label.config(text="⏹️ Parado")


# Exemplo de uso standalone (para teste)
if __name__ == "__main__":
    root = tk.Tk()
    app = KaraokeApp(root)
    root.mainloop()
