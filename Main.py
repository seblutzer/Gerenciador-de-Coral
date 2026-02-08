import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os
import threading
import shutil
import re
from pathlib import Path
from CoristasManager import CoristasManager
from Constants import VOICES, VOICE_BASE_RANGES
from KeyboardVisualizer import KeyboardVisualizer
from RangeVisualizer import RangeVisualizer
from GeneralFunctions import analyze_ranges_with_penalty, note_to_midi, transpose_note, midi_to_note, compute_per_voice_Os_for_T, transpose_key
from VocalTester import VocalTestCore, BeltIndicator, PitchLineChart
from MusicTranspose import AudioAnalyzer

class VoiceRangeApp:
    def __init__(self, master):
        self.analyzer = AudioAnalyzer(root_dir='Musicas')
        self.master = master
        self.master.title("Programa de Transposição Vocal - com Gerenciamento de Coristas")
        self.master.geometry("1000x900")
        self.master.resizable(True, True)

        # Testing Time
        self.testing_time = VocalTestCore.DEFAULT_TESTING_TIME
        self.testing_time_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Gerenciador de coristas
        self.coristas_mgr = CoristasManager()

        # Notebook para abas
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Aba 1: Gerenciar Coristas
        self.frame_coristas = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_coristas, text="Gerenciar Coristas")
        self.setup_coristas_tab()

        # Aba 2: Análise de Transposição
        self.frame_analise = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_analise, text="Análise de Transposição")

        # Dados de música carregados
        self.group_ranges = None
        self.group_extension = None
        self.solistas = None
        self.analysis_all = {}
        self.music_library = []  # música(s) salvas
        self.solist_rows = []  # lista de linhas de Soloists UI
        self.solist_count = 0

        # Dados da música atual
        self.music_name_var = tk.StringVar()
        self.root_var = tk.StringVar()
        self.mode_var = tk.StringVar()

        # Visualização de solistas no painel de análise
        self.setup_analise_tab()
        self._build_solists_ui()
    ### DATA MANAGER ESTRUTURAL
    def _sort_column(self, col_name):
        """Ordena a TreeView pela coluna clicada"""

        # Se clicou na mesma coluna, inverte a direção
        if self.sort_column == col_name:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col_name
            self.sort_reverse = False

        # Obtém os itens da TreeView
        items = []
        for item in self.tree_coristas.get_children():
            values = self.tree_coristas.item(item, 'values')
            items.append((item, values))

        # Define a função de ordenação baseada na coluna
        if col_name == "Range":
            # Para Range, precisa fazer sorting especial
            if not self.sort_reverse:
                # Ordena pela primeira nota (grave para agudo)
                items.sort(key=lambda x: self.coristas_mgr.note_to_number(x[1][1].split("⟷")[0].strip()))
            else:
                # Ordena pela segunda nota (agudo para grave)
                items.sort(key=lambda x: self.coristas_mgr.note_to_number(x[1][1].split("⟷")[1].strip()), reverse=True)
        else:
            # Para outras colunas, ordena alfabeticamente
            col_index = {
                "Nome": 0,
                "Range": 1,
                "Voz Atribuída": 2,
                "Voz(es) Recomendada(s)": 3,
                "Voz(es) Possível(is)": 4
            }
            index = col_index.get(col_name, 0)
            items.sort(key=lambda x: x[1][index], reverse=self.sort_reverse)

        # Remove todos os itens
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        # Reinsere os itens na ordem ordenada
        for item, values in items:
            self.tree_coristas.insert("", "end", values=values)

        # Atualiza o visual do cabeçalho (opcional - adiciona indicador de sort)
        self._atualizar_indicador_sort(col_name)

    def _atualizar_indicador_sort(self, col_name):
        """Atualiza o texto do cabeçalho com indicador de direção"""
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")

        for col in columns:
            if col == col_name:
                # Adiciona indicador
                if col == "Range" and not self.sort_reverse:
                    texto = f"{col} ▲"  # Primeira nota (grave para agudo)
                elif col == "Range" and self.sort_reverse:
                    texto = f"{col} ▼"  # Segunda nota (agudo para grave)
                else:
                    texto = f"{col} {'▲' if not self.sort_reverse else '▼'}"
            else:
                texto = col

            self.tree_coristas.heading(col, text=texto)

    def _on_noise_gate_changed(self, value):
        """Atualiza o NOISE_GATE_THRESHOLD quando o slider é movido"""
        try:
            new_threshold = float(value)
            # Atualiza o valor na classe VocalTestCore
            VocalTestCore.NOISE_GATE_THRESHOLD = new_threshold

            # Se houver um teste em andamento, atualiza também na instância
            if self.vocal_tester is not None:
                self.vocal_tester.NOISE_GATE_THRESHOLD = new_threshold

            # Atualiza o label com o valor formatado
            self.noise_gate_value_label.config(text=f"{new_threshold:.4f}")
        except ValueError:
            pass

    def setup_coristas_tab(self):
        """Configura a aba de gerenciamento de coristas com frames independentes lado a lado"""
        # Container principal com duas colunas independentes
        main_frame = ttk.Frame(self.frame_coristas)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: Adicionar/Editar Corista
        left_frame = ttk.LabelFrame(main_frame, text="Adicionar/Editar Corista", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Right: Teste Vocal Integrado
        right_frame = ttk.LabelFrame(main_frame, text="Teste Vocal Integrado", padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Ajusta peso das colunas para manter os frames proporcionais
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # ===== LEFT FRAME: Campos Adicionar/Editar Corista =====
        ttk.Label(left_frame, text="Nome:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entrada_nome = ttk.Entry(left_frame, width=30)
        self.entrada_nome.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Min (ex: G3):").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entrada_min = ttk.Entry(left_frame, width=15)
        self.entrada_min.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Max (ex: C5):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entrada_max = ttk.Entry(left_frame, width=15)
        self.entrada_max.grid(row=1, column=3, padx=5, pady=5)

        # Botão Adicionar na esquerda
        btn_add = ttk.Button(left_frame, text="Adicionar Corista", command=self.add_corista)
        btn_add.grid(row=2, column=0, columnspan=4, pady=10)

        # ===== RIGHT FRAME: Teste Vocal Integrado =====
        # Estado e repetição
        state_row = ttk.Frame(right_frame)
        state_row.pack(anchor="w", pady=(0, 5))

        ttk.Label(state_row, text="Tempo de teste (s):").pack(side="left", padx=(8, 0))
        self.testing_time_cb = ttk.Combobox(state_row, values=self.testing_time_values, state="readonly", width=5)
        self.testing_time_cb.pack(side="left", padx=(8, 0))
        self.testing_time_cb.current(self.testing_time_values.index(self.testing_time))
        self.testing_time_cb.bind("<<ComboboxSelected>>", self._on_testing_time_changed)

        self.btn_repeat_tone = ttk.Button(state_row, text="🔁 Repetir Tom",
                                          command=self.repeat_tone_vocal)
        self.btn_repeat_tone.pack(side="left", padx=(8, 0))

        # ================= Botões de Teste =================

        buttons_row = ttk.Frame(right_frame)
        buttons_row.pack(fill="x", pady=5)

        self.btn_start_test = ttk.Button(buttons_row, text="🏁 Iniciar Teste",
                                         command=self.start_vocal_test)
        self.btn_start_test.grid(row=0, column=0, padx=3, sticky="ew")

        self.btn_quick_test = ttk.Button(buttons_row, text="⚡ Teste Rápido",
                                         command=self.start_quick_vocal_test)
        self.btn_quick_test.grid(row=0, column=1, padx=3, sticky="ew")

        buttons_row.columnconfigure(0, weight=1)
        buttons_row.columnconfigure(1, weight=1)

        # ===== Botões de marcação =====
        marking_row = ttk.Frame(right_frame)
        marking_row.pack(fill="x", pady=5)

        self.btn_too_low = ttk.Button(marking_row, text="🔽️ Grave D.",
                                      command=self.mark_too_low_vocal, state='disabled')
        self.btn_too_low.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_too_high = ttk.Button(marking_row, text="🔼 Agudo D.",
                                       command=self.mark_too_high_vocal, state='disabled')
        self.btn_too_high.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_stop_test = ttk.Button(marking_row, text="🛑 Parar",
                                        command=self.stop_vocal_test, state='disabled')
        self.btn_stop_test.grid(row=0, column=2, padx=2, sticky="ew")

        marking_row.columnconfigure(0, weight=1)
        marking_row.columnconfigure(1, weight=1)
        marking_row.columnconfigure(2, weight=1)
        # ===== CONTROLE DE ABAFAMENTO DO MICROFONE (NOISE GATE) =====
        noise_gate_frame = ttk.LabelFrame(right_frame, text="Controle de Abafamento", padding=8)
        noise_gate_frame.pack(fill="x", pady=5)

        # Label informativo
        ttk.Label(noise_gate_frame, text="Nível de abafamento do microfone:",
                  font=("Arial", 9)).pack(anchor="w", padx=5)

        # Frame para slider e valor
        slider_frame = ttk.Frame(noise_gate_frame)
        slider_frame.pack(fill="x", padx=5, pady=5)

        # Slider
        self.noise_gate_slider = tk.Scale(
            slider_frame,
            from_=0,
            to=0.02,
            resolution=0.0001,
            orient="horizontal",
            length=300,
            command=self._on_noise_gate_changed
        )
        self.noise_gate_slider.set(VocalTestCore.NOISE_GATE_THRESHOLD)
        self.noise_gate_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Label para exibir valor atual
        self.noise_gate_value_label = ttk.Label(
            slider_frame,
            text=f"{VocalTestCore.NOISE_GATE_THRESHOLD:.4f}",
            font=("Arial", 9, "bold"),
            foreground="#2E86AB",
            width=8
        )
        self.noise_gate_value_label.pack(side="left")

        # ===== INDICADOR VISUAL (BELT) =====
        self.belt_indicator = BeltIndicator(right_frame, width=300, height=50)
        # Opcional: definir o alcance de semitons que o belt deve cobrir
        self.belt_indicator.set_range(-12, 12)
        self.belt_indicator.pack(pady=5)

        # Visualizador do pitch ao longo do tempo
        self.pitch_line_chart = PitchLineChart(left_frame, width=640, height=300,
                                               min_midi=40, max_midi=84)
        self.pitch_line_chart.grid(row=3, column=0, columnspan=5, pady=10)

        # ===== PROGRESSO DE TEMPO =====
        self.time_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.time_var,
                                            maximum=100, length=300, mode='determinate')
        self.progress_bar.pack(pady=3)

        self.time_label = ttk.Label(right_frame, text=f"Tempo: 0.0s / {self.testing_time}.0s",
                                    font=("Arial", 8))
        self.time_label.pack(pady=(0, 5))

        # ===== NOTAS ESPERADA E DETECTADA =====
        notes_frame = ttk.Frame(right_frame)
        notes_frame.pack(fill="x", pady=5)

        ttk.Label(notes_frame, text="Esperada:", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        self.expected_note_label = ttk.Label(notes_frame, text="--", font=("Arial", 9),
                                             foreground="#2E86AB")
        self.expected_note_label.pack(side="left", padx=2)

        ttk.Label(notes_frame, text="→", font=("Arial", 10)).pack(side="left", padx=5)

        ttk.Label(notes_frame, text="Detectada:", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        self.detected_note_label = ttk.Label(notes_frame, text="--", font=("Arial", 9),
                                             foreground="#888")
        self.detected_note_label.pack(side="left", padx=2)

        # ===== STATUS =====
        self.status_label = ttk.Label(right_frame, text="Aguardando...",
                                      font=("Arial", 9), foreground="#666")
        self.status_label.pack(pady=5)

        # Inicializa a instância do VocalTestCore
        self.vocal_tester = None

        # TABELA
        # Tabela de coristas
        table_frame = ttk.LabelFrame(self.frame_coristas, text="Coristas Cadastrados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        group_frame = ttk.Frame(table_frame, padding=10)
        group_frame.pack(side='left', fill="y", padx=10, pady=10)

        # ===== NOVO: Grupo de Coristas (carrega de coristas_music_data.json) =====
        ttk.Label(group_frame, text="Grupo de Coristas:").pack()
        # combobox de grupos carregados do coristas_music_data.json
        self.grupos_var = tk.StringVar()
        self.grupo_combo = ttk.Combobox(group_frame, textvariable=self.grupos_var, state="readonly", width=20)
        groups = self.coristas_mgr.read_data(extract='grupos', group_list=True)
        self.grupo_combo['values'] = groups
        if groups:
            self.grupo_combo.current(0)
        self.grupo_combo.pack()
        self.grupo_combo.bind("<<ComboboxSelected>>", self._on_group_selected)
        self.grupo_nome_var = tk.StringVar()

        # Botão "Adicionar Grupo"
        self.add_group_btn = ttk.Button(group_frame, text="Adicionar Grupo", command=self.adicionar_grupo)
        self.add_group_btn.pack(pady=2)

        # Cria Treeview
        self.sort_column = None
        self.sort_reverse = False
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="headings")

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(col, text=col)
            # Bind ao clique do cabeçalho
            self.tree_coristas.heading(col, command=lambda c=col: self._sort_column(c))

        self.tree_coristas.pack(fill="both", expand=True)

        # Atalhos da treeview
        self.tree_coristas.bind("<Double-1>", self._on_double_click_corista)
        self.tree_coristas.bind("<Delete>", self.on_delete_key)

        # Botões de ação
        button_frame = ttk.Frame(self.frame_coristas)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(group_frame, text="Remover Selecionado", command=self.remove_corista).pack(pady=2)
        ttk.Button(group_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(pady=2)

        # Determine o grupo atual (pode vir do combobox de grupo ou do campo de nome do grupo)
        grupo_selecionado = None
        if hasattr(self, "grupo_combo"):
            grupo_selecionado = self.grupo_combo.get()
        elif hasattr(self, "grupo_nome_var"):
            grupo_selecionado = self.grupo_nome_var.get()

        # Atualiza o CoristasManager para o grupo atual
        if grupo_selecionado:
            self.coristas_mgr.set_group(grupo_selecionado)
        else:
            # Caso não haja grupo definido, ainda assim tente manter o estado
            self.coristas_mgr.set_group("")

        self.grupo_nome_var.set(self.coristas_mgr.grupo)

        # Carrega dados iniciais
        self.reload_coristas_table()

    def setup_analise_tab(self):
        """Configura a aba de análise de transposição"""
        # Cabeçalho
        header = ttk.Label(self.frame_analise, text="Ajuste de tom e alcance por voz (compensação por penalidade)",
                           font=("Arial", 12, "bold"))
        header.pack(pady=10)

        # Slider de transposição
        self.t_slider = tk.Scale(self.frame_analise, from_=-11, to=11, orient="horizontal", label="Transposição (semítons)", command=self.on_t_change, length=600)
        self.t_slider.set(0)
        self.t_slider.pack(fill="x", padx=10, pady=10)

        # Novo container para manter dois painéis lado a lado
        main_pane = ttk.Frame(self.frame_analise)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # Faixas da peça (à esquerda)
        ranges_frame = ttk.LabelFrame(main_pane, text="Faixa da Música por Voz", padding=10)
        ranges_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Biblioteca de músicas (à direita)
        library_frame = ttk.LabelFrame(main_pane, text="Biblioteca de Músicas", padding=10)
        library_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Distribuição igual entre as duas colunas
        main_pane.columnconfigure(0, weight=1)
        main_pane.columnconfigure(1, weight=1)

        # Placeholder do nome da música
        self.music_name_var = tk.StringVar()
        self.music_name_entry = tk.Entry(library_frame, textvariable=self.music_name_var, width=30, fg="grey")
        self.music_name_placeholder = "Nome da música"
        self.music_name_entry.insert(0, self.music_name_placeholder)

        def _clear_name(event):
            if self.music_name_entry.get() == self.music_name_placeholder:
                self.music_name_entry.delete(0, tk.END)
                self.music_name_entry.config(fg="black")

        def _fill_name(event):
            val = self.music_name_entry.get()
            if val == "":
                self.music_name_entry.insert(0, self.music_name_placeholder)
                self.music_name_entry.config(fg="grey")
                self.music_name_var.set("")  # keep var sem placeholder
            else:
                # Atualiza a StringVar com o valor real (ignora o placeholder)
                self.music_name_var.set(val)

        self.music_name_entry.bind("<FocusIn>", _clear_name)
        self.music_name_entry.bind("<FocusOut>", _fill_name)
        self.music_name_entry.grid(row=0, column=0, padx=5, pady=5)  # ocupa o espaço da antiga label

        # Combobox com placeholder
        self.music_var = tk.StringVar()
        self.music_combo = ttk.Combobox(library_frame, textvariable=self.music_var, state="readonly", width=25)
        self.load_music_library()
        self.music_combo.set("-- Selecione uma música --")
        self.music_combo.grid(row=1, column=0, padx=5, pady=5)
        self.music_combo.bind("<<ComboboxSelected>>",
                              lambda e: self.load_music_ranges_for_selection(self.music_combo.get()))

        # Botões com ícones (em vez de textos)
        btn_save = ttk.Button(library_frame, text='💾', width=5, command=lambda: self.save_music_ranges_to_json(
            piece_name=(self.music_name_var.get() if self.music_name_var.get() != self.music_name_placeholder else "")
        ))
        btn_save.grid(row=0, column=1, padx=5, pady=5)

        btn_load = ttk.Button(library_frame, text='📂', command=self.load_voice_audio_files, width=5)
        btn_load.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(library_frame, text="Tom original (raiz):").grid(row=2, column=0, padx=5, pady=5)
        self.root_var = tk.StringVar()
        self.root_combo = ttk.Combobox(library_frame, textvariable=self.root_var, state="readonly", width=8,
                                       values=["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab",
                                               "A", "A#", "Bb", "B"])
        self.root_combo.current(0)
        self.root_combo.grid(row=2, column=1, padx=5, pady=5)
        self.root_combo.bind("<<ComboboxSelected>>", self._on_root_selected)

        ttk.Label(library_frame, text="Modo:").grid(row=3, column=0, padx=5, pady=5)
        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(library_frame, textvariable=self.mode_var, state="readonly", width=10,
                                       values=["maior", "menor"])
        self.mode_combo.current(0)
        self.mode_combo.grid(row=3, column=1, padx=5, pady=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        # Min/Max por voz: 3 linhas x 2 vozes (total de 6 vozes)
        self.voice_vars = {}

        for idx, v in enumerate(VOICES):
            row = idx // 2  # 3 linhas
            col = idx % 2  # 2 colunas
            frame_v = ttk.Frame(ranges_frame)
            frame_v.grid(row=row, column=col, padx=10, pady=5, sticky="w")

            ttk.Label(frame_v, text=f"{v}:").pack()

            min_entry = ttk.Entry(frame_v, width=10)
            min_entry.pack(side="left", padx=2)
            max_entry = ttk.Entry(frame_v, width=10)
            max_entry.pack(side="left", padx=2)

            # Valores padrão
            min_entry.insert(0, "")
            max_entry.insert(0, "")

            self.voice_vars[v] = {"min": min_entry, "max": max_entry}
            # Após criar os entries
            #self.voice_vars[v]["min_value"] = ""
            #self.voice_vars[v]["max_value"] = ""

            #self.bind_entry_to_var(min_entry, self.voice_vars[v], "min_value")
            #self.bind_entry_to_var(max_entry, self.voice_vars[v], "max_value")

        # ===== SOLISTAS (layout ajustado para refletir grupo quando carregado) =====
        # Novo: Combobox de número de solistas (0 a 5)
        solo_frame_header = ttk.LabelFrame(main_pane, padding=10, text='Solistas')
        solo_frame_header.grid(row=0, column=1, pady=5, padx=5, sticky="nsew")
        self.solist_count_cb = ttk.Combobox(solo_frame_header, values=[0,1,2,3,4,5], width=5, state="readonly")
        self.solist_count_cb.pack(side="left")
        self.solist_count_cb.set(0)
        self.solist_count_cb.bind("<<ComboboxSelected>>", self._on_solists_count_changed)

        # Frame para os solistas (dinâmico)
        self.solist_frame = ttk.Frame(solo_frame_header, padding=10)
        self.solist_frame.pack()

        # Botões de ação (continua)
        action_frame = ttk.Frame(self.frame_analise)
        action_frame.pack(fill="x", padx=10, pady=10)

        # Botão dinâmico de uso de coristas/base
        self.dynamic_ranges_button = ttk.Button(action_frame, text="Vozes Grupo",
                                                command=self.toggle_group_or_voice_ranges)
        self.dynamic_ranges_button.pack(side="left", padx=5)

        ttk.Button(action_frame, text="Executar análise", command=self.run_analysis).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Limpar resultados", command=self.clear_results).pack(side="left", padx=5)

        # Visualizador
        self.visualizer = RangeVisualizer(self.frame_analise, voices=VOICES, base_ranges=VOICE_BASE_RANGES, coristas=self.coristas_mgr.coristas)

        # Biblioteca de músicas (à direita)
        result_frame = ttk.LabelFrame(main_pane, text="Resultados", padding=10)
        result_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.results_text = tk.Text(result_frame, height=9, width=50, wrap="word", font=("Consolas", 10))
        self.results_text.pack(anchor="w", padx=5, pady=3, fill="x")

        self.results_text.insert("end", "Resultados: Informe os ranges vocais e a faixa da música por voz.\n")

        self.current_result = None

    def _build_solists_ui(self):
        """
        Constrói/Atualiza a UI para os solistas com base no número indicado na combobox.
        """
        # Limpa conteúdos existentes
        for child in self.solist_frame.winfo_children():
            child.destroy()
        self.solist_rows.clear()

        count = int(self.solist_count_cb.get()) if self.solist_count_cb.get() != "" else 0
        self.solist_count = count

        coristas_nomes = [c for c in self.coristas_mgr.coristas] or []
        corista_choices = ["Selecionar..."] + coristas_nomes

        for i in range(count):
            row_frame = ttk.Frame(self.solist_frame)
            row_frame.pack(fill="x", pady=3)

            ttk.Label(row_frame, text=f"Solista {i+1}:").pack(side="left", padx=(0,5))

            cb = ttk.Combobox(row_frame, values=corista_choices, state="readonly", width=20)
            cb.current(0)  # sem seleção
            cb.pack(side="left", padx=(0,5))

            min_ent = ttk.Entry(row_frame, width=8)
            min_ent.pack(side="left", padx=(0,5))

            max_ent = ttk.Entry(row_frame, width=8)
            max_ent.pack(side="left", padx=(0,5))

            self.solist_rows.append({
                "cb": cb,
                "min": min_ent,
                "max": max_ent,
            })

    def _on_solists_count_changed(self, event=None):
        self._build_solists_ui()
    ### DATA MANAGER SAVE/LOAD
    def _on_group_selected(self, event=None):
        """Atualiza estado ao selecionar grupo e refaz UI de solistas se necessário."""
        grupo = self.grupo_combo.get()
        self.grupo_nome_var.set(grupo)
        self.coristas_mgr.grupo = grupo
        data = self.coristas_mgr.read_data()
        self.music_library = {nome: info for nome, info in data.get("musicas", {}).items() if info.get("grupo") == grupo}
        self.music_names = list(self.music_library.keys())
        # versão: coristas é um dicionário, não lista
        self.coristas_mgr.coristas = data["grupos"][grupo]

        # limpar músicas
        # Resetar músicas
        self.music_name_var.set(self.music_name_placeholder)
        self.music_name_entry.delete(0, tk.END)
        self.music_name_entry.config(fg="black")
        self.music_name_entry.insert(0, self.music_name_placeholder)
        self.music_var.set('')
        self.music_combo.set("-- Selecione uma música --")
        self._clear_music_fields()

        # Atualisar lista de músicas
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names

        # Atualiza a UI dos solistas para refletir o grupo atual
        self.reload_coristas_table()

    def add_corista(self):
        nome = self.entrada_nome.get().strip()
        range_min = self.entrada_min.get().strip().upper()
        range_max = self.entrada_max.get().strip().upper()

        if not nome or not range_min or not range_max:
            messagebox.showerror("Erro", "Preenchimento obrigatório em todos os campos")
            return

        success, result = self.coristas_mgr.add_corista(nome, range_min, range_max)
        if success:
            voz_calc = result['voz_calculada']
            vozes_rec = result.get('vozes_recomendadas', [])
            vozes_poss = result.get('vozes_possiveis', [])

            msg = f"Corista '{nome}' adicionado!\n\n"
            msg += f"Voz Calculada: {voz_calc}\n\n"
            msg += f"Vozes Recomendadas: {', '.join(vozes_rec) if vozes_rec else 'Nenhuma'}\n"
            msg += f"Vozes Possíveis: {', '.join([v for v in vozes_poss]) if vozes_poss else 'Nenhuma'}"

            messagebox.showinfo("Sucesso", msg)
            self.entrada_nome.delete(0, "end")
            self.entrada_min.delete(0, "end")
            self.entrada_max.delete(0, "end")
            self.reload_coristas_table()

    def remove_corista(self):
        selection = self.tree_coristas.selection()

        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para remover")
            return
        item = selection[0]

        vals = self.tree_coristas.item(item, "values")
        corista_nome = vals[0] if vals else None
        sucesso = self.coristas_mgr.remove_corista(corista_nome)
        if sucesso:
            self.music_library = sucesso['musicas']
            self.reload_coristas_table()
            messagebox.showinfo("Sucesso", "Corista removido!")

    def reload_coristas_table(self):
        # Recarrega a visualização da tabela com os coristas do grupo atual
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        for corista in self.coristas_mgr.coristas:
            self.tree_coristas.insert("", "end", values=(
                corista,
                self.coristas_mgr.coristas[corista]['range_min'] + "  ⟷  " + self.coristas_mgr.coristas[corista]['range_max'],
                self.coristas_mgr.coristas[corista]['voz_atribuida'],
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_recomendadas']),
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_possiveis']))
            )

    def save_music_ranges_to_json(self, piece_name=None):
        """
        Orquestra a coleta de dados e delegação para CoristasManager.
        Responsável apenas por: UI, validações de entrada, confirmação.
        """
        # ===== COLETA DE DADOS DA UI =====

        # 1) Nome da música
        name = piece_name or "Untitled"
        if name == "Untitled":
            messagebox.showerror("Erro", "Preencha o nome da música")
            return

        # 2) Ranges de vozes
        piece_ranges = {}
        for voz in VOICES:
            min_val = self.voice_vars[voz]["min"].get().upper().strip()
            max_val = self.voice_vars[voz]["max"].get().upper().strip()
            if min_val or max_val:  # Se preenchido
                piece_ranges[voz] = {"min": min_val, "max": max_val}

        if not piece_ranges:
            messagebox.showwarning("Aviso", "Preencha ao menos um range de voz")
            return

        # 3) Solistas
        solistas = {}
        for row in getattr(self, 'solist_rows', []) or []:
            cb_widget = row.get('cb')
            min_widget = row.get('min')
            max_widget = row.get('max')

            if cb_widget is None:
                continue

            try:
                cb_name = cb_widget.get()
                min_val = min_widget.get() if min_widget else ""
                max_val = max_widget.get() if max_widget else ""

                # Só adiciona se houver nome de solista
                if cb_name and cb_name != "Selecionar...":
                    solistas[cb_name] = [min_val, max_val]
            except Exception:
                pass

        # 4) Voices (mapeamento de coristas por voz)
        voices = {}
        for corista in getattr(self.coristas_mgr, 'coristas', []) or []:
            nome = corista
            voz_atribuida = self.coristas_mgr.coristas[nome].get('voz_atribuida')
            if voz_atribuida and nome:
                voices.setdefault(voz_atribuida, []).append(nome)

        # 5) Música info
        orig_root = self.root_var.get()
        orig_mode = self.mode_var.get()

        # ===== VERIFICAR SE JÁ EXISTE =====
        existe = self.coristas_mgr.check_music_exists(name)

        if existe:
            substituir = messagebox.askyesno(
                "Música Existente",
                f"A música '{name}' já existe. Deseja substituir?"
            )
            if not substituir:
                messagebox.showinfo("Cancelado", "Operação cancelada.")
                return

        # ===== DELEGAÇÃO PARA CORISTASMANAGER =====
        sucesso, mensagem = self.coristas_mgr.save_music_ranges_to_json(
            music_name=name,
            ranges=piece_ranges,
            solistas=solistas,
            vozes_por_corista=voices,
            root=orig_root,
            mode=orig_mode
        )

        if sucesso:
            messagebox.showinfo("Sucesso", mensagem)
            # Atualizar biblioteca após salvar
            self.load_music_library()
        else:
            messagebox.showerror("Erro", mensagem)

    def load_music_library(self):
        """Carrega a biblioteca de músicas do coristas_music_data.json."""
        # Limpa/reinicializa listas
        self.music_library.clear()
        self.music_names = []

        data, musicas, groups = self.coristas_mgr.read_data(extract='musicas', all_in=True, group_list=True)
        grupo = self.grupo_nome_var.get() if hasattr(self.grupo_nome_var, "get") else self.grupo_nome_var
        self.music_library = {nome: info for nome, info in musicas.items() if info.get("grupo") == grupo}
        self.music_names = list(self.music_library.keys())

        # Carrega grupos: atualiza combobox de grupos com nomes disponíveis
        if hasattr(self, "grupo_combo") and groups:
            self.grupo_combo['values'] = groups

        # Atualiza combobox se existir
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names

    def load_music_ranges_for_selection(self, name):
        """Carrega os ranges de uma música selecionada na combobox."""

        # Validação básica
        if not name or name.startswith("--"):
            messagebox.showwarning("Aviso", "Nenhuma música válida selecionada.")
            self._clear_music_fields()
            return

        item = self.music_library.get(name)

        if item is None:
            messagebox.showerror("Erro", f"Música '{name}' não encontrada na biblioteca.")
            return

        # Preenche ranges
        ranges = item.get("ranges", {})
        for voice, vr in ranges.items():
            min_val = vr.get("min", "") if isinstance(vr, dict) else ""
            max_val = vr.get("max", "") if isinstance(vr, dict) else ""

            # Suporte a formatos alternativos
            if not min_val and isinstance(vr, dict):
                min_val = vr.get("0", "")
            if not max_val and isinstance(vr, dict):
                max_val = vr.get("1", "")

            if min_val == "" and max_val == "":
                continue

            if voice in self.voice_vars:
                self.voice_vars[voice]["min"].delete(0, "end")
                self.voice_vars[voice]["min"].insert(0, min_val)
                self.voice_vars[voice]["max"].delete(0, "end")
                self.voice_vars[voice]["max"].insert(0, max_val)

        # Determina e aplica grupo da música
        grupo = item.get("grupo")
        if grupo:
            # Tenta selecionar o grupo na combobox, se existir
            grupos_disponiveis = self.coristas_mgr.read_data(extract='grupos', group_list=True)
            if grupo in grupos_disponiveis:
                self.grupo_combo.set(grupo)
            else:
                # Se grupo não estiver na lista, mantém atual e seta nome do grupo
                self.grupo_combo.set(grupo)
                self.grupo_nome_var.set(grupo)

            self.grupo_nome_var.set(grupo)
        else:
            # Se não houver grupo definido, mantém o estado atual
            pass

        # Atualiza o name da música (campo)
        self.music_name_var.set(name)

        # Atualiza o tom da música (campo)
        self.root_var.set(item['root'])

        # Atualiza o modo da música (campo)
        self.mode_var.set(item['mode'])

        # Novo: carregar solistas da música (robusto para diferentes formatos de solistas)
        solistas_raw = item.get("solistas", None)

        # Atualiza UI de solistas com a lista normalizada
        if hasattr(self, "solist_count_cb"):
            cnt = min(max(len(solistas_raw.keys()), 0), 5)  # 0 a 5
            self.solist_count_cb.set(cnt)
            self._on_solists_count_changed()
            self.solistas = {}
            for idx, name in enumerate(solistas_raw):
                if idx >= len(self.solist_rows):
                    break
                row = self.solist_rows[idx]
                # Define o nome do solista
                if "cb" in row:
                    row["cb"].set(name)
                # Define range mínimo e máximo
                if "min" in row:
                    row["min"].delete(0, "end")
                    row["min"].insert(0, solistas_raw[name][0])
                if "max" in row:
                    row["max"].delete(0, "end")
                    row["max"].insert(0, solistas_raw[name][1])
                self.solistas[name] = (solistas_raw[name][0], solistas_raw[name][1])

        # Atribuir as vozes de cada corista para essa música
        voices = item.get("voices", {})
        for voice in voices:
            for name in voices[voice]:
                if self.coristas_mgr.coristas[name]['voz_atribuida'] != voice:
                    self.coristas_mgr.coristas[name]['voz_atribuida'] = voice

        self.reload_coristas_table()

        # Executa a análise com os dados carregados
        if getattr(self, '_use_group_ranges', None):
            self._use_group_ranges = not self._use_group_ranges
            self.toggle_group_or_voice_ranges()
        else:
            self.run_analysis()

    def read_voice_ranges(self):
        ranges = {}
        for v in VOICES:
            min_str = self.voice_vars[v]["min"].get().strip()
            max_str = self.voice_vars[v]["max"].get().strip()
            #if not min_str or not max_str:
            #    raise ValueError(f"Faixa de {v} está vazia.")
            ranges[v] = (min_str, max_str)
        return ranges

    # DATA MANAGER FUNCTIONS
    def edit_corista_voz(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        item = selection[0]

        # Obter o nome do corista a partir da treeview
        vals = self.tree_coristas.item(item, "values")
        corista_nome = vals[0] if vals else None

        if corista_nome is None:
            messagebox.showwarning("Aviso", "Corista inválido selecionado")
            return

        # Acesso ao dicionário reestruturado: coristas_mgr.coristas é dict {nome: {...}}
        corista = self.coristas_mgr.coristas.get(corista_nome)
        if corista is None:
            messagebox.showwarning("Aviso", "Corista não encontrado no gerenciador")
            return

        # Janela de diálogo para edição de voz
        dialog = tk.Toplevel(self.master)
        dialog.title("Editar Voz do Corista")
        dialog.geometry("900x750")

        # ===== Frame de Dados do Corista =====
        dados_frame = ttk.LabelFrame(dialog, text="Dados do Corista", padding=10)
        dados_frame.pack(fill="x", padx=10, pady=10)

        # Editar Nome
        ttk.Label(dados_frame, text="Nome:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5,
                                                                              pady=5)
        var_nome = tk.StringVar(value=corista_nome)
        entry_nome = ttk.Entry(dados_frame, textvariable=var_nome, width=30, font=("Arial", 10))
        entry_nome.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Editar Range Mínimo
        ttk.Label(dados_frame, text="Range Mínimo:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w",
                                                                                      padx=5, pady=5)
        var_range_min = tk.StringVar(value=corista['range_min'])
        entry_range_min = ttk.Entry(dados_frame, textvariable=var_range_min, width=30, font=("Arial", 10))
        entry_range_min.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Editar Range Máximo
        ttk.Label(dados_frame, text="Range Máximo:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w",
                                                                                      padx=5, pady=5)
        var_range_max = tk.StringVar(value=corista['range_max'])
        entry_range_max = ttk.Entry(dados_frame, textvariable=var_range_max, width=30, font=("Arial", 10))
        entry_range_max.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        dados_frame.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="💡 Dica: Use o teste vocal na aba de Adicionar Corista para determinar o range",
                  font=("Arial", 8), foreground="#666").pack(pady=5)

        # ===== Frame de Voz Calculada =====
        voz_calc_frame = ttk.LabelFrame(dialog, text="Voz Calculada", padding=5)
        voz_calc_frame.pack(fill="x", padx=10, pady=5)

        label_voz_calc = ttk.Label(voz_calc_frame, text=f"Voz Calculada: {corista['voz_calculada']}",
                                   font=("Arial", 10, "bold"))
        label_voz_calc.pack(anchor="w", padx=10, pady=5)

        # Separador
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista.get('voz_atribuida'))

        # ===== Visualizador de teclado =====
        keyboard = KeyboardVisualizer(dialog)

        # Frame para as opções de voz
        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Variável para armazenar os dados de vozes compatíveis
        vozes_data = {
            'recomendadas': [],
            'possiveis': []
        }

        # Função para atualizar a lista de vozes na interface
        def update_vozes_display():
            # Obter novos valores
            range_min = var_range_min.get()
            range_max = var_range_max.get()

            # Validação básica
            try:
                note_to_midi(range_min)
                note_to_midi(range_max)
                if note_to_midi(range_min) > note_to_midi(range_max):
                    return False
            except:
                return False

            # Calcular vozes compatíveis
            vozes_recomendadas, vozes_possiveis = self.coristas_mgr.calculate_compatible_voices(range_min, range_max, True)
            vozes_data['recomendadas'] = vozes_recomendadas
            vozes_data['possiveis'] = vozes_possiveis

            # Calcular nova voz calculada
            nova_voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0][0] if vozes_possiveis else VOICES[0])

            # Atualizar label de voz calculada
            label_voz_calc.config(text=f"Voz Calculada: {nova_voz_calculada}")

            # Se a voz atribuída não está mais compatível, redefine para a calculada
            voz_atual = var_voz.get()
            todas_vozes = vozes_recomendadas + [v[0] for v in vozes_possiveis]
            if voz_atual not in todas_vozes:
                var_voz.set(nova_voz_calculada)

            # Limpar frame de vozes antigo
            for widget in vozes_frame.winfo_children():
                widget.destroy()

            # Reconstruir radiobuttons com novas vozes
            # RECOMENDADAS
            if vozes_recomendadas:
                ttk.Label(vozes_frame, text="✓ Recomendadas (Encaixe Perfeito)",
                          font=("Arial", 11, "bold"), foreground="green").pack(anchor="w", pady=(10, 5))
                for v in vozes_recomendadas:
                    def on_select_recomendada(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(vozes_frame, text=v, variable=var_voz, value=v,
                                    command=on_select_recomendada).pack(anchor="w", padx=50, pady=3)

            # POSSÍVEIS
            if vozes_possiveis:
                ttk.Label(vozes_frame, text="⚠ Possíveis (com ressalva)",
                          font=("Arial", 11, "bold"), foreground="orange").pack(anchor="w", pady=(10, 5))
                for v, diff, obs in vozes_possiveis:
                    frame_poss = ttk.Frame(vozes_frame)
                    frame_poss.pack(anchor="w", padx=40, pady=3, fill="x")

                    def on_select_possivel(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(frame_poss, text=v, variable=var_voz, value=v,
                                    command=on_select_possivel).pack(side="left")
                    ttk.Label(frame_poss, text=f"({obs})", font=("Arial", 9),
                              foreground="gray").pack(side="left", padx=5)

            # Atualizar teclado
            voz_selecionada = var_voz.get()
            if voz_selecionada:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_selecionada]
                keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

            return True

        # Vinculação de eventos para validação e atualização em tempo real
        def on_range_changed(*args):
            try:
                update_vozes_display()
            except Exception as e:
                # Silencioso durante digitação, evita erro durante edição
                pass

        var_range_min.trace('w', on_range_changed)
        var_range_max.trace('w', on_range_changed)

        # Atualizar a exibição inicial
        update_vozes_display()

        def confirm():
            novo_nome = var_nome.get().strip()
            novo_range_min = var_range_min.get().strip().upper()
            novo_range_max = var_range_max.get().strip().upper()
            nova_voz = var_voz.get()

            # Validações
            if not novo_nome:
                messagebox.showerror("Erro", "Nome do corista não pode estar vazio")
                return

            # Validação de notas
            NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|B)?[2-7])?$")
            invalids = []
            if not NOTA_PATTERN.fullmatch(novo_range_min):
                invalids.append(novo_range_min)
            if not NOTA_PATTERN.fullmatch(novo_range_max):
                invalids.append(novo_range_max)

            if invalids:
                msgs = f"'{' e '.join(invalids)}' são inválidos!" if len(
                    invalids) > 1 else f"'{invalids[0]}' é inválido!"
                messagebox.showerror("Nota inexistente",
                                     msgs + "\nEsperado: uma letra A-G seguida de um número 2-7.\n")
                return

            # Padronizar bemois em sustenidos
            novo_range_min = self.coristas_mgr._note_to_sharp(novo_range_min)
            novo_range_max = self.coristas_mgr._note_to_sharp(novo_range_max)

            # Validar ranges
            try:
                note_to_midi(novo_range_min)
                note_to_midi(novo_range_max)
                if note_to_midi(novo_range_min) > note_to_midi(novo_range_max):
                    raise ValueError(f"Range inválido: {novo_range_min} > {novo_range_max}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao validar range: {str(e)}")
                return

            try:
                # Se o nome mudou, precisamos renomear no gerenciador
                if novo_nome != corista_nome:
                    # Verificar se novo nome já existe
                    if novo_nome in self.coristas_mgr.coristas:
                        messagebox.showerror("Erro", f"Corista '{novo_nome}' já existe!")
                        return
                    # Remover antigo e adicionar com novo nome
                    self.coristas_mgr.coristas.pop(corista_nome)

                # Recalcular vozes compatíveis com a lógica de add_corista
                vozes_recomendadas, vozes_possiveis = self.coristas_mgr.calculate_compatible_voices(
                    novo_range_min, novo_range_max)
                all_compatible = vozes_recomendadas + [v[0] for v in vozes_possiveis]
                voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                    vozes_possiveis[0][0] if vozes_possiveis else VOICES[0])

                # Atualizar dados do corista
                corista_atualizado = {
                    'range_min': novo_range_min,
                    'range_max': novo_range_max,
                    'voz_calculada': voz_calculada,
                    'voz_atribuida': nova_voz,
                    'vozes_recomendadas': vozes_recomendadas,
                    'vozes_possiveis': vozes_possiveis
                }

                self.coristas_mgr.coristas[novo_nome] = corista_atualizado
                self.coristas_mgr.save_corista(corista_nome=novo_nome, replace=corista_nome)

                # Se houve mudança de nome, remover arquivo antigo
                if novo_nome != corista_nome:
                    self.coristas_mgr.remove_corista(corista_nome)

                self.reload_coristas_table()
                self.coristas_mgr.save_corista(corista_nome=novo_nome)

                # Atualizar ranges de grupo/voz se necessário
                if self.music_name_var.get() != "Nome da música" and self.music_name_var.get() != "":
                    self.toggle_group_or_voice_ranges()
                    if not self._use_group_ranges:
                        self.toggle_group_or_voice_ranges()

                self.load_music_library()

                messagebox.showinfo("Sucesso", f"Corista '{novo_nome}' atualizado com sucesso!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Erro ao salvar", f"Erro ao atualizar corista: {str(e)}")

        # Botões
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Confirmar", command=confirm).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side="left", padx=10)

    def on_delete_key(self, event):
        """Chamado quando a tecla Delete é pressionada"""
        selected_item = self.tree_coristas.selection()
        if selected_item:
            self.remove_corista()
        return "break"  # Impede que o evento propague

    def _clear_music_fields(self):
        """Limpa todos os campos da UI relacionados à música atual (robusto)."""

        # Helper local para limpar variáveis que podem ser StringVar ou string comum
        def safe_clear_var(var):
            if var is None:
                return
            if hasattr(var, "set"):
                try:
                    var.set("")
                except Exception:
                    pass
            else:
                # Caso seja uma string simples armazenada como atributo
                return ""

        # Limpar ranges das vozes
        for voice, vr in getattr(self, "voice_vars", {}).items():
            min_entry = vr.get("min")
            max_entry = vr.get("max")

            for entry in (min_entry, max_entry):
                if entry is None:
                    continue
                if hasattr(entry, "delete"):
                    try:
                        entry.delete(0, "end")
                    except Exception:
                        pass
                if hasattr(entry, "insert"):
                    try:
                        entry.insert(0, "")
                    except Exception:
                        pass

        # Limpar o nome da música
        if hasattr(self, "music_name_var"):
            safe_clear_var(self.music_name_var)

        # Nova: limpar solistas
        if hasattr(self, "solist_count_cb"):
            try:
                self.solist_count_cb.set(0)
                self._build_solists_ui()
            except Exception:
                pass
        self.solistas = {}
        if hasattr(self, "solist_rows"):
            for idx, row in enumerate(self.solist_rows):
                if idx >= len(getattr(self, "solist_rows", [])):
                    break
                # Define o nome do solista
                if "cb" in row and row["cb"]:
                    try:
                        row["cb"].set("")
                    except Exception:
                        pass
                # Define range mínimo e máximo
                if "min" in row and row["min"]:
                    try:
                        row["min"].delete(0, "end")
                        row["min"].insert(0, "")
                    except Exception:
                        pass
                if "max" in row and row["max"]:
                    try:
                        row["max"].delete(0, "end")
                        row["max"].insert(0, "")
                    except Exception:
                        pass

        # Limpar coristas/voz atribuída (se aplicável)
        if hasattr(self, "coristas_mgr"):
            try:
                for c in self.coristas_mgr.coristas.values():
                    if isinstance(c, dict) and "voz_atribuida" in c:
                        c["voz_atribuida"] = ""
                self.reload_coristas_table()
            except Exception:
                pass

        # Limpar resultados e Análise
        self.clear_results()
        self.run_analysis()

    def adicionar_grupo(self):
        nome = simpledialog.askstring("Adicionar Grupo", "Nome do Novo Grupo:")
        if nome and nome.strip():
            nome = nome.strip()

            # Adicionar no banco de dados
            self.coristas_mgr.adicionar_grupo(nome)

            # Acrescentar grupo à lista de grupos
            self.grupo_combo.set(nome)
            self.grupo_combo['values'] = self.coristas_mgr.read_data(extract='grupos', group_list=True)

            # Resetar músicas
            self.music_name_var.set(self.music_name_placeholder)
            self.music_name_entry.delete(0, tk.END)
            self.music_name_entry.config(fg="black")
            self.music_name_entry.insert(0, self.music_name_placeholder)
            self.music_var.set('')
            self.music_combo.set("-- Selecione uma música --")
            self.load_music_ranges_for_selection(self.music_combo.get())

            # Atualisar lista de coristas
            self.coristas_mgr.coristas.clear()
            self._on_group_selected()

    def load_voice_audio_files(self):
        from tkinter import filedialog
        self.voice_audio_paths = {}
        for v in VOICES:
            path = filedialog.askopenfilename(title=f"Selecione áudio para a voz {v}",
                                              filetypes=[("Audio", "*.wav *.mp3 *.flac"), ("All files", "*.*")])
            if path:
                self.voice_audio_paths[v] = path
            else:
                self.voice_audio_paths[v] = None

        # Determina o nome da música
        music_name = None
        if hasattr(self, "music_name_var") and self.music_name_var:
            music_name = self.music_name_var.get().strip()

        if not music_name:
            # Deriva do primeiro caminho disponível
            for p in self.voice_audio_paths.values():
                if p:
                    base = os.path.basename(p)
                    music_name = os.path.splitext(base)[0]
                    break

        if not music_name:
            messagebox.showerror("Erro", "Nome da música não informado nem derivável a partir dos caminhos fornecidos.")
            return

        # Caminho de saída raiz (conforme sua organização)
        root_musicas = Path("root") / "Musicas"  # atende ao formato root/Musicas/{nome_da_musica}
        music_root = root_musicas / music_name
        # Não criamos ainda; criaremos ao salvar outputs por voz

        # Processa cada faixa por voz
        for voz, path in self.voice_audio_paths.items():
            if not path:
                continue

            # Processo com AudioAnalyzer
            result = self.analyzer.process_music(path, music_name)

            # Preenche min/max com extrema (extrema é uma lista tipo [min_note, max_note])
            extrema = result.get("extrema")
            if extrema and len(extrema) >= 2:
                min_name, max_name = extrema[0], extrema[1]
                if voz in self.voice_vars:
                    # Atualiza UI com as novas faixas
                    self.voice_vars[voz]["min"].delete(0, "end")
                    self.voice_vars[voz]["min"].insert(0, min_name)
                    self.voice_vars[voz]["max"].delete(0, "end")
                    self.voice_vars[voz]["max"].insert(0, max_name)

            # Hard: salvar outputs em root/Musicas/{nome_da_musica}/{voz}/
            voice_dir = music_root / voz
            voice_dir.mkdir(parents=True, exist_ok=True)

            # Caminhos de origem retornados pelo AudioAnalyzer
            notes_src = result.get("notes_detected_path")
            normalized_src = result.get("normalized_path")
            midi_src = result.get("midi_path")

            # Copia/Move para a pasta da música e com nomes únicos por voz
            if notes_src:
                dest_notes = voice_dir / f"{music_name}_notes_detected.json"
                try:
                    shutil.copy2(notes_src, dest_notes)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar notes para {dest_notes}: {e}")

            if normalized_src:
                dest_normalized = voice_dir / f"{music_name}_normalized.json"
                try:
                    shutil.copy2(normalized_src, dest_normalized)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar normalized para {dest_normalized}: {e}")

            if midi_src:
                dest_midi = voice_dir / f"{music_name}_midi.mid"
                try:
                    shutil.copy2(midi_src, dest_midi)
                except Exception as e:
                    print(f"Aviso: não foi possível copiar MIDI para {dest_midi}: {e}")

        messagebox.showinfo("Sucesso",
                            f"Processamento concluído para '{music_name}'. Saídas salvas em root/Musicas/{music_name}/ (por voz).")

    def _on_root_selected(self, event):
        self.root_var.set(self.root_combo.get())

    def _on_mode_selected(self, event):
        self.mode_var.set(self.mode_combo.get())

    def _on_double_click_corista(self, event):
        item_id = self.tree_coristas.focus()
        if not item_id:
            return

        # Opcional: garanta que o item esteja selecionado
        self.tree_coristas.selection_set(item_id)

        # Tenta chamar a função de edição de corista já existente
        # Se edit_corista_voz aceitar um argumento, passe-o; senão, chame sem argumentos
        try:
            self.edit_corista_voz(item_id)
        except TypeError:
            self.edit_corista_voz()

    def clear_results(self):
        """Limpa a área de resultados"""
        self.results_text.delete(1.0, "end")
        self.results_text.insert("end", "Resultados limpos. Informe os ranges vocais e execute a análise novamente.\n")

    ### TESTE VOCAL
    def _on_testing_time_changed(self, event):
        try:
            new_time = int(self.testing_time_cb.get())

            # Atualiza o valor por padrão no core (padrão global) e na UI
            VocalTestCore.DEFAULT_TESTING_TIME = new_time

            # Atualiza o valor local da UI
            self.testing_time = new_time

            # Se houver uma instância rodando do core de teste, atualize-a também
            if getattr(self, "vocal_tester", None) is not None:
                self.vocal_tester.testing_time = new_time

            # Atualiza o rótulo do tempo na UI (se aplicável)
            self.time_label.config(text=f"Tempo: 0.0s / {new_time}.0s")
        except Exception:
            pass

    def repeat_tone_vocal(self):
        """Reproduz o tom atual novamente (se houver tom ativo)"""
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            freq = self.vocal_tester.current_playing_frequency
            if freq and freq > 0:
                # Executa em outra thread para não bloquear a UI
                threading.Thread(target=self.vocal_tester.play_note, args=(freq, 2), daemon=True).start()
                self.status_label.config(text="Reproduzindo tom atual...", foreground='#27AE60')
                return
        # Caso não haja tom disponível
        messagebox.showinfo("Aviso", "Nenhum tom atual para repetir.")

    def start_vocal_test(self):
        """Inicia o teste vocal normal"""
        if self.vocal_tester is not None:
            messagebox.showwarning("Aviso", "Um teste já está em andamento!")
            return

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.update_vocal_test_ui,
            complete_callback=self.on_vocal_test_complete,
            button_callback=self.update_button_states
        )

        self.btn_start_test.config(state='disabled')
        self.btn_quick_test.config(state='disabled')
        self.btn_stop_test.config(state='normal')
        self.status_label.config(text="Iniciando teste normal...", foreground='#F39C12')

        threading.Thread(target=self.vocal_tester.start_test, daemon=True).start()

    def start_quick_vocal_test(self):
        """Inicia o teste vocal rápido"""
        if self.vocal_tester is not None:
            messagebox.showwarning("Aviso", "Um teste já está em andamento!")
            return

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.update_vocal_test_ui,
            complete_callback=self.on_vocal_test_complete,
            button_callback=self.update_button_states
        )

        self.btn_start_test.config(state='disabled')
        self.btn_quick_test.config(state='disabled')
        self.btn_stop_test.config(state='normal')

        self.status_label.config(text="Iniciando teste rápido...", foreground='#F39C12')

        threading.Thread(target=self.vocal_tester.start_quick_test, daemon=True).start()

    def mark_too_low_vocal(self):
        """Marca como grave demais"""
        if self.vocal_tester:
            self.vocal_tester.mark_too_low()

    def mark_too_high_vocal(self):
        """Marca como agudo demais"""
        if self.vocal_tester:
            self.vocal_tester.mark_too_high()

    def stop_vocal_test(self):
        """Para o teste vocal"""
        if self.vocal_tester:
            self.vocal_tester.stop_test()

        self.btn_start_test.config(state='normal')
        self.btn_quick_test.config(state='normal')
        self.btn_stop_test.config(state='disabled')
        self.btn_too_low.config(state='disabled')
        self.btn_too_high.config(state='disabled')

        self.status_label.config(text="Teste cancelado", foreground='#E74C3C')
        self.vocal_tester = None

    def update_vocal_test_ui(self, **kwargs):
        """Atualiza os elementos visuais do teste vocal"""
        if 'expected_note' in kwargs:
            self.expected_note_label.config(text=kwargs['expected_note'])

        if 'expected_freq' in kwargs:
            # Pode ser frequência ou texto
            pass

        if 'detected_note' in kwargs:
            self.detected_note_label.config(text=kwargs['detected_note'])

        if 'status' in kwargs:
            color = kwargs.get('status_color', '#666')
            self.status_label.config(text=kwargs['status'], foreground=color)

        if 'time' in kwargs:
            self.time_var.set(kwargs['time'])

        if 'time_text' in kwargs:
            self.time_label.config(text=kwargs['time_text'])

        if 'offset_cents' in kwargs:
            self.belt_indicator.set_offset(kwargs['offset_cents'])

        # Novo: aceitar também atualizações diretas de botões
        button_map = [
            ('start_button', getattr(self, 'btn_start_test', None)),
            ('start_quick_button', getattr(self, 'btn_quick_test', None)),
            ('stop_button', getattr(self, 'btn_stop_test', None)),
            ('repeat_button', getattr(self, 'btn_repeat', None)),  # pode não existir
            ('too_low_button', getattr(self, 'btn_too_low', None)),
            ('too_high_button', getattr(self, 'btn_too_high', None)),
        ]

        for key, btn in button_map:
            if btn is None:
                continue
            if key in kwargs:
                btn.config(state=kwargs[key])

        # Compatibilidade com o formato antigo: button_states
        if 'button_states' in kwargs:
            states = kwargs['button_states']
            if self.btn_too_low:
                self.btn_too_low.config(state=states.get('too_low', 'disabled'))
            if self.btn_too_high:
                self.btn_too_high.config(state=states.get('too_high', 'disabled'))
            # opcional: mapear outros botões se houver
            # Exemplos adicionais:
            if 'start' in states and self.btn_start_test:
                self.btn_start_test.config(state=states['start'])
            if 'start_quick' in states and self.btn_quick_test:
                self.btn_quick_test.config(state=states['start_quick'])
            if 'stop' in states and self.btn_stop_test:
                self.btn_stop_test.config(state=states['stop'])

        # Novo: alimentar gráfico de pitch em tempo real
        if 'pitch_hz' in kwargs:
            hz = kwargs['pitch_hz']
            if hz is not None and hz > 0:
                # Executa na thread da UI
                self.master.after(0, self.pitch_line_chart.add_sample, hz)

    def update_button_states(self, **kwargs):
        """Atualiza estado dos botões"""
        button_states = kwargs.get('button_states', {})
        self.btn_too_low.config(state=button_states.get('too_low', 'disabled'))
        self.btn_too_high.config(state=button_states.get('too_high', 'disabled'))

    def on_vocal_test_complete(self, range_min, range_max):
        """Chamado quando o teste vocal termina"""
        if range_min and range_max:
            self.entrada_min.delete(0, "end")
            self.entrada_min.insert(0, range_min)
            self.entrada_max.delete(0, "end")
            self.entrada_max.insert(0, range_max)

            self.status_label.config(
                text=f"✓ Ranges preenchidos: {range_min} - {range_max}",
                foreground='#27AE60'
            )
            messagebox.showinfo("Sucesso", f"Ranges preenchidos:\nMín: {range_min}\nMáx: {range_max}")
        else:
            self.status_label.config(text="Nenhum resultado", foreground='#E74C3C')
            messagebox.showwarning("Aviso", "Teste foi cancelado ou não retornou resultados")

        # Reset dos botões
        self.btn_start_test.config(state='normal')
        self.btn_quick_test.config(state='normal')
        self.btn_stop_test.config(state='disabled')
        self.btn_too_low.config(state='disabled')
        self.btn_too_high.config(state='disabled')

        self.vocal_tester = None
    ### ANÁLISE
    def toggle_group_or_voice_ranges(self):
        # Inverte o modo entre "Vozes Grupo" e "Vozes Base" (ou "VOICES")
        current = getattr(self, "_use_group_ranges", False)
        self._use_group_ranges = not current
        if getattr(self, "_use_group_ranges", False):
            # Estamos usando os ranges de grupo
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                self.group_ranges, self.group_extension = self.coristas_mgr.get_voice_group_ranges(solistas=self.solistas if self.solistas else None)

                # Atualiza o visualizador se ele suportar ranges de grupo
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(self.group_ranges)
            else:
                # Sem ranges de grupo disponíveis; fallback para base
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(None)
        else:
            self.group_ranges = None
            self.group_extension = None

        # Reexecuta a análise para refletir o novo range com o T atual
        self.run_analysis()

    def run_analysis(self):
        """
        Versão unificada de run_analysis:
        - Calcula a melhor transposição global (best_T, best_Os, nova chave)
        - Calcula O_i para o T atual (barra de transposição) para atualização do visualizador
        - Exibe resultados de forma consistente
        """
        try:
            piece_ranges = self.read_voice_ranges() if not getattr(self, "_use_group_ranges", False) or not self.solistas else self.solistas | self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            # T atual vindo da barra de transposição
            t_current = int(float(self.t_slider.get())) if hasattr(self, "t_slider") else 0

            # Obter ranking completo de Ts (debug) para exibir possíveis transposições
            self.analysis_all = analyze_ranges_with_penalty(self.root_var.get(), self.mode_var.get(), piece_ranges, self.group_ranges)

            # Exibir resultados de forma consistente
            self.on_t_change(t_current)

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def on_t_change(self, value):
        """
        Atualização: quando o usuário altera T, exibimos todas as mensagens de display_results
        usando os valores já aplicados (T atual) para manter consistência.
        """
        try:
            T = int(float(value))
            piece_ranges = getattr(self, "current_piece_ranges", None)

            if not piece_ranges:
                return

            # Calcula os O_i para o T atual
            per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, self.group_ranges)

            # Atualiza visualização gráfica com o T atual
            self.visualizer.update(piece_ranges, T, per_voice_Os, self.group_ranges, self.group_extension, self.analysis_all['voice_scores'])

            current_root = self.root_var.get()

            # Transposição atual para exibição
            transposed_root = transpose_note(current_root, T)

            # Construção consolidada do bloco de resultados
            self.results_text.delete(1.0, "end")

            best_T_global = self.analysis_all.get("best_T")
            best_key_root = self.analysis_all.get("best_key_root")
            best_key_mode = self.analysis_all.get("best_key_mode")
            if best_T_global is not None:
                self.results_text.insert("end", f"Melhor transposição: {best_T_global:+d} semitons → {best_key_root} {best_key_mode}\n")

            self.results_text.insert("end",
                                     f"Transposição atual: {T:+d} semitons ({current_root} → {transposed_root})\n")

            debug = self.analysis_all.get("debug", [])
            # Possíveis transposições (debug)
            if debug:
                if len(debug) > 0:
                    pairs = []
                    i = 0
                    while i < len(debug):
                        if debug[i] == 0:
                            pairs.append(str(debug[i]))  # 0 fica sozinho
                            i += 1
                        else:
                            pairs.append(f"({debug[i]}/{debug[i + 1]})")
                            i += 2
                    self.results_text.insert("end", "Possíveis transposições: " + ", ".join(pairs) + " semitons\n")
                else:
                    self.results_text.insert("end", f"Transposição possível: {debug[0]:+d} semitons\n")

            # Faixas resultantes após a transposição aplicada
            self.results_text.insert("end", "\nFaixas resultantes:\n")
            for v in self.group_ranges.keys() if getattr(self, "_use_group_ranges", False) else VOICES:
                mn, mx = piece_ranges.get(v, (None, None))
                if not mn or not mx:
                    continue
                min_m = note_to_midi(mn)
                max_m = note_to_midi(mx)
                O = per_voice_Os.get(v, 0)
                O_i = 'oitava' if O > -2 and O < 2 else 'oitavas'
                min_final = min_m + T + 12 * O
                max_final = max_m + T + 12 * O
                self.results_text.insert("end",f"  {v}: {midi_to_note(int(min_final))} → {midi_to_note(int(max_final))}")
                self.results_text.insert("end",f" ({O} {O_i})\n") if O != 0 else self.results_text.insert("end","\n")

        except Exception:
            pass

def main():
    root = tk.Tk()
    app = VoiceRangeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

# pyinstaller --onefile --windowed Main.py
# pyinstaller --onefile --windowed Main.py --add-data "C:\Users\Sérgio\PycharmProjects\Gerenciador de Coral;."