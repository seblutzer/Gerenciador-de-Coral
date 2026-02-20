import tkinter as tk
from tkinter import ttk
from Constants import VOICES, VOICE_BASE_RANGES
from CoristasManager import CoristasManager
import librosa

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

        # Adicionar tooltip
        self.tooltip = None
        self.tooltip_id = None

    def set_group_ranges(self,
                         group_ranges):
        """
        group_ranges: dict[str, tuple[str, str]] com (min_note, max_note) por voz
        """

        self.group_ranges = group_ranges

    def draw_grid(self,
                  group_ranges=None):
        for i, v in enumerate(self.voices if not group_ranges else group_ranges):
            y = 45 + i * self.ROW_HEIGHT
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
                note = librosa.midi_to_note(s)
                self.canvas.create_text(x + 2, 8, anchor="nw", text=note, fill="#888888", font=("Arial", 8))
            except Exception:
                pass

    def _x(self,
           midi_note):
        # Ajusta a coordenada X subtraindo MIDI_MIN
        return int(self.LEFT_PAD + (midi_note - self.MIDI_MIN) * self.scale) + 100

    def _show_tooltip(self, event, text):
        """Mostra tooltip próximo ao cursor"""
        if self.tooltip:
            self.tooltip.destroy()

        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

        label = tk.Label(self.tooltip, text=text,
                         background="#FFFFE0",
                         relief="solid",
                         borderwidth=1,
                         font=("Arial", 9),
                         padx=5, pady=3)
        label.pack()

    def _hide_tooltip(self, event=None):
        """Esconde tooltip"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def _move_tooltip(self, event):
        """Move tooltip com o cursor"""
        if self.tooltip:
            self.tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

    def _get_optimized_formation_text(self, voice, T, possible_fit, not_fit):
        """Gera texto da formação otimizada"""
        if not possible_fit or T not in possible_fit or voice not in possible_fit[T]:
            return "Nenhuma formação disponível"

        all_members = possible_fit[T][voice]

        # Separar membros que alcançam vs não alcançam
        fit_members = [m for m in all_members if m not in not_fit[T]]
        not_fit_members = [m for m in all_members if m in not_fit[T]]

        lines = []

        if fit_members:
            lines.append(f"Formação sugerida:")
            lines.append(', '.join(fit_members))

        if not_fit_members:
            if lines:
                lines.append("")  # linha em branco
            lines.append(", ".join(not_fit_members))
            lines.append("não alcançam as notas necessárias")

        return "\n".join(lines) if lines else "Nenhum membro disponível"

    def update(self, piece_ranges, T, Os, group_ranges=None, group_extension=None,
               voice_scores=None, possible_fit=None, not_fit=None):
        self.canvas.delete("all")
        self._hide_tooltip()  # Limpar tooltip ao atualizar
        self.draw_grid(group_ranges)

        for idx, v in enumerate(group_ranges if group_ranges else self.voices):
            y = 30 + idx * self.ROW_HEIGHT
            bar_y = y - 10 + (self.ROW_HEIGHT - self.BAR_HEIGHT) / 2

            # Determinar o range base para validação de transposição
            if group_ranges:
                g_min_m = librosa.note_to_midi(group_ranges[v][0])
                g_max_m = librosa.note_to_midi(group_ranges[v][1])
            else:
                g_min_m = librosa.note_to_midi(VOICE_BASE_RANGES[v][0])
                g_max_m = librosa.note_to_midi(VOICE_BASE_RANGES[v][1])

            # Desenhar barras de grupo se existirem
            if group_ranges is not None and group_extension is not None:
                # Desenhar barra de group_extension (com opacidade 50%) se aplicável
                if v in group_extension and v in group_ranges:
                    if group_extension[v] != group_ranges[v]:
                        ext_min_m = librosa.note_to_midi(group_extension[v][0])
                        ext_max_m = librosa.note_to_midi(group_extension[v][1])
                        ext_x1 = self._x(ext_min_m)
                        ext_x2 = self._x(ext_max_m)

                        # Desenha com opacidade 50% (usando stipple)
                        ext_rect = self.canvas.create_rectangle(
                            ext_x1, bar_y, ext_x2, bar_y + self.BAR_HEIGHT,
                            fill="#56BAF6", outline="#000080", stipple="gray50",
                            tags=f"ext_{v}")
                        ext_grave = min((nome for nome, dados in self.coristas.items() if dados['voz_atribuida'] == v),
                                        key=lambda n: librosa.note_to_midi(self.coristas[n]['range_min']))

                        ext_agudo = max((nome for nome, dados in self.coristas.items() if dados['voz_atribuida'] == v),
                                        key=lambda n: librosa.note_to_midi(self.coristas[n]['range_max']))

                        ext_text = f"{v} mais grave: {ext_grave} ({self.coristas[ext_grave]['range_min']}) | {v} mais agudo: {ext_agudo} ({self.coristas[ext_agudo]['range_max']})"

                        # Tooltip para group_extension
                        self.canvas.tag_bind(f"ext_{v}", "<Enter>",
                                             lambda e, txt=ext_text: self._show_tooltip(e, txt))
                        self.canvas.tag_bind(f"ext_{v}", "<Leave>", self._hide_tooltip)
                        self.canvas.tag_bind(f"ext_{v}", "<Motion>", self._move_tooltip)

                # Desenhar barra de group_ranges (sólida)
                if v in group_ranges:
                    gr_min_m = librosa.note_to_midi(group_ranges[v][0])
                    gr_max_m = librosa.note_to_midi(group_ranges[v][1])
                    gr_x1 = self._x(gr_min_m)
                    gr_x2 = self._x(gr_max_m)

                    gr_rect = self.canvas.create_rectangle(
                        gr_x1, bar_y, gr_x2, bar_y + self.BAR_HEIGHT,
                        fill="#4169E1", outline="#000080",
                        tags=f"group_{v}")

                    # Tooltip para group_ranges com formação otimizada
                    if possible_fit is not None and not_fit is not None:
                        tooltip_text = self._get_optimized_formation_text(v, T, possible_fit, not_fit)
                        self.canvas.tag_bind(f"group_{v}", "<Enter>",
                                             lambda e, txt=tooltip_text: self._show_tooltip(e, txt))
                        self.canvas.tag_bind(f"group_{v}", "<Leave>", self._hide_tooltip)
                        self.canvas.tag_bind(f"group_{v}", "<Motion>", self._move_tooltip)
            else:
                # Comportamento padrão quando não há group_ranges/group_extension
                base_min_m = librosa.note_to_midi(VOICE_BASE_RANGES[v][0])
                base_max_m = librosa.note_to_midi(VOICE_BASE_RANGES[v][1])
                x1 = self._x(base_min_m)
                x2 = self._x(base_max_m)

                self.canvas.create_rectangle(
                    x1, bar_y, x2, bar_y + self.BAR_HEIGHT,
                    fill="#4169E1", outline="#000080",
                    tags=f"base_{v}")

            # Resto da lógica (piece_ranges e transposição)
            if v in {k: y for k, y in piece_ranges.items() if y != ('', '')}:
                piece_min_str, piece_max_str = piece_ranges[v]
                piece_min_m = librosa.note_to_midi(piece_min_str)
                piece_max_m = librosa.note_to_midi(piece_max_str)

                O = Os.get(v, 0)
                trans_min = piece_min_m + T + 12 * O
                trans_max = piece_max_m + T + 12 * O

                # Nova lógica para escolher a transposição mais "confortável"
                best_score = None
                best_tmin = trans_min
                best_tmax = trans_max
                best_Op = O

                for delta in range(-2, 3):
                    Op = O + delta
                    tmin = piece_min_m + T + 12 * Op
                    tmax = piece_max_m + T + 12 * Op

                    inside = (tmin >= g_min_m) and (tmax <= g_max_m)
                    if inside:
                        dist_left = tmin - g_min_m
                        dist_right = g_max_m - tmax
                        min_dist = min(dist_left, dist_right)
                        score = (1, min_dist, dist_left, dist_right)
                    else:
                        left_excess = max(0, g_min_m - tmin)
                        right_excess = max(0, tmax - g_max_m)
                        outside_excess = left_excess + right_excess
                        score = (0, -outside_excess, 0, 0)

                    if best_score is None or score > best_score:
                        best_score = score
                        best_Op = Op
                        best_tmin = tmin
                        best_tmax = tmax

                trans_min = best_tmin
                trans_max = best_tmax

                tx1 = self._x(trans_min)
                tx2 = self._x(trans_max)

                red_thick = int(self.BAR_HEIGHT * 0.5)
                red_top = bar_y + (self.BAR_HEIGHT - red_thick) / 2
                red_bottom = red_top + red_thick
                self.canvas.create_rectangle(
                    tx1, red_top, tx2, red_bottom,
                    fill="#f7a40a", outline="#6e4b0b", tags=f"range_lvl_{v}")

                # Criar o texto do tooltip antes da lambda
                tooltip_text = f"Alcance exigido para {v}: {librosa.midi_to_note(piece_min_m + T)} → {librosa.midi_to_note(piece_max_m + T)}"

                self.canvas.tag_bind(f"range_lvl_{v}", "<Enter>",
                                     lambda e, txt=tooltip_text: self._show_tooltip(e, txt))
                self.canvas.tag_bind(f"range_lvl_{v}", "<Leave>", self._hide_tooltip)
                self.canvas.tag_bind(f"range_lvl_{v}", "<Motion>", self._move_tooltip)

                # Exibir score no meio do retângulo red_thick
                if voice_scores and v in voice_scores and T in voice_scores[v]:
                    score_value = voice_scores[v][T]
                    score_text = f"{score_value:.2f}"

                    text_x = (tx1 + tx2) / 2
                    text_y = (red_top + red_bottom) / 2

                    self.canvas.create_text(
                        text_x, text_y, text=score_text,
                        font=("Arial", 9, "bold"), fill="#FFFFFF")

            # Criar texto da voz com tooltip
            voice_text = self.canvas.create_text(
                5, y + 6, anchor="w", text=v,
                font=("Arial", 10, "bold"),
                tags=f"voice_text_{v}")

            # Tooltip para nome da voz
            self.canvas.tag_bind(f"voice_text_{v}", "<Enter>",
                                 lambda e, voz=v: self._show_tooltip(e, ', '.join(
                                     nome for nome, dados in self.coristas.items() if dados['voz_atribuida'] == voz)))
            self.canvas.tag_bind(f"voice_text_{v}", "<Leave>", self._hide_tooltip)
            self.canvas.tag_bind(f"voice_text_{v}", "<Motion>", self._move_tooltip)

        self.master.update_idletasks()