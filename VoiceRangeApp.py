import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import time
import threading
import shutil
from pathlib import Path
from CoristasManager import CoristasManager
from Constants import VOICES, VOICE_BASE_RANGES
from KeyboardVisualizer import KeyboardVisualizer
from RangeVisualizer import RangeVisualizer
from GeneralFunctions import analyze_ranges_with_penalty, note_to_midi, transpose_note, midi_to_note, compute_best_transposition, compute_per_voice_Os_for_T, transpose_key
from VocalTester import VocalTestCore, BeltIndicator, PitchLineChart
from MusicTranspose import AudioAnalyzer
import re


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

        # Dados de música carregados (vai vir de DATA_FILE_MAIN)
        self.coristas = False
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

        # ===== INDICADOR VISUAL (BELT) =====
        self.belt_indicator = BeltIndicator(right_frame, width=300, height=50)
        # Opcional: definir o alcance de semitons que o belt deve cobrir
        self.belt_indicator.set_range(-12, 12)
        self.belt_indicator.pack(pady=5)

        # Visualizador do pitch ao longo do tempo
        self.pitch_line_chart = PitchLineChart(left_frame, width=640, height=180,
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
        groups = self._load_group_names_from_json()
        self.grupo_combo['values'] = groups
        if groups:
            self.grupo_combo.current(0)
        self.grupo_combo.pack()
        self.grupo_combo.bind("<<ComboboxSelected>>", self._on_group_selected)

        ttk.Label(group_frame, text="Nome do Grupo:").pack()
        self.grupo_nome_var = tk.StringVar()
        self.grupo_nome_entry = ttk.Entry(group_frame, textvariable=self.grupo_nome_var, width=20)
        self.grupo_nome_entry.pack()

        # Cria Treeview
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="headings")

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(col, text=col)

        self.tree_coristas.pack(fill="both", expand=True)
        self.tree_coristas.bind("<Double-1>", self._on_double_click_corista)

        # Botões de ação
        button_frame = ttk.Frame(self.frame_coristas)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Remover Selecionado", command=self.remove_corista).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Salvar Dados", command=self.save_coristas).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Recarregar", command=self.reload_coristas_table).pack(side="left", padx=5)

        # Carrega dados iniciais
        self.reload_coristas_table()

    def setup_analise_tab(self):
        """Configura a aba de análise de transposição"""
        # Cabeçalho
        header = ttk.Label(self.frame_analise, text="Ajuste de tom e alcance por voz (compensação por penalidade)",
                           font=("Arial", 12, "bold"))
        header.pack(pady=10)

        # Slider de transposição
        self.t_slider = tk.Scale(self.frame_analise, from_=-12, to=12, orient="horizontal",
                                 label="Transposição (semítons)", command=self.on_t_change, length=600)
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
        music_name_entry = tk.Entry(library_frame, textvariable=self.music_name_var, width=30, fg="grey")
        music_name_placeholder = "Nome da música"
        music_name_entry.insert(0, music_name_placeholder)

        def _clear_name(event):
            if music_name_entry.get() == music_name_placeholder:
                music_name_entry.delete(0, tk.END)
                music_name_entry.config(fg="black")

        def _fill_name(event):
            val = music_name_entry.get()
            if val == "":
                music_name_entry.insert(0, music_name_placeholder)
                music_name_entry.config(fg="grey")
                self.music_name_var.set("")  # keep var sem placeholder
            else:
                # Atualiza a StringVar com o valor real (ignora o placeholder)
                self.music_name_var.set(val)

        music_name_entry.bind("<FocusIn>", _clear_name)
        music_name_entry.bind("<FocusOut>", _fill_name)
        music_name_entry.grid(row=0, column=0, padx=5, pady=5)  # ocupa o espaço da antiga label

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
            piece_name=(self.music_name_var.get() if self.music_name_var.get() != music_name_placeholder else "")
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
    def _load_group_names_from_json(self):
        """Carrega a lista de grupos existentes em coristas_music_data.json under 'grupos'."""
        data_file = "coristas_music_data.json"
        groups = []
        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                groups = list(data.get("grupos", {}).keys())
        except Exception:
            pass
        return groups

    def _on_group_selected(self, event=None):
        """Atualiza estado ao selecionar grupo e refaz UI de solistas se necessário."""
        grupo = self.grupo_combo.get()
        self.grupo_nome_var.set(grupo)
        # Atualiza a UI dos solistas para refletir o grupo atual
        self.reload_coristas_table()

    def _get_coristas_names_for_current_group(self):
        """Retorna a lista de nomes de coristas para o grupo selecionado (quando possível)."""
        group = self.grupo_combo.get() or self.grupo_nome_var.get() or "Grupo Vocal"
        names = []
        data_file = "coristas_music_data.json"
        if os.path.exists(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                group_entries = data.get("grupos", {}).get(group, {})
                if isinstance(group_entries, dict):
                    for key in sorted(group_entries.keys(), key=lambda x: int(x) if str(x).isdigit() else x):
                        cor = group_entries[key]
                        if isinstance(cor, dict) and "nome" in cor:
                            names.append(cor["nome"])
            except Exception:
                pass
        if not names:
            coristas = getattr(self.coristas_mgr, "coristas", [])
            names = [c.get("nome", "") for c in coristas]
        return names

    def add_corista(self):
        nome = self.entrada_nome.get().strip()
        range_min = self.entrada_min.get().strip()
        range_max = self.entrada_max.get().strip()

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
            msg += f"Vozes Possíveis: {', '.join([v for v, _, _ in vozes_poss]) if vozes_poss else 'Nenhuma'}"

            messagebox.showinfo("Sucesso", msg)
            self.entrada_nome.delete(0, "end")
            self.entrada_min.delete(0, "end")
            self.entrada_max.delete(0, "end")
            self.reload_coristas_table()
        else:
            messagebox.showerror("Erro", f"Erro ao adicionar corista:\n{result}")

    def remove_corista(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para remover")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)
        self.coristas_mgr.remove_corista(index)
        self.reload_coristas_table()
        messagebox.showinfo("Sucesso", "Corista removido!")

    def edit_corista_voz(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)

        # Obter o nome do corista a partir da treeview
        corista_nome = self.tree_coristas.item(item, "text")
        if not corista_nome:
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

        # Janela de diálogo para seleção de voz
        dialog = tk.Toplevel(self.master)
        dialog.title("Atribuir Voz")
        dialog.geometry("900x850")

        ttk.Label(dialog, text=f"Corista: {corista_nome}", font=("Arial", 12, "bold")).pack(pady=10)

        # Frame para range atual
        range_frame = ttk.LabelFrame(dialog, text="Range Atual", padding=5)
        range_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(range_frame, text=f"Range: {corista['range_min']} - {corista['range_max']}",
                  font=("Arial", 10)).pack(side="left", padx=10)

        ttk.Label(range_frame, text="💡 Dica: Use o teste vocal na aba de Adicionar Corista",
                  font=("Arial", 8), foreground="#666").pack(side="left", padx=10)

        ttk.Label(dialog, text=f"Voz Calculada: {corista['voz_calculada']}", font=("Arial", 10)).pack(pady=5)

        # Separador
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista.get('voz_atribuida'))

        # ===== Visualizador de teclado =====
        keyboard = KeyboardVisualizer(dialog)

        # Frame para as opções de voz
        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Função local para calcular vozes compatíveis
        def calculate_compatible_voices(range_min: str, range_max: str):
            min_midi = note_to_midi(range_min)
            max_midi = note_to_midi(range_max)

            vozes_recomendadas = []
            vozes_possiveis = []

            for voice in VOICES:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                voice_min = note_to_midi(voice_min_str)
                voice_max = note_to_midi(voice_max_str)

                # Encaixe perfeito
                if min_midi <= voice_min and max_midi >= voice_max:
                    vozes_recomendadas.append(voice)
                else:
                    diff_min = max(0, min_midi - voice_min)
                    diff_max = max(0, voice_max - max_midi)
                    max_diff = max(diff_min, diff_max)

                    if max_diff <= 5:
                        obs = ""
                        if diff_min > 0:
                            obs += f"Falta {diff_min} semitom"
                            obs += " grave"  # marcação conforme original
                        if diff_max > 0:
                            if obs:
                                obs += " e "
                            obs += f"Falta {diff_max} semitom"
                            obs += " agudo"
                        vozes_possiveis.append((voice, max_diff, obs))

            vozes_possiveis.sort(key=lambda x: x[1])
            return vozes_recomendadas, vozes_possiveis

        vozes_recomendadas, vozes_possiveis = calculate_compatible_voices(corista['range_min'], corista['range_max'])

        # RECOMENDADAS
        if vozes_recomendadas:
            ttk.Label(vozes_frame, text="✓ Recomendadas (Encaixe Perfeito)", font=("Arial", 11, "bold"),
                      foreground="green").pack(anchor="w", pady=(10, 5))
            for v in vozes_recomendadas:
                def on_select_recomendada(voice=v):
                    var_voz.set(voice)
                    voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                    keyboard.update(corista['range_min'], corista['range_max'],
                                    voice_min_str, voice_max_str)

                ttk.Radiobutton(vozes_frame, text=v, variable=var_voz, value=v,
                                command=on_select_recomendada).pack(anchor="w", padx=50, pady=3)

        # POSSÍVEIS
        if vozes_possiveis:
            ttk.Label(vozes_frame, text="⚠ Possíveis (com ressalva)", font=("Arial", 11, "bold"),
                      foreground="orange").pack(anchor="w", pady=(10, 5))
            for v, diff, obs in vozes_possiveis:
                frame_poss = ttk.Frame(vozes_frame)
                frame_poss.pack(anchor="w", padx=40, pady=3, fill="x")

                def on_select_possivel(voice=v):
                    var_voz.set(voice)
                    voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                    keyboard.update(corista['range_min'], corista['range_max'],
                                    voice_min_str, voice_max_str)

                ttk.Radiobutton(frame_poss, text=v, variable=var_voz, value=v,
                                command=on_select_possivel).pack(side="left")
                ttk.Label(frame_poss, text=f"({obs})", font=("Arial", 9), foreground="gray").pack(side="left", padx=5)

        # Atualiza o teclado inicialmente
        voz_inicial = var_voz.get()
        if voz_inicial:
            voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_inicial]
            keyboard.update(corista['range_min'], corista['range_max'],
                            voice_min_str, voice_max_str)

        def confirm():
            self.coristas_mgr.update_corista_voz(corista_nome, var_voz.get())
            self.reload_coristas_table()
            dialog.destroy()

        ttk.Button(dialog, text="Confirmar", command=confirm).pack(pady=20)

    def save_coristas(self):
        if self.coristas_mgr.save_corista():
            messagebox.showinfo("Sucesso", "Dados salvos em coristas_data.json")
        else:
            messagebox.showerror("Erro", "Erro ao salvar dados")

    def reload_coristas_table(self):
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

        # Recarrega a visualização da tabela com os coristas do grupo atual
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        for corista in self.coristas_mgr.coristas:
            self.tree_coristas.insert("", "end", values=(
                corista,
                self.coristas_mgr.coristas[corista]['range_min'] + "  ⟷  " + self.coristas_mgr.coristas[corista]['range_max'],
                self.coristas_mgr.coristas[corista]['voz_atribuida'],
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_recomendadas']),
                ", ".join(v for v in self.coristas_mgr.coristas[corista]['vozes_possiveis'])
            ))

    def save_music_ranges_to_json(self, piece_name=None):
        # Novo formato unificado: coristas_music_data.json
        data_file = "coristas_music_data.json"
        piece_ranges = {voz: {"min": self.voice_vars[voz]["min"].get().upper(), "max": self.voice_vars[voz]["max"].get().upper()} for voz in VOICES}

        # Validação: cada valor deve ser do formato A-G seguido de 2-7
        NOTA_PATTERN = re.compile(r"^(?:[A-G][2-7])?$")

        invalids = []
        for voz, rng in piece_ranges.items():
            min_v = rng.get("min", "")
            max_v = rng.get("max", "")

            if not NOTA_PATTERN.fullmatch(min_v):
                invalids.append((voz, "min", min_v))
            if not NOTA_PATTERN.fullmatch(max_v):
                invalids.append((voz, "max", max_v))

        if invalids:
            # Opcional: construir uma mensagem mais legível
            msgs = [
                f"'{valor}' é inválido para {voz} ({campo})!" for voz, campo, valor in invalids
            ]
            messagebox.showerror("Nota inexistente",
                                 "; ".join(msgs) + "\nEsperado: uma letra A-G seguida de um número 2-7.\n"
                                 )
            # Opcional: interromper o fluxo (depende do seu fluxo)
            return
            #raise ValueError("Notas inválidas detectadas em piece_ranges.")

        orig_root = self.root_var.get()
        orig_mode = self.mode_var.get()

        name = piece_name or "Untitled"

        # Construir solistas a partir de self.solist_rows
        self.solistas = {}
        for row in getattr(self, 'solist_rows', []) or []:
            cb_widget = row.get('cb')
            min_widget = row.get('min')
            max_widget = row.get('max')

            # Obter nome do solista a partir do Combobox (se for widget) ou valor direto
            cb_name = None
            if cb_widget is not None:
                try:
                    cb_name = cb_widget.get()
                except Exception:
                    cb_name = str(cb_widget)

            min_val = None
            if min_widget is not None:
                try:
                    min_val = min_widget.get()
                except Exception:
                    min_val = str(min_widget)

            max_val = None
            if max_widget is not None:
                try:
                    max_val = max_widget.get()
                except Exception:
                    max_val = str(max_widget)

            if cb_name:
                self.solistas[str(cb_name)] = [min_val, max_val]

        # Construir voices a partir de self.coristas_mgr.coristas
        voices = {}
        for corista in getattr(self.coristas_mgr, 'coristas', []) or []:
            nome = corista.get('nome')
            voz_atribuida = corista.get('voz_atribuida')
            if voz_atribuida and nome:
                voices.setdefault(voz_atribuida, []).append(nome)

        # Construir/gravar o mapeamento de grupos
        grupo_nome_var = getattr(self, 'grupo_nome_var', None)

        # Obter o valor efetivo (string) caso seja um StringVar
        grupo_nome = None
        if grupo_nome_var is not None:
            if isinstance(grupo_nome_var, str):
                grupo_nome = grupo_nome_var
            else:
                get_method = getattr(grupo_nome_var, 'get', None)
                if callable(get_method):
                    grupo_nome = get_method()
                else:
                    grupo_nome = str(grupo_nome_var)

        grupos_map = {}
        if grupo_nome:
            grupos_map = {grupo_nome: getattr(self.coristas_mgr, 'coristas', [])}

        # Entrada a ser gravada
        entry = {
            'grupos': grupos_map,
            "musicas": {
                name: {
                    "root": orig_root,
                    "mode": orig_mode,
                    "grupo": grupo_nome,
                    "ranges": piece_ranges,
                    "solistas": self.solistas,
                    "voices": voices,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
        }

        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            else:
                data = {"grupos": {}, "musicas": {}}

            if name == 'Untitled':
                messagebox.showinfo("Erro", f"Preencha o nome da música")
            elif name not in data["musicas"].keys():
                # Sem duplicata: adiciona
                if grupo_nome:
                    data["grupos"][grupo_nome] = entry['grupos'][grupo_nome]
                data["musicas"][name] = entry['musicas'][name]
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("Sucesso", f"Faixa salva em {data_file}")
                # Atualizar biblioteca após salvar
                self.load_music_library()
            else:
                # Duplicata encontrada: perguntar se deve substituir
                substituir = messagebox.askyesno(
                    "Aviso",
                    f"Já existe uma música chamada '{name}'. Deseja substituir a faixa existente?"
                )
                if substituir:
                    if grupo_nome:
                        data["grupos"][grupo_nome] = entry['grupos'][grupo_nome]
                    data["musicas"][name] = entry['musicas'][name]
                    with open(data_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("Sucesso", f"Faixa salva em {data_file}")
                    # Atualizar biblioteca após salvar
                    self.load_music_library()
                else:
                    messagebox.showinfo("Cancelado", "Operação cancelada. A faixa não foi modificada.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar faixa: {e}")

    def load_music_library(self):
        """Carrega a biblioteca de músicas do coristas_music_data.json."""
        data_file = "coristas_music_data.json"

        # Limpa/reinicializa listas
        self.music_library.clear()
        self.music_names = []

        if os.path.exists(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.music_library = data.get("musicas", {})
                self.music_names = list(self.music_library.keys())

                # Carrega grupos: atualiza combobox de grupos com nomes disponíveis
                groups = self._load_group_names_from_json()
                if hasattr(self, "grupo_combo") and groups:
                    self.grupo_combo['values'] = groups

            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar biblioteca: {e}")

        # Atualiza combobox se existir
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names


    def load_music_ranges_for_selection(self, name):
        """Carrega os ranges de uma música selecionada na combobox."""

        # Validação básica
        if not name or name.startswith("--"):
            messagebox.showwarning("Aviso", "Nenhuma música válida selecionada.")
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
            grupos_disponiveis = self._load_group_names_from_json()
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

        # Executa a análise com os dados carregados
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
            self.coristas = True
            # Estamos usando os ranges de grupo
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                group_ranges = self.coristas_mgr.get_voice_group_ranges(solistas=self.solistas)
                print(group_ranges)
                # Atualiza o visualizador se ele suportar ranges de grupo
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(group_ranges)
            else:
                # Sem ranges de grupo disponíveis; fallback para base
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(None)

        else:
            self.coristas = False
            # Usando VOICE_BASE_RANGES
            if hasattr(self.visualizer, "set_group_ranges"):
                self.visualizer.set_group_ranges(None)


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
            orig_root = self.root_var.get()
            orig_mode = self.mode_var.get()
            piece_ranges = self.read_voice_ranges() if not getattr(self, "_use_group_ranges", False) else self.solistas | self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            # T atual vindo da barra de transposição
            t_current = int(float(self.t_slider.get())) if hasattr(self, "t_slider") else 0

            # Group ranges (se ativo)
            group_ranges = None
            if getattr(self, "_use_group_ranges", False):
                if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                    group_ranges = self.solistas | self.coristas_mgr.get_voice_group_ranges()

            #print(group_ranges)
            # Cálculo unificado da melhor transposição
            analysis = compute_best_transposition(orig_root, orig_mode, piece_ranges, group_ranges)

            self._latest_analysis = analysis  # armazenar para uso futuro, se necessário

            # Exibir resultados de forma consistente
            self.on_t_change(0)

            # Cálculo dos Os para o T atual e atualização do visualizador
            per_voice_Os_for_T = compute_per_voice_Os_for_T(t_current, piece_ranges, group_ranges)
            self.visualizer.update(piece_ranges, t_current, per_voice_Os_for_T)

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
            group_ranges = self.coristas_mgr.get_voice_group_ranges() if self.coristas else None

            if not piece_ranges:
                return

            # Calcula os O_i para o T atual
            per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, group_ranges)

            # Atualiza visualização gráfica com o T atual
            self.visualizer.update(piece_ranges, T, per_voice_Os)

            current_root = self.root_var.get()
            current_mode = self.mode_var.get()

            # Transposição atual para exibição
            transposed_root = transpose_note(current_root, T)

            # Obter ranking completo de Ts (debug) para exibir possíveis transposições
            analysis_all = analyze_ranges_with_penalty(current_root, current_mode, piece_ranges, group_ranges)
            debug = analysis_all.get("debug", [])

            # Construção consolidada do bloco de resultados
            self.results_text.delete(1.0, "end")

            best_T_global = analysis_all.get("best_T")
            best_key_root = analysis_all.get("best_key_root")
            best_key_mode = analysis_all.get("best_key_mode")
            if best_T_global is not None:
                self.results_text.insert("end", f"Melhor transposição: {best_T_global:+d} semitons → {best_key_root} {best_key_mode}\n")

            self.results_text.insert("end",
                                     f"Transposição atual: {T:+d} semitons ({current_root} → {transposed_root})\n")

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
            for v in group_ranges.keys() if self.coristas else VOICES:
                mn, mx = piece_ranges.get(v, (None, None))
                if mn is None or mx is None:
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
class VoiceRangeApp2:
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

        # Dados de música carregados (vai vir de DATA_FILE_MAIN)
        self.coristas = False
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

        self.btn_too_low = ttk.Button(marking_row, text="🔽️ Grave D.", command=self.mark_too_low_vocal, state='disabled')
        self.btn_too_low.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_too_high = ttk.Button(marking_row, text="🔼 Agudo D.", command=self.mark_too_high_vocal, state='disabled')
        self.btn_too_high.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_stop_test = ttk.Button(marking_row, text="🛑 Parar", command=self.stop_vocal_test, state='disabled')
        self.btn_stop_test.grid(row=0, column=2, padx=2, sticky="ew")

        marking_row.columnconfigure(0, weight=1)
        marking_row.columnconfigure(1, weight=1)
        marking_row.columnconfigure(2, weight=1)

        # ===== INDICADOR VISUAL (BELT) =====
        self.belt_indicator = BeltIndicator(right_frame, width=300, height=50)
        # Opcional: definir o alcance de semitons que o belt deve cobrir
        self.belt_indicator.set_range(-12, 12)
        self.belt_indicator.pack(pady=5)

        # Visualizador do pitch ao longo do tempo
        self.pitch_line_chart = PitchLineChart(left_frame, width=640, height=180,
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

        # Cria Treeview
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) possível(is)")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="headings")

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(col, text=col)

        self.tree_coristas.pack(fill="both", expand=True)
        self.tree_coristas.bind("<Double-1>", self._on_double_click_corista)

        # Botões de ação
        button_frame = ttk.Frame(self.frame_coristas)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Remover Selecionado", command=self.remove_corista).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Salvar Dados", command=self.save_coristas).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Recarregar", command=self.reload_coristas_table).pack(side="left", padx=5)

        # Carrega dados iniciais
        self.reload_coristas_table()

    def setup_analise_tab(self):
        """Configura a aba de análise de transposição"""
        # Cabeçalho
        header = ttk.Label(self.frame_analise, text="Ajuste de tom e alcance por voz (compensação por penalidade)",
                           font=("Arial", 12, "bold"))
        header.pack(pady=10)

        # Slider de transposição
        self.t_slider = tk.Scale(self.frame_analise, from_=-12, to=12, orient="horizontal",
                                 label="Transposição (semítons)", command=self.on_t_change, length=600)
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
        music_name_entry = tk.Entry(library_frame, textvariable=self.music_name_var, width=30, fg="grey")
        music_name_placeholder = "Nome da música"
        music_name_entry.insert(0, music_name_placeholder)

        def _clear_name(event):
            if music_name_entry.get() == music_name_placeholder:
                music_name_entry.delete(0, tk.END)
                music_name_entry.config(fg="black")

        def _fill_name(event):
            val = music_name_entry.get()
            if val == "":
                music_name_entry.insert(0, music_name_placeholder)
                music_name_entry.config(fg="grey")
                self.music_name_var.set("")  # keep var sem placeholder
            else:
                # Atualiza a StringVar com o valor real (ignora o placeholder)
                self.music_name_var.set(val)

        music_name_entry.bind("<FocusIn>", _clear_name)
        music_name_entry.bind("<FocusOut>", _fill_name)
        music_name_entry.grid(row=0, column=0, padx=5, pady=5)  # ocupa o espaço da antiga label

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
            piece_ranges={voz: {"min": self.voice_vars[voz]["min"].get(), "max": self.voice_vars[voz]["max"].get()} for
                          voz in VOICES},
            orig_root=self.root_var.get(),
            orig_mode=self.mode_var.get(),
            piece_name=(self.music_name_var.get() if self.music_name_var.get() != music_name_placeholder else "")
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

        # NOVO: Combobox de número de solistas (0 a 5)
        solo_frame_header = ttk.LabelFrame(main_pane, padding=10, text='Solistas')
        solo_frame_header.grid(row=0, column=1, pady=5, padx=5, sticky="nsew")
        self.solist_count_cb = ttk.Combobox(solo_frame_header, values=[0,1,2,3,4,5], width=5, state="readonly")
        self.solist_count_cb.pack(side="left")
        self.solist_count_cb.set(0)
        self.solist_count_cb.bind("<<ComboboxSelected>>", self._on_solists_count_changed)

        # Frame para os solistas (dinâmico)
        self.solist_frame = ttk.Frame(solo_frame_header, padding=10)
        self.solist_frame.pack()

        # Botões de ação
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
        #self.results_text.grid(row=0, column=0, pady=5, sticky="w")
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

        coristas_nomes = [c.get("nome", "") for c in self.coristas_mgr.coristas] or []
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
        # Se já houver dados de música carregada, reflita-os
        if self.music_library:
            # opcional: já poderíamos carregar soloists da música atual se houver
            pass

    def _on_solists_count_changed(self, event=None):
        self._build_solists_ui()
    ### DATA MANAGER SAVE/LOAD
    def add_corista(self):
        nome = self.entrada_nome.get().strip()
        range_min = self.entrada_min.get().strip()
        range_max = self.entrada_max.get().strip()

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
            msg += f"Vozes Possíveis: {', '.join([v for v, _, _ in vozes_poss]) if vozes_poss else 'Nenhuma'}"

            messagebox.showinfo("Sucesso", msg)
            self.entrada_nome.delete(0, "end")
            self.entrada_min.delete(0, "end")
            self.entrada_max.delete(0, "end")
            self.reload_coristas_table()
        else:
            messagebox.showerror("Erro", f"Erro ao adicionar corista:\n{result}")

    def remove_corista(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para remover")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)
        self.coristas_mgr.remove_corista(index)
        self.reload_coristas_table()
        messagebox.showinfo("Sucesso", "Corista removido!")

    def edit_corista_voz(self):
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)
        corista = self.coristas_mgr.coristas[index]

        # Janela de diálogo para seleção de voz
        dialog = tk.Toplevel(self.master)
        dialog.title("Atribuir Voz")
        dialog.geometry("900x850")

        ttk.Label(dialog, text=f"Corista: {corista['nome']}", font=("Arial", 12, "bold")).pack(pady=10)

        # Frame para range atual
        range_frame = ttk.LabelFrame(dialog, text="Range Atual", padding=5)
        range_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(range_frame, text=f"Range: {corista['range_min']} - {corista['range_max']}",
                  font=("Arial", 10)).pack(side="left", padx=10)

        ttk.Label(range_frame, text="💡 Dica: Use o teste vocal na aba de Adicionar Corista",
                  font=("Arial", 8), foreground="#666").pack(side="left", padx=10)

        ttk.Label(dialog, text=f"Voz Calculada: {corista['voz_calculada']}", font=("Arial", 10)).pack(pady=5)

        # Separador
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista['voz_atribuida'])

        # ===== Visualizador de teclado =====
        keyboard = KeyboardVisualizer(dialog)

        # Frame para as opções de voz
        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # RECOMENDADAS
        vozes_recomendadas = corista.get('vozes_recomendadas', [])
        if vozes_recomendadas:
            ttk.Label(vozes_frame, text="✓ Recomendadas (Encaixe Perfeito)", font=("Arial", 11, "bold"),
                      foreground="green").pack(anchor="w", pady=(10, 5))
            for v in vozes_recomendadas:
                def on_select_recomendada(voice=v):
                    var_voz.set(voice)
                    voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                    keyboard.update(corista['range_min'], corista['range_max'],
                                    voice_min_str, voice_max_str)

                ttk.Radiobutton(vozes_frame, text=v, variable=var_voz, value=v,
                                command=on_select_recomendada).pack(anchor="w", padx=50, pady=3)

        # POSSÍVEIS
        vozes_possiveis = corista.get('vozes_possiveis', [])
        if vozes_possiveis:
            ttk.Label(vozes_frame, text="⚠ Possíveis (com ressalva)", font=("Arial", 11, "bold"),
                      foreground="orange").pack(anchor="w", pady=(10, 5))
            for v, diff, obs in vozes_possiveis:
                frame_poss = ttk.Frame(vozes_frame)
                frame_poss.pack(anchor="w", padx=40, pady=3, fill="x")

                def on_select_possivel(voice=v):
                    var_voz.set(voice)
                    voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                    keyboard.update(corista['range_min'], corista['range_max'],
                                    voice_min_str, voice_max_str)

                ttk.Radiobutton(frame_poss, text=v, variable=var_voz, value=v,
                                command=on_select_possivel).pack(side="left")
                ttk.Label(frame_poss, text=f"({obs})", font=("Arial", 9), foreground="gray").pack(side="left", padx=5)

        # Atualiza o teclado inicialmente
        voz_inicial = var_voz.get()
        if voz_inicial:
            voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_inicial]
            keyboard.update(corista['range_min'], corista['range_max'],
                            voice_min_str, voice_max_str)

        def confirm():
            self.coristas_mgr.update_corista_voz(index, var_voz.get())
            self.reload_coristas_table()
            dialog.destroy()

        ttk.Button(dialog, text="Confirmar", command=confirm).pack(pady=20)

    def save_coristas(self):
        if self.coristas_mgr.save_data():
            messagebox.showinfo("Sucesso", "Dados salvos em coristas_data.json")
        else:
            messagebox.showerror("Erro", "Erro ao salvar dados")

    def reload_coristas_table(self):
        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)
        print(self.coristas_mgr.coristas)
        for corista in self.coristas_mgr.coristas:
            self.tree_coristas.insert("", "end", values=(
                corista['nome'],
                corista['range_min'],
                corista['range_max'],
                corista['voz_calculada'],
                corista['voz_atribuida']
            ))

    def save_music_ranges_to_json(self, piece_ranges, orig_root, orig_mode, piece_name=None):
        data_file = "coristas_music_data.json"

        name = piece_name or self.music_name_var.get() or "Untitled"

        # Construção de solistas a partir da UI
        solistas = {}
        for idx, row in enumerate(self.solist_rows):
            cor_name = row["cb"].get()
            if cor_name == "Selecionar..." or not cor_name:
                continue
            min_note = row["min"].get()
            max_note = row["max"].get()
            solistas[str(cor_name)] = {"0": min_note, "1": max_note}

        # Construção de voices a partir do grupo atual
        voices = {}
        grupo_atual = self.grupo_combo.get() or self.grupo_nome_var.get() or "Grupo Vocal"
        # Tenta popular a partir da estrutura existente de coristas no grupo
        data_cache = {}
        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data_cache = json.load(f)
        except Exception:
            data_cache = {}

        group_entries = data_cache.get("grupos", {}).get(grupo_atual, {}) if isinstance(data_cache.get("grupos", {}),
                                                                                        dict) else {}

        # Mapear voz -> nomes encontrados no grupo atual
        for cor_key, cor in group_entries.items():
            if isinstance(cor, dict) and "voz_atribuida" in cor:
                voz = cor.get("voz_atribuida")
                if voz:
                    base = voices.get(voz, {})
                    base[str(len(base))] = cor.get("nome")
                    voices[voz] = base

        entry = {
            "name": name,
            "root": orig_root,
            "mode": orig_mode,
            "grupo": grupo_atual,
            "ranges": piece_ranges,
            "solistas": solistas,
            "voices": voices,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Carregar estrutura atual do coristas_music_data.json
        data = {}
        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"grupos": {}, "musicas": {}}
        except Exception:
            data = {"grupos": {}, "musicas": {}}

        music_map = data.get("musicas", {})
        # Encontrar se já existe música com o mesmo nome
        idx_key = None
        if isinstance(music_map, dict):
            for k, v in music_map.items():
                if isinstance(v, dict) and v.get("name", "").lower() == name.lower():
                    idx_key = k
                    break

        if idx_key is None:
            # Novo registro
            next_idx = 0
            if music_map:
                try:
                    existing_keys = [int(k) for k in music_map.keys() if str(k).isdigit()]
                    next_idx = max(existing_keys, default=-1) + 1
                except Exception:
                    next_idx = len(music_map)
            music_map[str(next_idx)] = entry
        else:
            music_map[idx_key] = entry

        data["musicas"] = music_map

        # Salvar alterações
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Sucesso", f"Faixa salva em {data_file}")
            self.load_music_library()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar faixa: {e}")

        # Nota: a parte de salvar/atualizar o conjunto de coristas por grupo (coristas dentro de 'grupos')
        # fica gerida pelo CoristasManager/ou por ações adicionais conforme necessário.

    def load_music_library(self):
        """
        Carrega a biblioteca de músicas do arquivo JSON.

        CORREÇÃO APLICADA:
        - Usar .clear() em vez de = [] para não perder a referência
        - Isto garante que self.music_library permanece acessível para outras funções
        """
        data_file = "coristas_music_data.json"

        # ✅ MUDANÇA CRÍTICA: Use .clear() ao invés de self.music_library = []
        self.music_library.clear()
        self.music_names = []

        if os.path.exists(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for m in data.get("musicas", []):
                    if isinstance(m, dict) and "name" in m:
                        self.music_library.append(m)
                        self.music_names.append(m["name"])

            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar biblioteca: {e}")

        # Atualiza combobox se existir
        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = self.music_names

    def load_music_ranges_for_selection(self, name):
        """
        Carrega os ranges de uma música selecionada na combobox.

        CORREÇÃO APLICADA:
        - Validar o placeholder ANTES de processar
        - Verificar que self.music_library contém dados (não está vazio)
        """

        # ✅ MUDANÇA 2: Valide o placeholder ANTES de tentar acessar a lista
        if not name or name.startswith("--"):
            messagebox.showwarning("Aviso", "Nenhuma música válida selecionada.")
            return

        # Agora self.music_library contém dados! (não foi zerado)
        item = next((m for m in self.music_library if m.get("name") == name), None)

        if item is None:
            messagebox.showerror("Erro", f"Música '{name}' não encontrada na biblioteca.")
            return

        # Preenche controles de cada voz com os ranges salvos
        ranges = item.get("ranges", {})
        for voice, vr in ranges.items():
            min_val = vr.get("min", "")
            max_val = vr.get("max", "")

            # Se ambos estiverem em branco, não preenche
            if min_val == "" and max_val == "":
                continue

            if voice in self.voice_vars:
                self.voice_vars[voice]["min"].delete(0, "end")
                self.voice_vars[voice]["min"].insert(0, min_val)
                self.voice_vars[voice]["max"].delete(0, "end")
                self.voice_vars[voice]["max"].insert(0, max_val)

        # Determina o nome da música
        self.music_name_var.set(item.get("name", ""))

        # Executa análise com os dados carregados
        self.run_analysis()

    def load_group_ranges(self):
        """Carrega os ranges calculados do grupo de coristas para as entradas"""
        if not self.coristas_mgr.coristas:
            messagebox.showwarning("Aviso", "Nenhum corista cadastrado!")
            return

        group_ranges = self.coristas_mgr.get_voice_group_ranges()
        if self.visualizer:
            self.visualizer.set_group_ranges(group_ranges)
        self.group_ranges = group_ranges
        # Atualize a análise para o novo range
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
            self.coristas = True
            # Estamos usando os ranges de grupo
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                group_ranges = self.coristas_mgr.get_voice_group_ranges()
                # Atualiza o visualizador se ele suportar ranges de grupo
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(group_ranges)
            else:
                # Sem ranges de grupo disponíveis; fallback para base
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(None)
        else:
            self.coristas = False
            # Usando VOICE_BASE_RANGES
            if hasattr(self.visualizer, "set_group_ranges"):
                self.visualizer.set_group_ranges(None)

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
            orig_root = self.root_var.get()
            orig_mode = self.mode_var.get()
            piece_ranges = self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            # T atual vindo da barra de transposição
            t_current = int(float(self.t_slider.get())) if hasattr(self, "t_slider") else 0

            # Group ranges (se ativo)
            group_ranges = None
            if getattr(self, "_use_group_ranges", False):
                if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                    group_ranges = self.coristas_mgr.get_voice_group_ranges()

            # Cálculo unificado da melhor transposição
            analysis = compute_best_transposition(orig_root, orig_mode, piece_ranges, group_ranges)

            self._latest_analysis = analysis  # armazenar para uso futuro, se necessário

            # Exibir resultados de forma consistente
            self.on_t_change(0)

            # Cálculo dos Os para o T atual e atualização do visualizador
            per_voice_Os_for_T = compute_per_voice_Os_for_T(t_current, piece_ranges, group_ranges)
            self.visualizer.update(piece_ranges, t_current, per_voice_Os_for_T)

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
            group_ranges = self.coristas_mgr.get_voice_group_ranges() if self.coristas else None

            if not piece_ranges:
                return

            # Calcula os O_i para o T atual
            per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, group_ranges)

            # Atualiza visualização gráfica com o T atual
            self.visualizer.update(piece_ranges, T, per_voice_Os)

            current_root = self.root_var.get()
            current_mode = self.mode_var.get()

            # Transposição atual para exibição
            transposed_root = transpose_note(current_root, T)

            # Obter ranking completo de Ts (debug) para exibir possíveis transposições
            analysis_all = analyze_ranges_with_penalty(current_root, current_mode, piece_ranges, group_ranges)
            debug = analysis_all.get("debug", [])

            # Construção consolidada do bloco de resultados
            self.results_text.delete(1.0, "end")

            best_T_global = analysis_all.get("best_T")
            best_key_root = analysis_all.get("best_key_root")
            best_key_mode = analysis_all.get("best_key_mode")
            if best_T_global is not None:
                self.results_text.insert("end", f"Melhor transposição: {best_T_global:+d} semitons → {best_key_root} {best_key_mode}\n")

            self.results_text.insert("end",
                                     f"Transposição atual: {T:+d} semitons ({current_root} → {transposed_root})\n")

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
            for v in group_ranges.keys() if self.coristas else VOICES:
                mn, mx = piece_ranges.get(v, (None, None))
                if mn is None or mx is None:
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