import tkinter as tk
from tkinter import ttk
from GeneralFunctions import is_black_key, generate_note_range, play_note
import librosa

# ===== VISUALIZADOR DE TECLADO =====
class KeyboardVisualizer:
    """Visualiza as notas no teclado com cores conforme o range do corista vs voz

    Características:
    - Visual idêntico ao PianoWindow (dimensões, cores, proporções)
    - Funcionalidade de range colorido (verde, vermelho, azul)
    - Reprodução de som ao clicar nas teclas
    """

    # Cores do sistema (igual ao PianoWindow)
    COLOR_WHITE_KEY = '#FFFFFF'      # Tecla branca padrão
    COLOR_BLACK_KEY = '#2C2C2C'      # Tecla preta padrão

    # Cores para indicação de range (da versão antiga, adaptadas)
    COLOR_GREEN_LIGHT = '#90EE90'    # Verde claro - consegue e é exigido
    COLOR_GREEN_DARK = '#228B22'     # Verde escuro - tecla preta, consegue e é exigido
    COLOR_RED_LIGHT = '#FF6B6B'      # Vermelho claro - é exigido mas não consegue
    COLOR_RED_DARK = '#CC0000'       # Vermelho escuro - tecla preta, é exigido mas não consegue
    COLOR_BLUE_LIGHT = '#87CEEB'     # Azul claro - consegue mas não é exigido
    COLOR_BLUE_DARK = '#0066CC'      # Azul escuro - tecla preta, consegue mas não é exigido

    percent = 0.725
    # Dimensões do piano (igual ao PianoWindow)
    WHITE_KEY_WIDTH = 40 * percent
    WHITE_KEY_HEIGHT = 150 * percent
    BLACK_KEY_WIDTH = 24 * percent
    BLACK_KEY_HEIGHT = 95 * percent

    def __init__(self, master):
        self.master = master

        # Frame com label
        frame = ttk.LabelFrame(master, text="Visualização de Notas no Teclado", padding=5)
        frame.pack(fill="both", expand=False, padx=10, pady=10)

        # Range de notas do piano (C2 a C6)
        self.piano_start_note = 'C2'
        self.piano_end_note = 'C6'
        self.note_list = generate_note_range(self.piano_start_note, self.piano_end_note)

        # Calcula largura do canvas baseado nas teclas brancas
        num_white_keys = len([n for n in self.note_list if not is_black_key(n)])
        canvas_width = num_white_keys * self.WHITE_KEY_WIDTH
        canvas_height = self.WHITE_KEY_HEIGHT + 60

        self.canvas = tk.Canvas(
            frame,
            width=canvas_width,
            height=canvas_height,
            bg='#F5F5F5',  # Fundo igual ao PianoWindow
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)

        # Cache de posições das teclas (para cliques)
        self.key_positions = {}

        # Estado atual
        self.corista_min_midi = None
        self.corista_max_midi = None
        self.voice_min_midi = None
        self.voice_max_midi = None

        # Bind de clique
        self.canvas.bind("<Button-1>", self._on_click)

        # Legenda
        legend_frame = ttk.Frame(master)
        legend_frame.pack(fill="x", padx=10, pady=5)

        self._create_legend_item(legend_frame, self.COLOR_GREEN_LIGHT, "Alcance exigido (consegue fazer)", 0)
        self._create_legend_item(legend_frame, self.COLOR_RED_LIGHT, "Alcance exigido (NÃO consegue)", 1)
        self._create_legend_item(legend_frame, self.COLOR_BLUE_LIGHT, "Alcance extra (além do exigido)", 2)

    def _create_legend_item(self,
                            parent, color, text, column):
        """Cria um item da legenda"""
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, padx=10)

        color_box = tk.Canvas(frame, width=20, height=20, bg=color, highlightthickness=1)
        color_box.pack(side="left", padx=(0, 5))

        label = ttk.Label(frame, text=text, font=("Arial", 9))
        label.pack(side="left")

    def update(self,
               corista_min_str, corista_max_str, voice_min_str, voice_max_str):
        """Atualiza o teclado com as cores"""
        try:
            self.corista_min_midi = librosa.note_to_midi(corista_min_str)
            self.corista_max_midi = librosa.note_to_midi(corista_max_str)
            self.voice_min_midi = librosa.note_to_midi(voice_min_str)
            self.voice_max_midi = librosa.note_to_midi(voice_max_str)

            self._draw_piano()
        except Exception as e:
            print(f"Erro ao atualizar teclado: {e}")

    def _draw_piano(self
                    ):
        """Desenha o teclado do piano completo"""
        self.canvas.delete("all")
        self.key_positions.clear()

        # Desenha teclas brancas primeiro
        white_key_index = 0
        for note in self.note_list:
            if not is_black_key(note):
                x = white_key_index * self.WHITE_KEY_WIDTH
                self._draw_white_key(note, x, white_key_index)
                white_key_index += 1

        # Desenha teclas pretas por cima
        white_key_index = 0
        for i, note in enumerate(self.note_list):
            if not is_black_key(note):
                # Verifica se próxima nota é preta
                if i + 1 < len(self.note_list) and is_black_key(self.note_list[i + 1]):
                    black_note = self.note_list[i + 1]
                    x = (white_key_index * self.WHITE_KEY_WIDTH) + (self.WHITE_KEY_WIDTH - self.BLACK_KEY_WIDTH // 2)
                    self._draw_black_key(black_note, x)
                white_key_index += 1

    def _get_key_color(self,
                       note):
        """Determina a cor de uma tecla baseado no estado"""
        if self.corista_min_midi is None:
            # Sem dados ainda, retorna cor padrão
            if is_black_key(note):
                return self.COLOR_BLACK_KEY
            else:
                return self.COLOR_WHITE_KEY

        midi = librosa.note_to_midi(note)
        is_black = is_black_key(note)

        # Lógica de cores (da versão antiga)
        if self.voice_min_midi <= midi <= self.voice_max_midi:
            if self.corista_min_midi <= midi <= self.corista_max_midi:
                # Verde - consegue cantar e é exigido
                return self.COLOR_GREEN_DARK if is_black else self.COLOR_GREEN_LIGHT
            else:
                # Vermelho - é exigido mas não consegue
                return self.COLOR_RED_DARK if is_black else self.COLOR_RED_LIGHT
        else:
            if self.corista_min_midi <= midi <= self.corista_max_midi:
                # Azul - consegue cantar mas não é exigido
                return self.COLOR_BLUE_DARK if is_black else self.COLOR_BLUE_LIGHT
            else:
                # Cor padrão
                return self.COLOR_BLACK_KEY if is_black else self.COLOR_WHITE_KEY

    def _draw_white_key(self,
                        note, x, index):
        """Desenha uma tecla branca"""
        # Determina a cor
        color = self._get_key_color(note)

        # Retângulo da tecla
        key_id = self.canvas.create_rectangle(
            x, 0,
            x + self.WHITE_KEY_WIDTH, self.WHITE_KEY_HEIGHT,
            fill=color,
            outline='#888',
            width=1,
            tags=f"key_{note}"
        )

        # Nome da nota
        text_y = self.WHITE_KEY_HEIGHT - 20
        text_color = '#333' if color in [self.COLOR_WHITE_KEY, self.COLOR_GREEN_LIGHT,
                                         self.COLOR_RED_LIGHT, self.COLOR_BLUE_LIGHT] else '#FFF'
        self.canvas.create_text(
            x + self.WHITE_KEY_WIDTH // 2, text_y,
            text=note,
            font=("Arial", 8, "bold"),
            fill=text_color,
            tags=f"label_{note}"
        )

        # Armazena posição para detecção de clique
        self.key_positions[note] = {
            'x': x,
            'y': 0,
            'width': self.WHITE_KEY_WIDTH,
            'height': self.WHITE_KEY_HEIGHT,
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
            x + self.BLACK_KEY_WIDTH, self.BLACK_KEY_HEIGHT,
            fill=color,
            outline='#000',
            width=1,
            tags=f"key_{note}"
        )

        # Nome da nota
        text_y = self.BLACK_KEY_HEIGHT - 15
        self.canvas.create_text(
            x + self.BLACK_KEY_WIDTH // 2, text_y,
            text=note,
            font=("Arial", 7, "bold"),
            fill='#FFF',
            tags=f"label_{note}"
        )

        # Armazena posição para detecção de clique
        self.key_positions[note] = {
            'x': x,
            'y': 0,
            'width': self.BLACK_KEY_WIDTH,
            'height': self.BLACK_KEY_HEIGHT,
            'type': 'black'
        }

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
