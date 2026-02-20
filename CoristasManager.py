import json
import os
import re
import time
import librosa
from tkinter import messagebox
from Constants import DATA_FILE, VOICES, VOICE_BASE_RANGES, SEMITONE_TO_SHARP
from GeneralFunctions import rreplace
from typing import overload, Literal

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
                msgs = [f"'{' e '.join(invalids)}' são inválidos!"] if len(invalids) > 1 else f"'{invalids[0]}' é inválido!"
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
                        msg += " - a lista de coristas de '" + {rreplace("', '".join(corista), ", ", " e ")} + "'\n"
                    if vozes:
                        for key in vozes:
                            msg += f"     - removerá '{vozes[key]}' da música: '{key}'\n"
                    if solista:
                        msg += " - a lista de solistas de '" + {rreplace("', '".join(solista), ", ", ' e ')} +"'"
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

    @overload
    def calculate_compatible_voices(
            self, range_min: str, range_max: str, observations: Literal[False] = False
    ) -> tuple[list[str], list[str]]:
        ...

    @overload
    def calculate_compatible_voices(
            self, range_min: str, range_max: str, observations: Literal[True]
    ) -> tuple[list[str], list[tuple[str, float, str]]]:
        ...

    def calculate_compatible_voices(self, range_min: str, range_max: str, observations: bool = False):
        """
        Retorna (vozes_recomendadas, vozes_possiveis)

        - vozes_recomendadas: list[str]
        - vozes_possiveis:
            - observations=False: list[str]
            - observations=True : list[tuple[str, float, str]] -> (voz, score, obs)
        """
        TOL = 5

        def fmt_poss(scored: list[tuple]):
            # scored: (voice, score) ou (voice, score, obs)
            if observations:
                return scored  # type: ignore[return-value]
            return [x[0] for x in scored]  # só vozes

        try:
            p_min = librosa.note_to_midi(range_min)
            p_max = librosa.note_to_midi(range_max)
            if p_min > p_max:
                p_min, p_max = p_max, p_min

            p_min_exp = p_min - TOL
            p_max_exp = p_max + TOL

            def fit_score(container_min: int, container_max: int, item_min: int, item_max: int) -> float | None:
                allowed_span = container_max - container_min
                required_span = item_max - item_min
                if required_span > allowed_span:
                    return None

                d_min = item_min - container_min
                d_max = container_max - item_max
                m = (allowed_span - required_span) / 2.0

                if m <= 0:
                    return 1.0 if (d_min == 0 and d_max == 0) else 0.0

                score = 1.0 - (abs(d_min - m) + abs(d_max - m)) / (2.0 * m)
                return max(0.0, min(1.0, float(score)))

            rec_scored = []  # (voice, score) | (voice, score, obs)
            possA_scored = []  # (voice, score) | (voice, score, obs)
            fallback = []  # (voice, violation) | (voice, violation, obs)

            for voice in VOICES:
                v_min_str, v_max_str = VOICE_BASE_RANGES[voice]
                v_min = librosa.note_to_midi(v_min_str)
                v_max = librosa.note_to_midi(v_max_str)

                # 1) Recomendadas: VOZ dentro da PESSOA (exato)
                if p_min <= v_min and p_max >= v_max:
                    score = fit_score(p_min, p_max, v_min, v_max) or 0.0
                    if observations:
                        obs = f"Folga pessoa: {v_min - p_min} st grave, {p_max - v_max} st agudo"
                        rec_scored.append((voice, score, obs))
                    else:
                        rec_scored.append((voice, score))

                # 2) Possíveis: VOZ dentro da PESSOA EXPANDIDA (±5)
                if v_min >= p_min_exp and v_max <= p_max_exp:
                    missing_low = max(0, p_min - v_min)
                    missing_high = max(0, v_max - p_max)
                    max_missing = max(missing_low, missing_high)

                    base = fit_score(p_min_exp, p_max_exp, v_min, v_max) or 0.0
                    penalty = max(0.0, 1.0 - (max_missing / float(TOL))) if TOL > 0 else 0.0
                    score = base * penalty

                    is_rec = (p_min <= v_min and p_max >= v_max)
                    if not is_rec:
                        if observations:
                            parts = []
                            if missing_low:
                                parts.append(f"falta {missing_low} st grave")
                            if missing_high:
                                parts.append(f"falta {missing_high} st agudo")
                            obs = "Quase alcança: " + (" e ".join(parts) if parts else "ok")
                            possA_scored.append((voice, score, obs))
                        else:
                            possA_scored.append((voice, score))

                # fallback (garantir 1 voz), contra VOZ expandida
                v_min_exp = v_min - TOL
                v_max_exp = v_max + TOL
                out_low = max(0, v_min_exp - p_min)
                out_high = max(0, p_max - v_max_exp)
                violation = max(out_low, out_high)
                if observations:
                    parts = []
                    if out_low:
                        parts.append(f"{out_low} st abaixo (mesmo com tolerância)")
                    if out_high:
                        parts.append(f"{out_high} st acima (mesmo com tolerância)")
                    obs = "Mais próxima (violação): " + (" e ".join(parts) if parts else "ok")
                    fallback.append((voice, violation, obs))
                else:
                    fallback.append((voice, violation))

            # Ordena recomendadas (usa score)
            if rec_scored:
                rec_scored.sort(key=lambda x: (-x[1], VOICES.index(x[0]) if x[0] in VOICES else 9999))
                vozes_recomendadas = [x[0] for x in rec_scored]

                possA_scored.sort(key=lambda x: (-x[1], VOICES.index(x[0]) if x[0] in VOICES else 9999))
                return vozes_recomendadas, fmt_poss(possA_scored)

            # 3) Sem recomendadas: pessoa dentro da VOZ expandida ±5
            possB_scored = []
            for voice in VOICES:
                v_min_str, v_max_str = VOICE_BASE_RANGES[voice]
                v_min = librosa.note_to_midi(v_min_str)
                v_max = librosa.note_to_midi(v_max_str)

                v_min_exp = v_min - TOL
                v_max_exp = v_max + TOL

                if p_min >= v_min_exp and p_max <= v_max_exp:
                    overflow_low = max(0, v_min - p_min)
                    overflow_high = max(0, p_max - v_max)
                    max_over = max(overflow_low, overflow_high)

                    base = fit_score(v_min_exp, v_max_exp, p_min, p_max) or 0.0
                    penalty = max(0.0, 1.0 - (max_over / float(TOL))) if TOL > 0 else 0.0
                    score = base * penalty

                    if observations:
                        parts = []
                        if overflow_low:
                            parts.append(f"{overflow_low} st abaixo do mínimo real")
                        if overflow_high:
                            parts.append(f"{overflow_high} st acima do máximo real")
                        obs = "Pessoa dentro (com tolerância). " + (
                            "Excesso: " + " e ".join(parts) if parts else "Dentro do range real"
                        )
                        possB_scored.append((voice, score, obs))
                    else:
                        possB_scored.append((voice, score))

            if possB_scored:
                possB_scored.sort(key=lambda x: (-x[1], VOICES.index(x[0]) if x[0] in VOICES else 9999))
                return [], fmt_poss(possB_scored)

            # 4) Garantia: pelo menos 1 voz (mais próxima)
            fallback.sort(key=lambda x: (x[1], VOICES.index(x[0]) if x[0] in VOICES else 9999))
            closest = fallback[0]

            if observations:
                voice, violation, obs = closest
                score = 1.0 / (1.0 + float(violation))
                return [], [(voice, score, obs)]
            else:
                voice, violation = closest
                return [], [voice]

        except Exception as e:
            print(f"Erro ao calcular vozes compatíveis: {e}")
            if observations:
                return [], [(VOICES[0], 0.0, "Fallback por erro")]
            return [], [VOICES[0]]
    def get_voice_group_ranges_old(self,
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
                    group_ranges[voz] = (librosa.midi_to_note(int(group_min)),  librosa.midi_to_note(int(group_max)))
                    group_extension[voz] = (librosa.midi_to_note(int(min(mins))),  librosa.midi_to_note(int(max(maxs))))

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

    def get_voice_group_ranges_all(self, solistas=None, best_fit=None, not_fit=None):
        """
        Calcula os ranges do grupo por voz.

        - group_ranges: range "comum" do grupo (interseção), considerando todos os coristas.
        - group_extension: extensão total do grupo (união), considerando todos os coristas.
        - group_ranges_fit: igual ao group_ranges, mas (quando best_fit e not_fit são fornecidos)
          desconsidera do CÁLCULO do range do grupo os coristas que estão em not_fit e não estão em best_fit.
          (Se estiver em ambos, continua valendo.)
          Obs.: essa exclusão NÃO afeta o group_extension.
        """
        voice_groups_all = {v: [] for v in VOICES}
        voice_groups_fit = {v: [] for v in VOICES}

        # Quando recebe ambos, exclui do "fit" quem está em not_fit mas não em best_fit
        # Quando recebe ambos, exclui do "fit" quem está em not_fit mas não está em best_fit
        excluded_from_fit = set()
        if best_fit is not None and not_fit is not None:
            # best_fit é dict: {alguma_coisa: [nomes...], ...}
            best_fit_names = {
                name
                for names in best_fit.values()
                for name in (names or [])
            }
            excluded_from_fit = set(not_fit) - best_fit_names

        # Agrupa coristas por voz atribuída
        for corista, data in self.coristas.items():
            voz = data['voz_atribuida']
            min_midi = librosa.note_to_midi(data['range_min'])
            max_midi = librosa.note_to_midi(data['range_max'])

            voice_groups_all[voz].append((min_midi, max_midi))

            # Para o cálculo "fit", aplica a exclusão (quando configurada)
            if corista not in excluded_from_fit:
                voice_groups_fit[voz].append((min_midi, max_midi))

        def _calc_group_ranges_and_extension(voice_groups: dict):
            group_ranges = {}
            group_extension = {}
            for voz in VOICES:
                if not voice_groups[voz]:
                    continue

                mins = [r[0] for r in voice_groups[voz]]
                maxs = [r[1] for r in voice_groups[voz]]

                group_min = max(mins)  # maior mínimo (interseção)
                group_max = min(maxs)  # menor máximo (interseção)

                if group_min <= group_max:
                    group_ranges[voz] = (
                        librosa.midi_to_note(int(group_min)),
                        librosa.midi_to_note(int(group_max)),
                    )

                group_extension[voz] = (
                    librosa.midi_to_note(int(min(mins))),
                    librosa.midi_to_note(int(max(maxs))),
                )

            return group_ranges, group_extension

        # "All": ranges e extensão com todos
        group_ranges, group_extension = _calc_group_ranges_and_extension(voice_groups_all)

        # "Fit": apenas ranges (extensão não muda)
        group_ranges_fit, _ = _calc_group_ranges_and_extension(voice_groups_fit)

        if solistas:
            # Atualiza os valores de solistas com os ranges de coristas quando disponíveis
            solistas_updated = {
                k: (self.coristas[k]['range_min'], self.coristas[k]['range_max'])
                if k in self.coristas else v
                for k, v in solistas.items()
            }

            # Une com as ranges de grupo
            group_ranges = solistas_updated | group_ranges
            group_ranges_fit = solistas_updated | group_ranges_fit
        #if best_fit and not_fit:
        return group_ranges, group_extension, group_ranges_fit
        #return group_ranges, group_extension

    def get_voice_group_ranges(self,
                               solistas=None,
                               best_fit=None,
                               not_fit=None) -> dict:
        """
        Calcula os ranges do grupo por voz.

        - group_ranges: desconsidera (quando best_fit e not_fit são passados) coristas em `not_fit`
          que NÃO estão em nenhuma lista dos valores de `best_fit`.
          Se o corista estiver em ambos (best_fit e not_fit), ele continua sendo considerado.
        - group_extension: NÃO aplica esse filtro (sempre usa todos os coristas).
        """
        # Conjunto de coristas a excluir APENAS do group_ranges
        exclude_from_group_range = []
        for name in self.coristas:
            if not self.coristas[name]['vozes_recomendadas']:
                exclude_from_group_range.append(name)

        voice_groups_for_range = {v: [] for v in VOICES}  # com filtro (group_ranges)
        voice_groups_for_extension = {v: [] for v in VOICES}  # sem filtro (group_extension)

        # Agrupa coristas por voz atribuída
        for corista, info in self.coristas.items():
            voz = info['voz_atribuida']
            min_midi = librosa.note_to_midi(info['range_min'])
            max_midi = librosa.note_to_midi(info['range_max'])

            # Sempre entra na extensão
            voice_groups_for_extension[voz].append((min_midi, max_midi))

            # Só entra no range se não estiver no conjunto excluído
            if corista not in exclude_from_group_range:
                voice_groups_for_range[voz].append((min_midi, max_midi))

        # Calcula range do grupo: maior mínimo e menor máximo
        group_ranges = {}
        group_extension = {}

        for voz in VOICES:
            # group_ranges (com filtro)
            if voice_groups_for_range[voz]:
                mins = [r[0] for r in voice_groups_for_range[voz]]
                maxs = [r[1] for r in voice_groups_for_range[voz]]

                group_min = max(mins)  # maior mínimo
                group_max = min(maxs)  # menor máximo

                if group_min <= group_max:
                    group_ranges[voz] = (
                        librosa.midi_to_note(int(group_min)),
                        librosa.midi_to_note(int(group_max)),
                    )

            # group_extension (sem filtro)
            if voice_groups_for_extension[voz]:
                mins_all = [r[0] for r in voice_groups_for_extension[voz]]
                maxs_all = [r[1] for r in voice_groups_for_extension[voz]]
                group_extension[voz] = (
                    librosa.midi_to_note(int(min(mins_all))),
                    librosa.midi_to_note(int(max(maxs_all))),
                )

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