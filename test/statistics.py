import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class StatisticsCalculator:
    """
    Classe per il calcolo delle statistiche dai dati di produzione energetica
    """
    def __init__(self, data_storage):
        """
        Inizializza il calcolatore di statistiche
        
        Args:
            data_storage: Oggetto per il caricamento dei dati
        """
        self.data_storage = data_storage
    
    def calculate_statistics(self, days=30):
        """
        Calcola statistiche dettagliate dai dati memorizzati
        
        Args:
            days: Numero di giorni da considerare
            
        Returns:
            dict: Dizionario con le statistiche calcolate
        """
        try:
            timestamps, power_values = self.data_storage.load_recent_data(days=days)
            
            # Se non ci sono dati, restituisci statistiche vuote
            if not timestamps or not power_values:
                logger.warning("Nessun dato disponibile per il calcolo delle statistiche")
                return {
                    "max_power": 0,
                    "avg_power": 0,
                    "total_energy": 0,
                    "operating_hours": 0,
                    "days_with_data": 0,
                    "best_day": {"date": "N/A", "energy": 0},
                    "monthly_energy": 0,
                    "daily_energy": {}
                }
            
            # Calcola la potenza massima
            max_power = max(power_values)
            max_time = timestamps[power_values.index(max_power)]
            
            # Calcola la potenza media (escludendo i valori zero)
            non_zero_powers = [p for p in power_values if p > 0]
            avg_power = sum(non_zero_powers) / len(non_zero_powers) if non_zero_powers else 0
            
            # Raggruppa per giorno
            daily_data = {}
            for i, dt in enumerate(timestamps):
                day_str = dt.strftime('%Y-%m-%d')
                if day_str not in daily_data:
                    daily_data[day_str] = {"powers": [], "times": []}
                daily_data[day_str]["powers"].append(power_values[i])
                daily_data[day_str]["times"].append(dt)
            
            # Calcola energia giornaliera per ogni giorno
            daily_energy = {}
            for day, data in daily_data.items():
                if len(data["times"]) < 2:
                    continue
                    
                # Ordina i dati per orario
                sorted_data = sorted(zip(data["times"], data["powers"]), key=lambda x: x[0])
                times, powers = zip(*sorted_data)
                
                # Calcola l'energia del giorno (integrale della potenza nel tempo)
                day_energy = 0
                for i in range(1, len(times)):
                    # Calcola il delta tempo in ore
                    delta_hours = (times[i] - times[i-1]).total_seconds() / 3600
                    # Usa la regola del trapezio per l'integrazione
                    avg_power_segment = (powers[i] + powers[i-1]) / 2
                    segment_energy = avg_power_segment * delta_hours
                    day_energy += segment_energy
                
                daily_energy[day] = day_energy
            
            # Trova il giorno migliore
            best_day = {"date": "N/A", "energy": 0}
            if daily_energy:
                best_day_date = max(daily_energy, key=daily_energy.get)
                best_day = {"date": best_day_date, "energy": daily_energy[best_day_date]}
            
            # Calcola l'energia totale
            total_energy = sum(daily_energy.values())
            
            # Calcola le ore di funzionamento (ore con potenza > 0)
            operating_hours = 0
            for i in range(1, len(timestamps)):
                if power_values[i] > 0:
                    delta_hours = (timestamps[i] - timestamps[i-1]).total_seconds() / 3600
                    operating_hours += delta_hours
            
            # Calcola l'energia del mese corrente
            current_month = datetime.now().strftime('%Y-%m')
            monthly_energy = sum(energy for day, energy in daily_energy.items() if day.startswith(current_month))
            
            return {
                "max_power": max_power,
                "max_time": max_time.strftime('%Y-%m-%d %H:%M'),
                "avg_power": avg_power,
                "total_energy": total_energy,
                "operating_hours": operating_hours,
                "days_with_data": len(daily_energy),
                "best_day": best_day,
                "monthly_energy": monthly_energy,
                "daily_energy": daily_energy
            }
        except Exception as e:
            logger.error(f"Errore nel calcolo delle statistiche: {e}")
            return None
    
    def calculate_monthly_data(self):
        """
        Calcola le statistiche mensili
        
        Returns:
            dict: Dizionario con i dati mensili
        """
        try:
            # Carica tutti i dati disponibili
            timestamps, power_values = self.data_storage.load_recent_data(days=9999)
            
            if not timestamps or not power_values:
                return {}
            
            # Raggruppa i dati per mese
            monthly_data = {}
            for i, dt in enumerate(timestamps):
                month_key = dt.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {"powers": [], "times": []}
                monthly_data[month_key]["powers"].append(power_values[i])
                monthly_data[month_key]["times"].append(dt)
            
            # Calcola l'energia mensile
            monthly_energy = {}
            for month, data in monthly_data.items():
                if len(data["times"]) < 2:
                    continue
                    
                # Ordina i dati per orario
                sorted_data = sorted(zip(data["times"], data["powers"]), key=lambda x: x[0])
                times, powers = zip(*sorted_data)
                
                # Calcola l'energia del mese (integrale della potenza nel tempo)
                month_energy = 0
                for i in range(1, len(times)):
                    delta_hours = (times[i] - times[i-1]).total_seconds() / 3600
                    avg_power_segment = (powers[i] + powers[i-1]) / 2
                    segment_energy = avg_power_segment * delta_hours
                    month_energy += segment_energy
                
                monthly_energy[month] = month_energy
            
            return monthly_energy
        except Exception as e:
            logger.error(f"Errore nel calcolo dei dati mensili: {e}")
            return {}
    
    def calculate_daily_energy(self, date_str=None):
        """
        Calcola l'energia prodotta in un giorno specifico
        
        Args:
            date_str: Data in formato '%Y-%m-%d' (default: oggi)
            
        Returns:
            float: Energia giornaliera in kWh
        """
        try:
            # Se non è specificata una data, usa oggi
            if date_str is None:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Carica i dati per quel giorno
            timestamps, power_values = self.data_storage.load_recent_data(days=1)
            
            if not timestamps or not power_values:
                return 0.0
            
            # Filtra solo i dati del giorno specificato
            day_timestamps = [ts for ts in timestamps if ts.strftime('%Y-%m-%d') == date_str]
            day_powers = [power_values[timestamps.index(ts)] for ts in day_timestamps]
            
            if not day_timestamps or len(day_timestamps) < 2:
                return 0.0
            
            # Calcola l'energia del giorno
            energy = 0.0
            for i in range(1, len(day_timestamps)):
                # Calcola il delta tempo in ore
                delta_hours = (day_timestamps[i] - day_timestamps[i-1]).total_seconds() / 3600
                # Usa la regola del trapezio per l'integrazione
                avg_power = (day_powers[i] + day_powers[i-1]) / 2
                segment_energy = avg_power * delta_hours
                energy += segment_energy
            
            return energy
        except Exception as e:
            logger.error(f"Errore nel calcolo dell'energia giornaliera: {e}")
            return 0.0
    
    def calculate_energy_summary(self, days=30):
        """
        Calcola un riepilogo energetico per un periodo
        
        Args:
            days: Numero di giorni da considerare
            
        Returns:
            dict: Dizionario con il riepilogo energetico
        """
        try:
            stats = self.calculate_statistics(days)
            if not stats:
                return None
            
            # Calcola il costo stimato dell'energia (0.20€/kWh come esempio)
            energy_cost_per_kwh = 0.20
            estimated_cost = stats["total_energy"] * energy_cost_per_kwh
            
            # Calcola l'emissione di CO2 evitata (0.4 kg/kWh come esempio)
            co2_per_kwh = 0.4
            co2_avoided = stats["total_energy"] * co2_per_kwh
            
            # Calcola la potenza media giornaliera
            daily_avg_energy = stats["total_energy"] / stats["days_with_data"] if stats["days_with_data"] > 0 else 0
            
            # Calcola l'efficienza stimata
            # Qui si dovrebbe inserire la potenza nominale dell'impianto, ma per ora è un valore fisso
            nominal_power_kw = 10.0  # Esempio
            nominal_daily_production = nominal_power_kw * 5  # Esempio: 5 ore di produzione teorica giornaliera
            efficiency = (daily_avg_energy / nominal_daily_production) * 100 if nominal_daily_production > 0 else 0
            
            return {
                "total_energy_kwh": stats["total_energy"],
                "daily_avg_energy_kwh": daily_avg_energy,
                "estimated_cost_saved": estimated_cost,
                "co2_avoided_kg": co2_avoided,
                "efficiency_percentage": efficiency,
                "start_date": (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
                "end_date": datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.error(f"Errore nel calcolo del riepilogo energetico: {e}")
            return None