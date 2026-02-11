"""
MusicDataManager - Responsável por gerenciar dados de músicas
Responsabilidades:
- Salvar músicas no JSON
- Carregar biblioteca de músicas
- Carregar ranges de uma música específica
- Validar e processar dados de música
"""

from tkinter import messagebox
from Constants import VOICES


class MusicDataManager:
    def __init__(self, coristas_mgr):
        self.coristas_mgr = coristas_mgr
        self.music_library = {}
        self.music_names = []

    def save_music_ranges(self, music_name, ranges, solistas, vozes_por_corista, root, mode):
        """
        Salva os ranges de uma música no JSON.

        Args:
            music_name: Nome da música
            ranges: Dicionário com ranges por voz {voz: {min, max}}
            solistas: Dicionário de solistas {nome: [min, max]}
            vozes_por_corista: Mapeamento {voz: [coristas]}
            root: Tom original da música
            mode: Modo (maior/menor)

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if not music_name or music_name == "Untitled":
            return False, "Nome da música é obrigatório"

        if not ranges:
            return False, "Preencha ao menos um range de voz"

        # Verificar se já existe
        existe = self.coristas_mgr.check_music_exists(music_name)

        if existe:
            # A confirmação deve ser feita pela UI, não aqui
            pass

        # Delega para o CoristasManager
        sucesso, mensagem = self.coristas_mgr.save_music_ranges_to_json(
            music_name=music_name,
            ranges=ranges,
            solistas=solistas,
            vozes_por_corista=vozes_por_corista,
            root=root,
            mode=mode
        )

        return sucesso, mensagem

    def load_music_library(self, grupo=None):
        """
        Carrega a biblioteca de músicas do JSON.

        Args:
            grupo: Nome do grupo (opcional, filtra por grupo)

        Returns:
            Lista de nomes de músicas
        """
        self.music_library.clear()
        self.music_names = []

        data, musicas, groups = self.coristas_mgr.read_data(
            extract='musicas',
            all_in=True,
            group_list=True
        )

        if grupo:
            self.music_library = {
                nome: info
                for nome, info in musicas.items()
                if info.get("grupo") == grupo
            }
        else:
            self.music_library = musicas

        self.music_names = list(self.music_library.keys())

        return self.music_names, groups

    def get_music_data(self, music_name):
        """
        Retorna os dados de uma música específica.

        Args:
            music_name: Nome da música

        Returns:
            Dicionário com dados da música ou None se não encontrada
        """
        return self.music_library.get(music_name)

    def normalize_solistas_data(self, solistas_raw):
        """
        Normaliza dados de solistas de diferentes formatos.

        Args:
            solistas_raw: Dados brutos de solistas (dict, list, etc)

        Returns:
            Dicionário normalizado {nome: [min, max]}
        """
        if solistas_raw is None:
            return {}

        # Se já é dicionário com formato correto
        if isinstance(solistas_raw, dict):
            return solistas_raw

        # Se é lista de dicts
        if isinstance(solistas_raw, list):
            normalized = {}
            for item in solistas_raw:
                if isinstance(item, dict):
                    nome = item.get('nome') or item.get('name')
                    min_val = item.get('min') or item.get('0', '')
                    max_val = item.get('max') or item.get('1', '')
                    if nome:
                        normalized[nome] = [min_val, max_val]
            return normalized

        return {}

    def validate_music_name(self, name):
        """
        Valida o nome de uma música.

        Args:
            name: Nome a validar

        Returns:
            (válido: bool, mensagem: str)
        """
        if not name or name.strip() == "" or name == "Untitled":
            return False, "Nome da música é obrigatório"

        return True, ""

    def check_music_exists(self, music_name):
        """
        Verifica se uma música já existe na biblioteca.

        Args:
            music_name: Nome da música

        Returns:
            bool
        """
        return self.coristas_mgr.check_music_exists(music_name)
