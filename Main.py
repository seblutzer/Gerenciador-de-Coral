"""
Main.py Refatorado - Aplicação de Gerenciamento Vocal
Responsabilidade única: Orquestração e inicialização da aplicação
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import webbrowser
from pathlib import Path

# Managers
from CoristasManager import CoristasManager
from MusicDataManager import MusicDataManager
from VocalTestManager import VocalTestManager
from AnalysisManager import AnalysisManager
from CoristasUIManager import CoristasUIManager
from MusicLibraryUIManager import MusicLibraryUIManager
from VocalTestUIBuilder import VocalTestUIBuilder

# Outros componentes
from Constants import VOICES, VOICE_BASE_RANGES
from RangeVisualizer import RangeVisualizer
from MusicTranspose import AudioAnalyzer
from VocalTester import VocalTestCore
from GeneralFunctions import rreplace

class VoiceRangeApp:
    """
    Aplicação principal de gerenciamento vocal.
    Responsabilidade: Orquestração e coordenação entre os componentes.
    """

    def __init__(self, master):
        self.master = master
        self.master.title("Gerenciamento do Grupo Vocal - By Eduardo Lutzer")
        self.master.geometry("1200x1000")
        self.master.resizable(True, True)

        # ===== INICIALIZAÇÃO DOS MANAGERS =====
        self.coristas_mgr = CoristasManager()
        self.analyzer = AudioAnalyzer(root_dir='Musicas')
        self.music_data_mgr = MusicDataManager(self.coristas_mgr)
        self.analysis_mgr = AnalysisManager(self.coristas_mgr)

        # Vocal test será inicializado com callbacks depois
        self.vocal_test_mgr = None

        # ===== NOTEBOOK PRINCIPAL =====
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== ABA 1: GERENCIAR CORISTAS =====
        self.frame_coristas = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_coristas, text="Gerenciar Coristas")
        self.setup_coristas_tab()

        # ===== ABA 2: BIBLIOTECA MUSICAL =====
        self.frame_analise = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_analise, text="Biblioteca Musical")
        self.setup_analise_tab()

        # Labels
        self.sugest_label = ttk.Label(self.buttons_frame, text="Sugestão de Formação:", font=("Arial, 10"), padding=10)

    # ============================================================
    # ABA 1: GERENCIAR CORISTAS
    # ============================================================

    def setup_coristas_tab(self
                           ):
        """Configura a aba de gerenciamento de coristas."""
        main_frame = ttk.Frame(self.frame_coristas)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== LEFT: Adicionar/Editar Corista =====
        left_frame = ttk.LabelFrame(main_frame, text="Adicionar/Editar Corista", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Campos de entrada
        ttk.Label(left_frame, text="Nome:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entrada_nome = ttk.Entry(left_frame, width=30)
        self.entrada_nome.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Min (ex: G3):").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entrada_min = ttk.Entry(left_frame, width=15)
        self.entrada_min.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(left_frame, text="Range Max (ex: C5):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entrada_max = ttk.Entry(left_frame, width=15)
        self.entrada_max.grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(left_frame, text="Adicionar Corista", command=self.add_corista).grid(
            row=2, column=0, columnspan=4, pady=10
        )

        # ===== RIGHT: Teste Vocal =====
        right_frame = ttk.LabelFrame(main_frame, text="Teste Vocal Integrado", padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Constrói UI de teste vocal
        testing_time_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        default_testing_time = VocalTestCore.DEFAULT_TESTING_TIME

        vocal_ui_builder = VocalTestUIBuilder(right_frame, testing_time_values, default_testing_time)
        vocal_ui_builder.build()
        self.vocal_widgets = vocal_ui_builder.get_widgets()

        # Adiciona gráfico de pitch ao left_frame
        pitch_chart = vocal_ui_builder.add_pitch_chart(left_frame)
        pitch_chart.grid(row=3, column=0, columnspan=5, pady=10)
        self.vocal_widgets['pitch_line_chart'] = pitch_chart

        # Inicializa VocalTestManager com callbacks
        self.vocal_test_mgr = VocalTestManager({
            'update_ui': self.update_vocal_test_ui,
            'on_complete': self.on_vocal_test_complete,
            'update_buttons': self.update_button_states
        })

        # Conecta botões
        self.vocal_widgets['btn_start_test'].config(command=self.start_vocal_test)
        self.vocal_widgets['btn_quick_test'].config(command=self.start_quick_vocal_test)
        self.vocal_widgets['btn_rec'].config(command=self.toggle_pitch_recording)
        self.vocal_widgets['btn_stop_test'].config(command=self.stop_vocal_test)
        self.vocal_widgets['btn_too_low'].config(command=self.mark_too_low_vocal)
        self.vocal_widgets['btn_too_high'].config(command=self.mark_too_high_vocal)
        self.vocal_widgets['btn_repeat_tone'].config(command=self.repeat_tone_vocal)
        self.vocal_widgets['testing_time_cb'].bind("<<ComboboxSelected>>", self._on_testing_time_changed)
        self.vocal_widgets['noise_gate_slider'].config(command=self._on_noise_gate_changed)
        self.vocal_widgets['piano_game_check'].config(command=self._on_piano_game_toggled)

        # ===== TABELA DE CORISTAS =====
        table_frame = ttk.LabelFrame(self.frame_coristas, text="Coristas Cadastrados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        group_frame = ttk.Frame(table_frame, padding=10)
        group_frame.pack(side='left', fill="y", padx=10, pady=10)

        # Inicializa CoristasUIManager
        self.coristas_ui_mgr = CoristasUIManager(
            table_frame,
            self.coristas_mgr,
            on_reload_callback=self.on_coristas_data_changed,
            on_group_changed=self.on_group_changed
        )
        self.coristas_ui_mgr.create_group_selector(group_frame)
        self.coristas_ui_mgr.create_table(table_frame)

        # Botões de ação
        ttk.Button(group_frame, text="Remover Selecionado", command=self.remove_corista).pack(pady=2)
        ttk.Button(group_frame, text="Editar Voz Atribuída", command=self.edit_corista_voz).pack(pady=2)

        # Carrega dados iniciais
        self.coristas_ui_mgr.reload_table()

    # ============================================================
    # ABA 2: BIBLIOTECA MUSICAL
    # ============================================================

    def setup_analise_tab(self
                          ):
        """Configura a aba de análise de transposição."""
        # Slider de transposição
        self.t_slider = tk.Scale(
            self.frame_analise,
            from_=-11, to=11,
            orient="horizontal",
            label="Transposição (semítons)",
            command=self.on_t_change,
            length=600
        )
        self.t_slider.set(0)
        self.t_slider.pack(fill="x", padx=10, pady=10)

        main_pane = ttk.Frame(self.frame_analise)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # ===== FAIXAS DA MÚSICA =====
        ranges_frame = ttk.LabelFrame(main_pane, text="Faixa da Música por Voz", padding=10)
        ranges_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ===== BIBLIOTECA DE MÚSICAS =====
        library_frame = ttk.LabelFrame(main_pane, text="Biblioteca de Músicas", padding=10)
        library_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        main_pane.columnconfigure(0, weight=1)
        main_pane.columnconfigure(1, weight=1)

        # Inicializa MusicLibraryUIManager
        self.music_ui_mgr = MusicLibraryUIManager(
            library_frame,
            self.coristas_mgr,
            self.music_data_mgr,
            self.analyzer
        )

        # Campo de nome
        music_name_entry = self.music_ui_mgr.create_music_name_field(library_frame)
        music_name_entry.grid(row=0, column=0, padx=5, pady=5)

        # Combobox de seleção
        music_combo = self.music_ui_mgr.create_music_selector(
            library_frame,
            self.load_music_ranges_for_selection
        )
        music_combo.grid(row=1, column=0, padx=5, pady=5)

        # Botões
        ttk.Button(library_frame, text='💾', width=5, command=self.save_music_ranges).grid(
            row=0, column=1, padx=5, pady=5
        )
        ttk.Button(library_frame, text='📂', command=self.load_voice_audio_files, width=5).grid(
            row=1, column=1, padx=5, pady=5
        )

        # Tom e modo
        ttk.Label(library_frame, text="Tom original (raiz):").grid(row=2, column=0, padx=5, pady=5)
        root_combo = self.music_ui_mgr.create_root_selector(library_frame, self._on_root_selected)
        root_combo.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(library_frame, text="Modo:").grid(row=3, column=0, padx=5, pady=5)
        mode_combo = self.music_ui_mgr.create_mode_selector(library_frame, self._on_mode_selected)
        mode_combo.grid(row=3, column=1, padx=5, pady=5)

        # Ranges de vozes
        self.music_ui_mgr.create_voice_range_entries(ranges_frame)

        # ===== SOLISTAS =====
        solo_frame_header = ttk.LabelFrame(main_pane, padding=10, text='Solistas')
        solo_frame_header.grid(row=0, column=1, pady=5, padx=5, sticky="nsew")
        self.music_ui_mgr.create_solists_ui(solo_frame_header)

        # ===== RESULTADOS =====
        result_frame = ttk.LabelFrame(main_pane, text="Resultados", padding=10)
        result_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.results_text = tk.Text(result_frame, height=9, width=50, wrap="word", font=("Consolas", 10))
        self.results_text.pack(anchor="w", padx=5, pady=3, fill="x")
        self.results_text.insert("end", "Resultados: Informe os ranges vocais e a faixa da música por voz.\n")

        self.buttons_frame = ttk.LabelFrame(self.frame_analise, padding=10)
        self.buttons_frame.pack(side='left')

        # ===== BOTÃO DINÂMICO =====
        self.dynamic_ranges_button = ttk.Button(self.buttons_frame, text="Vozes do Grupo", command=self.toggle_group_or_voice_ranges)
        self.dynamic_ranges_button.pack(padx=5)

        # ===== BOTÃO DE MELHORES VOZES =====
        self.calculate_voices_button = ttk.Button(self.buttons_frame, text="Aplicar Vozes", command=self.apply_best_voices)
        self.calculate_voices_button.pack(padx=5)

        # Slider de conforto
        self.confort_slider = tk.Scale(
            self.buttons_frame,
            from_=0, to=1,
            orient="horizontal",
            label="Grave - Agudo",
            command=self.on_confort_change,
            length=60,
            resolution=0.1
        )
        self.confort_slider.set(0.3)
        self.confort_slider.pack(fill="x", padx=10, pady=10)

        # ===== VISUALIZADOR =====
        self.visualizer = RangeVisualizer(
            self.frame_analise,
            voices=VOICES,
            base_ranges=VOICE_BASE_RANGES,
            coristas=self.coristas_mgr.coristas
        )

        # Carrega biblioteca inicial
        self.coristas_ui_mgr.grupo_nome_var.set(self.coristas_ui_mgr.grupo_combo.get())
        self.music_ui_mgr.update_music_library(self.coristas_ui_mgr.grupo_nome_var.get())

    def on_confort_change(self, value):
        self.run_analysis(confort=value)
        self.t_slider.set(self.analysis_mgr.analysis_all['best_T'])

    def apply_best_voices(self):
        try:
            best_voices = self.analysis_mgr.analysis_all['possible_fit'].get(int(self.t_slider.get()), None)

            # Coletar todas as mudanças propostas
            changes = []
            for voice in best_voices:
                if voice in VOICE_BASE_RANGES:
                    for name in best_voices[voice]:
                        current_voice = self.coristas_mgr.coristas[name]['voz_atribuida']
                        if current_voice != voice:
                            changes.append({
                                'name': name,
                                'from': current_voice,
                                'to': voice
                            })

            if not changes:
                messagebox.showinfo(title='Nenhuma alteração',
                                    message='Não há alterações a serem feitas.')
                return

            # Mostrar diálogo de seleção
            selected_changes = self.show_changes_dialog(changes)

            # Aplicar mudanças selecionadas
            if selected_changes:
                applied_msg = ''
                for change in selected_changes:
                    self.coristas_mgr.coristas[change['name']]['voz_atribuida'] = change['to']
                    applied_msg += f"- {change['name']} foi alterado de {change['from']} para {change['to']}\n"

                applied_msg += '\nPara salvar as alterações, salve a música'
                messagebox.showinfo(title='Alterações realizadas!', message=applied_msg)

                self.coristas_ui_mgr.reload_table()
                self.analysis_mgr._use_group_ranges = not self.analysis_mgr._use_group_ranges
                self.toggle_group_or_voice_ranges()

        except Exception as e:
            messagebox.showerror(title='Erro', message=f'Erro ao aplicar alterações: {str(e)}')

    def show_changes_dialog(self, changes):
        dialog = tk.Toplevel(self.master)
        dialog.title('Selecionar Mudanças')
        dialog.geometry('300x300')
        dialog.transient(self.master)
        dialog.grab_set()

        # Variável para armazenar o resultado
        result = []

        # Frame principal com scrollbar
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Label de instruções
        ttk.Label(main_frame,
                  text='Selecione as mudanças que deseja aplicar:',
                  font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        # Frame com canvas e scrollbar para a lista de checkboxes
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill='both', expand=True)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        # Variáveis para os checkboxes
        check_vars = []

        for i, change in enumerate(changes):
            var = tk.BooleanVar(value=True)  # Marcado por padrão
            check_vars.append(var)

            text = f"{change['name']}: {change['from']} → {change['to']}"
            cb = ttk.Checkbutton(scrollable_frame, text=text, variable=var)
            cb.pack(anchor='w', pady=2, padx=5)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Frame de botões
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 0))

        def apply_selected():
            nonlocal result
            result = [changes[i] for i, var in enumerate(check_vars) if var.get()]
            dialog.destroy()

        def cancel():
            nonlocal result
            result = []
            dialog.destroy()

        # Botões
        ttk.Button(button_frame, text='Aceitar',
                   command=apply_selected).pack(side='left', padx=15)
        ttk.Button(button_frame, text='Recusar',
                   command=cancel).pack(side='left', padx=15)

        # Centralizar diálogo
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')

        # Aguardar fechamento do diálogo
        dialog.wait_window()

        return result
    # ============================================================
    # CALLBACKS - CORISTAS
    # ============================================================

    def add_corista(self
                    ):
        """Adiciona um corista."""
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
            self.coristas_ui_mgr.reload_table()

    def remove_corista(self
                       ):
        """Remove o corista selecionado."""
        success, msg = self.coristas_ui_mgr.remove_selected_corista()
        if success:
            messagebox.showinfo("Sucesso", msg)
        else:
            messagebox.showwarning("Aviso", msg)

    def edit_corista_voz(self
                         ):
        """Abre janela de edição do corista selecionado."""
        self.coristas_ui_mgr.edit_selected_corista(self.master)

    def on_coristas_data_changed(self
                                 ):
        """Callback quando dados de coristas mudam."""
        # Recarrega lista de música
        self.music_ui_mgr.update_music_library(self.coristas_ui_mgr.get_current_group())
        # Reexecuta análise se houver
        if hasattr(self, 'analysis_mgr') and self.analysis_mgr.current_piece_ranges:
            self.run_analysis()

    def on_group_changed(self,
                         grupo):
        # limpa campos da aba de música
        self.music_ui_mgr.clear_all_fields()
        # limpa os resultados:
        self.results_text.delete(1.0, 'end')
        self.results_text.insert("end", "Resultados: Informe os ranges vocais e a faixa da música por voz.")

        # limpa a vizualização dos ranges
        self.visualizer.canvas.delete("all")
        self.visualizer.draw_grid()

    # ============================================================
    # CALLBACKS - TESTE VOCAL
    # ============================================================

    def start_vocal_test(self
                         ):
        """Inicia teste vocal normal."""
        success, msg = self.vocal_test_mgr.start_test('normal')
        if not success:
            messagebox.showwarning("Aviso", msg)
            return

        self.vocal_widgets['testing_time_cb'].config(state='disabled')
        self.vocal_widgets['btn_repeat_tone'].config(state='normal')
        self.vocal_widgets['btn_start_test'].config(state='disabled')
        self.vocal_widgets['btn_quick_test'].config(state='disabled')
        self.vocal_widgets['btn_rec'].config(state='disabled')
        self.vocal_widgets['btn_stop_test'].config(state='normal')
        self.vocal_widgets['status_label'].config(text="Iniciando teste normal...", foreground='#F39C12')

    def start_quick_vocal_test(self
                               ):
        """Inicia teste vocal rápido."""
        success, msg = self.vocal_test_mgr.start_test('quick')
        if not success:
            messagebox.showwarning("Aviso", msg)
            return

        self.vocal_widgets['testing_time_cb'].config(state='disabled')
        self.vocal_widgets['btn_start_test'].config(state='disabled')
        self.vocal_widgets['btn_quick_test'].config(state='disabled')
        self.vocal_widgets['btn_rec'].config(state='disabled')
        self.vocal_widgets['btn_stop_test'].config(state='normal')
        self.vocal_widgets['btn_repeat_tone'].config(state='disabled')
        self.vocal_widgets['status_label'].config(text="Iniciando teste rápido...", foreground='#F39C12')

    def stop_vocal_test(self
                        ):
        """Para o teste vocal ou gravação."""
        # Verifica se é gravação de pitch
        if self.vocal_test_mgr.vocal_tester and hasattr(self.vocal_test_mgr.vocal_tester, '_record_pitch') and self.vocal_test_mgr.vocal_tester._record_pitch:
            # É gravação - chama toggle para parar
            self.toggle_pitch_recording()
            return

        # É teste normal - para o teste
        self.vocal_test_mgr.stop_test()

        self.vocal_widgets['testing_time_cb'].config(state='normal')
        self.vocal_widgets['btn_start_test'].config(state='normal')
        self.vocal_widgets['btn_quick_test'].config(state='normal')
        self.vocal_widgets['btn_rec'].config(state='normal', text="🔴REC Pitch")
        self.vocal_widgets['btn_stop_test'].config(state='disabled')
        self.vocal_widgets['btn_too_low'].config(state='disabled')
        self.vocal_widgets['btn_too_high'].config(state='disabled')
        self.vocal_widgets['btn_repeat_tone'].config(state='disabled')
        self.vocal_widgets['status_label'].config(text="Teste cancelado", foreground='#E74C3C')

    def mark_too_low_vocal(self
                           ):
        """Marca como grave demais."""
        self.vocal_test_mgr.mark_too_low()

    def mark_too_high_vocal(self
                            ):
        """Marca como agudo demais."""
        self.vocal_test_mgr.mark_too_high()

    def repeat_tone_vocal(self
                          ):
        """Repete o tom atual."""
        success, msg = self.vocal_test_mgr.repeat_current_tone()
        if success:
            self.vocal_widgets['status_label'].config(text=msg, foreground='#27AE60')
        else:
            messagebox.showinfo("Aviso", msg)

    def _on_testing_time_changed(self,
                                 event):
        """Callback quando tempo de teste muda."""
        try:
            new_time = int(self.vocal_widgets['testing_time_cb'].get())
            self.vocal_test_mgr.update_testing_time(new_time)
            self.vocal_widgets['time_label'].config(text=f"Tempo: 0.0s / {new_time}.0s")
        except:
            pass

    def _on_noise_gate_changed(self,
                               value):
        """Callback quando noise gate muda."""
        try:
            new_threshold = float(value)
            self.vocal_test_mgr.update_noise_gate(new_threshold)
            self.vocal_widgets['noise_gate_value_label'].config(text=f"{new_threshold:.4f}")
        except:
            pass

    def _on_piano_game_toggled(self
                               ):
        """Callback quando checkbox do piano gamificado é alterado."""
        enabled = self.vocal_widgets['piano_game_var'].get()
        self.vocal_test_mgr.enable_piano_game(enabled)

    def update_vocal_test_ui(self,
                             **kwargs):
        """Atualiza elementos visuais do teste vocal."""
        if 'expected_note' in kwargs:
            self.vocal_widgets['expected_note_label'].config(text=kwargs['expected_note'])

        if 'detected_note' in kwargs:
            self.vocal_widgets['detected_note_label'].config(text=kwargs['detected_note'])

        if 'current_note' in kwargs:
            self.vocal_widgets['pitch_line_chart'].current_note = kwargs['current_note']

        if 'status' in kwargs:
            color = kwargs.get('status_color', '#666')
            self.vocal_widgets['status_label'].config(text=kwargs['status'], foreground=color)

        if 'time' in kwargs:
            self.vocal_widgets['time_var'].set(kwargs['time'])

        if 'time_text' in kwargs:
            self.vocal_widgets['time_label'].config(text=kwargs['time_text'])

        if 'offset_cents' in kwargs:
            self.vocal_widgets['belt_indicator'].set_offset(kwargs['offset_cents'])

        if 'pitch_hz' in kwargs:
            hz = kwargs['pitch_hz']
            if hz is not None and hz > 0:
                self.master.after(0, self.vocal_widgets['pitch_line_chart'].add_sample, hz)

        # Botões
        button_map = [
            ('start_button', 'btn_start_test'),
            ('start_quick_button', 'btn_quick_test'),
            ('recording_button', 'btn_rec'),
            ('stop_button', 'btn_stop_test'),
            ('repeat_button', 'btn_repeat_tone'),
            ('too_low_button', 'btn_too_low'),
            ('too_high_button', 'btn_too_high'),
        ]

        for key, widget_key in button_map:
            if key in kwargs and widget_key in self.vocal_widgets:
                self.vocal_widgets[widget_key].config(state=kwargs[key])

    def update_button_states(self,
                             **kwargs):
        """Atualiza estado dos botões."""
        button_states = kwargs.get('button_states', {})
        if 'too_low' in button_states:
            self.vocal_widgets['btn_too_low'].config(state=button_states['too_low'])
        if 'too_high' in button_states:
            self.vocal_widgets['btn_too_high'].config(state=button_states['too_high'])

    def on_vocal_test_complete(self,
                               range_min, range_max):
        """Callback quando teste vocal completa."""
        if range_min and range_max:
            self.entrada_min.delete(0, "end")
            self.entrada_min.insert(0, range_min)
            self.entrada_max.delete(0, "end")
            self.entrada_max.insert(0, range_max)

            self.vocal_widgets['status_label'].config(
                text=f"✓ Ranges preenchidos: {range_min} - {range_max}",
                foreground='#27AE60'
            )
            messagebox.showinfo("Sucesso", f"Ranges preenchidos:\nMín: {range_min}\nMáx: {range_max}")
        else:
            self.vocal_widgets['status_label'].config(text="Nenhum resultado", foreground='#E74C3C')
            messagebox.showwarning("Aviso", "Teste foi cancelado ou não retornou resultados")

        # Reset botões
        self.vocal_widgets['btn_start_test'].config(state='normal')
        self.vocal_widgets['btn_quick_test'].config(state='normal')
        self.vocal_widgets['btn_rec'].config(state='normal')
        self.vocal_widgets['btn_stop_test'].config(state='disabled')
        self.vocal_widgets['btn_too_low'].config(state='disabled')
        self.vocal_widgets['btn_too_high'].config(state='disabled')

    def toggle_pitch_recording(self
                               ):
        """Toggle entre iniciar e parar gravação de pitch."""
        # Verifica se está gravando
        if self.vocal_test_mgr.vocal_tester and hasattr(self.vocal_test_mgr.vocal_tester, '_record_pitch') and self.vocal_test_mgr.vocal_tester._record_pitch:
            # Está gravando - para
            success, html = self.vocal_test_mgr.stop_pitch_recording()
            if success:
                # Restaura botões
                self.vocal_widgets['btn_rec'].config(text="🔴REC Pitch")
                self.vocal_widgets['btn_start_test'].config(state='normal')
                self.vocal_widgets['btn_quick_test'].config(state='normal')
                self.vocal_widgets['btn_stop_test'].config(state='disabled')
                self.vocal_widgets['testing_time_cb'].config(state='normal')

                file_name = simpledialog.askstring("Nomear Arquivo", "Nome do Arquivo:")
                file_dir = "./Musicas/REC"

                if file_name and file_name.strip():
                    # Criar diretório se não existir
                    Path(file_dir).mkdir(parents=True, exist_ok=True)

                    file_path = Path(f"{file_dir}/{file_name}.html").resolve()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    messagebox.showinfo("Sucesso", f"Gravação de pitch salva em {file_dir}/{file_name}.html!")
                    webbrowser.open(f"file:///{file_path}")

                    # Salvar MIDI
                    pm = self.analyzer.notes_to_midi(success)
                    midi_path = Path(file_dir) / f"{file_name}.mid"
                    self.analyzer.save_midi(pm, midi_path)
                else:
                    messagebox.showinfo("Ação cancelada", f"Gravação cancelada!")
            else:
                messagebox.showinfo("Audio em branco", f"Nenhuma nota detectada!")
                self.vocal_widgets['btn_rec'].config(text="🔴REC Pitch")
                self.vocal_widgets['btn_start_test'].config(state='normal')
                self.vocal_widgets['btn_quick_test'].config(state='normal')
                self.vocal_widgets['btn_stop_test'].config(state='disabled')
                self.vocal_widgets['testing_time_cb'].config(state='normal')

        else:
            # Não está gravando - inicia
            success, msg = self.vocal_test_mgr.start_pitch_recording()
            self.music_ui_mgr.music_dir = None
            self.music_ui_mgr.music_name = None
            if success:
                # Desabilita outros botões e muda texto
                self.vocal_widgets['btn_rec'].config(text="⬛ Stop REC")
                self.vocal_widgets['btn_start_test'].config(state='disabled')
                self.vocal_widgets['btn_quick_test'].config(state='disabled')
                self.vocal_widgets['btn_stop_test'].config(state='normal')
                self.vocal_widgets['testing_time_cb'].config(state='disabled')
                self.vocal_widgets['status_label'].config(
                    text="Gravando pitch...",
                    foreground='#E74C3C'
                )
            else:
                messagebox.showwarning("Aviso", msg)

    # ============================================================
    # CALLBACKS - MÚSICA
    # ============================================================

    def save_music_ranges(self
                          ):
        """Salva ranges de música."""
        # Coleta dados
        name = self.music_ui_mgr.music_name_var.get()
        if name == self.music_ui_mgr.music_name_placeholder:
            messagebox.showerror("Erro", "Preencha o nome da música")
            return

        ranges = {}
        voice_ranges = self.music_ui_mgr.get_voice_ranges()
        for voz, (min_val, max_val) in voice_ranges.items():
            if min_val or max_val:
                ranges[voz] = {"min": min_val.upper(), "max": max_val.upper()}

        if not ranges:
            messagebox.showwarning("Aviso", "Preencha ao menos um range de voz")
            return

        solistas = self.music_ui_mgr.get_solistas()

        # Voices por corista
        voices = {}
        for corista_nome in self.coristas_mgr.coristas:
            voz_atribuida = self.coristas_mgr.coristas[corista_nome].get('voz_atribuida')
            if voz_atribuida and corista_nome:
                voices.setdefault(voz_atribuida, []).append(corista_nome)

        root = self.music_ui_mgr.root_var.get()
        mode = self.music_ui_mgr.mode_var.get()

        # Verificar existência
        existe = self.music_data_mgr.check_music_exists(name)
        if existe:
            substituir = messagebox.askyesno(
                "Música Existente",
                f"A música '{name}' já existe. Deseja substituir?"
            )
            if not substituir:
                return

        # Salva
        sucesso, mensagem = self.music_data_mgr.save_music_ranges(
            name, ranges, solistas, voices, root, mode
        )

        if sucesso:
            messagebox.showinfo("Sucesso", mensagem)
            self.music_ui_mgr.update_music_library(self.coristas_ui_mgr.get_current_group())
        else:
            messagebox.showerror("Erro", mensagem)

    def load_music_ranges_for_selection(self,
                                        name):
        """Carrega ranges de uma música selecionada."""
        if not name or name.startswith("--") or name == 'Nome da Música':
            messagebox.showwarning("Aviso", "Nenhuma música válida selecionada.")
            self.music_ui_mgr.clear_all_fields()
            return

        music_data = self.music_data_mgr.get_music_data(name)
        if music_data is None:
            messagebox.showerror("Erro", f"Música '{name}' não encontrada.")
            return

        # Apaga os ranges
        self.music_ui_mgr.eraser_voice_ranges()

        # Preenche ranges
        ranges = music_data.get("ranges", {})
        self.music_ui_mgr.set_voice_ranges(ranges)

        # Preenche solistas
        solistas_raw = music_data.get("solistas", {})
        solistas_normalized = self.music_data_mgr.normalize_solistas_data(solistas_raw)
        self.music_ui_mgr.set_solistas(solistas_normalized)
        self.analysis_mgr.set_solistas(solistas_normalized)

        # Atualiza tom e modo
        self.music_ui_mgr.music_name_var.set(name)
        self.music_ui_mgr.root_var.set(music_data.get('root', 'C'))
        self.music_ui_mgr.mode_var.set(music_data.get('mode', 'maior'))

        # Atualiza vozes atribuídas
        voices = music_data.get("voices", {})
        for voice, coristas in voices.items():
            for corista_nome in coristas:
                if corista_nome in self.coristas_mgr.coristas:
                    self.coristas_mgr.coristas[corista_nome]['voz_atribuida'] = voice

        # Atualisa lista de vozes de coristas
        self.coristas_ui_mgr.reload_table()

        # Executa análise
        if getattr(self.analysis_mgr, '_use_group_ranges', None):
            self.analysis_mgr._use_group_ranges = not self.analysis_mgr._use_group_ranges
            self.toggle_group_or_voice_ranges()
            self.t_slider.set(self.analysis_mgr.analysis_all['best_T'])
        else:
            self.on_confort_change(float(self.confort_slider.get()))
    def load_voice_audio_files(self
                               ):
        """Carrega e processa arquivos de áudio."""
        success, msg, voice = self.music_ui_mgr.load_voice_audio_files()
        if success:
            filtered_log, html = VocalTestCore.export_pitch_log_to_html(VocalTestCore(), external=success['notes'])
            success['notes'] = filtered_log

            # Salvar Gráfico:
            file_name = getattr(self.music_ui_mgr, 'music_name', None)
            file_dir = getattr(self.music_ui_mgr, 'music_dir', None)

            if file_name:
                if file_dir:
                    file_path = Path(f"{file_dir}/{file_name} - {voice}.html").resolve()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    messagebox.showinfo("Sucesso", f"Gravação de pitch salva em {file_name} - {voice}.html!")
                    webbrowser.open(f"file:///{file_path}")
                else:
                    file_path = Path(f"./Musicas/{file_name} - {voice}.html").resolve()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    messagebox.showinfo("Sucesso", f"Gravação de pitch salva em {file_name} - {voice}.html!")
                    webbrowser.open(f"file:///{file_path}")
            else:
                file_name = simpledialog.askstring("Nomear Arquivo", "Nome do Arquivo:")
                if file_name and file_name.strip():
                    if voice.lower() in file_name.lower():
                        file_path = Path(f"./Musicas/{file_name}.html").resolve()
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        messagebox.showinfo("Sucesso", f"Gravação de pitch salva em {file_name}.html!")
                        webbrowser.open(f"file:///{file_path}")
                    else:
                        file_path = Path(f"./Musicas/{file_name} - {voice}.html").resolve()
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        messagebox.showinfo("Sucesso", f"Gravação de pitch salva em {file_name} - {voice}.html!")
                        webbrowser.open(f"file:///{file_path}")
                else:
                    messagebox.showinfo("Ação cancelada", f"Gravação cancelada!")

            # Salva MIDI
            pm = self.analyzer.notes_to_midi(success)
            midi_path = self.music_ui_mgr.music_dir / f"{file_name}.mid" if self.music_ui_mgr.music_dir else f'./Musicas/{file_name}.mid'
            self.analyzer.save_midi(pm, midi_path)

        else:
            messagebox.showerror("Erro", msg)

    def _on_root_selected(self,
                          event):
        """Callback quando tom é selecionado."""
        self.music_ui_mgr.root_var.set(self.music_ui_mgr.root_combo.get())

    def _on_mode_selected(self,
                          event):
        """Callback quando modo é selecionado."""
        self.music_ui_mgr.mode_var.set(self.music_ui_mgr.mode_combo.get())

    # ============================================================
    # ANÁLISE
    # ============================================================

    def toggle_group_or_voice_ranges(self):
        mode, ranges = self.analysis_mgr.toggle_range_mode()

        if hasattr(self.visualizer, "set_group_ranges"):
            self.visualizer.set_group_ranges(ranges if mode == "grupo" else None)
        if mode == "grupo":
            self.dynamic_ranges_button.config(text="Padrão Vocal")
        else:
            self.dynamic_ranges_button.config(text="Vozes do Grupo")
        self.run_analysis()

    def run_analysis(self,
                     confort=None):
        """Executa análise de transposição."""
        #try:
        piece_ranges = self.music_ui_mgr.get_voice_ranges()
        root = self.music_ui_mgr.root_var.get()
        mode = self.music_ui_mgr.mode_var.get()
        confort = float(self.confort_slider.get()) if not confort else float(confort)

        # Executa análise
        viz_data = self.analysis_mgr.get_visualization_data(int(self.t_slider.get()))
        analysis_result = self.analysis_mgr.run_analysis(piece_ranges, root, mode, viz_data, confort)

        if analysis_result:
            # Atualiza exibição
            self.on_t_change(self.t_slider.get())

        #except Exception as e:
        #    messagebox.showerror("Erro", str(e))

    def on_t_change(self,
                    value):
        """Callback quando transposição muda."""
        try:
            T = int(float(value))
            piece_ranges = self.music_ui_mgr.get_voice_ranges() if not self.analysis_mgr.current_piece_ranges else self.analysis_mgr.current_piece_ranges

            if not any(mn or mx for mn, mx in piece_ranges.values()):
                return

            # Calcula O_i para T atual
            per_voice_Os = self.analysis_mgr.compute_transposition_for_t(T)

            # Atualiza visualização
            viz_data = self.analysis_mgr.get_visualization_data(T)
            self.visualizer.update(
                piece_ranges, T, per_voice_Os,
                group_ranges=viz_data['group_ranges'],
                group_extension=viz_data['group_extension'],
                voice_scores=viz_data['voice_scores'],
                possible_fit=viz_data['possible_fit'],
                not_fit=viz_data['not_fit']
            )

            # Atualiza texto de resultados
            root = self.music_ui_mgr.root_var.get()
            mode = self.music_ui_mgr.mode_var.get()
            results_text = self.analysis_mgr.format_results_text(T, root, mode)

            self.results_text.delete(1.0, "end")
            self.results_text.insert("end", results_text)
        except:
            pass


def main():
    root = tk.Tk()
    app = VoiceRangeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

# pyinstaller --onefile --windowed Main_Refatorado.py
