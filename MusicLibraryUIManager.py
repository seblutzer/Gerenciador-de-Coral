"""
MusicLibraryUIManager - Responsável pela interface da biblioteca musical
Responsabilidades:
- Gerenciar campos de entrada de dados de música
- Gerenciar solistas (UI dinâmica)
- Processar arquivos de áudio das vozes
- Sincronizar UI com dados de música
"""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
from pathlib import Path
from Constants import VOICES
import re


class MusicLibraryUIManager:

    def __init__(self, parent_frame, coristas_mgr, music_data_mgr, analyzer):
        """
        Args:
            parent_frame: Frame pai onde a UI será criada
            coristas_mgr: Instância do CoristasManager
            music_data_mgr: Instância do MusicDataManager
            analyzer: Instância do AudioAnalyzer
        """
        self.parent_frame = parent_frame
        self.coristas_mgr = coristas_mgr
        self.music_data_mgr = music_data_mgr
        self.analyzer = analyzer

        # Widgets de música
        self.music_name_var = tk.StringVar()
        self.music_name_entry = None
        self.music_name_placeholder = "Nome da música"
        self.music_combo = None
        self.music_var = tk.StringVar()
        self.root_var = tk.StringVar()
        self.root_combo = None
        self.mode_var = tk.StringVar()
        self.mode_combo = None

        # Widgets de vozes
        self.voice_vars = {}  # {voz: {"min": Entry, "max": Entry}}
        self.music_dir = None
        self.music_name = None

        # Solistas
        self.solist_frame = None
        self.solist_count_cb = None
        self.solist_rows = []  # Lista de dicts com widgets dos solistas
        self.solist_count = 0

    def create_music_name_field(self,
                                parent):
        """Cria o campo de nome da música com placeholder."""
        self.music_name_entry = tk.Entry(
            parent,
            textvariable=self.music_name_var,
            width=30,
            fg="grey"
        )
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
                self.music_name_var.set("")
            else:
                self.music_name_var.set(val)

        self.music_name_entry.bind("<FocusIn>", _clear_name)
        self.music_name_entry.bind("<FocusOut>", _fill_name)

        return self.music_name_entry

    def create_music_selector(self,
                              parent, on_select_callback):
        """Cria o combobox de seleção de música."""
        self.music_combo = ttk.Combobox(
            parent,
            textvariable=self.music_var,
            state="readonly",
            width=25
        )
        self.music_combo.set("-- Selecione uma música --")
        self.music_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: on_select_callback(self.music_combo.get())
        )
        return self.music_combo

    def create_root_selector(self,
                             parent, on_select_callback):
        """Cria o combobox de seleção de tom."""
        self.root_combo = ttk.Combobox(
            parent,
            textvariable=self.root_var,
            state="readonly",
            width=8,
            values=["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb",
                    "G", "G#", "Ab", "A", "A#", "Bb", "B"]
        )
        self.root_combo.current(0)
        self.root_combo.bind("<<ComboboxSelected>>", on_select_callback)
        return self.root_combo

    def create_mode_selector(self,
                             parent, on_select_callback):
        """Cria o combobox de seleção de modo."""
        self.mode_combo = ttk.Combobox(
            parent,
            textvariable=self.mode_var,
            state="readonly",
            width=10,
            values=["maior", "menor"]
        )
        self.mode_combo.current(0)
        self.mode_combo.bind("<<ComboboxSelected>>", on_select_callback)
        return self.mode_combo

    def create_voice_range_entries(self,
                                   parent):
        """Cria os campos de entrada de ranges por voz."""
        for idx, v in enumerate(VOICES):
            row = idx // 2
            col = idx % 2
            frame_v = ttk.Frame(parent)
            frame_v.grid(row=row, column=col, padx=10, pady=5, sticky="w")

            ttk.Label(frame_v, text=f"{v}:").pack()

            min_entry = ttk.Entry(frame_v, width=10)
            min_entry.pack(side="left", padx=2)
            max_entry = ttk.Entry(frame_v, width=10)
            max_entry.pack(side="left", padx=2)

            min_entry.insert(0, "")
            max_entry.insert(0, "")

            self.voice_vars[v] = {"min": min_entry, "max": max_entry}

    def create_solists_ui(self,
                          parent):
        """Cria a UI de solistas com combobox de contagem."""
        self.solist_count_cb = ttk.Combobox(
            parent,
            values=[0, 1, 2, 3, 4, 5],
            width=5,
            state="readonly"
        )
        self.solist_count_cb.pack(side="left")
        self.solist_count_cb.set(0)
        self.solist_count_cb.bind("<<ComboboxSelected>>", self._on_solists_count_changed)

        self.solist_frame = ttk.Frame(parent, padding=10)
        self.solist_frame.pack()

    def _on_solists_count_changed(self,
                                  event=None):
        """Atualiza a UI de solistas baseado no número selecionado."""
        self._build_solists_ui()

    def _build_solists_ui(self
                          ):
        """Constrói/Atualiza a UI para os solistas."""
        for child in self.solist_frame.winfo_children():
            child.destroy()
        self.solist_rows.clear()

        count = int(self.solist_count_cb.get()) if self.solist_count_cb.get() != "" else 0
        self.solist_count = count

        coristas_nomes = list(self.coristas_mgr.coristas.keys()) or []
        corista_choices = ["Selecionar..."] + coristas_nomes

        for i in range(count):
            row_frame = ttk.Frame(self.solist_frame)
            row_frame.pack(fill="x", pady=3)

            ttk.Label(row_frame, text=f"Solista {i+1}:").pack(side="left", padx=(0, 5))

            cb = ttk.Combobox(row_frame, values=corista_choices, state="readonly", width=20)
            cb.current(0)
            cb.pack(side="left", padx=(0, 5))

            min_ent = ttk.Entry(row_frame, width=8)
            min_ent.pack(side="left", padx=(0, 5))

            max_ent = ttk.Entry(row_frame, width=8)
            max_ent.pack(side="left", padx=(0, 5))

            self.solist_rows.append({
                "cb": cb,
                "min": min_ent,
                "max": max_ent,
            })

    def get_voice_ranges(self,
                         solistas=None):
        """
        Retorna os ranges de vozes da UI.

        Returns:
            dict: {voz: (min, max)}
        """
        ranges = {}
        for v in VOICES:
            min_str = self.voice_vars[v]["min"].get().strip()
            max_str = self.voice_vars[v]["max"].get().strip()
            ranges[v] = (min_str, max_str)



        return ranges

    def eraser_voice_ranges(self
                            ):
        for v, vr in self.voice_vars.items():
            [valor.delete(0, "end") for valor in vr.values()]

    def set_voice_ranges(self,
                         ranges):
        """
        Preenche os campos de ranges de vozes.

        Args:
            ranges: dict {voz: {"min": nota, "max": nota}}
        """
        for voice, vr in ranges.items():
            if voice not in self.voice_vars:
                continue

            min_val = vr.get("min", "") if isinstance(vr, dict) else ""
            max_val = vr.get("max", "") if isinstance(vr, dict) else ""

            # Suporte a formatos alternativos
            if not min_val and isinstance(vr, dict):
                min_val = vr.get("0", "")
            if not max_val and isinstance(vr, dict):
                max_val = vr.get("1", "")

            if min_val or max_val:
                self.voice_vars[voice]["min"].delete(0, "end")
                self.voice_vars[voice]["min"].insert(0, min_val)
                self.voice_vars[voice]["max"].delete(0, "end")
                self.voice_vars[voice]["max"].insert(0, max_val)

    def get_solistas(self
                     ):
        """
        Retorna os solistas da UI.

        Returns:
            dict: {nome: [min, max]}
        """
        solistas = {}
        for row in self.solist_rows:
            cb_widget = row.get('cb')
            min_widget = row.get('min')
            max_widget = row.get('max')

            if cb_widget is None:
                continue

            try:
                cb_name = cb_widget.get()
                min_val = min_widget.get() if min_widget else ""
                max_val = max_widget.get() if max_widget else ""

                if cb_name and cb_name != "Selecionar...":
                    solistas[cb_name] = [min_val, max_val]
            except:
                pass

        return solistas

    def set_solistas(self,
                     solistas):
        """
        Preenche os campos de solistas.

        Args:
            solistas: dict {nome: [min, max]}
        """
        if not solistas:
            self.solist_count_cb.set(0)
            self._build_solists_ui()
            return

        # Atualiza contagem
        cnt = min(max(len(solistas.keys()), 0), 5)
        self.solist_count_cb.set(cnt)
        self._build_solists_ui()


        # Preenche dados
        for idx, name in enumerate(solistas):
            if idx >= len(self.solist_rows):
                break
            row = self.solist_rows[idx]

            if "cb" in row:
                row["cb"].set(name)
            if "min" in row:
                row["min"].delete(0, "end")
                row["min"].insert(0, solistas[name][0])
            if "max" in row:
                row["max"].delete(0, "end")
                row["max"].insert(0, solistas[name][1])

    def clear_all_fields(self
                         ):
        """Limpa todos os campos da UI de música."""
        # Limpa ranges de vozes
        for voice, vr in self.voice_vars.items():
            vr["min"].delete(0, "end")
            vr["max"].delete(0, "end")

        # Limpa nome
        self.music_name_var.set("")
        if self.music_name_entry:
            self.music_name_entry.delete(0, tk.END)
            self.music_name_entry.insert(0, self.music_name_placeholder)
            self.music_name_entry.config(fg="grey")

        self.music_combo.set("-- Selecione uma música --")
        #self.root_var.set('C')
        self.root_combo.set('C')
        #self.mode_var.set('maior')
        self.mode_combo.set('maior')
        # Limpa solistas
        if self.solist_count_cb:
            self.solist_count_cb.set(0)
            self._build_solists_ui()

    def load_voice_audio_files(self
                               ):
        """
        Carrega arquivos de áudio para cada voz e processa.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        import shutil  # se ainda não estiver importado no seu arquivo
        # Abre o diálogo com as 3 opções
        root = self.master if hasattr(self, "master") else None  # ajuste conforme seu código
        mode_dialog = FileOpenModeDialog(root, title="Tipo de arquivo para abrir")
        mode = getattr(mode_dialog, "result", "Vozes")

        if mode == "Vozes":
            # Fluxo original (tenta abrir um arquivo para cada VOZ)
            voice_audio_paths = {}
            for v in VOICES:
                path = filedialog.askopenfilename(
                    title=f"Selecione áudio para a voz {v}",
                    filetypes=[("Audio", "*.wav *.mp3 *.flac"), ("All files", "*.*")]
                )
                if path:
                    voice_audio_paths[v] = path
                else:
                    voice_audio_paths[v] = None

            # Bloco restante igual ao original, unido pela helper
            ok, msg = self._process_voice_paths(voice_audio_paths)
            return ok, msg, 'voz_teste'

        elif mode == "Única Voz":
            # Escolha da voz única
            voice_dialog = VoiceSelectorDialog(root, title="Selecione a voz para único arquivo", voices=VOICES)
            voice = getattr(voice_dialog, "result", None)
            if not voice:
                return False, "Nenhuma voz selecionada"

            path = filedialog.askopenfilename(
                title=f"Selecione áudio para a voz {voice}",
                filetypes=[("Audio", "*.wav *.mp3 *.flac"), ("All files", "*.*")]
            )
            if not path:
                return False, "Arquivo não selecionado"

            # Monta o dict com apenas essa voz preenchida
            voice_audio_paths = {v: None for v in VOICES}
            voice_audio_paths[voice] = path

            ok, msg = self._process_voice_paths(voice_audio_paths)
            return ok, msg, voice

        elif mode == "json":
            # Placeholder para o fluxo ainda não implementado
            # Escolha da voz única
            voice_dialog = VoiceSelectorDialog(root, title="Selecione o arquivo de voz", voices=VOICES)
            voice = getattr(voice_dialog, "result", None)
            if not voice:
                return False, "Nenhuma voz selecionada"

            path = filedialog.askopenfilename(
                title=f"Selecione áudio para a voz {voice}",
                filetypes=[("Json", "*.json"), ("All files", "*.*")]
            )
            #[{'time': 0.0, 'freq': 193.42348771730548, 'note': 'G3'}, {'time': 0.05655384063720703, 'freq': 291.6882355949923, 'note': 'D4'},
            with open(path, 'r', encoding='utf-8') as f:
                raw_log = json.load(f)

            return raw_log, '', voice

        else:
            return False, "Modo desconhecido"

    def extract_music_name(self,
                           music_name, voice_audio_paths):
        """
        Remove o nome da voz e travessões adjacentes do nome da música.

        Args:
            music_name: Nome base da música
            voice_audio_paths: Dict com {voice: "path", ...}

        Returns:
            String com o nome da música limpo
        """
        if not music_name:
            return music_name

        # Criar padrão regex case-insensitive para todas as vozes
        # Ordena por tamanho descendente para evitar matches parciais
        voices = sorted(voice_audio_paths.keys(), key=len, reverse=True)

        # Escape special regex characters e cria padrão
        pattern = '|'.join(re.escape(voice) for voice in voices)

        # Regex que remove: [travessão opcional] + voz + [travessão opcional]
        # \s* permite espaços em branco, [\-_–—] é qualquer tipo de travessão
        cleaned = re.sub(
            rf'\s*[\-_–—]?\s*({pattern})\s*[\-_–—]?\s*',
            ' ',
            music_name,
            flags=re.IGNORECASE
        )

        # Remove espaços extras deixados pela substituição
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned if cleaned else music_name

    # Helper: executa o processamento com base no dict voz -> path
    def _process_voice_paths(self,
                             voice_audio_paths):
        # Copia do bloco original que processa cada voz
        self.music_name = self.music_name_var.get().strip()

        if not self.music_name or self.music_name == self.music_name_placeholder:
            # Deriva do primeiro caminho
            for voice, path in voice_audio_paths.items():
                if path:
                    base = os.path.basename(path)
                    self.music_name = os.path.splitext(base)[0]
                    break

            # Processa para remover nome da voz e travessões adjacentes
            self.music_name = self.extract_music_name(self.music_name, voice_audio_paths)

        if not self.music_name:
            return False, "Nome da música não informado nem derivável"

        # Processa cada faixa
        root_musicas = Path("root") / "Musicas"
        music_root = root_musicas / self.music_name

        for voz, path in voice_audio_paths.items():
            if not path:
                continue

            # Processa com AudioAnalyzer
            result = self.analyzer._analyze_mp3_to_notes(str(path))

            # Salva outputs
            voice_dir = music_root / voz
            voice_dir.mkdir(parents=True, exist_ok=True)

            # 4) Preparar diretório de saída
            self.music_dir = self.analyzer.root_dir / self.music_name
            self.music_dir.mkdir(parents=True, exist_ok=True)

            # 5) Salvar outputs
            notes_path = self.music_dir / f"{self.music_name}_notes - {voz}.json"
            with open(notes_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        return result, f"Processamento concluído para '{self.music_name}'"

    def update_music_library(self,
                             grupo=None):
        """Atualiza a lista de músicas no combobox."""
        music_names, _ = self.music_data_mgr.load_music_library(grupo)
        if self.music_combo:
            self.music_combo['values'] = music_names

class FileOpenModeDialog(simpledialog.Dialog):
    def __init__(self,
                 parent, title=None, options=("Vozes", "Única Voz", "json")):
        self.options = options
        self.selected = options[0]
        super().__init__(parent, title)

    def body(self,
             master):
        tk.Label(master, text="Selecione o tipo de arquivo a abrir:").grid(row=0, column=0, sticky="w")
        self.var = tk.StringVar(value=self.options[0])
        for idx, opt in enumerate(self.options):
            tk.Radiobutton(master, text=opt, variable=self.var, value=opt).grid(row=idx+1, column=0, sticky="w")
        return None

    def apply(self
              ):
        self.selected = self.var.get()
        self.result = self.selected

# Dialog para escolher qual voz usar (quando "Única Voz" é escolhido)
class VoiceSelectorDialog(simpledialog.Dialog):
    def __init__(self, parent, title="Selecione voz", voices=None):
        self.voices = voices or []
        self.selected_voice = None
        super().__init__(parent, title)

    def body(self,
             master):
        tk.Label(master, text="Selecione a voz:").grid(row=0, column=0, sticky="w")
        self.var = tk.StringVar()
        for i, v in enumerate(self.voices):
            tk.Radiobutton(master, text=v, variable=self.var, value=v).grid(row=i+1, column=0, sticky="w")
        return None

    def apply(self
              ):
        self.selected_voice = self.var.get()
        self.result = self.selected_voice

