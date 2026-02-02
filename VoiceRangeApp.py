import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
import sys
import time
from CoristasManager import CoristasManager
from Constants import VOICES, VOICE_BASE_RANGES
from KeyboardVisualizer import KeyboardVisualizer
from RangeVisualizer import RangeVisualizer
from GeneralFunctions import analyze_ranges_with_penalty, note_to_midi, transpose_note, midi_to_note

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

    def setup_coristas_tab(self):
        """Configura a aba de gerenciamento de coristas"""
        # Painel de entrada
        input_frame = ttk.LabelFrame(self.frame_coristas, text="Adicionar/Editar Corista", padding=10)
        input_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(input_frame, text="Nome:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entrada_nome = ttk.Entry(input_frame, width=30)
        self.entrada_nome.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(input_frame, text="Range Min (ex: G3):").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entrada_min = ttk.Entry(input_frame, width=15)
        self.entrada_min.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(input_frame, text="Range Max (ex: C5):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entrada_max = ttk.Entry(input_frame, width=15)
        self.entrada_max.grid(row=1, column=3, padx=5, pady=5)

        # Botão para teste vocal
        btn_vocal_test = ttk.Button(input_frame, text="🎤 Buscar Teste Vocal",
                                    command=self.search_and_fill_vocal_test)
        btn_vocal_test.grid(row=0, column=4, rowspan=2, padx=10, pady=5)

        # Botão adicionar
        btn_add = ttk.Button(input_frame, text="Adicionar Corista", command=self.add_corista)
        btn_add.grid(row=2, column=0, columnspan=5, pady=10)

        # Tabela de coristas
        table_frame = ttk.LabelFrame(self.frame_coristas, text="Coristas Cadastrados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Cria Treeview
        columns = ("Nome", "Range Min", "Range Max", "Voz Calculada", "Voz Atribuída")
        self.tree_coristas = ttk.Treeview(table_frame, columns=columns, height=12, show="tree headings")

        for col in columns:
            self.tree_coristas.column(col, width=150, anchor="center")
            self.tree_coristas.heading(col, text=col)

        self.tree_coristas.pack(fill="both", expand=True)

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

    def search_and_fill_vocal_test(self):
        """Busca o teste vocal e preenche os campos de range"""
        result = messagebox.askyesno("Teste Vocal",
                                     "Isto abrirá o programa de Teste Vocal.\n\n"
                                     "Após concluir o teste, os ranges serão preenchidos automaticamente.\n\n"
                                     "Deseja continuar?")
        if not result:
            return

        # Executa o teste vocal
        range_min, range_max = self.run_vocal_test()

        if range_min and range_max:
            self.entrada_min.delete(0, "end")
            self.entrada_min.insert(0, range_min)
            self.entrada_max.delete(0, "end")
            self.entrada_max.insert(0, range_max)
            messagebox.showinfo("Sucesso", f"Ranges preenchidos:\nMín: {range_min}\nMáx: {range_max}")
        else:
            messagebox.showwarning("Aviso", "Nenhum resultado de teste foi recebido")

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

    def run_vocal_test(self):
        """Executa o programa de teste vocal e aguarda os resultados"""
        try:
            # Executa o teste vocal como subprocess
            subprocess.Popen([sys.executable, "vocal_tester.py"])

            # Aguarda a criação do arquivo de resultado (máximo 60 segundos)
            result_file = "vocal_test_result.json"
            timeout = 180
            elapsed = 0

            while elapsed < timeout:
                if os.path.exists(result_file):
                    try:
                        with open(result_file, 'r', encoding='utf-8') as f:
                            result = json.load(f)

                        # Remove o arquivo após leitura
                        os.remove(result_file)

                        return result.get('range_min'), result.get('range_max')
                    except:
                        time.sleep(0.5)
                        elapsed += 0.5
                        continue

                time.sleep(0.5)
                elapsed += 0.5

            messagebox.showwarning("Aviso", "Teste vocal não retornou resultados em tempo hábil")
            return None, None

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao executar teste vocal: {e}")
            return None, None

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

        # Botão para atualizar range pelo teste vocal
        def update_range_from_test():
            result = messagebox.askyesno("Teste Vocal",
                                         "Isto abrirá o programa de Teste Vocal.\n\n"
                                         "Após concluir o teste, o range será atualizado.\n\n"
                                         "Deseja continuar?")
            if not result:
                return

            range_min, range_max = self.run_vocal_test()
            if range_min and range_max:
                corista['range_min'] = range_min
                corista['range_max'] = range_max

                # Recalcula vozes compatíveis
                vozes_recomendadas, vozes_possiveis = self.coristas_mgr.calculate_compatible_voices(
                    range_min, range_max
                )
                corista['vozes_recomendadas'] = vozes_recomendadas
                corista['vozes_possiveis'] = vozes_possiveis

                # Atualiza a voz calculada
                voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                    vozes_possiveis[0][0] if vozes_possiveis else VOICES[0]
                )
                corista['voz_calculada'] = voz_calculada
                var_voz.set(voz_calculada)

                # Atualiza o label
                ttk.Label(range_frame, text=f"Range: {range_min} - {range_max}",
                          font=("Arial", 10), foreground="green").pack(side="left", padx=10)

                messagebox.showinfo("Sucesso", f"Range atualizado:\nMín: {range_min}\nMáx: {range_max}\n\n"
                                               f"Voz recalculada: {voz_calculada}")

        ttk.Button(range_frame, text="🎤 Atualizar via Teste Vocal",
                   command=update_range_from_test).pack(side="left", padx=10)

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