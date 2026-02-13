import json
import os
import re
import time
import librosa
from tkinter import messagebox
from Constants import DATA_FILE, VOICES, VOICE_BASE_RANGES, SEMITONE_TO_SHARP


# ===== GERENCIAMENTO DE CORISTAS E DADOS =====
class CoristasManager:
    def __init__(self, data_file=DATA_FILE, grupo=None):
        self.data_file = data_file
        self.grupo = grupo          # Nome do grupo atual
        self.coristas = {}          # Dict de coristas do grupo atual

    def set_group(self,
            grupo):
        """Atualiza o grupo atual e recarrega os coristas desse grupo."""
        self.grupo = grupo
        self.load_data()

    def load_data(self
                  ):
        #data, lista_grupos = self.read_data('grupos', both=True, group_list=True)
        with open(self.data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            lista_grupos = list(data.get('grupos', {}).keys())

        self.grupo = lista_grupos[0] if len(lista_grupos) > 0 and not self.grupo else self.grupo

        # versão: coristas é um dicionário, não lista
        self.coristas = data['grupos'][self.grupo]

    def save_music_ranges_to_json(self,
                                  music_name: str, ranges: dict, solistas: dict, vozes_por_corista: dict, root: str, mode: str) -> bool:
        """
        Salva ou atualiza uma música no arquivo de dados.
        Realiza UMA ÚNICA LEITURA E ESCRITA do arquivo.

        Args:
            music_name: Nome da música
            ranges: Dict {voz: {"min": nota, "max": nota}} - ranges da música
            solistas: Dict {nome_solista: [min, max]} - ranges dos solistas
            vozes_por_corista: Dict {voz: [lista_de_coristas]} - vozes atribuídas
            root: Nota raiz (ex: "C")
            mode: Modo ("maior" ou "menor")

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if not music_name or music_name == "Untitled":
            return False, "Nome da música é obrigatório"

        # Normalizar ranges com _note_to_sharp
        ranges_normalized = {}
        for voz, rng in ranges.items():
            min_val = self._note_to_sharp(rng.get("min", "").upper())
            max_val = self._note_to_sharp(rng.get("max", "").upper())
            ranges_normalized[voz] = {"min": min_val, "max": max_val}

        # Validar ranges
        NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|b)?[2-7])?$")
        invalids = []
        for voz, rng in ranges_normalized.items():
            if not NOTA_PATTERN.fullmatch(rng.get("min", "")):
                invalids.append((voz, "min", rng.get("min")))
            if not NOTA_PATTERN.fullmatch(rng.get("max", "")):
                invalids.append((voz, "max", rng.get("max")))

        if invalids:
            msgs = [f"'{valor}' é inválido para {voz} ({campo})"
                    for voz, campo, valor in invalids]
            return False, "; ".join(msgs) + "\nEsperado: letra A-G + número 2-7"

        try:
            # ===== UMA ÚNICA ABERTURA DO ARQUIVO =====
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"grupos": {}, "musicas": {}}

            # ===== TODAS AS MODIFICAÇÕES EM MEMÓRIA =====
            # 1) Atualizar/criar grupo se necessário
            if self.grupo and self.grupo not in data.get("grupos", {}):
                data.setdefault("grupos", {})[self.grupo] = self.coristas

            # 2) Criar ou sobrescrever música
            data.setdefault("musicas", {})[music_name] = {
                "root": root,
                "mode": mode,
                "grupo": self.grupo,
                "ranges": ranges_normalized,
                "solistas": solistas or {},
                "voices": vozes_por_corista or {},
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            # ===== ÚNICA ESCRITA NO ARQUIVO =====
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True, f"Faixa '{music_name}' salva com sucesso!"

        except Exception as e:
            return False, f"Erro ao salvar faixa: {str(e)}"

    def check_music_exists(self,
                           music_name: str) -> bool:
        """Verifica se uma música já existe no arquivo"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return music_name in data.get("musicas", {})
        except Exception:
            pass
        return False

    def save_corista(self,
                     corista_nome=None, replace=None):
        """Salva dados no arquivo JSON sob o grupo atual: grupos -> nome_grupo -> coristas"""
        if not self.grupo:
            print("Grupo não definido para salvar coristas.")
            return False

        try:
            mode = 'r+' if os.path.exists(self.data_file) else 'w+'

            with open(self.data_file, mode, encoding='utf-8') as f:
                if mode == 'r+':
                    try:
                        f.seek(0)
                        data = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        data = {}

                if not isinstance(data, dict):
                    data = {}

                if 'grupos' not in data or not isinstance(data['grupos'], dict):
                    data['grupos'] = {}

                if self.grupo not in data['grupos']:
                    data['grupos'][self.grupo] = {}

                # Atualiza coristas
                if replace:
                    data['grupos'][self.grupo][corista_nome] = data['grupos'][self.grupo].pop(replace)

                    # Atualiza referências em músicas do mesmo grupo
                    if 'musicas' in data and isinstance(data['musicas'], dict):
                        for musica in data['musicas'].values():
                            if musica.get('grupo') == self.grupo:
                                # Solistas: renomeia chave mantendo valor
                                if 'solistas' in musica and replace in musica['solistas']:
                                    musica['solistas'][corista_nome] = musica['solistas'].pop(replace)

                                # Voices: substitui nome em listas de naipes
                                if 'voices' in musica and isinstance(musica['voices'], dict):
                                    for naipe in musica['voices'].values():
                                        if isinstance(naipe, list) and replace in naipe:
                                            naipe[naipe.index(replace)] = corista_nome

                if corista_nome:
                    data['grupos'][self.grupo][corista_nome] = self.coristas[corista_nome]
                else:
                    data['grupos'][self.grupo] = self.coristas

                # Escreve no arquivo
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"Erro ao salvar dados: {e}")
            return False

    def _note_to_sharp(self,
                       note: str) -> str:
        if len(note) < 3:
            return note
        letter = note[0]
        acc = note[1].lower()
        octave = int(note[2])

        natural_offsets = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        midi = 12 * (octave + 1) + natural_offsets[letter]

        if acc == '#':
            midi += 1
        elif acc == 'b':
            midi -= 1

        name = SEMITONE_TO_SHARP[midi % 12]
        out_oct = (midi // 12) - 1

        return f"{name}{out_oct}"

    def adicionar_grupo(self,
                        nome):
        with open(DATA_FILE, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data['grupos'][nome] = {}
            # Salvar
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()

    def read_data(self,
                  extract=None, all_in=False, both=False, group_list=False):
        if not os.path.exists(self.data_file):
            return {} if not extract else {f'{extract}_não_encontrado': True}

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Retorna apenas o que foi solicitado
            if extract:
                if all_in:
                    if group_list:
                        return data, data.get(extract, {}), list(data.get('grupos', {}).keys())
                    return data, data.get(extract, {})
                if group_list:
                    if both:
                        return data, list(data.get('grupos', {}).keys())
                    return list(data.get('grupos', {}).keys())
                return data.get(extract, {})

            return data

        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")
            return {} if not extract else {}
        except Exception as e:
            print(f"Erro ao ler dados: {e}")
            return {} if not extract else {}

    def add_corista(self,
                    nome, range_min, range_max):
        """Adiciona um corista com vozes compatíveis"""
        try:
            # Validação: cada valor deve ser do formato A-G seguido de 2-7
            NOTA_PATTERN = re.compile(r"^(?:[A-G](?:#|B)?[2-7])?$")

            invalids = []
            if not NOTA_PATTERN.fullmatch(range_min):
                invalids.append(range_min)
            if not NOTA_PATTERN.fullmatch(range_max):
                invalids.append(range_max)
            if invalids:
                # Opcional: construir uma mensagem mais legível
                msgs = [f"'{" e ".join(invalids)}' são inválidos!"] if len(invalids) > 1 else f"'{invalids[0]}' é inválido!"
                messagebox.showerror("Nota inexistente",
                                     msgs + "\nEsperado: uma letra A-G seguida de um número 2-7.\n"
                                     )
                return False, []

            # Padroniza bemois em sustenidos
            range_min = self._note_to_sharp(range_min)
            range_max = self._note_to_sharp(range_max)

            # Valida ranges
            #librosa.note_to_midi(range_min)
            #librosa.note_to_midi(range_max)
            if  librosa.note_to_midi(range_min) >  librosa.note_to_midi(range_max):
                raise ValueError(f"Range inválido: {range_min} > {range_max}")

            # Calcula vozes compatíveis
            vozes_recomendadas, vozes_possiveis = self.calculate_compatible_voices(range_min, range_max)
            all_compatible = vozes_recomendadas + [v for v in vozes_possiveis]
            voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0] if vozes_possiveis else VOICES[0])

            corista = {
                    'range_min': range_min,
                    'range_max': range_max,
                    'voz_calculada': voz_calculada,
                    'voz_atribuida': voz_calculada,
                    'vozes_recomendadas': vozes_recomendadas,
                    'vozes_possiveis': vozes_possiveis  # Lista de tuples: (voz, diff, obs)
                }

            self.coristas[nome] = corista
            self.save_corista(nome)
            return True, corista
        except Exception as e:
            return False, str(e)

    def remove_corista(self,
                       corista_nome):
        # Verifica se o corista existe no grupo atual
        if corista_nome not in self.coristas:
            return False

        # Remove o corista do grupo na memória (já usaremos self.grupo apenas para referência)
        self.coristas.pop(corista_nome, None)
        grupo = self.grupo

        def rreplace(s, old, new):
            if old == "":
                return ""

            i = s.rfind(old)
            if i == -1:
                return s
            return s[:i] + new + s[i + len(old):]

        try:
            with open(self.data_file, 'r+', encoding='utf-8') as f:
                data = json.load(f)

                # 1) Construir todas_vozes a partir das informações do corista antes da remoção
                groups = data.setdefault("grupos", {})
                grupo_dict = groups.setdefault(grupo, {})

                corista_info = grupo_dict.get(corista_nome, {})
                todas_vozes = set()

                if corista_info:
                    voz_atribuida = corista_info.get("voz_atribuida")
                    if voz_atribuida:
                        todas_vozes.add(voz_atribuida)

                    todas_vozes.update(corista_info.get("vozes_recomendadas", []))
                    todas_vozes.update(corista_info.get("vozes_possiveis", []))

                # 2) Remover o corista do grupo
                grupo_dict.pop(corista_nome, None)

                # 3) Atualizar músicas do mesmo grupo
                musics = data.get("musicas", {})
                solista = []
                corista = []
                vozes = {}
                for music, value in musics.items():
                    if value.get("grupo") != grupo:
                        continue

                    # 3a) Remover do mapeamento de voices
                    voices_map = value.setdefault("voices", {})
                    for voice_name, members in list(voices_map.items()):
                        if voice_name in todas_vozes and isinstance(members, list) and corista_nome in members:
                            corista.append(music)
                            members.remove(corista_nome)
                            # Se a lista ficou vazia, remova a voz por completo
                            if len(members) == 0:
                                vozes[music] =  voice_name
                                del voices_map[voice_name]

                    # 3b) Remover do campo solistas, se estiver presente
                    solistas_map = value.get("solistas", {})
                    if corista_nome in solistas_map:
                        solista.append(music)
                        del solistas_map[corista_nome]

                # 4) Gravação atômica de volta no arquivo (ou simples overwrite com truncate)
                msg = f"Tem certeza que quer remover '{corista_nome}'?"
                if solista or corista or vozes:
                    msg += " Isso afetará:\n"
                    if corista:
                        msg += f" - a lista de coristas de '{rreplace("', '".join(corista), ", ", " e ")}'\n"
                    if vozes:
                        for key in vozes:
                            msg += f"     - removerá '{vozes[key]}' da música: '{key}'\n"
                    if solista:
                        msg += f" - a lista de solistas de '{rreplace("', '".join(solista), ", ", ' e ')}'"
                remover = messagebox.askyesno(
                    "Aviso",
                    msg
                )
                if remover:
                    f.seek(0)
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.truncate()

                    return data
                return False
        except Exception as e:
            # Opcional: loga o erro
            print(f"Erro ao atualizar dados: {e}")
            return False

    def calculate_compatible_voices(self,
                                    range_min: str, range_max: str, observations=False) -> tuple:
        """
        Calcula todas as vozes compatíveis com o range fornecido.

        Retorna: (vozes_recomendadas, vozes_possiveis)
        - vozes_recomendadas: lista de vozes com encaixe perfeito
        - vozes_possiveis: lista de tuples (voz, max_diff, obs) com até 3 semitons de diferença
        """
        try:
            min_midi =  librosa.note_to_midi(range_min)
            max_midi =  librosa.note_to_midi(range_max)

            vozes_recomendadas = []
            vozes_possiveis = []

            for voice in VOICES:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                voice_min =  librosa.note_to_midi(voice_min_str)
                voice_max =  librosa.note_to_midi(voice_max_str)

                # Encaixe perfeito: o range do corista CABE dentro da faixa da voz
                if min_midi <= voice_min and max_midi >= voice_max:
                    vozes_recomendadas.append(voice)
                else:
                    diff_min = max(0, min_midi - voice_min)
                    diff_max = max(0, voice_max - max_midi)
                    max_diff = max(diff_min, diff_max)

                    if max_diff <= 5:
                        if observations:
                            obs = ""
                            if diff_min > 0:
                                obs += f"Falta {diff_min} semitom"
                                obs += " grave"
                            if diff_max > 0:
                                if obs:
                                    obs += " e "
                                obs += f"Falta {diff_max} semitom"
                                obs += " agudo"
                            vozes_possiveis.append((voice, max_diff, obs))
                        else:
                            vozes_possiveis.append(voice)

            vozes_possiveis.sort(key=lambda x: x[1])

            return vozes_recomendadas, vozes_possiveis
        except Exception as e:
            print(f"Erro ao calcular vozes compatíveis: {e}")
            return [], []

    def get_voice_group_ranges(self,
                               solistas=None) -> dict:
        """
        Calcula os ranges do grupo por voz.
        """
        voice_groups = {v: [] for v in VOICES}

        # Agrupa coristas por voz atribuída
        for corista in self.coristas:
            voz = self.coristas[corista]['voz_atribuida']
            min_midi =  librosa.note_to_midi(self.coristas[corista]['range_min'])
            max_midi =  librosa.note_to_midi(self.coristas[corista]['range_max'])
            voice_groups[voz].append((min_midi, max_midi))

        # Calcula range do grupo: maior mínimo e menor máximo
        group_ranges = {}
        group_extension = {}
        for voz in VOICES:
            if voice_groups[voz]:
                mins = [r[0] for r in voice_groups[voz]]
                maxs = [r[1] for r in voice_groups[voz]]

                group_min = max(mins)  # maior mínimo
                group_max = min(maxs)  # menor máximo

                if group_min <= group_max:
                    group_ranges[voz] = ( librosa.midi_to_note(int(group_min)),  librosa.midi_to_note(int(group_max)))
                    group_extension[voz] = ( librosa.midi_to_note(int(min(mins))),  librosa.midi_to_note(int(max(maxs))))

        if solistas:
            # Atualiza os valores de solistas com os ranges de coristas quando disponíveis
            solistas_updated = {
                k: (self.coristas[k]['range_min'], self.coristas[k]['range_max'])
                if k in self.coristas else v
                for k, v in solistas.items()
            }

            # Une com as ranges de grupo
            group_ranges = solistas_updated | group_ranges

        return group_ranges, group_extension