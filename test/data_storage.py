import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DataStorage:
    """
    Classe per gestire il salvataggio e il caricamento dei dati energetici in formato XML
    """
    def __init__(self, config_manager):
        """
        Inizializza il gestore dei dati
        
        Args:
            config_manager: Gestore della configurazione
        """
        self.config = config_manager
        self.xml_file_path = self.config.get_setting('XML_FILE_PATH', 'energy_data.xml')
        self.retention_days = self.config.get_int_setting('DATA_RETENTION_DAYS', 30)
        
        # Inizializza il file XML se non esiste
        self.initialize_xml_file()
    
    def initialize_xml_file(self):
        """
        Inizializza il file XML se non esiste o carica quello esistente
        """
        if not os.path.exists(self.xml_file_path):
            root = ET.Element("energy_data")
            tree = ET.ElementTree(root)
            tree.write(self.xml_file_path)
            logger.info(f"Creato nuovo file XML: {self.xml_file_path}")
            return tree
        else:
            try:
                tree = ET.parse(self.xml_file_path)
                # Pulizia dati più vecchi del periodo di conservazione
                self.clean_old_data(tree)
                logger.info(f"Caricato file XML esistente: {self.xml_file_path}")
                return tree
            except ET.ParseError:
                # Fallback in caso di XML corrotto
                logger.error(f"File XML corrotto: {self.xml_file_path}, creazione nuovo file")
                root = ET.Element("energy_data")
                tree = ET.ElementTree(root)
                tree.write(self.xml_file_path)
                return tree
    
    def clean_old_data(self, tree):
        """
        Rimuove dati più vecchi del periodo di conservazione
        
        Args:
            tree: Albero XML da pulire
        """
        root = tree.getroot()
        today = datetime.now()
        retention_date = today - timedelta(days=self.retention_days)
        retention_str = retention_date.strftime('%Y-%m-%d')
        
        # Trova tutti i giorni più vecchi del periodo di conservazione
        for day_elem in root.findall("./day"):
            day_date = day_elem.get('date')
            if day_date < retention_str:
                root.remove(day_elem)
                logger.debug(f"Rimossi dati per il giorno: {day_date}")
        
        tree.write(self.xml_file_path)
    
    def save_power_data(self, timestamp, power_value):
        """
        Salva i dati di potenza nel file XML
        
        Args:
            timestamp: Timestamp della lettura (stringa in formato %H:%M:%S)
            power_value: Valore della potenza in kW
        """
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()
            
            # Estrai data e ora dal timestamp
            dt = datetime.strptime(timestamp, '%H:%M:%S')
            today = datetime.now()
            dt = datetime(today.year, today.month, today.day, dt.hour, dt.minute, dt.second)
            date_str = dt.strftime('%Y-%m-%d')
            time_str = dt.strftime('%H:%M:%S')
            
            # Cerca l'elemento del giorno o crealo se non esiste
            day_elem = None
            for elem in root.findall(f"./day[@date='{date_str}']"):
                day_elem = elem
                break
            
            if day_elem is None:
                day_elem = ET.SubElement(root, "day")
                day_elem.set("date", date_str)
            
            # Aggiungi il nuovo valore di potenza
            power_elem = ET.SubElement(day_elem, "power")
            power_elem.set("time", time_str)
            power_elem.set("value", str(power_value))
            
            # Salva il file XML
            tree.write(self.xml_file_path)
            logger.debug(f"Salvato dato: {date_str} {time_str} - {power_value} kW")
            
        except Exception as e:
            logger.error(f"Errore nel salvataggio dati XML: {e}")
    
    def load_recent_data(self, days=1):
        """
        Carica i dati più recenti dal file XML
        
        Args:
            days: Numero di giorni da caricare (default: 1 - solo oggi)
            
        Returns:
            tuple: (timestamps, power_values) - Liste di timestamp e valori di potenza
        """
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()
            
            timestamps = []
            powers = []
            
            # Calcola le date per il periodo richiesto
            today = datetime.now()
            start_date = today - timedelta(days=days-1)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            # Estrai i dati per il periodo specificato
            for day_elem in root.findall("./day"):
                day_date = day_elem.get('date')
                if day_date >= start_date_str:
                    for power_elem in day_elem.findall("./power"):
                        time_str = power_elem.get('time')
                        power_value = float(power_elem.get('value'))
                        
                        # Crea un timestamp completo
                        dt = datetime.strptime(f"{day_date} {time_str}", '%Y-%m-%d %H:%M:%S')
                        timestamps.append(dt)
                        powers.append(power_value)
            
            # Ordina i dati per timestamp
            sorted_data = sorted(zip(timestamps, powers), key=lambda x: x[0])
            if sorted_data:
                timestamps, powers = zip(*sorted_data)
            else:
                timestamps, powers = [], []
                
            logger.debug(f"Caricati {len(timestamps)} punti dati degli ultimi {days} giorni")
            return timestamps, powers
            
        except Exception as e:
            logger.error(f"Errore nel caricamento dati XML: {e}")
            return [], []
    
    def export_to_csv(self, export_path, days=None):
        """
        Esporta i dati in formato CSV
        
        Args:
            export_path: Percorso del file CSV di output
            days: Numero di giorni da esportare (None = tutti)
            
        Returns:
            bool: True se l'esportazione è riuscita, False altrimenti
        """
        try:
            # Carica tutti i dati o quelli per il periodo specificato
            timestamps, power_values = self.load_recent_data(days=days or 9999)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write("Timestamp,Potenza (kW)\n")
                for i in range(len(timestamps)):
                    f.write(f"{timestamps[i].strftime('%Y-%m-%d %H:%M:%S')},{power_values[i]}\n")
            
            logger.info(f"Dati esportati in CSV: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'esportazione CSV: {e}")
            return False
    
    def export_to_xml(self, export_path):
        """
        Esporta i dati in formato XML (copia del file dati originale)
        
        Args:
            export_path: Percorso del file XML di output
            
        Returns:
            bool: True se l'esportazione è riuscita, False altrimenti
        """
        try:
            import shutil
            shutil.copy2(self.xml_file_path, export_path)
            logger.info(f"Dati esportati in XML: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'esportazione XML: {e}")
            return False
    
    def update_retention_period(self, days):
        """
        Aggiorna il periodo di conservazione dei dati e pulisce i dati vecchi
        
        Args:
            days: Nuovo periodo di conservazione in giorni
        """
        self.retention_days = days
        self.config.set_setting('DATA_RETENTION_DAYS', days)
        tree = ET.parse(self.xml_file_path)
        self.clean_old_data(tree)
        logger.info(f"Periodo di conservazione dati aggiornato a {days} giorni")
    
    def update_xml_file_path(self, path):
        """
        Aggiorna il percorso del file XML
        
        Args:
            path: Nuovo percorso del file XML
        """
        # Se il file attuale esiste, copialo nel nuovo percorso
        if os.path.exists(self.xml_file_path) and self.xml_file_path != path:
            import shutil
            try:
                shutil.copy2(self.xml_file_path, path)
                logger.info(f"File XML copiato da {self.xml_file_path} a {path}")
            except Exception as e:
                logger.error(f"Errore nella copia del file XML: {e}")
        
        self.xml_file_path = path
        self.config.set_setting('XML_FILE_PATH', path)
        logger.info(f"Percorso file XML aggiornato a {path}")
        
        # Inizializza il nuovo file se non esiste
        self.initialize_xml_file()