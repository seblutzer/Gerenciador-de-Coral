"""
VocalTestManager - Responsável por gerenciar testes vocais
Responsabilidades:
- Iniciar/parar testes vocais
- Gerenciar estado do teste (normal/rápido)
- Controlar marcações (grave/agudo demais)
- Atualizar UI durante o teste
- Processar resultados do teste
"""

import threading
from GeneralFunctions import play_note
from VocalTester import VocalTestCore

class VocalTestManager:
    def __init__(self, ui_callbacks):
        """
        Args:
            ui_callbacks: Dicionário com callbacks da UI:
                - update_ui: função para atualizar elementos visuais
                - on_complete: função chamada ao completar teste
                - update_buttons: função para atualizar estado dos botões
        """
        self.vocal_tester = None
        self.ui_callbacks = ui_callbacks
        self.testing_time = VocalTestCore.DEFAULT_TESTING_TIME
        self.piano_enabled = False  # Piano desabilitado por padrão

    def start_test(self,
                   test_type='normal'):
        """
        Inicia um teste vocal.

        Args:
            test_type: 'normal' ou 'quick'

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester is not None:
            return False, "Um teste já está em andamento!"

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.ui_callbacks['update_ui'],
            complete_callback=self._on_test_complete_internal,
            button_callback=self.ui_callbacks['update_buttons']
        )

        # Ativa piano se habilitado
        if self.piano_enabled:
            self.vocal_tester.enable_piano_window(True)

        if test_type == 'quick':
            threading.Thread(target=self.vocal_tester.start_quick_test, daemon=True).start()
            return True, "Teste rápido iniciado"
        else:
            threading.Thread(target=self.vocal_tester.start_test, daemon=True).start()
            return True, "Teste normal iniciado"

    def stop_test(self
                  ):
        """
        Para o teste vocal em andamento.

        Returns:
            bool: True se havia teste rodando
        """
        if self.vocal_tester:
            self.vocal_tester.stop_test()
            self.vocal_tester = None
            return True
        return False

    def mark_too_low(self
                     ):
        """Marca a nota atual como grave demais."""
        if self.vocal_tester:
            self.vocal_tester.mark_too_low()
            return True
        return False

    def mark_too_high(self
                      ):
        """Marca a nota atual como agudo demais."""
        if self.vocal_tester:
            self.vocal_tester.mark_too_high()
            return True
        return False

    def repeat_current_tone(self
                            ):
        """
        Reproduz o tom atual novamente.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester and hasattr(self.vocal_tester, 'current_playing_frequency'):
            freq = self.vocal_tester.current_playing_frequency
            if freq and freq > 0:
                threading.Thread(
                    target=play_note,
                    args=(freq, 2),
                    daemon=True
                ).start()
                return True, "Reproduzindo tom atual..."
        return False, "Nenhum tom atual para repetir"

    def update_testing_time(self,
                            new_time):
        """
        Atualiza o tempo de teste.

        Args:
            new_time: Novo tempo em segundos (int)
        """
        self.testing_time = new_time
        VocalTestCore.DEFAULT_TESTING_TIME = new_time

        if self.vocal_tester is not None:
            self.vocal_tester.testing_time = new_time

    def update_noise_gate(self,
                          threshold):
        """
        Atualiza o threshold do noise gate.

        Args:
            threshold: Novo threshold (float)
        """
        VocalTestCore.NOISE_GATE_THRESHOLD = threshold

        if self.vocal_tester is not None:
            self.vocal_tester.NOISE_GATE_THRESHOLD = threshold

    def is_testing(self
                   ):
        """Retorna True se há um teste em andamento."""
        return self.vocal_tester is not None

    def _on_test_complete_internal(self,
                                   range_min, range_max):
        """
        Callback interno para processar conclusão do teste.
        Delega para o callback da UI.

        Args:
            range_min: Nota mínima detectada
            range_max: Nota máxima detectada
        """
        # Limpa a instância do teste
        self.vocal_tester = None

        # Chama o callback da UI
        if 'on_complete' in self.ui_callbacks:
            self.ui_callbacks['on_complete'](range_min, range_max)

    def start_pitch_recording(self
                              ):
        """
        Inicia gravação pura de pitch sem teste de notas.

        Returns:
            (sucesso: bool, mensagem: str)
        """
        if self.vocal_tester is not None:
            return False, "Um teste ou gravação já está em andamento!"

        self.vocal_tester = VocalTestCore()
        self.vocal_tester.set_ui_callbacks(
            update_callback=self.ui_callbacks['update_ui'],
            complete_callback=self._on_recording_complete_internal,
            button_callback=self.ui_callbacks['update_buttons']
        )

        # Inicia thread de gravação pura
        threading.Thread(target=self.vocal_tester.run_pitch_recording_only, daemon=True).start()
        return True, "Gravação de pitch iniciada"

    def stop_pitch_recording(self
                             ):
        """
        Para a gravação de pitch e gera o HTML.

        Returns:
            (sucesso: bool, caminho_html: str ou None)
        """
        if self.vocal_tester and hasattr(self.vocal_tester, '_record_pitch'):
            # Para a gravação
            self.vocal_tester.is_testing = False
            self.vocal_tester.is_listening = False

            try:
                filtered_notes, html = self.vocal_tester.export_pitch_log_to_html()

                self.vocal_tester = None

                return filtered_notes, html
            except:
                self.vocal_tester = None
                return False, False
        return False

    def _on_recording_complete_internal(self,
                                        range_min, range_max):
        """
        Callback interno para conclusão de gravação.
        Gravação pura não retorna ranges, então apenas limpa.
        """
        self.vocal_tester = None

    def enable_piano_game(self,
                          enabled=True):
        """
        Ativa/desativa a janela de piano gamificada

        Args:
            enabled: True para ativar, False para desativar
        """
        self.piano_enabled = enabled

        if self.vocal_tester is not None:
            self.vocal_tester.enable_piano_window(enabled)