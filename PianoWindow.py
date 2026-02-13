"""
PianoGameWindow - Interface de Piano Gamificada para Testes Vocais
Exibe um teclado de piano interativo que mostra:
- Nota alvo em vermelho
- Nota atual cantada em amarelo
- Notas conquistadas em azul
- Mensagens motivacionais de progresso
- Indicadores de meta para próximas vozes
"""

import tkinter as tk
from tkinter import ttk
import librosa
from Constants import VOICE_BASE_RANGES
from GeneralFunctions import is_black_key, generate_note_range, play_note


class PianoGameWindow:
    """Janela separada com interface de piano gamificada para testes vocais"""

    # Cores do sistema
    COLOR_TARGET = '#FF4444'      # Vermelho - nota alvo
    COLOR_CURRENT = '#FFD700'     # Amarelo - nota atual
    COLOR_ACHIEVED = '#4169E1'    # Azul - nota conquistada
    COLOR_WHITE_KEY = '#FFFFFF'   # Tecla branca
    COLOR_BLACK_KEY = '#2C2C2C'   # Tecla preta
    COLOR_GOAL_RANGE = '#90EE90'  # Verde claro - range da voz alvo

    def __init__(self, test_mode='normal'):
        """
        Inicializa a janela de piano gamificada

        Args:
            test_mode: 'normal' ou 'quick'
        """
        self.window = None
        self.canvas = None
        self.test_mode = test_mode
        self.is_active = False

        # Estado do teste
        self.target_note = None
        self.current_note = None
        self.achieved_notes = set()  # Notas conquistadas
        self.highest_achieved = None  # Nota mais aguda conquistada
        self.lowest_achieved = None   # Nota mais grave conquistada
        self.phase = 'ascending'      # 'ascending' ou 'descending'

        # Calibração do teste rápido
        self.calibration_highest = None  # Nota mais aguda da calibração
        self.calibration_lowest = None   # Nota mais grave da calibração

        # Mensagens
        self.message_label = None
        self.semitone_label = None

        # Geometria do piano
        self.white_key_width = 40
        self.white_key_height = 150
        self.black_key_width = 24
        self.black_key_height = 95

        # Range de notas do piano (E2 a A5 - cobre todas as vozes)
        self.piano_start_note = 'C2'
        self.piano_end_note = 'E6'
        self.note_list = generate_note_range(self.piano_start_note, self.piano_end_note)

        # Cache de posições das teclas
        self.key_positions = {}

    def open(self
             ):
        """Abre a janela do piano"""
        if self.window is not None:
            return  # Já está aberta

        self.window = tk.Toplevel()
        self.window.wm_attributes("-topmost", True)
        self.window.title("🎹 Piano Gamificado - Teste Vocal")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        # Frame principal
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Mensagens no topo
        self.message_label = ttk.Label(
            main_frame,
            text="Aguardando início do teste...",
            font=("Arial", 12, "bold"),
            foreground="#2E86AB"
        )
        self.message_label.pack(pady=5)

        self.semitone_label = ttk.Label(
            main_frame,
            text="",
            font=("Arial", 10),
            foreground="#666"
        )
        self.semitone_label.pack(pady=2)

        # Canvas do piano
        canvas_width = len([n for n in self.note_list if not is_black_key(n)]) * self.white_key_width
        canvas_height = self.white_key_height + 60

        self.canvas = tk.Canvas(
            main_frame,
            width=canvas_width,
            height=canvas_height,
            bg='#F5F5F5',
            highlightthickness=0
        )
        self.canvas.pack(pady=10)

        # Desenha o piano inicial
        self._draw_piano()

        # Legenda
        legend_frame = ttk.Frame(main_frame)
        legend_frame.pack(pady=5)

        self._create_legend_item(legend_frame, self.COLOR_TARGET, "Nota Alvo", 0)
        self._create_legend_item(legend_frame, self.COLOR_CURRENT, "Nota Atual", 1)
        self._create_legend_item(legend_frame, self.COLOR_ACHIEVED, "Conquistado", 2)
        self._create_legend_item(legend_frame, self.COLOR_GOAL_RANGE, "Meta Voz", 3)

        self.is_active = True
        self.window.geometry(f"{canvas_width + 40}x{canvas_height + 200}")

    def _create_legend_item(self,
                            parent, color, text, column):
        """Cria um item da legenda"""
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, padx=10)

        color_box = tk.Canvas(frame, width=20, height=20, bg=color, highlightthickness=1)
        color_box.pack(side="left", padx=(0, 5))

        label = ttk.Label(frame, text=text, font=("Arial", 9))
        label.pack(side="left")

    def close(self
              ):
        """Fecha a janela do piano"""
        if self.window:
            self.is_active = False
            self.window.destroy()
            self.window = None
            self.canvas = None

    def _draw_piano(self
                    ):
        """Desenha o teclado do piano completo"""
        if not self.canvas:
            return

        self.canvas.delete("all")
        self.key_positions.clear()

        # Desenha indicadores de range da voz alvo primeiro (fundo)
        self._draw_goal_range_indicator()

        # Bind de clique
        self.canvas.bind("<Button-1>", self._on_click)

        # Desenha teclas brancas primeiro
        white_key_index = 0
        for note in self.note_list:
            if not is_black_key(note):
                x = white_key_index * self.white_key_width
                self._draw_white_key(note, x, white_key_index)
                white_key_index += 1

        # Desenha teclas pretas por cima
        white_key_index = 0
        for i, note in enumerate(self.note_list):
            if not is_black_key(note):
                # Verifica se próxima nota é preta
                if i + 1 < len(self.note_list) and is_black_key(self.note_list[i + 1]):
                    black_note = self.note_list[i + 1]
                    x = (white_key_index * self.white_key_width) + (self.white_key_width - self.black_key_width // 2)
                    self._draw_black_key(black_note, x)
                white_key_index += 1

    def _draw_goal_range_indicator(self
                                   ):
        """Desenha indicadores visuais do range da voz alvo"""
        if not self.canvas:
            return

        # Encontra a voz alvo baseado na nota mais aguda conquistada
        target_voice, target_type = self._get_next_voice_goal()

        if target_voice is None:
            return

        voice_range = VOICE_BASE_RANGES[target_voice]

        if target_type == 'high':
            goal_note = voice_range[1]  # Agudo
        else:
            goal_note = voice_range[0]  # Grave

        # Desenha colchete na posição da meta
        if goal_note in self.note_list:
            white_keys_before = len([n for n in self.note_list[:self.note_list.index(goal_note)]
                                     if not is_black_key(n)])

            if is_black_key(goal_note):
                # Tecla preta
                prev_white = len([n for n in self.note_list[:self.note_list.index(goal_note)]
                                 if not is_black_key(n)])
                x = (prev_white * self.white_key_width) + (self.white_key_width - self.black_key_width // 2)
                width = self.black_key_width
                height = self.black_key_height
            else:
                # Tecla branca
                x = white_keys_before * self.white_key_width
                width = self.white_key_width
                height = self.white_key_height

            # Desenha colchete
            bracket_color = '#32CD32'
            bracket_width = 3

            # Linha superior
            self.canvas.create_line(
                x, 5, x + width, 5,
                fill=bracket_color, width=bracket_width, tags="goal_indicator"
            )
            # Linha esquerda
            self.canvas.create_line(
                x, 5, x, height + 30,
                fill=bracket_color, width=bracket_width, tags="goal_indicator"
            )
            # Linha direita
            self.canvas.create_line(
                x + width, 5, x + width, height + 30,
                fill=bracket_color, width=bracket_width, tags="goal_indicator"
            )
            # Texto da voz
            self.canvas.create_text(
                x + width // 2, height + 45,
                text=f"Meta: {target_voice}",
                font=("Arial", 8, "bold"),
                fill=bracket_color,
                tags="goal_indicator"
            )

    def _draw_white_key(self,
                        note, x, index):
        """Desenha uma tecla branca"""
        # Determina a cor
        color = self._get_key_color(note)

        # Retângulo da tecla
        key_id = self.canvas.create_rectangle(
            x, 0,
            x + self.white_key_width, self.white_key_height,
            fill=color,
            outline='#888',
            width=1,
            tags=f"key_{note}"
        )

        # Nome da nota
        text_y = self.white_key_height - 20
        self.canvas.create_text(
            x + self.white_key_width // 2, text_y,
            text=note,
            font=("Arial", 8, "bold"),
            fill='#333',
            tags=f"label_{note}"
        )

        # Armazena posição
        self.key_positions[note] = {
            'x': x,
            'y': 0,
            'width': self.white_key_width,
            'height': self.white_key_height,
            'type': 'white'
        }

    def _draw_black_key(self,
                        note, x):
        """Desenha uma tecla preta"""
        # Determina a cor
        color = self._get_key_color(note)

        # Retângulo da tecla
        key_id = self.canvas.create_rectangle(
            x, 0,
            x + self.black_key_width, self.black_key_height,
            fill=color,
            outline='#000',
            width=1,
            tags=f"key_{note}"
        )

        # Nome da nota
        text_y = self.black_key_height - 15
        self.canvas.create_text(
            x + self.black_key_width // 2, text_y,
            text=note,
            font=("Arial", 7, "bold"),
            fill='#FFF',
            tags=f"label_{note}"
        )

        # Armazena posição
        self.key_positions[note] = {
            'x': x,
            'y': 0,
            'width': self.black_key_width,
            'height': self.black_key_height,
            'type': 'black'
        }

    def _get_key_color(self,
                       note):
        """Determina a cor de uma tecla baseado no estado"""
        # Prioridade: atual > alvo > conquistado > padrão

        if note == self.current_note:
            return self.COLOR_CURRENT

        if note == self.target_note:
            return self.COLOR_TARGET

        if note in self.achieved_notes:
            return self.COLOR_ACHIEVED

        # Cor padrão
        if is_black_key(note):
            return self.COLOR_BLACK_KEY
        else:
            return self.COLOR_WHITE_KEY

    def update_state(self,
                     target_note=None, current_note=None, phase=None):
        """
        Atualiza o estado do piano

        Args:
            target_note: Nota alvo atual (vermelho)
            current_note: Nota sendo cantada (amarelo)
            phase: 'ascending' ou 'descending'
        """
        if not self.is_active:
            return

        if target_note:
            self.target_note = target_note

        if current_note:
            self.current_note = current_note

        if phase:
            self.phase = phase

        try:
            # Redesenha o piano
            self._draw_piano()

            # Atualiza mensagens
            self._update_messages()
        except:
            pass

    def mark_note_achieved(self,
                           note):
        """Marca uma nota como conquistada (azul)"""
        if not note:
            return

        self.achieved_notes.add(note)

        # Atualiza limites
        note_midi = librosa.note_to_midi(note)

        if self.highest_achieved is None or note_midi > librosa.note_to_midi(self.highest_achieved):
            self.highest_achieved = note

        if self.lowest_achieved is None or note_midi < librosa.note_to_midi(self.lowest_achieved):
            self.lowest_achieved = note

        # Redesenha
        self._draw_piano()
        self._update_messages()

    def set_calibration_range(self,
                              highest_note, lowest_note):
        """
        Define o range de calibração do teste rápido

        Args:
            highest_note: Nota mais aguda da calibração
            lowest_note: Nota mais grave da calibração
        """
        self.calibration_highest = highest_note
        self.calibration_lowest = lowest_note

        # No teste rápido, marca todas as notas entre os limites como conquistadas
        if highest_note and lowest_note:
            highest_midi = librosa.note_to_midi(highest_note)
            lowest_midi = librosa.note_to_midi(lowest_note)

            for note in self.note_list:
                note_midi = librosa.note_to_midi(note)
                if lowest_midi <= note_midi <= highest_midi:
                    self.achieved_notes.add(note)

            self.highest_achieved = highest_note
            self.lowest_achieved = lowest_note

            self._draw_piano()
            self._update_messages()

    def _update_messages(self
                         ):
        """Atualiza as mensagens motivacionais"""
        if not self.message_label or not self.semitone_label:
            return

        # Mensagem principal
        if self.phase == 'ascending':
            if self.highest_achieved:
                self.message_label.config(
                    text=f"🎵 Fase Ascendente - Maior nota: {self.highest_achieved}",
                    foreground='#2E86AB'
                )
            else:
                self.message_label.config(
                    text="🎵 Iniciando teste...",
                    foreground='#2E86AB'
                )
        else:
            if self.lowest_achieved:
                self.message_label.config(
                    text=f"🎵 Fase Descendente - Menor nota: {self.lowest_achieved}",
                    foreground='#9B59B6'
                )
            else:
                self.message_label.config(
                    text="🎵 Fase Descendente",
                    foreground='#9B59B6'
                )

        # Mensagem de progresso
        progress_msg = self._get_progress_message()
        self.semitone_label.config(text=progress_msg)

    def _get_progress_message(self
                              ):
        """Gera mensagem de progresso baseada nas notas conquistadas"""
        if self.phase == 'ascending':
            reference_note = self.highest_achieved
            direction = 'agudo'
        else:
            reference_note = self.lowest_achieved
            direction = 'grave'

        if not reference_note:
            return "Conquiste a primeira nota!"

        # Encontra próxima voz
        target_voice, target_type = self._get_next_voice_goal()

        if target_voice is None:
            if direction == 'agudo':
                return "🎉 Parabéns! Você alcançou o agudo do SOPRANO! Continue cantando para estender ainda mais o seu limite de agudo."
            else:
                return "🎉 Parabéns! Você alcançou o grave do BAIXO! Continue cantando para estender ainda mais o seu limite de grave."

        # Calcula distância em semitons
        voice_range = VOICE_BASE_RANGES[target_voice]
        goal_note = voice_range[1] if target_type == 'high' else voice_range[0]

        reference_midi = librosa.note_to_midi(reference_note)
        goal_midi = librosa.note_to_midi(goal_note)
        semitones_remaining = abs(goal_midi - reference_midi)

        if semitones_remaining == 0:
            return f"🎉 Parabéns, você alcançou o {direction} do {target_voice.upper()}!"
        else:
            return f"Só faltam {semitones_remaining} semitons para alcançar o {direction} do {target_voice.upper()}"

    def _get_next_voice_goal(self
                             ):
        """
        Determina a próxima voz a ser alcançada

        Returns:
            (nome_voz, tipo) onde tipo é 'high' ou 'low', ou (None, None)
        """
        if self.phase == 'ascending':
            return self._get_next_high_voice()
        else:
            return self._get_next_low_voice()

    def _get_next_high_voice(self
                             ):
        """Encontra a próxima voz mais aguda a ser alcançada"""
        if not self.highest_achieved:
            # Primeira voz a tentar
            return 'Baixo', 'high'

        current_midi = librosa.note_to_midi(self.highest_achieved)

        # Ordem das vozes por agudo (do mais grave ao mais agudo)
        voice_order = ['Baixo', 'Barítono', 'Tenor', 'Contralto', 'Mezzo-soprano', 'Soprano']

        closest_voice = None
        min_distance = float('inf')

        for voice in voice_order:
            high_note = VOICE_BASE_RANGES[voice][1]
            high_midi = librosa.note_to_midi(high_note)

            # Só considera vozes acima da atual
            if high_midi > current_midi:
                distance = high_midi - current_midi
                if distance < min_distance:
                    min_distance = distance
                    closest_voice = voice

        return (closest_voice, 'high') if closest_voice else (None, None)

    def _get_next_low_voice(self
                            ):
        """Encontra a próxima voz mais grave a ser alcançada"""
        if not self.lowest_achieved:
            # Primeira voz a tentar (começando do mais agudo)
            return 'Mezzo-soprano', 'low'

        current_midi = librosa.note_to_midi(self.lowest_achieved)

        # Ordem das vozes por grave (do mais agudo ao mais grave)
        voice_order = ['Soprano', 'Mezzo-soprano', 'Contralto', 'Tenor', 'Barítono', 'Baixo']

        closest_voice = None
        min_distance = float('inf')

        for voice in voice_order:
            low_note = VOICE_BASE_RANGES[voice][0]
            low_midi = librosa.note_to_midi(low_note)

            # Só considera vozes abaixo da atual
            if low_midi < current_midi:
                distance = current_midi - low_midi
                if distance < min_distance:
                    min_distance = distance
                    closest_voice = voice

        return (closest_voice, 'low') if closest_voice else (None, None)

    def reset(self
              ):
        """Reseta o estado do piano"""
        self.target_note = None
        self.current_note = None
        self.achieved_notes.clear()
        self.highest_achieved = None
        self.lowest_achieved = None
        self.calibration_highest = None
        self.calibration_lowest = None
        self.phase = 'ascending'

        if self.is_active:
            self._draw_piano()
            self._update_messages()

    def _on_click(self,
                  event):
        """Callback quando o usuário clica no canvas"""
        click_x = event.x
        click_y = event.y

        # Verifica primeiro teclas pretas (estão por cima)
        for note, pos in self.key_positions.items():
            if pos['type'] == 'black':
                if (pos['x'] <= click_x <= pos['x'] + pos['width'] and
                    pos['y'] <= click_y <= pos['y'] + pos['height']):
                    play_note(note)
                    self._highlight_key(note)
                    return

        # Se não clicou em preta, verifica brancas
        for note, pos in self.key_positions.items():
            if pos['type'] == 'white':
                if (pos['x'] <= click_x <= pos['x'] + pos['width'] and
                    pos['y'] <= click_y <= pos['y'] + pos['height']):
                    play_note(note)
                    self._highlight_key(note)
                    return

    def _highlight_key(self,
                       note):
        """Dá um feedback visual temporário ao clicar na tecla"""
        # Salva cor original
        original_color = self._get_key_color(note)

        # Muda para cor de destaque (amarelo)
        items = self.canvas.find_withtag(f"key_{note}")
        if items:
            self.canvas.itemconfig(items[0], fill='#FFD700')

            # Volta para cor original após 200ms
            self.canvas.after(200, lambda: self.canvas.itemconfig(items[0], fill=original_color))