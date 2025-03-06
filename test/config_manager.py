import os
import configparser
from pathlib import Path

class ConfigManager:
    """
    Classe per gestire la configurazione dell'applicazione Energy Monitor
    """
    def __init__(self, config_file='config.ini'):
        """
        Inizializza il gestore della configurazione
        
        Args:
            config_file (str): Percorso del file di configurazione
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # Carica la configurazione esistente o crea una nuova
        if os.path.exists(config_file):
            self.config.read(config_file)
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """Crea una configurazione predefinita"""
        # Impostazioni FusionSolar
        self.config['CREDENTIALS'] = {
            'USERNAME': '',
            'PASSWORD': '',
            'SUBDOMAIN': '',
            'CAPTCHA_MODEL_PATH': ''
        }
        
        # Impostazioni generali
        self.config['SETTINGS'] = {
            'TIME_INTERVAL': '5',
            'ALARM_ENABLED': 'True',
            'DATA_RETENTION_DAYS': '30',
            'XML_FILE_PATH': os.path.join(os.getcwd(), 'energy_data.xml')
        }
        
        # Impostazioni esportazione
        self.config['EXPORT'] = {
            'AUTO_EXPORT_ENABLED': 'False',
            'AUTO_EXPORT_INTERVAL_HOURS': '24',
            'AUTO_EXPORT_FOLDER': os.getcwd(),
            'AUTO_EXPORT_FORMAT': 'csv'
        }
        
        # Salva la configurazione predefinita
        self.save()
    
    def save(self):
        """Salva la configurazione nel file"""
        with open(self.config_file, 'w') as config_file:
            self.config.write(config_file)
    
    def get(self, section, key, fallback=None):
        """
        Ottiene un valore dalla configurazione
        
        Args:
            section (str): Sezione della configurazione
            key (str): Chiave da ottenere
            fallback: Valore predefinito se la chiave non esiste
            
        Returns:
            Il valore della configurazione o il fallback
        """
        return self.config.get(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=None):
        """Ottiene un valore intero dalla configurazione"""
        return self.config.getint(section, key, fallback=fallback)
    
    def getfloat(self, section, key, fallback=None):
        """Ottiene un valore float dalla configurazione"""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=None):
        """Ottiene un valore booleano dalla configurazione"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def set(self, section, key, value):
        """
        Imposta un valore nella configurazione
        
        Args:
            section (str): Sezione della configurazione
            key (str): Chiave da impostare
            value: Valore da impostare
        """
        if section not in self.config:
            self.config.add_section(section)
        
        self.config.set(section, key, str(value))
    
    def has_section(self, section):
        """Controlla se esiste una sezione"""
        return self.config.has_section(section)
    
    def get_sections(self):
        """Ottiene tutte le sezioni della configurazione"""
        return self.config.sections()
    
    def get_credential(self, key):
        """Ottiene una credenziale dalla configurazione"""
        return self.get('CREDENTIALS', key, '')
    
    def set_credential(self, key, value):
        """Imposta una credenziale nella configurazione"""
        self.set('CREDENTIALS', key, value)
    
    def get_setting(self, key, fallback=None):
        """Ottiene un'impostazione dalla configurazione"""
        return self.get('SETTINGS', key, fallback)
    
    def set_setting(self, key, value):
        """Imposta un'impostazione nella configurazione"""
        self.set('SETTINGS', key, value)
    
    def get_int_setting(self, key, fallback=None):
        """Ottiene un'impostazione intera dalla configurazione"""
        return self.getint('SETTINGS', key, fallback)
    
    def get_bool_setting(self, key, fallback=None):
        """Ottiene un'impostazione booleana dalla configurazione"""
        return self.getboolean('SETTINGS', key, fallback)
    
    def get_export_setting(self, key, fallback=None):
        """Ottiene un'impostazione di esportazione dalla configurazione"""
        return self.get('EXPORT', key, fallback)
    
    def set_export_setting(self, key, value):
        """Imposta un'impostazione di esportazione nella configurazione"""
        self.set('EXPORT', key, value)