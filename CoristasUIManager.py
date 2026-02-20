"""
CoristasUIManager - Responsável pela interface de gerenciamento de coristas
Responsabilidades:
- Criar e gerenciar a TreeView de coristas
- Ordenar coristas por coluna
- Adicionar/remover/editar coristas via UI
- Gerenciar grupos de coristas
- Sincronizar UI com dados do CoristasManager
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
import librosa
from Constants import VOICES, VOICE_BASE_RANGES
from KeyboardVisualizer import KeyboardVisualizer


class CoristasUIManager:
    def __init__(self, parent_frame, coristas_mgr, on_reload_callback=None, on_group_changed=None):
        """
        Args:
            parent_frame: Frame pai onde a UI será criada
            coristas_mgr: Instância do CoristasManager
            on_reload_callback: Função a chamar quando dados forem atualizados
        """
        self.parent_frame = parent_frame
        self.coristas_mgr = coristas_mgr
        self.on_reload_callback = on_reload_callback
        self.on_group_changed = on_group_changed

        # Controle de ordenação
        self.sort_column = None
        self.sort_reverse = False

        # Widgets
        self.tree_coristas = None
        self.grupo_combo = None
        self.grupos_var = None
        self.grupo_nome_var = tk.StringVar()

    def create_table(self,
                     table_frame):
        """
        Cria a TreeView de coristas.

        Args:
            table_frame: Frame onde a tabela será inserida
        """
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")
        self.tree_coristas = ttk.Treeview(
            table_frame,
            columns=columns,
            height=12,
            show="headings"
        )

        self._setup_voice_tags()

        for col in columns:
            self.tree_coristas.column(col, width=100, anchor="center")
            self.tree_coristas.heading(
                col, text=col,
                command=lambda c=col: self._sort_column(c)
            )

        self.tree_coristas.pack(fill="both", expand=True)

        # Atalhos
        self.tree_coristas.bind("<Double-1>", self._on_double_click)
        self.tree_coristas.bind("<Delete>", self._on_delete_key)

    def create_group_selector(self,
                              group_frame):
        """
        Cria o seletor de grupos.

        Args:
            group_frame: Frame onde o seletor será inserido
        """
        ttk.Label(group_frame, text="Grupo de Coristas:").pack()

        self.grupos_var = tk.StringVar()
        self.grupo_combo = ttk.Combobox(
            group_frame,
            textvariable=self.grupos_var,
            state="readonly",
            width=20
        )

        groups = self.coristas_mgr.read_data(extract='grupos', group_list=True)
        self.grupo_combo['values'] = groups
        if groups:
            self.grupo_combo.current(0)

        self.grupo_combo.pack()
        self.grupo_combo.bind("<<ComboboxSelected>>", self._on_group_selected)

        # Botão adicionar grupo
        ttk.Button(
            group_frame,
            text="Adicionar Grupo",
            command=self.add_group
        ).pack(pady=2)

    def reload_table(self
                     ):
        if self.tree_coristas is None:
            return

        for item in self.tree_coristas.get_children():
            self.tree_coristas.delete(item)

        if not self.coristas_mgr.coristas:
            self.coristas_mgr.load_data()

        for corista_nome in self.coristas_mgr.coristas:
            corista = self.coristas_mgr.coristas[corista_nome]
            range_str = f"{corista['range_min']}  ⟷  {corista['range_max']}"
            vozes_rec = ", ".join(corista.get("vozes_recomendadas", []))
            vozes_pos = ", ".join(corista.get("vozes_possiveis", []))

            voz = (corista.get("voz_atribuida") or "").strip()
            tag = voz if voz in getattr(self, "_voice_colors", {}) else ""

            self.tree_coristas.insert(
                "", "end",
                values=(corista_nome, range_str, voz, vozes_rec, vozes_pos),
                tags=(tag,) if tag else ()
            )
        self._sort_column('Voz Atribuída')


    def _setup_voice_tags(self
                          ):
        # Masculinas: mais grave -> mais escuro
        self._voice_colors = {
            "Baixo": ("#0B3D91", "white"),
            "Barítono": ("#2A6FBB", "white"),
            "Tenor": ("#7AB8FF", "black"),

            # Femininas: mais grave -> mais escuro
            "Contralto": ("#8B1E5D", "white"),
            "Mezzo-soprano": ("#C2185B", "white"),
            "Soprano": ("#F48FB1", "black"),
        }

        # Opcional: caso vazio/desconhecido
        self._default_row = ("", "")  # não muda

        for voz, (bg, fg) in self._voice_colors.items():
            self.tree_coristas.tag_configure(voz, background=bg, foreground=fg)

    def add_group(self
                  ):
        """Adiciona um novo grupo de coristas."""
        nome = simpledialog.askstring("Adicionar Grupo", "Nome do Novo Grupo:")
        if nome and nome.strip():
            nome = nome.strip()

            # Adiciona no banco de dados
            self.coristas_mgr.adicionar_grupo(nome)

            # Atualiza combobox
            self.grupo_combo.set(nome)
            groups = self.coristas_mgr.read_data(extract='grupos', group_list=True)
            self.grupo_combo['values'] = groups

            # Limpa coristas
            self.coristas_mgr.coristas.clear()
            self._on_group_selected()

    def get_selected_corista(self
                             ):
        """
        Retorna o nome do corista selecionado na TreeView.

        Returns:
            str ou None
        """
        selection = self.tree_coristas.selection()
        if not selection:
            return None

        item = selection[0]
        vals = self.tree_coristas.item(item, "values")
        return vals[0] if vals else None

    def remove_selected_corista(self
                                ):
        """
        Remove o corista selecionado.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        corista_nome = self.get_selected_corista()

        if not corista_nome:
            return False, "Selecione um corista para remover"

        sucesso = self.coristas_mgr.remove_corista(corista_nome)
        if sucesso:
            self.reload_table()
            if self.on_reload_callback:
                self.on_reload_callback()
            return True, "Corista removido!"

        return False, "Erro ao remover corista"

    def edit_selected_corista(self,
                              master):
        """
        Abre janela de edição para o corista selecionado.

        Args:
            master: Janela principal (para criar Toplevel)
        """
        corista_nome = self.get_selected_corista()

        if not corista_nome:
            messagebox.showwarning("Aviso", "Selecione um corista para editar")
            return

        corista = self.coristas_mgr.coristas.get(corista_nome)
        if corista is None:
            messagebox.showwarning("Aviso", "Corista não encontrado")
            return

        # Cria janela de edição
        self._create_edit_dialog(master, corista_nome, corista)

    def _create_edit_dialog(self,
                            master, corista_nome, corista):
        """Cria a janela de diálogo para editar corista."""
        dialog = tk.Toplevel(master)
        dialog.title("Editar Voz do Corista")
        dialog.geometry("900x750")

        # Frame de dados
        dados_frame = ttk.LabelFrame(dialog, text="Dados do Corista", padding=10)
        dados_frame.pack(fill="x", padx=10, pady=10)

        # Nome
        ttk.Label(dados_frame, text="Nome:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        var_nome = tk.StringVar(value=corista_nome)
        entry_nome = ttk.Entry(dados_frame, textvariable=var_nome, width=30, font=("Arial", 10))
        entry_nome.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Range Mínimo
        ttk.Label(dados_frame, text="Range Mínimo:", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        var_range_min = tk.StringVar(value=corista['range_min'])
        entry_range_min = ttk.Entry(dados_frame, textvariable=var_range_min, width=30, font=("Arial", 10))
        entry_range_min.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Range Máximo
        ttk.Label(dados_frame, text="Range Máximo:", font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky="w", padx=5, pady=5
        )
        var_range_max = tk.StringVar(value=corista['range_max'])
        entry_range_max = ttk.Entry(dados_frame, textvariable=var_range_max, width=30, font=("Arial", 10))
        entry_range_max.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        dados_frame.columnconfigure(1, weight=1)

        # Dica
        ttk.Label(
            dialog,
            text="💡 Dica: Use o teste vocal na aba de Adicionar Corista para determinar o range",
            font=("Arial", 8),
            foreground="#666"
        ).pack(pady=5)

        # Voz calculada
        voz_calc_frame = ttk.LabelFrame(dialog, text="Voz Calculada", padding=5)
        voz_calc_frame.pack(fill="x", padx=10, pady=5)

        label_voz_calc = ttk.Label(
            voz_calc_frame,
            text=f"Voz Calculada: {corista['voz_calculada']}",
            font=("Arial", 10, "bold")
        )
        label_voz_calc.pack(anchor="w", padx=10, pady=5)

        # Separador
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=10, pady=10)

        var_voz = tk.StringVar(value=corista.get('voz_atribuida'))

        # Visualizador de teclado
        keyboard = KeyboardVisualizer(dialog)

        # Frame para opções de voz
        vozes_frame = ttk.Frame(dialog)
        vozes_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Dados de vozes compatíveis
        vozes_data = {'recomendadas': [], 'possiveis': []}

        def update_vozes_display():
            """Atualiza lista de vozes na interface."""
            range_min = var_range_min.get()
            range_max = var_range_max.get()

            # Validação
            try:
                #librosa.note_to_midi(range_min)
                #librosa.note_to_midi(range_max)
                if librosa.note_to_midi(range_min) > librosa.note_to_midi(range_max):
                    return False
            except:
                return False

            # Calcula vozes compatíveis
            vozes_recomendadas, vozes_possiveis = \
                self.coristas_mgr.calculate_compatible_voices(range_min, range_max, True)
            vozes_data['recomendadas'] = vozes_recomendadas
            vozes_data['possiveis'] = vozes_possiveis

            # Nova voz calculada
            nova_voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0][0] if vozes_possiveis else VOICES[0]
            )

            label_voz_calc.config(text=f"Voz Calculada: {nova_voz_calculada}")

            # Verifica se voz atual ainda é compatível
            voz_atual = var_voz.get()
            todas_vozes = vozes_recomendadas + [v[0] for v in vozes_possiveis]
            if voz_atual not in todas_vozes:
                var_voz.set(nova_voz_calculada)

            # Reconstrói radiobuttons
            for widget in vozes_frame.winfo_children():
                widget.destroy()

            # RECOMENDADAS
            if vozes_recomendadas:
                ttk.Label(
                    vozes_frame,
                    text="✓ Recomendadas (Encaixe Perfeito)",
                    font=("Arial", 11, "bold"),
                    foreground="green"
                ).pack(anchor="w", pady=(10, 5))

                for v in vozes_recomendadas:
                    def on_select_recomendada(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(
                        vozes_frame, text=v, variable=var_voz, value=v,
                        command=on_select_recomendada
                    ).pack(anchor="w", padx=50, pady=3)

            # POSSÍVEIS
            if vozes_possiveis:
                ttk.Label(
                    vozes_frame,
                    text="⚠ Possíveis (com ressalva)",
                    font=("Arial", 11, "bold"),
                    foreground="orange"
                ).pack(anchor="w", pady=(10, 5))

                for v, diff, obs in vozes_possiveis:
                    frame_poss = ttk.Frame(vozes_frame)
                    frame_poss.pack(anchor="w", padx=40, pady=3, fill="x")

                    def on_select_possivel(voice=v):
                        var_voz.set(voice)
                        voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                        keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

                    ttk.Radiobutton(
                        frame_poss, text=v, variable=var_voz, value=v,
                        command=on_select_possivel
                    ).pack(side="left")
                    ttk.Label(
                        frame_poss, text=f"({obs})",
                        font=("Arial", 9), foreground="gray"
                    ).pack(side="left", padx=5)

            # Atualiza teclado
            voz_selecionada = var_voz.get()
            if voz_selecionada:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voz_selecionada]
                keyboard.update(range_min, range_max, voice_min_str, voice_max_str)

            return True

        # Eventos para atualização em tempo real
        def on_range_changed(*args):
            try:
                update_vozes_display()
            except:
                pass

        var_range_min.trace('w', on_range_changed)
        var_range_max.trace('w', on_range_changed)

        # Atualiza exibição inicial
        update_vozes_display()

        def confirm():
            """Confirma e salva as alterações."""
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
                msgs = f"'{' e '.join(invalids)}' são inválidos!" if len(invalids) > 1 \
                    else f"'{invalids[0]}' é inválido!"
                messagebox.showerror(
                    "Nota inexistente",
                    msgs + "\nEsperado: uma letra A-G seguida de um número 2-7.\n"
                )
                return

            # Padronizar bemois
            novo_range_min = self.coristas_mgr._note_to_sharp(novo_range_min)
            novo_range_max = self.coristas_mgr._note_to_sharp(novo_range_max)

            # Validar ranges
            try:
                if librosa.note_to_midi(novo_range_min) > librosa.note_to_midi(novo_range_max):
                    raise ValueError(f"Range inválido: {novo_range_min} > {novo_range_max}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao validar range: {str(e)}")
                return

            try:
                # Renomear se necessário
                if novo_nome != corista_nome:
                    if novo_nome in self.coristas_mgr.coristas:
                        messagebox.showerror("Erro", f"Corista '{novo_nome}' já existe!")
                        return
                    self.coristas_mgr.coristas.pop(corista_nome)

                # Recalcular vozes
                vozes_recomendadas, vozes_possiveis = \
                    self.coristas_mgr.calculate_compatible_voices(novo_range_min, novo_range_max)
                voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                    vozes_possiveis[0][0] if vozes_possiveis else VOICES[0]
                )

                # Atualizar corista
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

                # Remove arquivo antigo se houve renomeação
                if novo_nome != corista_nome:
                    self.coristas_mgr.remove_corista(corista_nome)

                self.reload_table()
                self.coristas_mgr.save_corista(corista_nome=novo_nome)

                if self.on_reload_callback:
                    self.on_reload_callback()

                messagebox.showinfo("Sucesso", f"Corista '{novo_nome}' atualizado com sucesso!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Erro ao salvar", f"Erro ao atualizar corista: {str(e)}")

        # Botões
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Confirmar", command=confirm).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side="left", padx=10)

    def _sort_column(self,
                     col_name):
        """Ordena a TreeView pela coluna clicada."""
        if self.sort_column == col_name:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col_name
            self.sort_reverse = False

        items = []
        for item in self.tree_coristas.get_children():
            values = self.tree_coristas.item(item, 'values')
            items.append((item, values))

        if col_name == "Range":
            if not self.sort_reverse:
                items.sort(key=lambda x: librosa.note_to_midi(x[1][1].split("⟷")[0].strip()))
            else:
                items.sort(key=lambda x: librosa.note_to_midi(x[1][1].split("⟷")[1].strip()), reverse=True)
        elif col_name == "Voz Atribuída":
            rank = {k: i for i, k in enumerate(VOICE_BASE_RANGES)}

            def voice_rank(s: str) -> int:
                # Se tiver "Baixo, Tenor" etc, pega a melhor (menor) posição
                parts = [p.strip() for p in (s or "").split(",") if p.strip()]
                return min((rank.get(p, 10 ** 9) for p in parts), default=10 ** 9)

            items.sort(
                key=lambda it: voice_rank(it[1][2]),
                reverse=self.sort_reverse
            )
        else:
            col_index = {
                "Nome": 0,
                "Range": 1,
                "Voz Atribuída": 2,
                "Voz(es) Recomendada(s)": 3,
                "Voz(es) Possível(is)": 4
            }
            index = col_index.get(col_name, 0)
            items.sort(key=lambda x: x[1][index], reverse=self.sort_reverse)

        for i, (item, values) in enumerate(items):
            self.tree_coristas.move(item, "", i)

        self._update_sort_indicator(col_name)

    def _update_sort_indicator(self,
                               col_name):
        """Atualiza o texto do cabeçalho com indicador de direção."""
        columns = ("Nome", "Range", "Voz Atribuída", "Voz(es) Recomendada(s)", "Voz(es) Possível(is)")

        for col in columns:
            if col == col_name:
                if col == "Range" and not self.sort_reverse:
                    texto = f"{col} ▲"
                elif col == "Range" and self.sort_reverse:
                    texto = f"{col} ▼"
                else:
                    texto = f"{col} {'▲' if not self.sort_reverse else '▼'}"
            else:
                texto = col

            self.tree_coristas.heading(col, text=texto)

    def _on_group_selected(self,
                           event=None):
        """Callback quando grupo é selecionado."""
        grupo = self.grupo_combo.get()
        self.grupo_nome_var.set(grupo)
        self.coristas_mgr.grupo = grupo

        data = self.coristas_mgr.read_data()
        self.coristas_mgr.coristas = data["grupos"][grupo]

        self.reload_table()

        if self.on_reload_callback:
            self.on_reload_callback()

        if self.on_group_changed:
            self.on_group_changed(grupo)

    def _on_double_click(self,
                         event):
        """Callback para duplo clique na TreeView."""
        item_id = self.tree_coristas.focus()
        if not item_id:
            return

        self.tree_coristas.selection_set(item_id)
        self.edit_selected_corista(self.parent_frame.master)

    def _on_delete_key(self,
                       event):
        """Callback para tecla Delete."""
        if self.tree_coristas.selection():
            self.remove_selected_corista()
        return "break"

    def get_current_group(self
                          ):
        """Retorna o nome do grupo atual."""
        return self.grupo_nome_var.get()