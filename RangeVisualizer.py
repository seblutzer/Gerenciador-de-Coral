import tkinter as tk
from tkinter import ttk
from GeneralFunctions import note_to_midi, midi_to_note
from Constants import SEMITONE_TO_SHARP, VOICES, VOICE_BASE_RANGES, NOTE_TO_SEMITONE

# ===== VISUALIZADOR DE RANGES =====
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

        # Frame container para o canvas
        canvas_frame = ttk.LabelFrame(master, text="Visualização de Ranges", padding=5)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(canvas_frame, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
                                bg="white", highlightthickness=1, highlightbackground="black")
        self.canvas.pack(fill="both", expand=True, pady=10)

        self.scale = (self.CANVAS_WIDTH - self.LEFT_PAD - self.RIGHT_PAD) / 127.0
        self.draw_grid()

    def set_group_ranges(self, group_ranges):
        """
        group_ranges: dict[str, tuple[str, str]] com (min_note, max_note) por voz
        """

        self.group_ranges = group_ranges

    def draw_grid(self):
        for i, v in enumerate(self.voices):
            y = 10 + i * self.ROW_HEIGHT
            self.canvas.create_line(0, y, self.CANVAS_WIDTH, y, fill="#f0f0f0")

        for s in range(0, 128, 12):
            x = int(self.LEFT_PAD + s * self.scale)
            self.canvas.create_line(x, 0, x, self.CANVAS_HEIGHT, fill="#e6e6e6", dash=(2, 4))
            try:
                note = midi_to_note(s)
                self.canvas.create_text(x + 2, 8, anchor="nw", text=note, fill="#888888", font=("Arial", 8))
            except Exception:
                pass

    def _x(self, midi_note):
        return int(self.LEFT_PAD + midi_note * self.scale)

    def update(self, piece_ranges, T, Os):
        self.canvas.delete("all")

        self.draw_grid()

        for idx, v in enumerate([voice for voice in self.voices if voice in self.group_ranges] if self.group_ranges else self.voices):
            y = 30 + idx * self.ROW_HEIGHT

            base_min_m = note_to_midi(self.base_ranges[v][0])
            base_max_m = note_to_midi(self.base_ranges[v][1])

            bar_y = y - 10 + (self.ROW_HEIGHT - self.BAR_HEIGHT) / 2

            x1 = self._x(base_min_m)
            x2 = self._x(base_max_m)

            # Se houver range de grupo para esta voz, desenhe duas barras:
            # - uma externa (base) com transparência
            # - uma interna (grupo) sem transparência

            if self.group_ranges and v in self.group_ranges:
                g_min_m = note_to_midi(self.group_ranges[v][0])
                g_max_m = note_to_midi(self.group_ranges[v][1])

                # Barreira externa (base) com transparência (simulada via stipple)
                self.canvas.create_rectangle(x1, bar_y, x2, bar_y + self.BAR_HEIGHT,
                                             fill="#90ee90", outline="#2e8b57", stipple="gray50")
                # Bar interna (grupo) sem transparência
                gx1 = self._x(g_min_m)
                gx2 = self._x(g_max_m)
                self.canvas.create_rectangle(gx1, bar_y, gx2, bar_y + self.BAR_HEIGHT,
                                             fill="#90ee90", outline="#2e8b57")
            else:
                self.canvas.create_rectangle(x1, bar_y, x2, bar_y + self.BAR_HEIGHT,
                                             fill="#90ee90", outline="#2e8b57")

            if v in piece_ranges:
                piece_min_str, piece_max_str = piece_ranges[v]
                piece_min_m = note_to_midi(piece_min_str)
                piece_max_m = note_to_midi(piece_max_str)

                O = Os.get(v, 0)
                trans_min = piece_min_m + T + 12 * O
                trans_max = piece_max_m + T + 12 * O

                tx1 = self._x(trans_min)
                tx2 = self._x(trans_max)

                red_thick = int(self.BAR_HEIGHT * 0.8)
                red_top = bar_y + (self.BAR_HEIGHT - red_thick) / 2
                red_bottom = red_top + red_thick
                self.canvas.create_rectangle(tx1, red_top, tx2, red_bottom,
                                             fill="#ff7f7f", outline="#c11b1b", stipple="gray50")

            self.canvas.create_text(5, y + 6, anchor="w", text=v, font=("Arial", 10, "bold"))

        self.master.update_idletasks()