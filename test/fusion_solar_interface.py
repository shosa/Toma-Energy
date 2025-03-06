import logging
import socket
import time
from dataclasses import dataclass
from fusion_solar_py.client import FusionSolarClient

logger = logging.getLogger(__name__)

@dataclass
class PowerStatus:
    """Classe per i dati sullo stato di potenza"""
    current_power_kw: float
    status: str
    timestamp: str

class FusionSolarInterface:
    """
    Classe per interfacciarsi con l'API FusionSolar e gestire la connessione
    """
    def __init__(self, config_manager):
        """
        Inizializza l'interfaccia FusionSolar
        
        Args:
            config_manager: Gestore della configurazione
        """
        self.config = config_manager
        self.username = self.config.get_credential('USERNAME')
        self.password = self.config.get_credential('PASSWORD')
        self.subdomain = self.config.get_credential('SUBDOMAIN')
        self.captcha_model_path = self.config.get_credential('CAPTCHA_MODEL_PATH')
        
        self.client = None
        self.initialize_client()
    
    def initialize_client(self):
        """Inizializza il client FusionSolar"""
        if not all([self.username, self.password]):
            logger.warning("Credenziali mancanti o incomplete")
            return
        
        try:
            self.client = FusionSolarClient(
                self.username, 
                self.password,
                captcha_model_path=self.captcha_model_path,
                huawei_subdomain=self.subdomain
            )
            logger.info("Client FusionSolar inizializzato con successo")
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del client FusionSolar: {e}")
            self.client = None
    
    def update_credentials(self, username, password, subdomain, captcha_model_path):
        """
        Aggiorna le credenziali e reinizializza il client
        
        Args:
            username: Nome utente FusionSolar
            password: Password FusionSolar
            subdomain: Sottodominio Huawei
            captcha_model_path: Percorso del modello per captcha
            
        Returns:
            bool: True se l'aggiornamento è riuscito, False altrimenti
        """
        # Salva le nuove credenziali
        self.username = username
        self.password = password
        self.subdomain = subdomain
        self.captcha_model_path = captcha_model_path
        
        # Aggiorna le credenziali nella configurazione
        self.config.set_credential('USERNAME', username)
        self.config.set_credential('PASSWORD', password)
        self.config.set_credential('SUBDOMAIN', subdomain)
        self.config.set_credential('CAPTCHA_MODEL_PATH', captcha_model_path)
        self.config.save()
        
        # Reinizializza il client
        try:
            self.client = FusionSolarClient(
                self.username, 
                self.password,
                captcha_model_path=self.captcha_model_path,
                huawei_subdomain=self.subdomain
            )
            logger.info("Credenziali aggiornate e client reinizializzato con successo")
            return True
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento delle credenziali: {e}")
            return False
    
    def is_session_valid(self):
        """
        Verifica se la sessione è ancora valida
        
        Returns:
            bool: True se la sessione è valida, False altrimenti
        """
        if not self.client:
            return False
            
        try:
            # Prima verifichiamo se c'è connessione internet
            socket.create_connection(("www.google.com", 80), timeout=2)
            
            # Poi verifichiamo se la sessione è valida
            test_status = self.client.get_power_status()
            return True  # Se la richiesta va a buon fine, la sessione è valida
        except socket.error:
            logger.warning("Nessuna connessione internet disponibile")
            return False
        except Exception as e:
            logger.warning(f"Sessione scaduta o errore API: {e}")
            return False
    
    def renew_session(self):
        """
        Rinnova la sessione FusionSolar
        
        Returns:
            bool: True se il rinnovo è riuscito, False altrimenti
        """
        if not all([self.username, self.password]):
            logger.warning("Impossibile rinnovare la sessione: credenziali mancanti")
            return False
            
        try:
            logger.info("Rinnovo della sessione FusionSolar in corso...")
            self.client = FusionSolarClient(
                self.username, 
                self.password,
                captcha_model_path=self.captcha_model_path,
                huawei_subdomain=self.subdomain
            )
            logger.info("Sessione rinnovata con successo")
            return True
        except Exception as e:
            logger.error(f"Errore nel rinnovo della sessione: {e}")
            return False
    
    def get_power_status(self):
        """
        Ottiene lo stato di potenza attuale dall'impianto
        
        Returns:
            PowerStatus: Oggetto con i dati di potenza o None in caso di errore
        """
        if not self.client:
            logger.warning("Client FusionSolar non inizializzato")
            return None
            
        try:
            # Verifica se la sessione è ancora valida, altrimenti rinnovala
            if not self.is_session_valid():
                if not self.renew_session():
                    logger.error("Impossibile rinnovare la sessione")
                    return None
            
            # Ottieni lo stato di potenza
            stats = self.client.get_power_status()
            current_power = stats.current_power_kw
            status = "Operativo" if current_power > 0 else "Nessuna Produzione"
            timestamp = time.strftime('%H:%M:%S')
            
            return PowerStatus(
                current_power_kw=current_power,
                status=status,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Errore nell'ottenimento dello stato di potenza: {e}")
            return None
    
    def get_plant_info(self):
        """
        Ottiene informazioni sull'impianto
        
        Returns:
            dict: Dati dell'impianto o None in caso di errore
        """
        if not self.client:
            logger.warning("Client FusionSolar non inizializzato")
            return None
            
        try:
            # Verifica se la sessione è ancora valida, altrimenti rinnovala
            if not self.is_session_valid():
                if not self.renew_session():
                    logger.error("Impossibile rinnovare la sessione")
                    return None
            
            # Ottieni informazioni sull'impianto
            plant_info = self.client.get_plant_info()
            return plant_info
        except Exception as e:
            logger.error(f"Errore nell'ottenimento delle informazioni sull'impianto: {e}")
            return None