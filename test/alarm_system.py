import logging
import threading
import time
import tkinter as tk
import winsound

logger = logging.getLogger(__name__)

class AlarmSystem:
    """
    Classe per la gestione degli allarmi nell'applicazione
    """
    def __init__(self, root, config_manager):
        """
        Inizializza il sistema di allarme
        
        Args:
            root: La finestra principale tkinter
            config_manager: Gestore della configurazione
        """
        self.root = root
        self.config = config_manager
        self.alarm_active = False
        self.alarm_thread = None
        self.alarm_enabled = self.config.get_bool_setting('ALARM_ENABLED', True)
        
        # Creazione dell'overlay per l'allarme
        self.alarm_overlay = tk.Frame(root, bg="red", width=1200, height=700)
        self.alarm_label = tk.Label(
            self.alarm_overlay, 
            text="!!! ALLARME ATTIVO !!!", 
            font=("Segoe UI", 40, "bold"), 
            fg="white", 
            bg="red"
        )
        self.alarm_label.pack(expand=True)
        
        # Pulsante di reset
        self.reset_button = tk.Button(
            self.alarm_overlay, 
            text="RESET ALLARME", 
            font=("Segoe UI", 12, "bold"), 
            bg="yellow", 
            fg="black",
            command=self.reset_alarm
        )
        self.reset_button.pack(pady=20)
    
    def trigger_alarm(self, reason="Allarme generato"):
        """
        Attiva l'allarme visivo e sonoro
        
        Args:
            reason: Motivo dell'allarme
        """
        if not self.alarm_enabled:
            logger.info(f"Allarme non attivato (disabilitato): {reason}")
            return
        
        if self.alarm_active:
            # Allarme già attivo
            return
        
        logger.warning(f"Attivazione allarme: {reason}")
        self.alarm_active = True
        
        # Mostra l'overlay di allarme
        self.alarm_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.alarm_label.config(text=f"!!! ALLARME ATTIVO !!!\n{reason}")
        
        # Avvia il thread per l'allarme
        if self.alarm_thread is None or not self.alarm_thread.is_alive():
            self.alarm_thread = threading.Thread(target=self.alarm_blink, daemon=True)
            self.alarm_thread.start()
    
    def alarm_blink(self):
        """Funzione per far lampeggiare l'allarme e emettere suoni"""
        blink_count = 0
        while self.alarm_active:
            # Alterna i colori dell'overlay
            self.alarm_overlay.config(bg="red" if self.alarm_overlay.cget("bg") == "black" else "black")
            
            # Emetti un suono
            try:
                winsound.Beep(1000, 500)
            except Exception as e:
                logger.error(f"Errore nell'emissione del suono di allarme: {e}")
            
            # Aumenta il contatore e attendi
            blink_count += 1
            time.sleep(0.5)
            
            # Dopo 20 lampeggi (circa 10 secondi), abbassa il volume dell'allarme
            if blink_count >= 20:
                time.sleep(2.0)  # Attendi più a lungo tra i beep
    
    def reset_alarm(self):
        """Disattiva l'allarme"""
        if not self.alarm_active:
            return
            
        logger.info("Reset allarme")
        self.alarm_active = False
        self.alarm_overlay.place_forget()  # Nascondi l'overlay
    
    def toggle_alarm_enabled(self):
        """
        Attiva/disattiva l'allarme
        
        Returns:
            bool: Nuovo stato dell'allarme (True = attivo, False = disattivo)
        """
        self.alarm_enabled = not self.alarm_enabled
        self.config.set_setting('ALARM_ENABLED', str(self.alarm_enabled))
        self.config.save()
        
        logger.info(f"Allarme {'abilitato' if self.alarm_enabled else 'disabilitato'}")
        return self.alarm_enabled
    
    def is_alarm_enabled(self):
        """
        Verifica se l'allarme è abilitato
        
        Returns:
            bool: True se l'allarme è abilitato, False altrimenti
        """
        return self.alarm_enabled
    
    def is_alarm_active(self):
        """
        Verifica se l'allarme è attivo
        
        Returns:
            bool: True se l'allarme è attivo, False altrimenti
        """
        return self.alarm_active
    
    def simulate_alarm(self):
        """Simula un allarme per testare il sistema"""
        self.trigger_alarm("Simulazione allarme")
        logger.info("Simulazione allarme attivata")