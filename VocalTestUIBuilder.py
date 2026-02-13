"""
VocalTestUIBuilder - Responsável por construir a UI de teste vocal
Responsabilidades:
- Criar todos os widgets do teste vocal
- Organizar layout da UI de teste
- Gerenciar referências aos widgets
"""

import tkinter as tk
from tkinter import ttk
from VocalTester import BeltIndicator, VocalTestCore, PitchLineChart

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

    def build(self
              ):
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

        # Checkbox do piano gamificado
        self.piano_game_var = tk.BooleanVar(value=False)
        self.piano_game_check = ttk.Checkbutton(
            state_row,
            text="🎹 MOSTRAR PIANO",
            variable=self.piano_game_var,
        )
        self.piano_game_check.pack(side="left", padx=(15, 0))

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

    def add_pitch_chart(self,
                        parent_frame):
        """Adiciona o gráfico de pitch à UI (separado pois vai em outro frame)."""
        self.pitch_line_chart = PitchLineChart(
            parent_frame,
            width=640,
            height=300,
            min_midi=40,
            max_midi=84
        )
        return self.pitch_line_chart

    def get_widgets(self
                    ):
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
            'status_label': self.status_label,
            'piano_game_var': self.piano_game_var,
            'piano_game_check': self.piano_game_check
        }