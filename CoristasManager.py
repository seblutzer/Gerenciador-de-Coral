import json
import os
from Constants import DATA_FILE, VOICES, VOICE_BASE_RANGES
from GeneralFunctions import note_to_midi, midi_to_note

# ===== GERENCIAMENTO DE CORISTAS E DADOS =====
class CoristasManager:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.coristas = []
        self.load_data()

    def load_data(self):
        """Carrega dados do arquivo JSON"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.coristas = data.get('coristas', [])
            except Exception as e:
                print(f"Erro ao carregar dados: {e}")
                self.coristas = []
        else:
            self.coristas = []

    def save_data(self):
        """Salva dados em arquivo JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump({'coristas': self.coristas}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Erro ao salvar dados: {e}")
            return False

    def add_corista(self, nome, range_min, range_max):
        """Adiciona um corista com vozes compatíveis"""
        try:
            # Valida ranges
            note_to_midi(range_min)
            note_to_midi(range_max)
            if note_to_midi(range_min) > note_to_midi(range_max):
                raise ValueError(f"Range inválido: {range_min} > {range_max}")

            # Calcula vozes compatíveis
            vozes_recomendadas, vozes_possiveis = self.calculate_compatible_voices(range_min, range_max)
            all_compatible = vozes_recomendadas + [v for v, _, obs in vozes_possiveis]
            voz_calculada = vozes_recomendadas[0] if vozes_recomendadas else (
                vozes_possiveis[0][0] if vozes_possiveis else VOICES[0])

            corista = {
                'nome': nome,
                'range_min': range_min,
                'range_max': range_max,
                'voz_calculada': voz_calculada,
                'voz_atribuida': voz_calculada,
                'vozes_recomendadas': vozes_recomendadas,
                'vozes_possiveis': vozes_possiveis  # Lista de tuples: (voz, diff, obs)
            }
            self.coristas.append(corista)
            return True, corista
        except Exception as e:
            return False, str(e)

    def remove_corista(self, index):
        """Remove um corista pelo índice"""
        if 0 <= index < len(self.coristas):
            self.coristas.pop(index)
            return True
        return False

    def update_corista_voz(self, index, voz_atribuida):
        """Atualiza a voz atribuída de um corista"""
        if 0 <= index < len(self.coristas):
            self.coristas[index]['voz_atribuida'] = voz_atribuida
            return True
        return False

    def calculate_compatible_voices(self, range_min: str, range_max: str) -> tuple:
        """
        Calcula todas as vozes compatíveis com o range fornecido.

        Retorna: (vozes_recomendadas, vozes_possiveis)
        - vozes_recomendadas: lista de vozes com encaixe perfeito
        - vozes_possiveis: lista de tuples (voz, max_diff, obs) com até 3 semitons de diferença
        """
        try:
            min_midi = note_to_midi(range_min)
            max_midi = note_to_midi(range_max)

            vozes_recomendadas = []
            vozes_possiveis = []

            for voice in VOICES:
                voice_min_str, voice_max_str = VOICE_BASE_RANGES[voice]
                voice_min = note_to_midi(voice_min_str)
                voice_max = note_to_midi(voice_max_str)

                # LÓGICA CORRIGIDA:
                # Encaixe perfeito: o range do corista CABE dentro da faixa da voz
                # Ou seja: voice_min <= corista_min E corista_max <= voice_max
                if min_midi <= voice_min and max_midi >= voice_max:
                    vozes_recomendadas.append(voice)
                else:
                    # Calcula quanto está faltando para encaixar perfeitamente
                    # Se corista_min < voice_min, faltam (voice_min - corista_min) tons graves
                    # Se corista_max > voice_max, faltam (corista_max - voice_max) tons agudos
                    diff_min = max(0, min_midi - voice_min)  # Semitons graves que faltam
                    diff_max = max(0, voice_max - max_midi)  # Semitons agudos que sobram

                    max_diff = max(diff_min, diff_max)

                    if max_diff <= 5:
                        # Próximo: até 5 semitons de diferença
                        obs = ""
                        if diff_min > 0:
                            obs += f"Falta {diff_min} semitom" if diff_min == 1 else f"Falta {diff_min} semitons"
                            obs += " grave"
                        if diff_max > 0:
                            if obs:
                                obs += " e "
                            obs += f"Falta {diff_max} semitom" if diff_max == 1 else f"Falta {diff_max} semitons"
                            obs += " agudo"

                        vozes_possiveis.append((voice, max_diff, obs))

            # Ordena os "possíveis" pela menor diferença
            vozes_possiveis.sort(key=lambda x: x[1])

            return vozes_recomendadas, vozes_possiveis
        except Exception as e:
            print(f"Erro ao calcular vozes compatíveis: {e}")
            return [], []

    def calculate_voice(self, range_min: str, range_max: str) -> str:
        """
        Retorna a voz primária (a melhor entre as compatíveis).
        """
        vozes_recomendadas, vozes_possiveis = self.calculate_compatible_voices(range_min, range_max)

        if vozes_recomendadas:
            return vozes_recomendadas[0]
        elif vozes_possiveis:
            return vozes_possiveis[0][0]
        else:
            return VOICES[0]

    def get_voice_group_ranges(self) -> dict:
        """
        Calcula os ranges do grupo por voz.
        Para cada voz: maior mínimo e menor máximo dos coristas dessa voz.
        """
        voice_groups = {v: [] for v in VOICES}

        # Agrupa coristas por voz atribuída
        for corista in self.coristas:
            voz = corista['voz_atribuida']
            min_midi = note_to_midi(corista['range_min'])
            max_midi = note_to_midi(corista['range_max'])
            voice_groups[voz].append((min_midi, max_midi))

        # Calcula range do grupo: maior mínimo e menor máximo
        group_ranges = {}
        for voz in VOICES:
            if voice_groups[voz]:
                mins = [r[0] for r in voice_groups[voz]]
                maxs = [r[1] for r in voice_groups[voz]]
                group_min = max(mins)  # maior mínimo
                group_max = min(maxs)  # menor máximo

                if group_min <= group_max:
                    group_ranges[voz] = (midi_to_note(int(group_min)), midi_to_note(int(group_max)))
            #    else:
                    # Se não há sobreposição, usa a primeira dupla de referência
           #         group_ranges[voz] = VOICE_BASE_RANGES[voz]
            #else:
            #    group_ranges[voz] = VOICE_BASE_RANGES[voz]

        return group_ranges