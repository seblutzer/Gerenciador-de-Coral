import json
import math
import numpy as np
import librosa
import pretty_midi
from pathlib import Path
from Constants import NOTES_FREQUENCY_HZ

class AudioAnalyzer:
    """
    Encapsula o fluxo de análise de áudio por voz em uma classe.
    Ao chamar process_music(mp3_path, music_name), cria a estrutura
    root/musicas/{music_name} com os arquivos de saída:
      - {music_name}_notes_detected.json
      - {music_name}_normalized.json
      - {music_name}_midi.mid
    """
    def __init__(self, root_dir: str = "root"):
        self.root_dir = Path(root_dir)

    # -----------------------------
    # Helpers (reproduzem o seu pipeline)
    # -----------------------------
    @staticmethod
    def hz_to_midi_round(freq_hz):
        if freq_hz is None or freq_hz <= 0:
            return None
        try:
            midi = int(round(librosa.hz_to_midi(freq_hz)))
            if midi < 0:
                return None
            if midi > 127:
                return 127
            return midi
        except Exception:
            return None

    @staticmethod
    def midi_to_freq_hz(midi):
        if midi is None:
            return None
        try:
            return pretty_midi.note_number_to_hz(int(midi))
        except AttributeError:
            return 440.0 * (2.0 ** ((int(midi) - 69) / 12.0))

    @staticmethod
    def midi_to_name(midi):
        if midi is None:
            return None
        try:
            return pretty_midi.note_number_to_name(int(midi))
        except Exception:
            return None

    @staticmethod
    def save_notes_json(notes, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_notes_json(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def normalize_and_filter_notes(
            detected_notes,
            min_dur=0.1,
            max_gap_merge=2,
            return_extrema=False,
            normalize_population=0.95
    ):
        frames = []
        for n in detected_notes:
            f_hz = float(n.get('frequency_hz')) if 'frequency_hz' in n else None
            t0 = float(n.get('start_sec'))
            dur = float(n.get('duration_sec'))
            midi = AudioAnalyzer.hz_to_midi_round(f_hz)
            freq_norm = AudioAnalyzer.midi_to_freq_hz(midi)
            name = AudioAnalyzer.midi_to_name(midi)

            frames.append({
                'start_sec': t0,
                'duration_sec': max(dur, 0.0),
                'pitch_midi': int(midi) if midi is not None else None,
                'frequency_hz': freq_norm,
                'note_name': name
            })

        frames = [f for f in frames if f['pitch_midi'] is not None]

        # Passo 2: agrupar frames em notas contínuas da mesma pitch
        grouped = []
        current = None  # {'start': ..., 'end': ..., 'midi': ...}
        for f in frames:
            s = float(f['start_sec'])
            e = s + float(f['duration_sec'])
            midi = int(f['pitch_midi'])

            if current is None:
                current = {'start': s, 'end': e, 'midi': midi}
            else:
                if midi == current['midi']:
                    current['end'] = max(current['end'], e)
                else:
                    duration = current['end'] - current['start']
                    if duration >= min_dur:
                        grouped.append({
                            'start_sec': current['start'],
                            'duration_sec': duration,
                            'pitch_midi': int(current['midi']),
                            'frequency_hz': AudioAnalyzer.midi_to_freq_hz(current['midi']),
                            'note_name': AudioAnalyzer.midi_to_name(current['midi'])
                        })
                    current = {'start': s, 'end': e, 'midi': midi}

        if current is not None:
            duration = current['end'] - current['start']
            if duration >= min_dur:
                grouped.append({
                    'start_sec': current['start'],
                    'duration_sec': duration,
                    'pitch_midi': int(current['midi']),
                    'frequency_hz': AudioAnalyzer.midi_to_freq_hz(current['midi']),
                    'note_name': AudioAnalyzer.midi_to_name(current['midi'])
                })

        # Mesclar notas adjacentes da mesma pitch com gaps pequenos
        if not grouped:
            return []

        merged = [grouped[0]]
        for i in range(1, len(grouped)):
            prev = merged[-1]
            cur = grouped[i]
            gap = cur['start_sec'] - (prev['start_sec'] + prev['duration_sec'])
            if cur['pitch_midi'] == prev['pitch_midi'] and gap <= max_gap_merge:
                new_start = prev['start_sec']
                new_end = max(prev['start_sec'] + prev['duration_sec'], cur['start_sec'] + cur['duration_sec'])
                merged[-1] = {
                    'start_sec': new_start,
                    'duration_sec': new_end - new_start,
                    'pitch_midi': int(cur['pitch_midi']),
                    'frequency_hz': AudioAnalyzer.midi_to_freq_hz(cur['pitch_midi']),
                    'note_name': AudioAnalyzer.midi_to_name(cur['pitch_midi'])
                }
            else:
                merged.append(cur)

        final_notes = [m for m in merged if m['duration_sec'] >= min_dur]

        if normalize_population and final_notes:
            freqs = [n['frequency_hz'] for n in final_notes if n.get('frequency_hz') is not None]
            if freqs:
                freqs_sorted = sorted(freqs)

                def percentile(p):
                    if not freqs_sorted:
                        return None
                    idx = int(p * (len(freqs_sorted) - 1))
                    return freqs_sorted[idx]

                lower_p = (1.0 - normalize_population) / 2.0
                upper_p = 1.0 - lower_p
                central_lower = percentile(lower_p)
                central_upper = percentile(upper_p)

                semitone_ratio = 2 ** (1.0 / 12.0)
                four_semitones = semitone_ratio ** 4

                safe_min = None
                safe_max = None
                if central_lower is not None:
                    safe_min = central_lower / four_semitones
                if central_upper is not None:
                    safe_max = central_upper * four_semitones

                MIN_ALLOWED = NOTES_FREQUENCY_HZ['C2']
                MAX_ALLOWED = NOTES_FREQUENCY_HZ['E5']

                if safe_min is not None:
                    safe_min = max(safe_min, MIN_ALLOWED)
                if safe_max is not None:
                    safe_max = min(safe_max, MAX_ALLOWED)

                if safe_min is not None and safe_max is not None:
                    exclused_notes = [n.get('note_name') for n in [
                        n for n in final_notes
                        if not safe_min <= n['frequency_hz'] <= safe_max
                    ]]
                    final_notes = [
                        n for n in final_notes
                        if safe_min <= n['frequency_hz'] <= safe_max
                    ]
                    print(exclused_notes)

        if return_extrema:
            if final_notes:
                lowest_midi = min(n['pitch_midi'] for n in final_notes)
                highest_midi = max(n['pitch_midi'] for n in final_notes)
                extrema = [AudioAnalyzer.midi_to_name(lowest_midi),
                           AudioAnalyzer.midi_to_name(highest_midi)]
            else:
                extrema = None
            return {'notes': final_notes, 'extrema': extrema}
        else:
            return final_notes

    @staticmethod
    def notes_to_midi(normalized_notes, transpose_semitones=0, instrument_program=0):
        pm = pretty_midi.PrettyMIDI()
        piano = pretty_midi.Instrument(program=instrument_program, name="Detected Piano (normalized)")

        for n in (normalized_notes if not isinstance(normalized_notes, dict) else normalized_notes.get('notes', [])):
            midi = int(n['pitch_midi']) + int(transpose_semitones)
            if midi < 0 or midi > 127:
                continue
            start = float(n['start_sec'])
            end = start + float(n['duration_sec'])
            vel = 100
            note = pretty_midi.Note(velocity=vel, pitch=int(midi), start=start, end=end)
            piano.notes.append(note)

        pm.instruments.append(piano)
        return pm

    @staticmethod
    def save_midi(pm, midi_path):
        pm.write(str(midi_path))

    # -----------------------------
    # Novo: geração de HTML de Pitch History
    # -----------------------------
    @staticmethod
    def _generate_pitch_html(final_notes, music_dir: Path, music_name: str):
        """
        Gera um HTML com Pitch History em estilo "step/linha" onde cada nota
        é representada por um segmento horizontal ao longo do tempo.
        Eixo Y mostra as notas (labels vindas de NOTES_FREQUENCY_HZ).
        """
        html_path = music_dir / f"{music_name}_pitch_history.html"

        # Ordem das notas conforme NOTES_FREQUENCY_HZ (preserva ordem ascendente)
        note_order = list(NOTES_FREQUENCY_HZ.keys())
        name_to_index = {name: idx for idx, name in enumerate(note_order)}

        # Construção de pontos: cada nota gera dois pontos (início e fim),
        # e há um ponto adicional na transição para a próxima nota para
        # criar o salto vertical.
        data_points = []
        if isinstance(final_notes, list):
            for i, n in enumerate(final_notes):
                start = float(n.get('start_sec', 0.0))
                dur = float(n.get('duration_sec', 0.0))

                # Obter o nome da nota
                name = n.get('note_name')
                if name is None:
                    midi = n.get('pitch_midi')
                    if midi is not None:
                        name = AudioAnalyzer.midi_to_name(int(midi))

                idx = name_to_index.get(name)
                if idx is None:
                    continue

                end = start + max(dur, 0.0)

                # Segmento da nota atual
                data_points.append({'x': start, 'y': idx})
                data_points.append({'x': end, 'y': idx})

                # Salto vertical para a próxima nota (se houver)
                if i + 1 < len(final_notes):
                    next_n = final_notes[i + 1]
                    next_name = next_n.get('note_name')
                    if next_name is None:
                        m = next_n.get('pitch_midi')
                        if m is not None:
                            next_name = AudioAnalyzer.midi_to_name(int(m))
                    next_idx = name_to_index.get(next_name)
                    if next_idx is not None:
                        data_points.append({'x': end, 'y': next_idx})

        # HTML com Chart.js (CDN)

        html_lines = []
        html_lines.append('<!DOCTYPE html>')
        html_lines.append('<html lang="pt-BR">')
        html_lines.append('<head>')
        html_lines.append('  <meta charset="UTF-8">')
        html_lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_lines.append(f'  <title>Pitch History - {music_name}</title>')
        html_lines.append('  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>')
        html_lines.append('</head>')
        html_lines.append('<body>')
        html_lines.append(f'  <h2>Pitch History: {music_name}</h2>')
        html_lines.append('  <div style="width:100%; height:500px; position: relative;">')
        html_lines.append('    <canvas id="pitchChart" style="width:100%; height:100%;"></canvas>')
        html_lines.append('  </div>')

        # Embarcar variáveis para renderização
        html_lines.append('  <script>')
        html_lines.append('    const NOTE_ORDER = ' + json.dumps(note_order) + ';')
        html_lines.append('    const dataPoints = ' + json.dumps(data_points) + ';')
        html_lines.append('    const ctx = document.getElementById("pitchChart").getContext("2d");')
        html_lines.append("    new Chart(ctx, {")
        html_lines.append("      type: 'line',")
        html_lines.append("      data: {")
        html_lines.append("        datasets: [{")
        html_lines.append("          label: 'Pitch (Note)',")
        html_lines.append("          data: dataPoints,")
        html_lines.append("          borderColor: 'rgb(75, 192, 192)',")
        html_lines.append("          backgroundColor: 'rgba(75,192,192,0.2)',")
        html_lines.append("          fill: false,")
        html_lines.append("          pointRadius: 0,")
        html_lines.append("          lineTension: 0,")
        html_lines.append("          stepped: true")
        html_lines.append("        }]")
        html_lines.append("      },")
        html_lines.append("      options: {")
        html_lines.append("        scales: {")
        html_lines.append(
            "          x: { type: 'linear', position: 'bottom', title: { display: true, text: 'Tempo (s)' }, min: 0 },")
        html_lines.append("          y: {")
        html_lines.append("            type: 'linear',")
        html_lines.append("            min: 0,")
        html_lines.append("            max: " + str(len(note_order) - 1) + ",")
        html_lines.append("            ticks: {")
        html_lines.append("              callback: function(value) {")
        html_lines.append("                const idx = Math.round(value);")
        html_lines.append("                return (idx >= 0 && idx < NOTE_ORDER.length) ? NOTE_ORDER[idx] : '';")
        html_lines.append("              }")
        html_lines.append("            },")
        html_lines.append("            title: { display: true, text: 'Nota' }")
        html_lines.append("          }")
        html_lines.append("        },")
        html_lines.append("        responsive: true,")
        html_lines.append("        maintainAspectRatio: false,")
        html_lines.append("        plugins: { legend: { display: false } }")
        html_lines.append("      }")
        html_lines.append("    });")
        html_lines.append("  </script>")
        html_lines.append('</body>')
        html_lines.append('</html>')

        html_content = "\n".join(html_lines)

        # Escreve o HTML
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(html_path)

    # -----------------------------
    # Fluxo público
    # -----------------------------
    def process_music(self, mp3_path: str, music_name: str):
        """
        Processa um mp3 e salva output em root/musicas/{music_name}/
        Retorna um dict com caminhos e informações de alcance da voz.
        """
        mp3_path = Path(mp3_path)
        # 1) Análise para notas detectadas
        notes, sr = self._analyze_mp3_to_notes(str(mp3_path))
        # 2) Normalização/Filtragem
        normalized = self.normalize_and_filter_notes(notes, return_extrema=True)

        final_notes = normalized.get('notes', []) if isinstance(normalized, dict) else normalized
        # 3) Determinar min/max da voz selecionada a partir dos resultados
        if final_notes:
            min_hz = min(
                n['frequency_hz'] for n in final_notes if 'frequency_hz' in n and n['frequency_hz'] is not None)
            max_hz = max(
                n['frequency_hz'] for n in final_notes if 'frequency_hz' in n and n['frequency_hz'] is not None)
        else:
            min_hz, max_hz = None, None

        # 4) Preparar diretório de saída
        music_dir = self.root_dir / "musicas" / music_name
        music_dir.mkdir(parents=True, exist_ok=True)

        # 5) Salvar outputs
        notes_path = music_dir / f"{music_name}_notes_detected.json"
        with open(notes_path, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

        normalized_path = music_dir / f"{music_name}_normalized.json"
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)

        pm = self.notes_to_midi(normalized)
        midi_path = music_dir / f"{music_name}_midi.mid"
        self.save_midi(pm, midi_path)

        # Novo: gerar HTML de Pitch History (Pitch Line)
        pitch_html_path = self._generate_pitch_html(final_notes, music_dir, music_name)

        return {
            "notes_detected_path": str(notes_path),
            "normalized_path": str(normalized_path),
            "midi_path": str(midi_path),
            "pitch_history_html_path": pitch_html_path,
            "voice_min_hz": min_hz,
            "voice_max_hz": max_hz,
            "extrema": normalized.get('extrema') if isinstance(normalized, dict) else None
        }

    def _analyze_mp3_to_notes(self, mp3_path: str, sr=22050, fmin=55.0, fmax=2000.0,
                              hop_length=512, frame_length=2048):
        """
        Wrapper próprio que reproduz seu fluxo de análise original.
        Retorna (notes, sr).
        """
        # Carrega o áudio
        y, sr = librosa.load(mp3_path, sr=sr, mono=True)

        # Estima pitch por frame (fundamental)
        f0, voiced_flag, _ = librosa.pyin(y,
                                          fmin=fmin,
                                          fmax=fmax,
                                          sr=sr,
                                          frame_length=frame_length,
                                          hop_length=hop_length)

        times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)

        notes = []
        current_midi = None
        onset = None

        for i, freq in enumerate(f0):
            t = times[i]
            if np.isnan(freq):
                if current_midi is not None:
                    duration = t - onset
                    hz = librosa.midi_to_hz(current_midi)
                    notes.append({
                        "frequency_hz": hz,
                        "start_sec": onset,
                        "duration_sec": duration,
                        "pitch_midi": int(current_midi)
                    })
                    current_midi = None
            else:
                midi = librosa.hz_to_midi(freq)
                if current_midi is None:
                    current_midi = midi
                    onset = t
                else:
                    if abs(midi - current_midi) >= 0.5:
                        duration = t - onset
                        hz = librosa.midi_to_hz(current_midi)
                        notes.append({
                            "frequency_hz": hz,
                            "start_sec": onset,
                            "duration_sec": duration,
                            "pitch_midi": int(current_midi)
                        })
                        current_midi = midi
                        onset = t

        if current_midi is not None:
            duration = times[-1] - onset
            hz = librosa.midi_to_hz(current_midi)
            notes.append({
                "frequency_hz": hz,
                "start_sec": onset,
                "duration_sec": duration,
                "pitch_midi": int(current_midi)
            })

        return notes, sr
