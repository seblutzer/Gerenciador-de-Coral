"""
AnalysisManager - Responsável por análises de transposição
Responsabilidades:
- Executar análise de transposição
- Calcular melhores transposições
- Calcular O_i para cada voz
- Processar ranges de vozes e grupos
- Gerar dados para visualização
"""
import librosa
from Constants import VOICES, VOICE_BASE_RANGES
from GeneralFunctions import transpose_note, transpose_key
from typing import Dict, Optional, Any


class AnalysisManager:
    def __init__(self,coristas_mgr):
        self.coristas_mgr = coristas_mgr
        self.group_ranges = None
        self.group_extension = None
        self.solistas = None
        self.analysis_all = {}
        self.current_piece_ranges = None
        self._use_group_ranges = False

    def set_solistas(self,
                     solistas):
        """
        Define os solistas para análise.

        Args:
            solistas: Dicionário {nome: (min, max)}
        """
        self.solistas = solistas

    def toggle_range_mode(self
                          ):
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

    def run_analysis(self,
                     piece_ranges, root, mode):
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
        self.analysis_all = self.analyze_ranges_with_penalty(
            root, mode, self.current_piece_ranges, self.group_ranges
        )

        return self.analysis_all

    def compute_per_voice_Os_for_T(self, T: int,
                                   piece_ranges: Dict[str, tuple], group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, int]:
        """
        Calcula, para uma transposição T dada, os O_i para cada voz.
        Usa a regra de penalidade semelhante à usada em on_t_change.
        """
        # Vozes consideradas
        voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if not group_ranges else list(
            group_ranges.keys())

        if group_ranges is None:
            group_ranges = VOICE_BASE_RANGES

        per_voice_Os: Dict[str, int] = {}

        for v in voices:
            if v not in piece_ranges or piece_ranges[v] == ('', ''):
                continue

            mn = librosa.note_to_midi(piece_ranges[v][0])
            mx = librosa.note_to_midi(piece_ranges[v][1])

            # Faixa da voz (grupo/base)
            if v in group_ranges:
                g_min = librosa.note_to_midi(group_ranges[v][0])
                g_max = librosa.note_to_midi(group_ranges[v][1])
            else:
                g_min = librosa.note_to_midi(VOICE_BASE_RANGES[v][0])
                g_max = librosa.note_to_midi(VOICE_BASE_RANGES[v][1])

            best_O = None
            best_pen = float('inf')

            for O in range(-4, 5):
                low = mn + T + 12 * O
                high = mx + T + 12 * O

                pen = max(0, g_min - low) + max(0, high - g_max)

                if pen < best_pen or (pen == best_pen and (best_O is None or abs(O) < abs(best_O))):
                    best_O = O
                    best_pen = pen

            per_voice_Os[v] = best_O

        return per_voice_Os

    def analyze_ranges_with_penalty(self,
                                    original_root: str,original_mode: str, piece_ranges: Dict[str, tuple], group_ranges: Optional[Dict[str, tuple]] = None) -> Dict[str, Any]:
        """
        Análise com pontuação para encontrar o melhor T usando o esquema descrito.
        Retorna um dict com:
          - best_T
          - best_Os (offsets por voz)
          - best_key_root, best_key_mode
          - voice_scores: dicionário com {voice: {T: score}} para todas as transposições
          - debug (ranking de Ts para debug)
        """
        voices = list(
            {k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) if group_ranges is None else list(
            group_ranges.keys())

        if group_ranges is None:
            group_ranges = VOICE_BASE_RANGES

        # Mapear ranges por voz, com fallback para valores padrão se ausentes
        piece_mins = {}
        piece_maxs = {}
        for v in voices:
            if v in piece_ranges:
                mn, mx = piece_ranges[v]
                piece_mins[v] = librosa.note_to_midi(mn)
                piece_maxs[v] = librosa.note_to_midi(mx)
            else:
                piece_mins[v] = librosa.note_to_midi("A4")
                piece_maxs[v] = librosa.note_to_midi("A5")

        voice_base_mins = {}
        voice_base_maxs = {}
        for v in voices:
            mn, mx = group_ranges[v]
            voice_base_mins[v] = librosa.note_to_midi(mn)
            voice_base_maxs[v] = librosa.note_to_midi(mx)

        # Inicializar dicionário de scores por voz
        voice_scores_by_voice = {v: {} for v in voices}

        # Faixas de transposição consideradas
        T_values = list(range(-11, 12))

        best_T = None
        best_score = -float('inf')
        best_offsets = {}

        t_scores = {}
        feasible_Ts = []
        all_feasible = []

        for T in T_values:
            offsets = {}
            total_score = 0.0
            feasible_for_T = True

            for v in voices:
                if v in piece_ranges and piece_ranges[v] != ('', ''):
                    min_i = piece_mins[v]
                    max_i = piece_maxs[v]

                    min_v = voice_base_mins[v]
                    max_v = voice_base_maxs[v]

                    required_span = max_i - min_i
                    allowed_span = max_v - min_v

                    best_score_v = -float('inf')
                    best_O = None
                    best_L = best_H = None
                    best_d_min = best_d_max = None

                    for O in range(-4, 5):
                        low = min_i + T + 12 * O
                        high = max_i + T + 12 * O

                        # Verificar encaixe na faixa da voz
                        if low < min_v or high > max_v:
                            continue

                        d_min = low - min_v
                        d_max = max_v - high

                        m = (allowed_span - required_span) / 2.0

                        score_v = 1.0 - (abs(d_min - m) + abs(d_max - m)) / (2 * m) if m != 0 else 0  # -math.inf

                        if (score_v > best_score_v) or (
                                abs(score_v - best_score_v) < 1e-12 and (best_O is None or abs(O) < abs(best_O))):
                            best_score_v = score_v
                            best_O = O
                            best_L = low
                            best_H = high
                            best_d_min = d_min
                            best_d_max = d_max

                    if best_O is None:
                        feasible_for_T = False
                        voice_scores_by_voice[v][T] = 0.0  # Transposição inviável para esta voz
                        # break

                    offsets[v] = best_O
                    voice_scores_by_voice[v][T] = best_score_v  # Armazenar score por voz
                    total_score += best_score_v
                else:
                    voice_scores_by_voice[v][T] = 0.0

            if feasible_for_T:
                t_scores[T] = total_score
                feasible_Ts.append(T)

                if best_T is None or total_score > best_score or (
                        abs(total_score - best_score) < 1e-12 and abs(T) < abs(best_T)):
                    best_T = T
                    best_score = total_score
                    best_offsets = offsets

            all_feasible.append((T, total_score, offsets))

        debug_ranking_T = sorted(feasible_Ts, key=lambda t: (-t_scores.get(t, -float('inf')), abs(t)))

        if best_T is None:
            return {
                "best_T": None,
                "best_Os": {},
                "best_key_root": original_root,
                "best_key_mode": original_mode,
                "voice_scores": voice_scores_by_voice,
                "debug": debug_ranking_T
            }

        new_root, new_mode = transpose_key(original_root, original_mode, best_T)

        return {
            "best_T": best_T,
            "best_Os": best_offsets,
            "best_key_root": new_root,
            "best_key_mode": new_mode,
            "voice_scores": voice_scores_by_voice,
            "debug": debug_ranking_T
        }

    def compute_transposition_for_t(self,
                                    T, piece_ranges=None):
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

        per_voice_Os = self.compute_per_voice_Os_for_T(T, piece_ranges, self.group_ranges)
        return per_voice_Os

    def get_transposed_key(self,
                           root, T):
        """
        Retorna a nova tonalidade após transposição.

        Args:
            root: Tom original
            T: Transposição em semitons

        Returns:
            str: Nova tonalidade
        """
        return transpose_note(root, T)

    def get_transposed_ranges(self,
                              piece_ranges, T, per_voice_Os=None):
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

            min_m = librosa.note_to_midi(mn)
            max_m = librosa.note_to_midi(mx)
            O = per_voice_Os.get(v, 0)

            min_final = int(min_m + T + 12 * O)
            max_final = int(max_m + T + 12 * O)

            transposed[v] = {
                'min': librosa.midi_to_note(min_final),
                'max': librosa.midi_to_note(max_final),
                'O': O
            }

        return transposed

    def format_results_text(self,
                            T, root, mode):
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

    def get_visualization_data(self
                               ):
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

    def is_using_group_ranges(self
                              ):
        """Retorna True se está usando ranges de grupo."""
        return self._use_group_ranges
