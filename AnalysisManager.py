from __future__ import annotations
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
from Constants import VOICES, VOICE_BASE_RANGES, MALE_VOICES, FEMALE_VOICES, OCTAVE_SHIFTS
from copy import deepcopy
from GeneralFunctions import transpose_note, transpose_key
from typing import Dict, Optional, Any
from itertools import combinations
from functools import lru_cache
import math


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
                     piece_ranges, root, mode, viz_data, confort):
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
            root, mode, self.current_piece_ranges, self.group_ranges, confort
        )

        return True

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

    def get_visualization_data(self,
                               T):
        """
        Retorna dados necessários para atualização do visualizador.

        Returns:
            dict com: group_ranges, group_extension, voice_scores
        """

        return {
            'group_ranges': self.group_ranges,
            'group_extension': self.group_extension,
            'voice_scores': self.analysis_all.get('voice_scores', {}),
            'use_group_ranges': self._use_group_ranges,
            'possible_fit': self.analysis_all.get('possible_fit', {}),
            'not_fit': self.analysis_all.get('not_fit', {})
        }

    def is_using_group_ranges(self
                              ):
        """Retorna True se está usando ranges de grupo."""
        return self._use_group_ranges

    def calculate_best_fit_voices(self,
                                  T: int):
        coristas: dict = self.coristas_mgr.coristas
        piece_range: dict = self.current_piece_ranges

        female_order = ["Soprano", "Mezzo-soprano", "Contralto"]  # agudo -> grave
        male_order = ["Tenor", "Barítono", "Baixo"]  # agudo -> grave

        # ----------------------------
        # Helpers
        # ----------------------------
        def infer_sex(cdata: dict) -> str | None:
            sx = cdata.get("sexo") or cdata.get("gender")
            if sx:
                sx = str(sx).lower()
                if sx.startswith("m"):
                    return "M"
                if sx.startswith("f"):
                    return "F"

            for k in ("voz_calculada", "voz_atribuida"):
                v = cdata.get(k)
                if v in FEMALE_VOICES:
                    return "F"
                if v in MALE_VOICES:
                    return "M"

            rec = cdata.get("vozes_recomendadas") or []
            poss = cdata.get("vozes_possiveis") or []
            any_voices = list(rec) + list(poss)
            if any(v in FEMALE_VOICES for v in any_voices):
                return "F"
            if any(v in MALE_VOICES for v in any_voices):
                return "M"
            return None

        def person_range_midi(name: str) -> tuple[int, int] | None:
            c = coristas[name]
            rmin = c.get("range_min") or ""
            rmax = c.get("range_max") or ""
            if not rmin or not rmax:
                return None
            p_min = int(librosa.note_to_midi(rmin))
            p_max = int(librosa.note_to_midi(rmax))
            return (p_min, p_max) if p_min <= p_max else (p_max, p_min)

        def voice_range_midi_transposed(v: str) -> tuple[int, int] | None:
            r = piece_range.get(v)
            if not r or r == ("", "") or not r[0] or not r[1]:
                return None
            mn = int(librosa.note_to_midi(r[0])) + int(T)
            mx = int(librosa.note_to_midi(r[1])) + int(T)
            return (mn, mx) if mn <= mx else (mx, mn)

        def fits_in_some_octave(p_min: int, p_max: int, m_min: int, m_max: int) -> bool:
            k_lo = math.ceil((p_min - m_min) / 12.0)
            k_hi = math.floor((p_max - m_max) / 12.0)
            return k_lo <= k_hi

        def best_intersection_len(p_min: int, p_max: int, m_min: int, m_max: int) -> int:
            # para not_fit no possible_fit: maximiza quantos semitons do requerido ele cobre
            cp = (p_min + p_max) / 2.0
            cm = (m_min + m_max) / 2.0
            k0 = int(round((cp - cm) / 12.0))
            best = 0
            for k in range(k0 - 3, k0 + 4):
                a1, b1 = p_min, p_max
                a2, b2 = m_min + 12 * k, m_max + 12 * k
                inter = max(0, min(b1, b2) - max(a1, a2))
                best = max(best, inter)
            return int(best)

        def pick_side_for_unknown(name: str, female_active: list[str], male_active: list[str], music_midi: dict):
            pr = person_range_midi(name)
            if pr is None:
                return None
            p_min, p_max = pr

            def side_cost(voices: list[str]) -> float:
                if not voices:
                    return float("inf")
                best = float("inf")
                for v in voices:
                    m_min, m_max = music_midi[v]
                    if fits_in_some_octave(p_min, p_max, m_min, m_max):
                        return 0.0
                    inter = best_intersection_len(p_min, p_max, m_min, m_max)
                    best = min(best, 10_000 - inter)
                return best

            if female_active and not male_active:
                return "F"
            if male_active and not female_active:
                return "M"
            if not female_active and not male_active:
                return None

            return "F" if side_cost(female_active) <= side_cost(male_active) else "M"

        # ----------------------------
        # 1) Vozes ativas + ranges em MIDI (já com T)
        # ----------------------------
        active_voices = []
        music_midi: dict[str, tuple[int, int]] = {}
        for v in piece_range.keys():
            rr = voice_range_midi_transposed(v)
            if rr is not None:
                active_voices.append(v)
                music_midi[v] = rr

        best_fit = {v: [] for v in active_voices}
        possible_fit = {v: [] for v in active_voices}
        not_fit: list[str] = []

        female_active = [v for v in active_voices if v in FEMALE_VOICES]
        male_active = [v for v in active_voices if v in MALE_VOICES]

        # ----------------------------
        # 2) Separar por sexo (unknown tenta escolher lado)
        # ----------------------------
        females, males, unknown = [], [], []
        for name, cdata in coristas.items():
            sx = infer_sex(cdata)
            if sx == "F":
                females.append(name)
            elif sx == "M":
                males.append(name)
            else:
                unknown.append(name)

        for name in unknown:
            side = pick_side_for_unknown(name, female_active, male_active, music_midi)
            if side == "F":
                females.append(name)
            elif side == "M":
                males.append(name)
            else:
                not_fit.append(name)

        # ----------------------------
        # 3) BEST_FIT por lado
        #    - cafés só entram se encaixarem perfeitamente
        #    - quem tem recomendadas SEMPRE entra (mesmo sem encaixar) e entra em not_fit também
        # ----------------------------
        def allocate_best_for_side(names: list[str], voices: list[str], voice_order: list[str]):
            if not voices:
                return {v: [] for v in voices}, list(names)

            order_idx = {v: i for i, v in enumerate(voice_order)}
            voices_sorted = sorted(voices, key=lambda v: order_idx.get(v, 10 ** 9))
            voices_set = set(voices_sorted)

            people = {}
            side_not_fit: list[str] = []

            # monta candidatos
            for nm in names:
                c = coristas[nm]
                rec_set = set(c.get("vozes_recomendadas") or [])
                poss_set = set(c.get("vozes_possiveis") or [])
                is_cafe = (len(rec_set) == 0)

                pr = person_range_midi(nm)
                if pr is None:
                    if rec_set:
                        side_not_fit.append(nm)
                        # não tem range => entra no best_fit mesmo assim, em alguma voz do lado
                        people[nm] = dict(
                            p_min=0, p_max=0,
                            rec_set=rec_set, poss_set=poss_set,
                            is_cafe=False,
                            fit_voices=[],
                            allowed=list(voices_sorted),  # forçado
                            rec_count=len(rec_set),
                        )
                    else:
                        side_not_fit.append(nm)
                    continue

                p_min, p_max = pr

                fit_voices = []
                for v in voices_sorted:
                    m_min, m_max = music_midi[v]
                    if fits_in_some_octave(p_min, p_max, m_min, m_max):
                        fit_voices.append(v)

                if not fit_voices:
                    side_not_fit.append(nm)
                    if is_cafe:
                        # café com leite que não cabe => não entra no best_fit
                        continue
                    # tem recomendadas: entra no best_fit mesmo sem caber (vai invalidar o T depois)
                    people[nm] = dict(
                        p_min=p_min, p_max=p_max,
                        rec_set=rec_set, poss_set=poss_set,
                        is_cafe=False,
                        fit_voices=[],
                        allowed=list(voices_sorted),  # forçado
                        rec_count=len(rec_set),
                    )
                    continue

                # CORREÇÃO PRINCIPAL:
                # - influentes (tem rec) podem ir para QUALQUER voz que caiba (último recurso).
                # - cafés só entram se couberem; allowed = fit_voices (com preferência por poss no util)
                allowed = list(fit_voices)

                people[nm] = dict(
                    p_min=p_min, p_max=p_max,
                    rec_set=rec_set, poss_set=poss_set,
                    is_cafe=is_cafe,
                    fit_voices=fit_voices,
                    allowed=allowed,
                    rec_count=len(rec_set),
                )

            alloc = {v: [] for v in voices_sorted}

            influents = [nm for nm, d in people.items() if not d["is_cafe"]]
            cafes = [nm for nm, d in people.items() if d["is_cafe"]]

            # DP para influentes (sem caps fixos; minimiza desequilíbrio)
            n = len(influents)
            k = len(voices_sorted)
            if n > 0:
                voice_to_j = {v: j for j, v in enumerate(voices_sorted)}

                feasible_rec_mask = 0
                for j, v in enumerate(voices_sorted):
                    ok = any((v in people[nm]["rec_set"]) and (v in people[nm]["fit_voices"]) for nm in influents)
                    if ok:
                        feasible_rec_mask |= (1 << j)

                required_mask = feasible_rec_mask  # só "cobra" onde existe recomendado possível

                def util(nm: str, v: str) -> tuple[int, int, int, int]:
                    d = people[nm]
                    rec_set = d["rec_set"]
                    poss_set = d["poss_set"]
                    p_min = d["p_min"]
                    p_max = d["p_max"]
                    rec_count = d["rec_count"]

                    if v in rec_set:
                        label = 2
                        spec = 1000 // max(1, rec_count)
                    elif v in poss_set:
                        label = 1
                        spec = 0
                    else:
                        label = 0
                        spec = 0

                    rank = order_idx.get(v, 10 ** 9)
                    high_weight = (k - 1 - min(rank, k - 1))
                    low_weight = min(rank, k - 1)
                    high_pref = high_weight * int(p_max)
                    low_pref = low_weight * int(-p_min)
                    return (label, spec, high_pref, low_pref)

                def imbalance(counts: tuple[int, ...]) -> int:
                    if k <= 1:
                        return 0
                    return max(counts) - min(counts)

                @lru_cache(maxsize=None)
                def dp(i: int, counts: tuple[int, ...], rec_mask: int):
                    if i == n:
                        cover = int((rec_mask & required_mask).bit_count())
                        imb = imbalance(counts)
                        # maximiza cover, depois minimiza imbalance, depois preferências
                        return (cover, -imb, 0, 0, 0, 0)

                    nm = influents[i]
                    best = None
                    for v in people[nm]["allowed"]:
                        j = voice_to_j[v]
                        new_counts = list(counts)
                        new_counts[j] += 1
                        new_counts = tuple(new_counts)

                        new_mask = rec_mask
                        if (v in people[nm]["rec_set"]) and (v in people[nm]["fit_voices"]):
                            new_mask |= (1 << j)

                        nxt = dp(i + 1, new_counts, new_mask)
                        if nxt is None:
                            continue

                        u = util(nm, v)
                        val = (nxt[0], nxt[1], nxt[2] + u[0], nxt[3] + u[1], nxt[4] + u[2], nxt[5] + u[3])
                        if best is None or val > best:
                            best = val
                    return best

                # reconstrução
                counts = tuple([0] * k)
                rec_mask = 0
                for i, nm in enumerate(influents):
                    best_choice = None
                    best_val = None
                    for v in people[nm]["allowed"]:
                        j = voice_to_j[v]
                        new_counts = list(counts)
                        new_counts[j] += 1
                        new_counts = tuple(new_counts)

                        new_mask = rec_mask
                        if (v in people[nm]["rec_set"]) and (v in people[nm]["fit_voices"]):
                            new_mask |= (1 << j)

                        nxt = dp(i + 1, new_counts, new_mask)
                        if nxt is None:
                            continue

                        u = util(nm, v)
                        val = (nxt[0], nxt[1], nxt[2] + u[0], nxt[3] + u[1], nxt[4] + u[2], nxt[5] + u[3])
                        if best_val is None or val > best_val:
                            best_val = val
                            best_choice = (v, new_counts, new_mask)

                    v, counts, rec_mask = best_choice
                    alloc[v].append(nm)

            # cafés entram depois (não influenciam), balanceando por tamanho do grupo
            def cafe_sort_key(nm: str):
                d = people[nm]
                span = d["p_max"] - d["p_min"]
                return (len(d["allowed"]), -span, nm)

            for nm in sorted(cafes, key=cafe_sort_key):
                opts = people[nm]["allowed"]
                chosen = min(opts, key=lambda v: (len(alloc[v]), order_idx.get(v, 10 ** 9)))
                alloc[chosen].append(nm)

            return alloc, side_not_fit

        if female_active:
            alloc_f, nf_f = allocate_best_for_side(females, female_active, female_order)
            for v, lst in alloc_f.items():
                best_fit[v].extend(lst)
            not_fit.extend(nf_f)
        else:
            not_fit.extend(females)

        if male_active:
            alloc_m, nf_m = allocate_best_for_side(males, male_active, male_order)
            for v, lst in alloc_m.items():
                best_fit[v].extend(lst)
            not_fit.extend(nf_m)
        else:
            not_fit.extend(males)

        # dedup not_fit preservando ordem
        seen_nf = set()
        not_fit = [nm for nm in not_fit if not (nm in seen_nf or seen_nf.add(nm))]

        # ----------------------------
        # 4) POSSIBLE_FIT: best_fit + (somente quem ainda não está alocado) vindo do not_fit
        # ----------------------------
        possible_fit = deepcopy(best_fit)

        def already_allocated(nm: str) -> bool:
            for v in possible_fit.keys():
                if nm in possible_fit[v]:
                    return True
            return False

        def add_not_fit_to_possible(nm: str, side_voices: list[str], voice_order: list[str]):
            if not side_voices:
                return

            order_idx = {v: i for i, v in enumerate(voice_order)}
            pr = person_range_midi(nm)

            if pr is None:
                chosen = min(side_voices, key=lambda v: (len(possible_fit[v]), order_idx.get(v, 10 ** 9)))
                possible_fit[chosen].append(nm)
                return

            p_min, p_max = pr
            best_v = None
            best_key = None
            for v in side_voices:
                m_min, m_max = music_midi[v]
                inter = best_intersection_len(p_min, p_max, m_min, m_max)
                key = (-inter, len(possible_fit[v]), order_idx.get(v, 10 ** 9))
                if best_key is None or key < best_key:
                    best_key = key
                    best_v = v

            possible_fit[best_v].append(nm)

        for nm in not_fit:
            if already_allocated(nm):
                continue  # evita duplicar (caso típico: tem recomendadas e foi forçado ao best_fit)

            sx = infer_sex(coristas.get(nm, {})) if nm in coristas else None
            if sx == "F" and female_active:
                add_not_fit_to_possible(nm, female_active, female_order)
            elif sx == "M" and male_active:
                add_not_fit_to_possible(nm, male_active, male_order)
            else:
                if female_active and not male_active:
                    add_not_fit_to_possible(nm, female_active, female_order)
                elif male_active and not female_active:
                    add_not_fit_to_possible(nm, male_active, male_order)
                elif female_active and male_active:
                    pr = person_range_midi(nm)
                    if pr is None:
                        add_not_fit_to_possible(nm, male_active, male_order)
                    else:
                        p_min, p_max = pr
                        bestF = max(best_intersection_len(p_min, p_max, *music_midi[v]) for v in female_active)
                        bestM = max(best_intersection_len(p_min, p_max, *music_midi[v]) for v in male_active)
                        if bestF >= bestM:
                            add_not_fit_to_possible(nm, female_active, female_order)
                        else:
                            add_not_fit_to_possible(nm, male_active, male_order)

        self.best_fit = best_fit
        self.possible_fit = possible_fit
        self.not_fit = not_fit
        return best_fit, not_fit, possible_fit

    def analyze_ranges_with_penalty(
            self,
            original_root: str,
            original_mode: str,
            piece_ranges: Dict[str, tuple],
            group_ranges: Optional[Dict[str, tuple]] = None,
            confort: float = 0.33
    ) -> Dict[str, Any]:

        voices = list({k: v for k, v in piece_ranges.items() if v != ('', '')}.keys()) \
            if group_ranges is None else list(group_ranges.keys())

        if group_ranges is None:
            group_ranges = VOICE_BASE_RANGES

        # garante que calculate_best_fit_voices use estes ranges
        self.current_piece_ranges = piece_ranges

        piece_mins, piece_maxs = {}, {}
        for v in voices:
            if v in piece_ranges:
                mn, mx = piece_ranges[v]
                if mn and mx:
                    piece_mins[v] = librosa.note_to_midi(mn)
                    piece_maxs[v] = librosa.note_to_midi(mx)
            else:
                piece_mins[v] = librosa.note_to_midi("A4")
                piece_maxs[v] = librosa.note_to_midi("A5")

        voice_base_mins, voice_base_maxs = {}, {}
        for v in voices:
            mn, mx = group_ranges[v]
            if mn and mx:
                voice_base_mins[v] = librosa.note_to_midi(mn)
                voice_base_maxs[v] = librosa.note_to_midi(mx)

        voice_scores_by_voice = {v: {} for v in voices}
        T_values = list(range(-11, 12))

        def calculate_comfort_score_for_range2(low: int, high: int, min_v: int, max_v: int) -> float:
            """
            Calcula score de conforto baseado no piece_range vs group_range.

            Regras:
            - Dentro dos limites: sempre >= 0, máximo no ponto ideal (1/3 do excedente acima do grave)
            - Nas extremidades (low == min_v ou high == max_v): score = 0
            - Acima do ideal: penalidade com peso metade (cada 2 semitons acima = 1 abaixo)
            - Fora dos limites: penalidade 3x maior
            """
            required_span = high - low
            allowed_span = max_v - min_v

            # Excedente: quanto espaço há além do necessário
            excess = allowed_span - required_span

            # Verifica se está fora dos limites
            if low < min_v or high > max_v:
                # Fora dos limites - penalidade 3x maior
                below = max(0, min_v - low)  # semitons abaixo do mínimo
                above = max(0, high - max_v)  # semitons acima do máximo

                # Calcula a penalidade base (o peso normal seria 1/ideal_range)
                if excess > 0:
                    ideal_range = excess / 3.0  # 1/3 do excedente
                    base_weight = 1.0 / ideal_range
                else:
                    base_weight = 1.0  # se não há excedente, peso unitário

                # Penalidade 3x maior que o normal
                total_penalty = (below + above) * base_weight * 3.0
                return -total_penalty

            # Dentro dos limites
            if excess == 0:
                # Cabe exatamente nas extremidades
                return 0.0

            # Ponto ideal: 1/3 do excedente acima do grave
            # (equivale a 2/3 do excedente abaixo do agudo)
            ideal_start = min_v + (excess / 3.0)
            actual_start = low

            # Se está em alguma extremidade, score = 0
            if actual_start == min_v or high == max_v:
                return 0.0

            # Calcula distância do ponto ideal
            distance_from_ideal = actual_start - ideal_start

            if distance_from_ideal <= 0:
                # Está abaixo do ideal (mais para o grave)
                # Penalidade proporcional simples
                score = 1.0 - abs(distance_from_ideal) / (excess / 3.0)
            else:
                # Está acima do ideal (mais para o agudo)
                # Penalidade com peso metade: cada 2 semitons acima = 1 semitom abaixo
                effective_distance = distance_from_ideal / 2.0
                score = 1.0 - effective_distance / (excess / 3.0)

            # Garante que seja não-negativo dentro dos limites
            return max(0.0, score)

        def calculate_comfort_score_for_range(
                low: int,
                high: int,
                min_v: int,
                max_v: int,
                confort: float,
        ) -> float:
            """
            Score de conforto baseado no piece_range vs vocal_range, com ponto ideal controlado por `confort`.

            Interpretação:
            - excess = (max_v - min_v) - (high - low)  # folga disponível para "posicionar" o trecho
            - O início ideal (low ideal) fica em: min_v + confort * excess
              * confort=0   => ideal no limite do grave (min_v)
              * confort=1/2 => ideal no meio
              * confort=1   => ideal no limite do agudo (min_v + excess)

            Regras:
            - Fora dos limites (low < min_v ou high > max_v): score negativo com penalidade 3x.
            - Dentro dos limites:
              * score máximo (=1) no ponto ideal.
              * score decresce linearmente até 0 nas extremidades possíveis.
              * A assimetria da penalidade é automática: o lado com mais margem penaliza menos.
            """
            if not (0.0 <= confort <= 1.0):
                raise ValueError("confort must be between 0.0 and 1.0")

            required_span = high - low
            allowed_span = max_v - min_v
            excess = allowed_span - required_span

            # Fora dos limites
            if low < min_v or high > max_v:
                below = max(0, min_v - low)
                above = max(0, high - max_v)

                if excess > 0:
                    left_margin = confort * excess
                    right_margin = (1.0 - confort) * excess
                    ref = min(left_margin, right_margin)
                    if ref <= 0:  # confort == 0 ou 1
                        ref = excess
                    base_weight = 1.0 / ref
                else:
                    base_weight = 1.0

                total_penalty = (below + above) * base_weight * 3.0
                return -total_penalty

            # Dentro dos limites
            if excess <= 0:
                return 0.0  # sem folga (ou inválido), não há "conforto" extra a pontuar

            ideal_start = min_v + (confort * excess)
            d = low - ideal_start  # <0: mais grave; >0: mais agudo

            left_margin = confort * excess
            right_margin = (1.0 - confort) * excess

            if d < 0:
                margin = left_margin
            elif d > 0:
                margin = right_margin
            else:
                return 1.0  # exatamente no ideal

            # Robustez (casos extremos confort=0 ou 1)
            if margin <= 0:
                return 0.0

            score = 1.0 - (abs(d) / margin)
            return max(0.0, min(1.0, score))

        # novos: formações por transposição
        best_fit_by_T: Dict[int, dict] = {}
        possible_fit_by_T: Dict[int, dict] = {}
        not_fit_by_T: Dict[int, list] = {}
        invalid_Ts = set()

        best_T = None
        best_score = -float('inf')
        best_offsets = {}

        t_scores = {}  # T -> soma
        t_has_neg = {}  # T -> bool
        all_T_info = []  # (T, total_score, has_negative, offsets)

        for T in T_values:
            offsets = {}
            total_score = 0.0
            has_negative = False

            for v in voices:
                if v in piece_ranges and piece_ranges[v] != ('', ''):
                    min_i = piece_mins[v]
                    max_i = piece_maxs[v]
                    min_v = voice_base_mins[v]
                    max_v = voice_base_maxs[v]

                    best_score_v = -float('inf')
                    best_O = None

                    # Testa diferentes oitavas
                    for O in range(-4, 5):
                        low = min_i + T + 12 * O
                        high = max_i + T + 12 * O

                        # Calcula o score usando a nova função de conforto
                        score_v = calculate_comfort_score_for_range(low, high, min_v, max_v, confort)

                        # Escolhe a melhor oitava (maior score, desempate por O mais próximo de 0)
                        if (score_v > best_score_v) or (
                                abs(score_v - best_score_v) < 1e-12 and (best_O is None or abs(O) < abs(best_O))
                        ):
                            best_score_v = score_v
                            best_O = O

                    offsets[v] = best_O
                    voice_scores_by_voice[v][T] = best_score_v
                    total_score += best_score_v
                    if best_score_v < 0:
                        has_negative = True
                else:
                    voice_scores_by_voice[v][T] = 0.0

            t_scores[T] = total_score
            t_has_neg[T] = has_negative
            all_T_info.append((T, total_score, has_negative, offsets))

            # chama calculate_best_fit_voices para este T e salva
            bf, nf, pf = self.calculate_best_fit_voices(T)
            best_fit_by_T[T] = deepcopy(bf)
            possible_fit_by_T[T] = deepcopy(pf)
            not_fit_by_T[T] = list(nf)  # nf já é list[str]

            # invalidez: alguém está em best_fit e também em not_fit
            best_names = set()
            for vv, lst in bf.items():
                best_names.update(lst)
            if best_names.intersection(nf):
                invalid_Ts.add(T)

            # Melhor T: prioriza "válido", depois "sem negativos", depois maior soma, depois |T| menor
            if T not in invalid_Ts:
                if best_T is None:
                    best_T, best_score, best_offsets = T, total_score, offsets
                else:
                    curr_key = (True, not has_negative, total_score, -abs(T))
                    best_key = (True, not t_has_neg[best_T], t_scores[best_T], -abs(best_T))
                    if curr_key > best_key:
                        best_T, best_score, best_offsets = T, total_score, offsets

        # ranking debug: remove inválidos
        nonneg = [T for (T, _, has_neg, _) in all_T_info if (not has_neg) and (T not in invalid_Ts)]
        withneg = [T for (T, _, has_neg, _) in all_T_info if has_neg and (T not in invalid_Ts)]

        nonneg_sorted = sorted(nonneg, key=lambda t: (-t_scores[t], abs(t)))
        withneg_sorted = sorted(withneg, key=lambda t: (-t_scores[t], abs(t)))
        debug_ranking_T = nonneg_sorted + withneg_sorted

        if best_T is None:
            new_root, new_mode = original_root, original_mode
        else:
            new_root, new_mode = transpose_key(original_root, original_mode, best_T)

        return {
            "best_T": best_T,
            "best_Os": best_offsets,
            "best_key_root": new_root,
            "best_key_mode": new_mode,
            "voice_scores": voice_scores_by_voice,
            "debug": debug_ranking_T,
            "debug_non_negative": nonneg_sorted,
            "debug_with_negative": withneg_sorted,

            # novos retornos pedidos
            "best_fit": best_fit_by_T,  # {T: {voz: [nomes]}}
            "possible_fit": possible_fit_by_T,  # {T: {voz: [nomes]}}
            "not_fit": not_fit_by_T,  # {T: [nomes]}

            # útil para inspeção (não entra no ranking)
            "invalid_Ts": sorted(invalid_Ts),
        }