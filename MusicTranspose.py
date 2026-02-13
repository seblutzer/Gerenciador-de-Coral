import numpy as np
import librosa
import pretty_midi
from pathlib import Path

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

    def notes_to_midi(self,
                      notation, transpose_semitones=0, instrument_program=0):
        if isinstance(notation, dict):
            bpm = notation.get('bpm', 100)
            normalized_notes = notation.get('notes', [])
        else:
            bpm = 100
            normalized_notes = notation

        pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        piano = pretty_midi.Instrument(program=instrument_program, name="Detected Piano")

        i = 0
        while i < len(normalized_notes):
            current_pitch = normalized_notes[i]['pitch_midi']
            start_time = float(normalized_notes[i]['time'])

            # Encontra o fim do grupo de notas com o mesmo pitch
            j = i + 1
            while j < len(normalized_notes) and normalized_notes[j]['pitch_midi'] == current_pitch:
                j += 1

            # Se há próxima nota, usa seu tempo como end; senão, adiciona 10 segundos
            if j < len(normalized_notes):
                end_time = float(normalized_notes[j]['time'])
            else:
                end_time = start_time + 10

            # Cria a nota agrupada
            midi = int(current_pitch) + int(transpose_semitones)
            if 0 <= midi <= 127:
                vel = 64
                note = pretty_midi.Note(velocity=vel, pitch=int(midi), start=start_time, end=end_time)
                piano.notes.append(note)

            # Avança para o próximo grupo
            i = j

        pm.instruments.append(piano)
        return pm

    def save_midi(self,
                  pm, midi_path):
        pm.write(str(midi_path))

    # -----------------------------
    # Fluxo público
    # -----------------------------

    def _analyze_mp3_to_notes(self,
                              mp3_path: str, sr=22050, fmin=55.0, fmax=2000.0, hop_length=512, frame_length=2048):
        """
        Wrapper que analisa pitch E detecta BPM.
        Retorna (notes, sr, bpm, tempo_info).
        """

        #Carrega o áudio
        y, sr = librosa.load(mp3_path, sr=sr, mono=True)

        #===== DETECÇÃO DE BPM =====
        #Método 1: Usando beat tracking (mais preciso)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bpm, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

        #Tempos dos beats em segundos
        beat_times = librosa.frames_to_time(beats, sr=sr)

        #Método alternativo: librosa.feature.tempogram (mais robusta)
        #Descomente se quiser tentar
        oenv = librosa.onset.onset_strength(y=y, sr=sr)
        tempogram = librosa.feature.tempogram(onset_envelope=oenv, sr=sr)
        bpm = librosa.feature.tempo(onset_envelope=oenv, sr=sr)[0]
        #===== ANÁLISE DE PITCH =====
        f0, voiced_flag, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=frame_length, hop_length=hop_length)

        times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)

        notes = []
        current_midi = None
        onset = None

        for i, freq in enumerate(f0):
            t = times[i]
            if np.isnan(freq):
                if current_midi is not None:
                    hz = librosa.midi_to_hz(current_midi)
                    notes.append({
                        "freq": hz,
                        "time": onset,
                        "pitch_midi": int(current_midi),
                        "note":  librosa.midi_to_note(int(current_midi))
                    })
                    current_midi = None
            else:
                midi = librosa.hz_to_midi(freq)
                if current_midi is None:
                    current_midi = midi
                    onset = t
                else:
                    if abs(midi - current_midi) >= 0.5:
                        hz = librosa.midi_to_hz(current_midi)
                        notes.append({
                            "freq": hz,
                            "time": onset,
                            "pitch_midi": int(current_midi),
                            "note":  librosa.midi_to_note(int(current_midi))
                        })
                        current_midi = midi
                        onset = t

        if current_midi is not None:
            hz = librosa.midi_to_hz(current_midi)
            notes.append({
                "freq": hz,
                "time": onset,
                "pitch_midi": int(current_midi),
                "note":  librosa.midi_to_note(int(current_midi))
            })

        music_notation = {
            'bpm': bpm,
            'notes': notes
        }

        #Organizar informações de tempo
        tempo_info = {
            "bpm": float(bpm),
            "beat_times": beat_times.tolist(),
            "beat_frames": beats.tolist(),
            "confidence": "High" if 60 <= bpm <= 200 else "Low" # BPM razoável
        }

        return music_notation
