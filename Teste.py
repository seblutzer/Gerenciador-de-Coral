
    def add_corista(self):
        """Adiciona um corista (ADAPTADO)"""
        nome = self.entrada_nome.get().strip()
        range_min = self.entrada_min.get().strip()
        range_max = self.entrada_max.get().strip()

        if not nome or not range_min or not range_max:
            messagebox.showerror("Erro", "Preenchimento obrigatório em todos os campos")
            return

        # ===== NOVO: Usa CoristasManager =====
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
        """Remove um corista (ADAPTADO)"""
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para remover")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)
        # ===== NOVO: Usa CoristasManager =====
        self.coristas_mgr.remove_corista(index)
        self.reload_coristas_table()
        messagebox.showinfo("Sucesso", "Corista removido!")

    def edit_corista_voz(self):
        """Edita voz atribuída do corista (ADAPTADO)"""
        selection = self.tree_coristas.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        item = selection[0]
        index = self.tree_coristas.index(item)
        # ===== NOVO: Usa CoristasManager =====
        corista = self.coristas_mgr.coristas[index]

        dialog = tk.Toplevel(self.master)
        dialog.title("Atribuir Voz")
        dialog.geometry("900x850")

        ttk.Label(dialog, text=f"Corista: {corista['nome']}", font=("Arial", 12, "bold")).pack(pady=10)

        range_frame = ttk.LabelFrame(dialog, text="Range Atual", padding=5)
        range_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(range_frame, text=f"Range: {corista['range_min']} - {corista['range_max']}",
                  font=("Arial", 10)).pack(side="left", padx=10)

        ttk.Label(range_frame, text="💡 Dica: Use o teste vocal na aba de Adicionar Corista",
                  font=("Arial", 8), foreground="#666").pack(side="left", padx=10)

        ttk.Label(dialog, text=f"Voz Calculada: {corista['voz_calculada']}", font=("Arial", 10)).pack(pady=5)

        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista.get('voz_atribuida', ''))

        keyboard = KeyboardVisualizer(dialog)

        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

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

        voz_inicial = var_voz.get()
        if voz_inicial:
            voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_inicial]
            keyboard.update(corista['range_min'], corista['range_max'],
                            voice_min_str, voice_max_str)

        def confirm():
            # ===== NOVO: Usa CoristasManager =====
            self.coristas_mgr.update_corista_voz_atribuida(index, var_voz.get())
            self.reload_coristas_table()
            dialog.destroy()
            messagebox.showinfo("Sucesso", "Voz atribuída!")

        ttk.Button(dialog, text="Confirmar", command=confirm).pack(pady=20)

    def save_coristas(self):
        """Salva dados (ADAPTADO)"""
        # ===== NOVO: Usa DataStore diretamente =====
        if self.store.save():
            messagebox.showinfo("Sucesso", "Dados salvos em music_unified.json")
        else:
            messagebox.showerror("Erro", "Erro ao salvar dados")

    def reload_coristas_table(self):
        """Recarrega tabela (ADAPTADO)"""
        # ===== NOVO: Recarrega do CoristasManager =====
        self.coristas_mgr.reload()

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

    def save_music_ranges_to_json(self, piece_ranges, orig_root, orig_mode, piece_name=None):
        """Salva música (ADAPTADO)"""
        name = piece_name or "Untitled"

        # Coleta dados de solistas
        solistas = []
        coristas_por_voz = {}

        for i in range(len(self.solist_rows)):
            row = self.solist_rows[i]
            corista_nome = row["cb"].get()
            if corista_nome and corista_nome != "Selecionar...":
                solista_name = f"Solista {i + 1}"
                solistas.append({
                    "index": i + 1,
                    "name": solista_name,
                    "corista_nome": corista_nome,
                    "min": row["min"].get().strip(),
                    "max": row["max"].get().strip()
                })
                if solista_name not in coristas_por_voz:
                    coristas_por_voz[solista_name] = []
                coristas_por_voz[solista_name].append(corista_nome)

        # Adiciona vozes normais ao coristas_por_voz
        for voz in VOICES:
            if voz not in coristas_por_voz:
                coristas_por_voz[voz] = []

        # ===== NOVO: Usa CoristasManager =====
        success, msg = self.coristas_mgr.add_or_update_music(
            name=name,
            root=orig_root,
            mode=orig_mode,
            voices=piece_ranges,
            solistas=solistas,
            coristas_por_voz=coristas_por_voz
        )

        if success:
            messagebox.showinfo("Sucesso", msg)
            self.load_music_library()
        else:
            messagebox.showerror("Erro", msg)

    def load_music_library(self):
        """Carrega biblioteca (ADAPTADO)"""
        # ===== NOVO: Usa CoristasManager =====
        music_names = self.coristas_mgr.get_music_names()
        self.music_library = [self.coristas_mgr.load_music(name) for name in music_names]

        if hasattr(self, "music_combo") and self.music_combo:
            self.music_combo['values'] = music_names
            if music_names:
                self.music_combo.current(0)

    def load_music_ranges_for_selection(self, name):
        """Carrega música selecionada (ADAPTADO)"""
        if not name:
            messagebox.showwarning("Aviso", "Nenhuma música selecionada.")
            return

        # ===== NOVO: Usa CoristasManager =====
        music = self.coristas_mgr.load_music(name)
        if not music:
            messagebox.showerror("Erro", f"Música '{name}' não encontrada na biblioteca.")
            return

        # Preenche controles de cada voz com os ranges salvos
        ranges = music.get("voices", {})
        for v in VOICES:
            rg = ranges.get(v, {})
            min_val = rg.get("min", "")
            max_val = rg.get("max", "")
            if v in self.voice_vars:
                self.voice_vars[v]["min"].delete(0, "end")
                self.voice_vars[v]["min"].insert(0, min_val)
                self.voice_vars[v]["max"].delete(0, "end")
                self.voice_vars[v]["max"].insert(0, max_val)

        # Carrega solistas
        solistas = music.get("solistas", [])
        self.solist_count_cb.set(len(solistas))
        self._build_solists_ui()

        # Preenche dados de solistas
        for i, s in enumerate(solistas):
            if i < len(self.solist_rows):
                row = self.solist_rows[i]
                corista_nome = s.get("corista_nome")
                if corista_nome:
                    row["cb"].set(corista_nome)
                row["min"].delete(0, "end")
                row["min"].insert(0, s.get("min", ""))
                row["max"].delete(0, "end")
                row["max"].insert(0, s.get("max", ""))

        # Determina o nome da música
        self.music_name_var.set(music.get("name", ""))

        # Root e mode
        self.root_var.set(music.get("root", "C"))
        self.mode_var.set(music.get("mode", "maior"))

        # Opcional: atualizar visualizador com os ranges carregados
        self.run_analysis()

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

        # Caminho de saída raiz
        root_musicas = Path("root") / "Musicas"
        music_root = root_musicas / music_name

        # Processa cada faixa por voz
        for voz, path in self.voice_audio_paths.items():
            if not path:
                continue

            # Processo com AudioAnalyzer
            result = self.analyzer.process_music(path, music_name)

            # Preenche min/max com extrema
            extrema = result.get("extrema")
            if extrema and len(extrema) >= 2:
                min_name, max_name = extrema[0], extrema[1]
                if voz in self.voice_vars:
                    self.voice_vars[voz]["min"].delete(0, "end")
                    self.voice_vars[voz]["min"].insert(0, min_name)
                    self.voice_vars[voz]["max"].delete(0, "end")
                    self.voice_vars[voz]["max"].insert(0, max_name)

            # Salvar outputs em root/Musicas/{nome_da_musica}/{voz}/
            voice_dir = music_root / voz
            voice_dir.mkdir(parents=True, exist_ok=True)

            # Caminhos de origem retornados pelo AudioAnalyzer
            notes_src = result.get("notes_detected_path")
            normalized_src = result.get("normalized_path")
            midi_src = result.get("midi_path")

            # Copia/Move para a pasta da música
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

    def load_group_ranges(self):
        """Carrega os ranges calculados do grupo de coristas para as entradas"""
        if not self.coristas_mgr.coristas:
            messagebox.showwarning("Aviso", "Nenhum corista cadastrado!")
            return

        group_ranges = self.coristas_mgr.get_voice_group_ranges()
        if self.visualizer:
            self.visualizer.set_group_ranges(group_ranges)
        self.group_ranges = group_ranges
        self.run_analysis()

    def read_voice_ranges(self):
        ranges = {}
        for v in VOICES:
            min_str = self.voice_vars[v]["min"].get().strip()
            max_str = self.voice_vars[v]["max"].get().strip()
            if not min_str or not max_str:
                raise ValueError(f"Faixa de {v} está vazia.")
            ranges[v] = (min_str, max_str)
        return ranges

    # ========== MÉTODOS MANTIDOS SEM ALTERAÇÃO ==========
    # Cole aqui todos os outros métodos que você listou:
    # - _on_root_selected
    # - _on_mode_selected
    # - _on_double_click_corista
    # - clear_results
    # - _on_testing_time_changed
    # - repeat_tone_vocal
    # - start_vocal_test
    # - start_quick_vocal_test
    # - mark_too_low_vocal
    # - mark_too_high_vocal
    # - stop_vocal_test
    # - update_vocal_test_ui
    # - update_button_states
    # - on_vocal_test_complete
    # - toggle_group_or_voice_ranges
    # - run_analysis
    # - on_t_change
    # [COPIE TODO O CÓDIGO ORIGINAL SEM MUDANÇAS]

    def _on_root_selected(self, event):
        self.root_var.set(self.root_combo.get())

    def _on_mode_selected(self, event):
        self.mode_var.set(self.mode_combo.get())

    def _on_double_click_corista(self, event):
        item_id = self.tree_coristas.focus()
        if not item_id:
            return
        self.tree_coristas.selection_set(item_id)
        try:
            self.edit_corista_voz(item_id)
        except TypeError:
            self.edit_corista_voz()

    def clear_results(self):
        """Limpa a área de resultados"""
        self.results_text.delete(1.0, "end")
        self.results_text.insert("end", "Resultados limpos. Informe os ranges vocais e execute a análise novamente.\n")

    def _on_testing_time_changed(self, event):
        try:
            new_time = int(self.testing_time_cb.get())
            VocalTestCore.DEFAULT_TESTING_TIME = new_time
            self.testing_time = new_time
            if getattr(self, "vocal_tester", None) is not None:
                self.vocal_tester.testing_time = new_time
            self.time_label.config(text=f"Tempo: 0.0s / {new_time}.0s")
        except Exception:
            pass

    def repeat_tone_vocal(self):
        """Reproduz o tom atual novamente"""
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            freq = self.vocal_tester.current_playing_frequency
            if freq and freq > 0:
                threading.Thread(target=self.vocal_tester.play_note, args=(freq, 2), daemon=True).start()
                self.status_label.config(text="Reproduzindo tom atual...", foreground='#27AE60')
                return
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

        button_map = [
            ('start_button', getattr(self, 'btn_start_test', None)),
            ('start_quick_button', getattr(self, 'btn_quick_test', None)),
            ('stop_button', getattr(self, 'btn_stop_test', None)),
            ('repeat_button', getattr(self, 'btn_repeat', None)),
            ('too_low_button', getattr(self, 'btn_too_low', None)),
            ('too_high_button', getattr(self, 'btn_too_high', None)),
        ]

        for key, btn in button_map:
            if btn is None:
                continue
            if key in kwargs:
                btn.config(state=kwargs[key])

        if 'button_states' in kwargs:
            states = kwargs['button_states']
            if self.btn_too_low:
                self.btn_too_low.config(state=states.get('too_low', 'disabled'))
            if self.btn_too_high:
                self.btn_too_high.config(state=states.get('too_high', 'disabled'))
            if 'start' in states and self.btn_start_test:
                self.btn_start_test.config(state=states['start'])
            if 'start_quick' in states and self.btn_quick_test:
                self.btn_quick_test.config(state=states['start_quick'])
            if 'stop' in states and self.btn_stop_test:
                self.btn_stop_test.config(state=states['stop'])

        if 'pitch_hz' in kwargs:
            hz = kwargs['pitch_hz']
            if hz is not None and hz > 0:
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

        self.btn_start_test.config(state='normal')
        self.btn_quick_test.config(state='normal')
        self.btn_stop_test.config(state='disabled')
        self.btn_too_low.config(state='disabled')
        self.btn_too_high.config(state='disabled')

        self.vocal_tester = None

    def toggle_group_or_voice_ranges(self):
        current = getattr(self, "_use_group_ranges", False)
        self._use_group_ranges = not current

        if getattr(self, "_use_group_ranges", False):
            self.coristas = True
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                group_ranges = self.coristas_mgr.get_voice_group_ranges()
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(group_ranges)
            else:
                if hasattr(self.visualizer, "set_group_ranges"):
                    self.visualizer.set_group_ranges(None)
        else:
            self.coristas = False
            if hasattr(self.visualizer, "set_group_ranges"):
                self.visualizer.set_group_ranges(None)

        self.run_analysis()

    def run_analysis(self):
        """Versão unificada de run_analysis"""
        try:
            orig_root = self.root_var.get()
            orig_mode = self.mode_var.get()
            piece_ranges = self.read_voice_ranges()

            self.current_piece_ranges = piece_ranges

            t_current = int(float(self.t_slider.get())) if hasattr(self, "t_slider") else 0

            group_ranges = None
            if getattr(self, "_use_group_ranges", False):
                if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                    group_ranges = self.coristas_mgr.get_voice_group_ranges()

            analysis = compute_best_transposition(orig_root, orig_mode, piece_ranges, group_ranges)
            self._latest_analysis = analysis

            self.on_t_change(0)

            per_voice_Os_for_T = compute_per_voice_Os_for_T(t_current, piece_ranges, group_ranges)
            self.visualizer.update(piece_ranges, t_current, per_voice_Os_for_T)

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def on_t_change(self, value):
        """Atualização quando o usuário altera T"""
        try:
            T = int(float(value))
            piece_ranges = getattr(self, "current_piece_ranges", None)
            group_ranges = self.coristas_mgr.get_voice_group_ranges() if self.coristas else None

            if not piece_ranges:
                return

            per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, group_ranges)
            self.visualizer.update(piece_ranges, T, per_voice_Os)

            current_root = self.root_var.get()
            current_mode = self.mode_var.get()
            transposed_root = transpose_note(current_root, T)

            analysis_all = analyze_ranges_with_penalty(current_root, current_mode, piece_ranges, group_ranges)
            debug = analysis_all.get("debug", [])

            self.results_text.delete(1.0, "end")

            best_T_global = analysis_all.get("best_T")
            best_key_root = analysis_all.get("best_key_root")
            best_key_mode = analysis_all.get("best_key_mode")
            if best_T_global is not None:
                self.results_text.insert("end",
                                         f"Melhor transposição: {best_T_global:+d} semitons → {best_key_root} {best_key_mode}\n")

            self.results_text.insert("end",
                                     f"Transposição atual: {T:+d} semitons ({current_root} → {transposed_root})\n")

            if debug:
                if len(debug) > 0:
                    pairs = []
                    i = 0
                    while i < len(debug):
                        if debug[i] == 0:
                            pairs.append(str(debug[i]))
                            i += 1
                        else:
                            pairs.append(f"({debug[i]}/{debug[i + 1]})")
                            i += 2
                    self.results_text.insert("end", "Possíveis transposições: " + ", ".join(pairs) + " semitons\n")
                else:
                    self.results_text.insert("end", f"Transposição possível: {debug[0]:+d} semitons\n")

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
                self.results_text.insert("end",
                                         f"  {v}: {midi_to_note(int(min_final))} → {midi_to_note(int(max_final))}")
                self.results_text.insert("end", f" ({O} {O_i})\n") if O != 0 else self.results_text.insert("end", "\n")

        except Exception:
            pass