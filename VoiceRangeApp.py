import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import time
from CoristasManager import CoristasManager
from Constants import VOICES, VOICE_BASE_RANGES
from KeyboardVisualizer import KeyboardVisualizer
from RangeVisualizer import RangeVisualizer
from GeneralFunctions import analyze_ranges_with_penalty, note_to_midi, transpose_note, midi_to_note
from VocalTester import VocalTestCore, BeltIndicator
import threading

# ===== INTERFACE GRÁFICA =====
class VoiceRangeApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Programa de Transposição Vocal - com Gerenciamento de Coristas")
        self.master.geometry("1000x900")
        self.master.resizable(True, True)

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
        self.setup_analise_tab()

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

        # Estado e repetição
        state_row = ttk.Frame(right_frame)
        state_row.pack(anchor="w", pady=(0, 5))

        ttk.Label(state_row, text="Estado: Pronto", font=("Arial", 9),
                  foreground="#2E86AB").pack(side="left")

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

        self.btn_too_low = ttk.Button(marking_row, text="⬇️ Grave D.",
                                      command=self.mark_too_low_vocal, state='disabled')
        self.btn_too_low.grid(row=0, column=0, padx=2, sticky="ew")

        self.btn_too_high = ttk.Button(marking_row, text="⬆️ Agudo D.",
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

        # ===== PROGRESSO DE TEMPO =====
        self.time_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.time_var,
                                            maximum=100, length=300, mode='determinate')
        self.progress_bar.pack(pady=3)

        self.time_label = ttk.Label(right_frame, text="Tempo: 0.0s / 3.0s",
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

        # Botão adicionar
        btn_add = ttk.Button(left_frame, text="Adicionar Corista", command=self.add_corista)
        btn_add.grid(row=2, column=0, columnspan=5, pady=10)

        # Tabela de coristas
        table_frame = ttk.LabelFrame(self.frame_coristas, text="Coristas Cadastrados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Cria Treeview
        columns = ("Nome", "Range Min", "Range Max", "Voz Calculada", "Voz Atribuída")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="headings")

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(col, text=col)

        self.tree_coristas.pack(fill="both", expand=True)
        self.tree_coristas.bind("<Double-1>", self._on_double_click_corista)

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_coristas.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_coristas.configure(yscroll=scrollbar.set)

        # Botões de ação
        button_frame = ttk.Frame(self.frame_coristas)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Remover Selecionado", command=self.remove_corista).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Salvar Dados", command=self.save_coristas).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Recarregar", command=self.reload_coristas_table).pack(side="left", padx=5)

        # Carrega dados iniciais
        self.reload_coristas_table()

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

        # Ambos habilitados ao iniciar
        #self.btn_too_low.config(state='normal')
        #self.btn_too_high.config(state='normal')
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

    def setup_analise_tab(self):
        """Configura a aba de análise de transposição"""
        # Cabeçalho
        header = ttk.Label(self.frame_analise, text="Ajuste de tom e alcance por voz (compensação por penalidade)",
                           font=("Arial", 12, "bold"))
        header.pack(pady=10)

        # Controles de tonalidade
        ctrl_frame = ttk.Frame(self.frame_analise)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(ctrl_frame, text="Tom original (raiz):").pack(side="left", padx=5)
        self.root_var = tk.StringVar()
        self.root_combo = ttk.Combobox(ctrl_frame, textvariable=self.root_var, state="readonly", width=8,
                                       values=["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab",
                                               "A", "A#", "Bb", "B"])
        self.root_combo.current(0)
        self.root_combo.pack(side="left", padx=5)

        ttk.Label(ctrl_frame, text="Modo:").pack(side="left", padx=5)
        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(ctrl_frame, textvariable=self.mode_var, state="readonly", width=10,
                                       values=["maior", "menor"])
        self.mode_combo.current(0)
        self.mode_combo.pack(side="left", padx=5)

        # Slider de transposição
        self.t_slider = tk.Scale(self.frame_analise, from_=-24, to=24, orient="horizontal",
                                 label="Transposição (semítons)", command=self.on_t_change, length=600)
        self.t_slider.set(0)
        self.t_slider.pack(fill="x", padx=10, pady=10)

        # Faixas da peça (carregadas do grupo de coristas)
        ranges_frame = ttk.LabelFrame(self.frame_analise, text="Faixa da Música por Voz", padding=10)
        ranges_frame.pack(fill="x", padx=10, pady=10)

        self.voice_vars = {}
        for idx, v in enumerate(VOICES):
            row = idx // 3
            col = idx % 3
            frame_v = ttk.Frame(ranges_frame)
            frame_v.grid(row=row, column=col, padx=10, pady=5)

            ttk.Label(frame_v, text=f"{v}:").pack(side="left")
            min_entry = ttk.Entry(frame_v, width=10)
            min_entry.pack(side="left", padx=2)
            max_entry = ttk.Entry(frame_v, width=10)
            max_entry.pack(side="left", padx=2)

            # Valores padrão
            min_entry.insert(0, "A4")
            max_entry.insert(0, "A5")

            self.voice_vars[v] = {"min": min_entry, "max": max_entry}

        # Botões de ação
        action_frame = ttk.Frame(self.frame_analise)
        action_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(action_frame, text="Usar ranges do grupo de coristas", command=self.load_group_ranges).pack(
            side="left", padx=5)
        ttk.Button(action_frame, text="Executar análise", command=self.run_analysis).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Limpar resultados", command=self.clear_results).pack(side="left", padx=5)

        # Visualizador
        self.visualizer = RangeVisualizer(self.frame_analise, voices=VOICES, base_ranges=VOICE_BASE_RANGES, coristas=self.coristas_mgr.coristas)

        # Área de resultados
        result_label = ttk.Label(self.frame_analise, text="Resultados", font=("Arial", 11, "bold"))
        result_label.pack(pady=(10, 0))

        self.results_text = tk.Text(self.frame_analise, height=10, width=110, wrap="word", font=("Consolas", 10))
        self.results_text.pack(fill="both", expand=True, padx=10, pady=5)

        self.results_text.insert("end", "Informe os ranges vocais e a faixa da música por voz.\n")

        self.current_result = None

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

        for corista in self.coristas_mgr.coristas:
            self.tree_coristas.insert("", "end", values=(
                corista['nome'],
                corista['range_min'],
                corista['range_max'],
                corista['voz_calculada'],
                corista['voz_atribuida']
            ))

    def save_music_ranges_to_json(self, piece_ranges, best_T, orig_root, orig_mode):
        data_file = "music_ranges.json"

        entry = {
            "id": int(time.time()),
            "root": orig_root,
            "mode": orig_mode,
            "transposition": best_T,
            "ranges": piece_ranges,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"musicas": []}
                data["musicas"].append(entry)
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("Sucesso", f"Faixa salva em {data_file}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar faixa: {e}")

    def load_group_ranges(self):
        """Carrega os ranges calculados do grupo de coristas para as entradas"""
        if not self.coristas_mgr.coristas:
            messagebox.showwarning("Aviso", "Nenhum corista cadastrado!")
            return

        group_ranges = self.coristas_mgr.get_voice_group_ranges()

        # Armazena para uso no visualizador (sem alterar faixas de música)
        if hasattr(self, "visualizer") and self.visualizer:
            self.visualizer.set_group_ranges(group_ranges)

            self.group_ranges = group_ranges  # guarda para acesso posterior, se necessário
            messagebox.showinfo("Sucesso",
                                "Ranges do grupo de coristas carregados para visualização (não alteram Faixas da Música).")

    def clear_results(self):
        """Limpa a área de resultados"""
        self.results_text.delete(1.0, "end")
        self.results_text.insert("end", "Resultados limpos. Informe os ranges vocais e execute a análise novamente.\n")

    def read_voice_ranges(self):
        ranges = {}
        for v in VOICES:
            min_str = self.voice_vars[v]["min"].get().strip()
            max_str = self.voice_vars[v]["max"].get().strip()
            if not min_str or not max_str:
                raise ValueError(f"Faixa de {v} está vazia.")
            ranges[v] = (min_str, max_str)
        return ranges

    def run_analysis(self):
        try:
            orig_root = self.root_var.get()
            orig_mode = self.mode_var.get()
            piece_ranges = self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            result = analyze_ranges_with_penalty(orig_root, orig_mode, piece_ranges)
            self.display_results(result, orig_root, orig_mode, piece_ranges)

            if result and result.get("best_T") is not None:
                best_T = result["best_T"]
                best_Os = result.get("best_Os", {})
                self.visualizer.update(piece_ranges, best_T, best_Os)
                # Novo: salvar faixa de música com a transposição aplicada
                self.save_music_ranges_to_json(piece_ranges, best_T, orig_root, orig_mode)

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def on_t_change(self, value):
        try:
            T = int(float(value))
            piece_ranges = getattr(self, "current_piece_ranges", None)
            if not piece_ranges:
                return

            per_voice_Os = {}
            for v in VOICES:
                mn = note_to_midi(piece_ranges[v][0])
                mx = note_to_midi(piece_ranges[v][1])

                best_O = None
                best_pen = float('inf')
                for O in range(-4, 5):
                    low = mn + T + 12 * O
                    high = mx + T + 12 * O
                    pen = max(0, note_to_midi(VOICE_BASE_RANGES[v][0]) - low) + \
                          max(0, high - note_to_midi(VOICE_BASE_RANGES[v][1]))
                    if pen < best_pen or (pen == best_pen and (best_O is None or abs(O) < abs(best_O))):
                        best_O = O
                        best_pen = pen
                per_voice_Os[v] = best_O

            self.visualizer.update(piece_ranges, T, per_voice_Os)

            self.results_text.delete(1.0, "end")
            current_root = self.root_var.get()  # Pega o valor do Combobox
            transposed_root = transpose_note(current_root, T)

            self.results_text.insert("end",
                                     f"Transposição atual (T): {T:+d} semitons ({current_root} → {transposed_root})\n")

            self.results_text.insert("end", "Ajustes por voz (O_i):\n")
            for v in VOICES:
                self.results_text.insert("end", f"  - {v}: O_i = {per_voice_Os[v]}\n")

        except Exception:
            pass

    def display_results(self, result, orig_root, orig_mode, piece_ranges):
        self.results_text.delete(1.0, "end")

        if result["best_T"] is None:
            self.results_text.insert("end", "Não foi possível encontrar uma transposição adequada.\n")
            return

        best_T = result["best_T"]
        best_Os = result.get("best_Os", {})
        best_key_root = result["best_key_root"]
        best_key_mode = result["best_key_mode"]

        self.results_text.insert("end", f"Tom original: {orig_root} {orig_mode}\n")
        self.results_text.insert("end", f"Melhor transposição: {best_T:+d} semitons\n")
        self.results_text.insert("end", f"Nova chave: {best_key_root} {best_key_mode}\n\n")

        self.results_text.insert("end", "Ajustes por voz (O_i):\n")
        for v in VOICES:
            o = best_Os.get(v, 0)
            min_str, max_str = piece_ranges[v]
            self.results_text.insert("end", f"  {v}: O_i = {o}  (faixa {min_str} .. {max_str})\n")

        self.results_text.insert("end", "\nFaixas resultantes:\n")
        for v in VOICES:
            mn, mx = piece_ranges[v]
            min_m = note_to_midi(mn)
            max_m = note_to_midi(mx)
            O = best_Os.get(v, 0)
            min_final = min_m + best_T + 12 * O
            max_final = max_m + best_T + 12 * O
            self.results_text.insert("end",
                                     f"  {v}: {midi_to_note(int(min_final))} .. {midi_to_note(int(max_final))}\n")