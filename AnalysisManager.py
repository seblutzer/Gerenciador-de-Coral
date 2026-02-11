"""
AnalysisManager - Responsável por análises de transposição
Responsabilidades:
- Executar análise de transposição
- Calcular melhores transposições
- Calcular O_i para cada voz
- Processar ranges de vozes e grupos
- Gerar dados para visualização
"""

from Constants import VOICES
from GeneralFunctions import (
    analyze_ranges_with_penalty,
    compute_per_voice_Os_for_T,
    transpose_note,
    note_to_midi,
    midi_to_note
)


class AnalysisManager:
    def __init__(self, coristas_mgr):
        self.coristas_mgr = coristas_mgr
        self.group_ranges = None
        self.group_extension = None
        self.solistas = None
        self.analysis_all = {}
        self.current_piece_ranges = None
        self._use_group_ranges = False

    def set_solistas(self, solistas):
        """
        Define os solistas para análise.

        Args:
            solistas: Dicionário {nome: (min, max)}
        """
        self.solistas = solistas

    def toggle_range_mode(self):
        """
        Alterna entre usar ranges de grupo ou ranges base.

        Returns:
            (modo_atual: str, ranges_atualizados: dict)
            modo_atual: 'grupo' ou 'base'
        """
        self._use_group_ranges = not self._use_group_ranges

        if self._use_group_ranges:
            # Carrega ranges do grupo
            if hasattr(self.coristas_mgr, "get_voice_group_ranges"):
                self.group_ranges, self.group_extension = \
                    self.coristas_mgr.get_voice_group_ranges(
                        solistas=self.solistas if self.solistas else None
                    )
                return 'grupo', self.group_ranges
            else:
                # Fallback para base
                self._use_group_ranges = False
                self.group_ranges = None
                self.group_extension = None
                return 'base', None
        else:
            self.group_ranges = None
            self.group_extension = None
            return 'base', None

    def run_analysis(self, piece_ranges, root, mode):
        """
        Executa análise completa de transposição.

        Args:
            piece_ranges: Ranges da peça {voz: (min, max)}
            root: Tom original (ex: "C", "D#")
            mode: Modo da música ("maior" ou "menor")

        Returns:
            Dicionário com resultados da análise
        """
        if not piece_ranges:
            return None

        # Combina ranges da peça com solistas se estiver usando ranges de grupo

        if self._use_group_ranges and self.solistas:
            combined_ranges = self.solistas.copy()
            combined_ranges.update(piece_ranges)
            piece_ranges = combined_ranges

        self.current_piece_ranges = piece_ranges

        # Executa análise completa
        self.analysis_all = analyze_ranges_with_penalty(
            root, mode, self.current_piece_ranges, self.group_ranges
        )

        return self.analysis_all

    def compute_transposition_for_t(self, T, piece_ranges=None):
        """
        Calcula os O_i para uma transposição T específica.

        Args:
            T: Transposição em semitons (int)
            piece_ranges: Ranges da peça (opcional, usa o último se None)

        Returns:
            Dicionário {voz: O_i}
        """
        if piece_ranges is None:
            piece_ranges = self.current_piece_ranges

        if not piece_ranges:
            return {}

        per_voice_Os = compute_per_voice_Os_for_T(T, piece_ranges, self.group_ranges)
        return per_voice_Os

    def get_transposed_key(self, root, T):
        """
        Retorna a nova tonalidade após transposição.

        Args:
            root: Tom original
            T: Transposição em semitons

        Returns:
            str: Nova tonalidade
        """
        return transpose_note(root, T)

    def get_transposed_ranges(self, piece_ranges, T, per_voice_Os=None):
        """
        Calcula as faixas resultantes após transposição.

        Args:
            piece_ranges: Ranges originais {voz: (min, max)}
            T: Transposição em semitons
            per_voice_Os: Dicionário com O_i por voz (opcional, calcula se None)

        Returns:
            Dicionário {voz: {'min': nota, 'max': nota, 'O': int}}
        """
        if per_voice_Os is None:
            per_voice_Os = self.compute_transposition_for_t(T, piece_ranges)

        transposed = {}
        voices_to_check = self.group_ranges.keys() if self._use_group_ranges else VOICES

        for v in voices_to_check:
            mn, mx = piece_ranges.get(v, (None, None))
            if not mn or not mx:
                continue

            min_m = note_to_midi(mn)
            max_m = note_to_midi(mx)
            O = per_voice_Os.get(v, 0)

            min_final = int(min_m + T + 12 * O)
            max_final = int(max_m + T + 12 * O)

            transposed[v] = {
                'min': midi_to_note(min_final),
                'max': midi_to_note(max_final),
                'O': O
            }

        return transposed

    def format_results_text(self, T, root, mode):
        """
        Formata o texto de resultados para exibição.

        Args:
            T: Transposição atual
            root: Tom original
            mode: Modo original

        Returns:
            str: Texto formatado
        """
        if not self.analysis_all:
            return "Nenhuma análise disponível. Execute a análise primeiro.\n"

        lines = []

        # Melhor transposição global
        best_T_global = self.analysis_all.get("best_T")
        best_key_root = self.analysis_all.get("best_key_root")
        best_key_mode = self.analysis_all.get("best_key_mode")

        if best_T_global is not None:
            lines.append(
                f"Melhor transposição: {best_T_global:+d} semitons → "
                f"{best_key_root} {best_key_mode}"
            )

        # Transposição atual
        transposed_root = self.get_transposed_key(root, T)
        lines.append(
            f"Transposição atual: {T:+d} semitons ({root} → {transposed_root})"
        )

        # Possíveis transposições
        debug = self.analysis_all.get("debug", [])
        if debug:
            if len(debug) > 1:
                pairs = []
                i = 0
                while i < len(debug):
                    if debug[i] == 0:
                        pairs.append(str(debug[i]))
                        i += 1
                    else:
                        if i + 1 < len(debug):
                            pairs.append(f"({debug[i]}/{debug[i + 1]})")
                            i += 2
                        else:
                            pairs.append(str(debug[i]))
                            i += 1
                lines.append("Possíveis transposições: " + ", ".join(pairs) + " semitons")
            else:
                lines.append(f"Transposição possível: {debug[0]:+d} semitons")

        # Faixas resultantes
        per_voice_Os = self.compute_transposition_for_t(T)
        transposed_ranges = self.get_transposed_ranges(
            self.current_piece_ranges, T, per_voice_Os
        )

        lines.append("\nFaixas resultantes:")
        for v, data in transposed_ranges.items():
            O = data['O']
            O_text = 'oitava' if -2 < O < 2 else 'oitavas'
            min_note = data['min']
            max_note = data['max']

            if O != 0:
                lines.append(f"  {v}: {min_note} → {max_note} ({O} {O_text})")
            else:
                lines.append(f"  {v}: {min_note} → {max_note}")

        return "\n".join(lines) + "\n"

    def get_visualization_data(self):
        """
        Retorna dados necessários para atualização do visualizador.

        Returns:
            dict com: group_ranges, group_extension, voice_scores
        """
        return {
            'group_ranges': self.group_ranges,
            'group_extension': self.group_extension,
            'voice_scores': self.analysis_all.get('voice_scores', {}),
            'use_group_ranges': self._use_group_ranges
        }

    def is_using_group_ranges(self):
        """Retorna True se está usando ranges de grupo."""
        return self._use_group_ranges
