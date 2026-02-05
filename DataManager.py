import json
import os
from typing import List, Optional

class DataStore:
    """
    Gerencia toda a persistência em um único arquivo JSON unificado.
    Estrutura:
    {
        "coristas": [
            {
                "nome": "...",
                "range_min": "...",
                "range_max": "...",
                "voz_calculada": "...",
                "voz_atribuida": "...",
                "vozes_recomendadas": [...],
                "vozes_possiveis": [...]
            }
        ],
        "musicas": [
            {
                "name": "...",
                "root": "...",
                "mode": "...",
                "voices": {
                    "Soprano": {"min": "...", "max": "..."},
                    "Solista 1": {"min": "...", "max": "..."}
                },
                "solistas": [
                    {"index": 1, "name": "Solista 1", "corista_nome": "...", "min": "...", "max": "..."}
                ],
                "coristas_por_voz": {
                    "Soprano": ["Corista A", "Corista B"],
                    "Solista 1": ["Corista C"]
                },
                "timestamp": "..."
            }
        ]
    }
    """

    def __init__(self, filepath: str = "music_unified.json"):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        """Carrega dados do arquivo ou cria estrutura vazia."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao carregar {self.filepath}: {e}")
                return self._empty_structure()
        return self._empty_structure()

    def _empty_structure(self) -> dict:
        """Retorna estrutura vazia padrão."""
        return {"coristas": [], "musicas": []}

    def save(self) -> bool:
        """Salva dados no arquivo JSON."""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Erro ao salvar {self.filepath}: {e}")
            return False

    # ========== CORISTAS ==========
    def get_coristas(self) -> List[dict]:
        return self.data.setdefault("coristas", [])

    def add_corista(self, corista: dict) -> None:
        self.get_coristas().append(corista)
        self.save()

    def remove_corista(self, index: int) -> bool:
        coristas = self.get_coristas()
        if 0 <= index < len(coristas):
            coristas.pop(index)
            self.save()
            return True
        return False

    def update_corista(self, index: int, corista: dict) -> bool:
        coristas = self.get_coristas()
        if 0 <= index < len(coristas):
            coristas[index] = corista
            self.save()
            return True
        return False

    # ========== MÚSICAS ==========
    def get_musicas(self) -> List[dict]:
        return self.data.setdefault("musicas", [])

    def find_music_by_name(self, name: str) -> Optional[dict]:
        """Busca música por nome (case-insensitive)."""
        name_normalized = (name or "").strip().lower()
        for m in self.get_musicas():
            if (m.get("name") or "").strip().lower() == name_normalized:
                return m
        return None

    def add_or_update_music(self, music: dict) -> None:
        """Adiciona ou atualiza música pelo nome."""
        existing = self.find_music_by_name(music.get("name", ""))
        if existing:
            idx = self.get_musicas().index(existing)
            self.get_musicas()[idx] = music
        else:
            self.get_musicas().append(music)
        self.save()

    def remove_music(self, name: str) -> bool:
        music = self.find_music_by_name(name)
        if music:
            self.get_musicas().remove(music)
            self.save()
            return True
        return False

    def get_music_names(self) -> List[str]:
        return [m.get("name", "") for m in self.get_musicas()]