import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import sys
import os
import subprocess
import winsound
import configparser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from fusion_solar_py.client import FusionSolarClient
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import socket
from matplotlib.backend_bases import MouseButton
import mplcursors

# Impostazione tema moderno
plt.style.use('ggplot')

# Caricamento configurazioni
config = configparser.ConfigParser()
config.read('config.ini')

# Configurazioni di default se non esistono
if not os.path.exists('config.ini'):
    config['CREDENTIALS'] = {
        'USERNAME': '',
        'PASSWORD': '',
        'SUBDOMAIN': '',
        'CAPTCHA_MODEL_PATH': ''
    }
    config['SETTINGS'] = {
        'TIME_INTERVAL': '5',
        'ALARM_ENABLED': 'True',
        'DATA_RETENTION_DAYS': '30'
    }
    config['EXPORT'] = {
        'AUTO_EXPORT_ENABLED': 'False',
        'AUTO_EXPORT_INTERVAL_HOURS': '24',
        'AUTO_EXPORT_FOLDER': os.getcwd()
    }
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

# Recupero delle credenziali e impostazioni
USERNAME = config.get('CREDENTIALS', 'USERNAME', fallback='')
PASSWORD = config.get('CREDENTIALS', 'PASSWORD', fallback='')
SUBDOMAIN = config.get('CREDENTIALS', 'SUBDOMAIN', fallback='')
CAPTCHA_MODEL_PATH = config.get('CREDENTIALS', 'CAPTCHA_MODEL_PATH', fallback='')
INTERVAL = config.getint('SETTINGS', 'TIME_INTERVAL', fallback=5)
ALARM_ENABLED = config.getboolean('SETTINGS', 'ALARM_ENABLED', fallback=True)
DATA_RETENTION_DAYS = config.getint('SETTINGS', 'DATA_RETENTION_DAYS', fallback=30)
XML_FILE_PATH = config.get('SETTINGS', 'XML_FILE_PATH', fallback='energy_data.xml')

def save_config():
    """Salva le configurazioni nel file config.ini"""
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

# Inizializzazione client FusionSolar
try:
    client = FusionSolarClient(
        USERNAME, PASSWORD,
        captcha_model_path=CAPTCHA_MODEL_PATH,
        huawei_subdomain=SUBDOMAIN
    )
except Exception as e:
    print(f"Errore nell'inizializzazione del client: {e}")
    client = None

# ===== FUNZIONI PER LA GESTIONE DEI DATI XML =====

def initialize_xml_file():
    """
    Inizializza il file XML se non esiste o carica quello esistente
    """
    if not os.path.exists(XML_FILE_PATH):
        root = ET.Element("energy_data")
        tree = ET.ElementTree(root)
        tree.write(XML_FILE_PATH)
        return tree
    else:
        try:
            tree = ET.parse(XML_FILE_PATH)
            # Pulizia dati più vecchi del periodo di conservazione
            clean_old_data(tree)
            return tree
        except ET.ParseError:
            # Fallback in caso di XML corrotto
            root = ET.Element("energy_data")
            tree = ET.ElementTree(root)
            tree.write(XML_FILE_PATH)
            return tree

def clean_old_data(tree):
    """
    Rimuove dati più vecchi del periodo di conservazione
    """
    root = tree.getroot()
    today = datetime.now()
    retention_date = today - timedelta(days=DATA_RETENTION_DAYS)
    retention_str = retention_date.strftime('%Y-%m-%d')
    
    # Trova tutti i giorni più vecchi del periodo di conservazione
    for day_elem in root.findall("./day"):
        day_date = day_elem.get('date')
        if day_date < retention_str:
            root.remove(day_elem)
    
    tree.write(XML_FILE_PATH)

def save_power_data(timestamp, power_value):
    """
    Salva i dati di potenza nel file XML
    """
    try:
        tree = ET.parse(XML_FILE_PATH)
        root = tree.getroot()
        
        # Estrai data e ora dal timestamp
        dt = datetime.strptime(timestamp, '%H:%M:%S')
        today = datetime.now()
        dt = datetime(today.year, today.month, today.day, dt.hour, dt.minute, dt.second)
        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M:%S')
        
        # Cerca l'elemento del giorno o crealo se non esiste
        day_elem = None
        for elem in root.findall("./day[@date='{}']".format(date_str)):
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
        tree.write(XML_FILE_PATH)
    except Exception as e:
        print(f"Errore nel salvataggio dati XML: {e}")

def load_recent_data(days=1):
    """
    Carica i dati più recenti dal file XML
    days: numero di giorni da caricare (default: 1 - solo oggi)
    """
    try:
        tree = ET.parse(XML_FILE_PATH)
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
            
        return timestamps, powers
    except Exception as e:
        print(f"Errore nel caricamento dati XML: {e}")
        return [], []

# ===== FUNZIONI STATISTICHE =====

def calculate_statistics(days=30):
    """
    Calcola statistiche dettagliate dai dati memorizzati
    """
    try:
        timestamps, power_values = load_recent_data(days=days)
        
        if not timestamps or not power_values:
            return {
                "max_power": 0,
                "avg_power": 0,
                "total_energy": 0,
                "operating_hours": 0,
                "days_with_data": 0,
                "best_day": {"date": "N/A", "energy": 0},
                "monthly_energy": 0
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
        print(f"Errore nel calcolo delle statistiche: {e}")
        return None

# ===== SISTEMA DI ALLARME =====

# Variabile per l'allarme
alarm_active = False

def trigger_alarm():
    """Attiva l'allarme visivo e sonoro"""
    global alarm_active
    alarm_active = True
    
    # Mostra l'overlay di allarme
    alarm_overlay.place(x=0, y=0, relwidth=1, relheight=1)
    
    # Avvia il thread per l'allarme
    threading.Thread(target=alarm_blink, daemon=True).start()

def alarm_blink():
    """Funzione per far lampeggiare l'allarme e emettere suoni"""
    blink_count = 0
    while alarm_active:
        # Alterna i colori dell'overlay
        alarm_overlay.config(bg="red" if alarm_overlay.cget("bg") == "black" else "black")
        
        # Emetti un suono
        winsound.Beep(1000, 500)
        
        # Aumenta il contatore e attendi
        blink_count += 1
        time.sleep(0.5)
        
        # Dopo 20 lampeggi (circa 10 secondi), abbassa il volume dell'allarme
        if blink_count >= 20:
            time.sleep(2.0)  # Attendi più a lungo tra i beep

def reset_alarm():
    """Disattiva l'allarme"""
    global alarm_active
    alarm_active = False
    alarm_overlay.place_forget()  # Nascondi l'overlay

# ===== CONNESSIONE CLIENT =====

def is_session_valid():
    """
    Funzione per verificare se la sessione FusionSolar è ancora attiva.
    """
    try:
        # Prima verifichiamo se c'è connessione internet
        socket.create_connection(("www.google.com", 80), timeout=2)
        
        # Poi verifichiamo se la sessione è valida
        test_status = client.get_power_status()
        return True  # Se la richiesta va a buon fine, la sessione è valida
    except socket.error:
        print("Nessuna connessione internet disponibile")
        return False
    except Exception as e:
        print(f"Sessione scaduta o errore API: {e}")
        return False  # Se c'è un errore, potrebbe essere necessario rieffettuare il login

def renew_session():
    """
    Funzione per effettuare nuovamente il login in caso di sessione scaduta.
    """
    global client
    try:
        print("Rinnovo della sessione FusionSolar...")
        client = FusionSolarClient(
            USERNAME, PASSWORD,
            captcha_model_path=CAPTCHA_MODEL_PATH,
            huawei_subdomain=SUBDOMAIN
        )
        print("Sessione rinnovata con successo!")
        return True
    except Exception as e:
        print(f"Errore nel rinnovo della sessione: {e}")
        return False

# ===== FUNZIONI PER LE FINESTRE E VISUALIZZAZIONI =====

def open_settings():
    """Apre la finestra delle impostazioni"""
    settings_window = tk.Toplevel(root)
    settings_window.title("Impostazioni")
    settings_window.geometry("800x600")
    settings_window.configure(bg=COLOR_BG)
    settings_window.grab_set()  # Modalità modale
    
    # Frame principale
    settings_frame = ttk.Frame(settings_window, style='Card.TFrame')
    settings_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Titolo
    ttk.Label(settings_frame, text="IMPOSTAZIONI", style='Title.TLabel').pack(pady=10)
    
    # Notebook per le schede
    notebook = ttk.Notebook(settings_frame)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    
    # ===== Scheda Allarmi =====
    alarm_tab = ttk.Frame(notebook, style='Card.TFrame')
    notebook.add(alarm_tab, text="Allarmi")
    
    # Impostazione allarme
    ttk.Label(alarm_tab, text="Allarme per produzione zero", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(10, 5))
    
    def toggle_alarm():
        global ALARM_ENABLED
        ALARM_ENABLED = not ALARM_ENABLED
        config.set('SETTINGS', 'ALARM_ENABLED', str(ALARM_ENABLED))
        save_config()
        log_message(f"MODIFICATE IMPOSTAZIONI - Allarme: {'Attivo' if ALARM_ENABLED else 'Disattivo'}")
        alarm_toggle_btn.config(text="Attivo" if ALARM_ENABLED else "Disattivo", style='Success.TButton' if ALARM_ENABLED else 'Warning.TButton')
    
    alarm_toggle_btn = ttk.Button(alarm_tab, text="Attivo" if ALARM_ENABLED else "Disattivo", 
                                style='Success.TButton' if ALARM_ENABLED else 'Warning.TButton', command=toggle_alarm)
    alarm_toggle_btn.pack(anchor="w", padx=10, pady=5)
    
    ttk.Button(alarm_tab, text="Simula Allarme", style='Warning.TButton', command=trigger_alarm).pack(anchor="w", padx=10, pady=5)
    
    # ===== Scheda Aggiornamento =====
    update_tab = ttk.Frame(notebook, style='Card.TFrame')
    notebook.add(update_tab, text="Aggiornamento")
    
    # Impostazione intervallo aggiornamento
    ttk.Label(update_tab, text="Intervallo di aggiornamento", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(10, 5))
    
    interval_var = tk.IntVar(value=INTERVAL)
    ttk.Label(update_tab, text="Secondi tra gli aggiornamenti:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    
    interval_slider = ttk.Scale(update_tab, from_=1, to=60, orient="horizontal", 
                              variable=interval_var)
    interval_slider.pack(fill="x", padx=10, pady=5)
    
    # Etichetta per il valore attuale
    interval_value_label = ttk.Label(update_tab, text=f"{interval_var.get()} sec", style='TLabel')
    interval_value_label.pack(anchor="w", padx=10, pady=5)
    
    # Aggiorna l'etichetta quando il valore cambia
    def update_interval_label(*args):
        interval_value_label.config(text=f"{interval_var.get()} sec")
    
    interval_var.trace_add("write", update_interval_label)
    
    def save_interval():
        global INTERVAL
        INTERVAL = interval_var.get()
        config.set('SETTINGS', 'TIME_INTERVAL', str(INTERVAL))
        save_config()
        log_message(f"MODIFICATE IMPOSTAZIONI - Intervallo: {INTERVAL} secondi")
    
    ttk.Button(update_tab, text="Salva Intervallo", style='Success.TButton', 
              command=save_interval).pack(anchor="w", padx=10, pady=10)
    
    # ===== Scheda Dati =====
    data_tab = ttk.Frame(notebook, style='Card.TFrame')
    notebook.add(data_tab, text="Dati")
    
    # Impostazione conservazione dati
    ttk.Label(data_tab, text="Conservazione Dati", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(10, 5))
    
    retention_var = tk.IntVar(value=DATA_RETENTION_DAYS)
    ttk.Label(data_tab, text="Giorni di conservazione dati:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    
    retention_frame = ttk.Frame(data_tab, style='Card.TFrame')
    retention_frame.pack(fill="x", padx=10, pady=5)
    
    retention_spinbox = ttk.Spinbox(retention_frame, from_=7, to=365, textvariable=retention_var, width=5)
    retention_spinbox.pack(side="left", padx=5)
    
    ttk.Label(retention_frame, text="giorni", style='TLabel').pack(side="left", padx=5)
    
    def save_retention():
        global DATA_RETENTION_DAYS
        DATA_RETENTION_DAYS = retention_var.get()
        config.set('SETTINGS', 'DATA_RETENTION_DAYS', str(DATA_RETENTION_DAYS))
        save_config()
        clean_old_data(xml_tree)
        log_message(f"MODIFICATE IMPOSTAZIONI - Conservazione dati: {DATA_RETENTION_DAYS} giorni")
    
    ttk.Button(data_tab, text="Salva Impostazione", style='Success.TButton', 
              command=save_retention).pack(anchor="w", padx=10, pady=10)
    
    # Percorso file XML
    ttk.Label(data_tab, text="Percorso file dati XML:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    
    xml_path_var = tk.StringVar(value=XML_FILE_PATH)
    xml_path_entry = ttk.Entry(data_tab, textvariable=xml_path_var, width=40)
    xml_path_entry.pack(fill="x", padx=10, pady=5)
    
    def browse_xml_path():
        filename = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(XML_FILE_PATH),
            title="Seleziona percorso file XML",
            defaultextension=".xml",
            filetypes=[("File XML", "*.xml")]
        )
        if filename:
            xml_path_var.set(filename)
    
    def save_xml_path():
        global XML_FILE_PATH
        XML_FILE_PATH = xml_path_var.get()
        config.set('SETTINGS', 'XML_FILE_PATH', XML_FILE_PATH)
        save_config()
        log_message(f"MODIFICATE IMPOSTAZIONI - Percorso file: {XML_FILE_PATH}")
    
    xml_buttons_frame = ttk.Frame(data_tab, style='Card.TFrame')
    xml_buttons_frame.pack(fill="x", padx=10, pady=5)
    
    ttk.Button(xml_buttons_frame, text="Sfoglia", command=browse_xml_path).pack(side="left", padx=5)
    ttk.Button(xml_buttons_frame, text="Salva Percorso", style='Success.TButton', command=save_xml_path).pack(side="left", padx=5)
    
    # ===== Scheda Connessione =====
    conn_tab = ttk.Frame(notebook, style='Card.TFrame')
    notebook.add(conn_tab, text="Connessione")
    
    # Credenziali FusionSolar
    ttk.Label(conn_tab, text="Credenziali FusionSolar", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(10, 5))
    
    # Username
    ttk.Label(conn_tab, text="Username:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    username_var = tk.StringVar(value=USERNAME)
    username_entry = ttk.Entry(conn_tab, textvariable=username_var, width=30)
    username_entry.pack(fill="x", padx=10, pady=5)
    
    # Password
    ttk.Label(conn_tab, text="Password:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    password_var = tk.StringVar(value=PASSWORD)
    password_entry = ttk.Entry(conn_tab, textvariable=password_var, width=30, show="*")
    password_entry.pack(fill="x", padx=10, pady=5)
    
    # Subdomain
    ttk.Label(conn_tab, text="Subdomain:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    subdomain_var = tk.StringVar(value=SUBDOMAIN)
    subdomain_entry = ttk.Entry(conn_tab, textvariable=subdomain_var, width=30)
    subdomain_entry.pack(fill="x", padx=10, pady=5)
    
    # Captcha model path
    ttk.Label(conn_tab, text="Percorso modello captcha:", style='TLabel').pack(anchor="w", padx=10, pady=5)
    captcha_var = tk.StringVar(value=CAPTCHA_MODEL_PATH)
    captcha_entry = ttk.Entry(conn_tab, textvariable=captcha_var, width=30)
    captcha_entry.pack(fill="x", padx=10, pady=5)
    
    def save_credentials():
        global USERNAME, PASSWORD, SUBDOMAIN, CAPTCHA_MODEL_PATH, client
        
        USERNAME = username_var.get()
        PASSWORD = password_var.get()
        SUBDOMAIN = subdomain_var.get()
        CAPTCHA_MODEL_PATH = captcha_var.get()
        
        # Salva nel config
        config.set('CREDENTIALS', 'USERNAME', USERNAME)
        config.set('CREDENTIALS', 'PASSWORD', PASSWORD)
        config.set('CREDENTIALS', 'SUBDOMAIN', SUBDOMAIN)
        config.set('CREDENTIALS', 'CAPTCHA_MODEL_PATH', CAPTCHA_MODEL_PATH)
        save_config()
        
        # Reinizializza il client
        try:
            client = FusionSolarClient(
                USERNAME, PASSWORD,
                captcha_model_path=CAPTCHA_MODEL_PATH,
                huawei_subdomain=SUBDOMAIN
            )
            log_message("Credenziali aggiornate e client reinizializzato")
            messagebox.showinfo("Successo", "Credenziali aggiornate con successo!")
        except Exception as e:
            log_message(f"Errore nell'inizializzazione del client: {e}")
            messagebox.showerror("Errore", f"Errore nell'aggiornamento delle credenziali: {e}")
    
    ttk.Button(conn_tab, text="Salva Credenziali", style='Success.TButton', 
              command=save_credentials).pack(anchor="w", padx=10, pady=10)
    
    # ===== Bottoni comuni =====
    buttons_frame = ttk.Frame(settings_frame, style='Card.TFrame')
    buttons_frame.pack(fill="x", padx=10, pady=10)
    
    # Pulsante per avviare l'updater e chiudere l'app
    def start_updater():
        updater_path = r"C:\EnergyMonitor\Updater.exe"  # Percorso di updater.exe
        if os.path.exists(updater_path):  # Controlla se il file esiste
            subprocess.Popen(updater_path, shell=True)  # Avvia updater.exe
            root.destroy()  # Chiude l'app principale
        else:
            messagebox.showerror("Errore", "Updater non trovato!")
    
    ttk.Button(buttons_frame, text="Aggiorna Software", style='Primary.TButton', 
              command=start_updater).pack(side="left", padx=5, pady=5)
    
    ttk.Button(buttons_frame, text="Chiudi", style='Warning.TButton', 
              command=settings_window.destroy).pack(side="right", padx=5, pady=5)

def show_statistics():
    """Visualizza una finestra con statistiche dettagliate"""
    stats_window = tk.Toplevel(root)
    stats_window.title("Statistiche di Produzione")
    stats_window.geometry("1200x900")
    stats_window.configure(bg=COLOR_BG)
    stats_window.grab_set()  # Modalità modale
    
    # Frame principale
    main_stats_frame = ttk.Frame(stats_window, style='Card.TFrame')
    main_stats_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Titolo
    ttk.Label(main_stats_frame, text="STATISTICHE IMPIANTO FV", style='Title.TLabel').pack(pady=10)
    
    # Frame per le statistiche generali
    general_frame = ttk.LabelFrame(main_stats_frame, text="Statistiche Generali", style='Card.TFrame')
    general_frame.pack(fill="x", padx=10, pady=5)
    
    # Calcola le statistiche
    stats = calculate_statistics()
    
    if not stats:
        ttk.Label(general_frame, text="Nessun dato disponibile", style='Warning.TLabel').pack(pady=10)
        return
    
    # Griglia per le statistiche
    stats_grid = ttk.Frame(general_frame, style='Card.TFrame')
    stats_grid.pack(fill="x", padx=10, pady=10)
    
    # Prima colonna
    col1 = ttk.Frame(stats_grid, style='Card.TFrame')
    col1.pack(side="left", fill="both", expand=True)
    
    ttk.Label(col1, text=f"Potenza Massima:", style='TLabel').grid(row=0, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col1, text=f"{stats['max_power']:.2f} kW", style='Value.TLabel').grid(row=0, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col1, text=f"Data record massimo:", style='TLabel').grid(row=1, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col1, text=f"{stats['max_time']}", style='TLabel').grid(row=1, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col1, text=f"Potenza Media:", style='TLabel').grid(row=2, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col1, text=f"{stats['avg_power']:.2f} kW", style='Value.TLabel').grid(row=2, column=1, sticky="e", padx=5, pady=2)
    
    # Seconda colonna
    col2 = ttk.Frame(stats_grid, style='Card.TFrame')
    col2.pack(side="left", fill="both", expand=True)
    
    ttk.Label(col2, text=f"Energia Totale:", style='TLabel').grid(row=0, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col2, text=f"{stats['total_energy']:.2f} kWh", style='Value.TLabel').grid(row=0, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col2, text=f"Energia Mensile:", style='TLabel').grid(row=1, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col2, text=f"{stats['monthly_energy']:.2f} kWh", style='Value.TLabel').grid(row=1, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col2, text=f"Ore Funzionamento:", style='TLabel').grid(row=2, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col2, text=f"{stats['operating_hours']:.1f} ore", style='TLabel').grid(row=2, column=1, sticky="e", padx=5, pady=2)
    
    # Terza colonna
    col3 = ttk.Frame(stats_grid, style='Card.TFrame')
    col3.pack(side="left", fill="both", expand=True)
    
    ttk.Label(col3, text=f"Miglior Giorno:", style='TLabel').grid(row=0, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col3, text=f"{stats['best_day']['date']}", style='TLabel').grid(row=0, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col3, text=f"Energia miglior giorno:", style='TLabel').grid(row=1, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col3, text=f"{stats['best_day']['energy']:.2f} kWh", style='Value.TLabel').grid(row=1, column=1, sticky="e", padx=5, pady=2)
    
    ttk.Label(col3, text=f"Giorni con dati:", style='TLabel').grid(row=2, column=0, sticky="w", padx=5, pady=2)
    ttk.Label(col3, text=f"{stats['days_with_data']}", style='TLabel').grid(row=2, column=1, sticky="e", padx=5, pady=2)
    
    # Frame per il grafico della produzione giornaliera
    chart_frame = ttk.Frame(main_stats_frame, style='Card.TFrame')
    chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Grafico della produzione giornaliera
    fig2 = Figure(figsize=(8, 4), dpi=100)
    ax2 = fig2.add_subplot(111)
    
    # Prepara i dati per il grafico
    if stats['daily_energy']:
        days = list(stats['daily_energy'].keys())[-30:]  # Ultimi 30 giorni
        energies = [stats['daily_energy'][day] for day in days]
        
        # Converti le date in oggetti datetime per l'ordinamento
        days_dt = [datetime.strptime(day, '%Y-%m-%d') for day in days]
        days_energies = sorted(zip(days_dt, energies), key=lambda x: x[0])
        days_dt, energies = zip(*days_energies)
        
        # Formatta le date come stringhe
        days_str = [dt.strftime('%d/%m') for dt in days_dt]
        
        # Crea un grafico a barre
        bars = ax2.bar(days_str, energies, color=COLOR_SECONDARY)
        
        # Aggiungi etichette per i valori
        for i, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:  # Mostra etichette solo per valori positivi
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{energies[i]:.1f}',
                        ha='center', va='bottom', rotation=0, fontsize=8)
        
        ax2.set_title("Produzione Energetica Giornaliera", fontsize=12, color=COLOR_PRIMARY)
        ax2.set_xlabel("Data")
        ax2.set_ylabel("Energia (kWh)")
        ax2.grid(True, linestyle='--', alpha=0.7, axis='y')
        
        # Migliora l'aspetto del grafico
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        
        # Ruota le etichette sull'asse x per maggiore leggibilità
        plt.setp(ax2.get_xticklabels(), rotation=45, ha='right', fontsize=8)
        
        fig2.tight_layout()
        
        canvas2 = FigureCanvasTkAgg(fig2, master=chart_frame)
        canvas2.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar per il grafico
        toolbar2 = NavigationToolbar2Tk(canvas2, chart_frame)
        toolbar2.update()
    
    # Pulsanti
    buttons_frame = ttk.Frame(main_stats_frame, style='Card.TFrame')
    buttons_frame.pack(fill="x", padx=10, pady=5)
    
    def export_statistics():
        """Esporta le statistiche in un file di testo"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = filedialog.asksaveasfilename(
            initialdir=os.getcwd(),
            title="Salva statistiche come",
            defaultextension=".txt",
            filetypes=[("File di testo", "*.txt"), ("Tutti i file", "*.*")],
            initialfile=f"statistiche_{timestamp}.txt"
        )
        
        if not export_path:
            return
            
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write("STATISTICHE IMPIANTO FOTOVOLTAICO\n")
            f.write("=============================\n\n")
            f.write(f"Data report: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Potenza Massima: {stats['max_power']:.2f} kW (registrata il {stats['max_time']})\n")
            f.write(f"Potenza Media: {stats['avg_power']:.2f} kW\n")
            f.write(f"Energia Totale Prodotta: {stats['total_energy']:.2f} kWh\n")
            f.write(f"Energia Mensile Corrente: {stats['monthly_energy']:.2f} kWh\n")
            f.write(f"Ore di Funzionamento: {stats['operating_hours']:.1f} ore\n")
            f.write(f"Miglior Giorno: {stats['best_day']['date']} ({stats['best_day']['energy']:.2f} kWh)\n\n")
            f.write("PRODUZIONE GIORNALIERA\n")
            f.write("----------------------\n\n")
            
            # Ordina i giorni dal più recente al più vecchio
            sorted_days = sorted(stats['daily_energy'].keys(), reverse=True)
            for day in sorted_days:
                f.write(f"{day}: {stats['daily_energy'][day]:.2f} kWh\n")
        
        log_message(f"Statistiche esportate in: {export_path}")
        messagebox.showinfo("Esportazione completata", f"Statistiche esportate in:\n{export_path}")
    
    ttk.Button(buttons_frame, text="Esporta Statistiche", style='Primary.TButton', 
              command=export_statistics).pack(side="left", padx=5, pady=5)
    
    ttk.Button(buttons_frame, text="Visualizza Mensile", style='Success.TButton', 
              command=lambda: show_monthly_comparison()).pack(side="left", padx=5, pady=5)
    
    ttk.Button(buttons_frame, text="Chiudi", style='Warning.TButton', 
              command=stats_window.destroy).pack(side="right", padx=5, pady=5)

def show_monthly_comparison():
    """Visualizza un confronto della produzione mensile"""
    compare_window = tk.Toplevel(root)
    compare_window.title("Confronto Produzione Mensile")
    compare_window.geometry("1200x900")
    compare_window.configure(bg=COLOR_BG)
    compare_window.grab_set()  # Modalità modale
    
    # Frame principale
    compare_frame = ttk.Frame(compare_window, style='Card.TFrame')
    compare_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Titolo
    ttk.Label(compare_frame, text="CONFRONTO PRODUZIONE MENSILE", style='Title.TLabel').pack(pady=10)
    
    # Carica tutti i dati
    timestamps, power_values = load_recent_data(days=9999)  # Carica tutti i dati disponibili
    
    if not timestamps:
        ttk.Label(compare_frame, text="Dati insufficienti per il confronto", style='Warning.TLabel').pack(pady=10)
        return
    
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
    
    # Grafico del confronto mensile
    chart_frame = ttk.Frame(compare_frame, style='Card.TFrame')
    chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    fig3 = Figure(figsize=(8, 4), dpi=100)
    ax3 = fig3.add_subplot(111)
    
    # Prepara i dati per il grafico
    if monthly_energy:
        months = sorted(monthly_energy.keys())
        energies = [monthly_energy[month] for month in months]
        
        # Crea etichette più leggibili
        month_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]
        
        # Crea un grafico a barre
        bars = ax3.bar(month_labels, energies, color=COLOR_PRIMARY)
        
        # Aggiungi etichette con i valori sopra le barre
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{energies[i]:.1f}',
                    ha='center', va='bottom', rotation=0)
        
        ax3.set_title("Produzione Energetica Mensile", fontsize=12, color=COLOR_PRIMARY)
        ax3.set_ylabel("Energia (kWh)")
        ax3.grid(True, linestyle='--', alpha=0.7, axis='y')
        
        # Migliora l'aspetto del grafico
        ax3.spines['top'].set_visible(False)
        ax3.spines['right'].set_visible(False)
        
        # Ruota le etichette sull'asse x per maggiore leggibilità
        plt.setp(ax3.get_xticklabels(), rotation=45, ha='right')
        
        fig3.tight_layout()
        
        canvas3 = FigureCanvasTkAgg(fig3, master=chart_frame)
        canvas3.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar per il grafico
        toolbar3 = NavigationToolbar2Tk(canvas3, chart_frame)
        toolbar3.update()
    
    # Tabella dei dati mensili
    table_frame = ttk.LabelFrame(compare_frame, text="Dati mensili", style='Card.TFrame')
    table_frame.pack(fill="x", padx=10, pady=10)
    
    table = ttk.Treeview(table_frame, columns=("month", "energy"), show="headings", height=6)
    table.heading("month", text="Mese")
    table.heading("energy", text="Energia (kWh)")
    table.column("month", width=150)
    table.column("energy", width=150)
    
    # Inserisci i dati nella tabella
    for month in sorted(monthly_energy.keys(), reverse=True):
        month_label = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
        table.insert("", "end", values=(month_label, f"{monthly_energy[month]:.2f}"))
    
    table.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Pulsanti
    buttons_frame = ttk.Frame(compare_frame, style='Card.TFrame')
    buttons_frame.pack(fill="x", padx=10, pady=5)
    
    def export_monthly_data():
        """Esporta i dati mensili in un file CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = filedialog.asksaveasfilename(
            initialdir=os.getcwd(),
            title="Salva dati mensili come",
            defaultextension=".csv",
            filetypes=[("File CSV", "*.csv"), ("Tutti i file", "*.*")],
            initialfile=f"dati_mensili_{timestamp}.csv"
        )
        
        if not export_path:
            return
            
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write("Mese,Energia (kWh)\n")
            for month in sorted(monthly_energy.keys()):
                month_label = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
                f.write(f"{month_label},{monthly_energy[month]:.2f}\n")
        
        log_message(f"Dati mensili esportati in: {export_path}")
        messagebox.showinfo("Esportazione completata", f"Dati mensili esportati in:\n{export_path}")
    
    ttk.Button(buttons_frame, text="Esporta CSV", style='Primary.TButton', 
              command=export_monthly_data).pack(side="left", padx=5, pady=5)
    
    ttk.Button(buttons_frame, text="Chiudi", style='Warning.TButton', 
              command=compare_window.destroy).pack(side="right", padx=5, pady=5)

def export_data():
    """Esporta i dati in XML"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = filedialog.asksaveasfilename(
        initialdir=os.getcwd(),
        title="Salva dati come",
        defaultextension=".xml",
        filetypes=[("File XML", "*.xml"), ("Tutti i file", "*.*")],
        initialfile=f"energy_data_{timestamp}.xml"
    )
    
    if not export_path:
        return
        
    try:
        # Crea una copia del file XML
        import shutil
        shutil.copy2(XML_FILE_PATH, export_path)
        
        log_message(f"Dati esportati con successo in: {export_path}")
        messagebox.showinfo("Esportazione completata", f"Dati esportati in:\n{export_path}")
    except Exception as e:
        log_message(f"Errore nell'esportazione dati: {e}")
        messagebox.showerror("Errore", f"Errore nell'esportazione dati: {e}")

def export_csv():
    """Esporta i dati in CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = filedialog.asksaveasfilename(
        initialdir=os.getcwd(),
        title="Salva dati come",
        defaultextension=".csv",
        filetypes=[("File CSV", "*.csv"), ("Tutti i file", "*.*")],
        initialfile=f"energy_data_{timestamp}.csv"
    )
    
    if not export_path:
        return
        
    try:
        # Carica tutti i dati
        timestamps, power_values = load_recent_data(days=9999)  # Carica tutti i dati disponibili
        
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write("Timestamp,Potenza (kW)\n")
            for i in range(len(timestamps)):
                f.write(f"{timestamps[i].strftime('%Y-%m-%d %H:%M:%S')},{power_values[i]}\n")
        
        log_message(f"Dati esportati in CSV: {export_path}")
        messagebox.showinfo("Esportazione completata", f"Dati esportati in CSV:\n{export_path}")
    except Exception as e:
        log_message(f"Errore nell'esportazione CSV: {e}")
        messagebox.showerror("Errore", f"Errore nell'esportazione CSV: {e}")
def setup_auto_export():
    """Configura l'esportazione automatica dei dati"""
    auto_export_window = tk.Toplevel(root)
    auto_export_window.title("Esportazione Automatica")
    auto_export_window.geometry("500x400")
    auto_export_window.configure(bg=COLOR_BG)
    auto_export_window.grab_set()  # Modalità modale
    
    # Frame principale
    auto_frame = ttk.Frame(auto_export_window, style='Card.TFrame')
    auto_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Titolo
    ttk.Label(auto_frame, text="ESPORTAZIONE AUTOMATICA", style='Title.TLabel').pack(pady=10)
    
    # Opzioni di esportazione
    export_enabled = tk.BooleanVar(value=config.getboolean('EXPORT', 'AUTO_EXPORT_ENABLED', fallback=False))
    export_interval = tk.IntVar(value=config.getint('EXPORT', 'AUTO_EXPORT_INTERVAL_HOURS', fallback=24))
    export_folder = tk.StringVar(value=config.get('EXPORT', 'AUTO_EXPORT_FOLDER', fallback=os.getcwd()))
    
    # Checkbox per abilitare l'esportazione automatica
    ttk.Checkbutton(auto_frame, text="Abilita esportazione automatica", variable=export_enabled, 
                  style='TCheckbutton').pack(anchor="w", padx=10, pady=10)
    
    # Frame per l'intervallo
    interval_frame = ttk.Frame(auto_frame, style='Card.TFrame')
    interval_frame.pack(fill="x", padx=10, pady=10)
    
    ttk.Label(interval_frame, text="Intervallo (ore):", style='TLabel').pack(side="left")
    ttk.Spinbox(interval_frame, from_=1, to=168, textvariable=export_interval, width=5).pack(side="left", padx=5)
    
    # Frame per la cartella
    folder_frame = ttk.LabelFrame(auto_frame, text="Cartella di esportazione", style='Card.TFrame')
    folder_frame.pack(fill="x", padx=10, pady=10)
    
    folder_entry = ttk.Entry(folder_frame, textvariable=export_folder, width=40)
    folder_entry.pack(fill="x", pady=10, padx=10)
    
    def browse_folder():
        folder = filedialog.askdirectory()
        if folder:
            export_folder.set(folder)
    
    ttk.Button(folder_frame, text="Sfoglia", command=browse_folder).pack(anchor="e", pady=5, padx=10)
    
    # Formato di esportazione
    format_frame = ttk.LabelFrame(auto_frame, text="Formato di esportazione", style='Card.TFrame')
    format_frame.pack(fill="x", padx=10, pady=10)
    
    export_format = tk.StringVar(value=config.get('EXPORT', 'AUTO_EXPORT_FORMAT', fallback='csv'))
    
    ttk.Radiobutton(format_frame, text="CSV", variable=export_format, value="csv").pack(anchor="w", padx=10, pady=5)
    ttk.Radiobutton(format_frame, text="XML", variable=export_format, value="xml").pack(anchor="w", padx=10, pady=5)
    
    # Pulsante per salvare le impostazioni
    def save_export_settings():
        # Salva le impostazioni nel file di configurazione
        if 'EXPORT' not in config:
            config.add_section('EXPORT')
        
        config.set('EXPORT', 'AUTO_EXPORT_ENABLED', str(export_enabled.get()))
        config.set('EXPORT', 'AUTO_EXPORT_INTERVAL_HOURS', str(export_interval.get()))
        config.set('EXPORT', 'AUTO_EXPORT_FOLDER', export_folder.get())
        config.set('EXPORT', 'AUTO_EXPORT_FORMAT', export_format.get())
        
        save_config()
        
        # Avvia il thread di esportazione automatica se abilitato
        if export_enabled.get():
            threading.Thread(target=auto_export_thread, daemon=True).start()
            log_message(f"Esportazione automatica abilitata ogni {export_interval.get()} ore")
        
        auto_export_window.destroy()
        messagebox.showinfo("Impostazioni salvate", "Impostazioni di esportazione automatica salvate con successo!")
    
    buttons_frame = ttk.Frame(auto_frame, style='Card.TFrame')
    buttons_frame.pack(fill="x", padx=10, pady=10)
    
    ttk.Button(buttons_frame, text="Salva Impostazioni", style='Success.TButton', 
              command=save_export_settings).pack(side="left", padx=5, pady=5)
    
    ttk.Button(buttons_frame, text="Annulla", style='Warning.TButton', 
              command=auto_export_window.destroy).pack(side="right", padx=5, pady=5)

def auto_export_thread():
    """Thread per l'esportazione automatica dei dati"""
    while True:
        # Verifica se l'esportazione automatica è abilitata
        if not config.getboolean('EXPORT', 'AUTO_EXPORT_ENABLED', fallback=False):
            break
        
        # Intervallo in ore
        interval_hours = config.getint('EXPORT', 'AUTO_EXPORT_INTERVAL_HOURS', fallback=24)
        
        # Cartella di destinazione
        export_folder = config.get('EXPORT', 'AUTO_EXPORT_FOLDER', fallback=os.getcwd())
        
        # Formato di esportazione
        export_format = config.get('EXPORT', 'AUTO_EXPORT_FORMAT', fallback='csv')
        
        try:
            # Crea un timestamp per il nome file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if export_format == 'csv':
                # Esporta in CSV
                csv_path = os.path.join(export_folder, f"auto_export_{timestamp}.csv")
                
                # Carica tutti i dati
                timestamps, power_values = load_recent_data(days=9999)
                
                with open(csv_path, 'w') as f:
                    f.write("Timestamp,Potenza (kW)\n")
                    for i in range(len(timestamps)):
                        f.write(f"{timestamps[i].strftime('%Y-%m-%d %H:%M:%S')},{power_values[i]}\n")
                
                log_message(f"Esportazione automatica CSV completata: {csv_path}")
            else:
                # Esporta in XML
                xml_path = os.path.join(export_folder, f"auto_export_{timestamp}.xml")
                import shutil
                shutil.copy2(XML_FILE_PATH, xml_path)
                log_message(f"Esportazione automatica XML completata: {xml_path}")
            
        except Exception as e:
            log_message(f"Errore nell'esportazione automatica: {e}")
        
        # Attendi l'intervallo specificato
        time.sleep(interval_hours * 3600)

# ===== AGGIORNAMENTO DATI =====

# Aggiungi questa riga all'inizio del file, dopo le importazioni
plot_lock = threading.Lock()

def update_data():
    """
    Aggiorna i dati solo se il refresh non è in pausa.
    """
    global alarm_active
    last_energy_update = time.time()
    
    while True:
        if not refresh_paused:  # Controllo se il refresh è attivo
            try:
                # Verifica se la sessione è ancora attiva, altrimenti rifai il login
                if not is_session_valid():
                    if not renew_session():
                        # Se il rinnovo della sessione fallisce, attiva l'allarme
                        if not alarm_active:
                            log_message("Impossibile rinnovare la sessione, attivazione allarme.")
                            trigger_alarm()
                        time.sleep(INTERVAL)
                        continue

                # Ottenere lo stato di potenza dall'impianto
                stats = client.get_power_status()
                current_power = stats.current_power_kw
                inverter_status = "✅ Operativo" if current_power > 0 else "⚠️ Nessuna Produzione"
                
                # Aggiorna le etichette dell'interfaccia
                power_value_label.config(text=f"{current_power:.2f} kW")
                status_value_label.config(text=inverter_status)
                
                # Aggiorna il colore in base allo stato
                if current_power > 0:
                    power_value_label.config(foreground=COLOR_SECONDARY)
                    status_value_label.config(foreground=COLOR_SECONDARY)
                else:
                    power_value_label.config(foreground=COLOR_WARNING)
                    status_value_label.config(foreground=COLOR_WARNING)
                
                current_time = time.strftime('%H:%M:%S')
                times.append(current_time)
                powers.append(current_power)
                
                # Salva i dati nel file XML
                save_power_data(current_time, current_power)
                
                # Aggiorna il grafico con i dati XML - Usa il lock e root.after per evitare problemi di concorrenza
                with plot_lock:
                    # Utilizza root.after per eseguire l'aggiornamento del grafico nel thread principale di tkinter
                    root.after(0, lambda: plot_graph())
                
                log_message(f"Potenza: {current_power:.2f} kW - Stato: {inverter_status}")
                
                # Aggiorna il calcolo dell'energia giornaliera ogni ora
                current_time_secs = time.time()
                if current_time_secs - last_energy_update > 3600:  # 3600 secondi = 1 ora
                    # Calcola l'energia per la giornata corrente
                    stats = calculate_statistics(days=1)
                    if stats and 'total_energy' in stats:
                        daily_energy_value_label.config(text=f"{stats['total_energy']:.2f} kWh")
                    last_energy_update = current_time_secs
                
                # Controllo allarme
                if not is_session_valid():
                    log_message("Errore di comunicazione con l'impianto: sessione non valida.")
                    if not alarm_active:
                        trigger_alarm()  # Attiva sempre l'allarme per errore di comunicazione
                elif ALARM_ENABLED and current_power == 0:
                    log_message("Attivazione allarme per produzione 0.")
                    if not alarm_active:
                        trigger_alarm()  # Attiva l'allarme solo se ALARM_ENABLED è attivo
                else:
                    # Se tutto è a posto, resetta l'allarme se era attivo
                    if alarm_active:
                        reset_alarm()

            except Exception as e:
                log_message(f"Errore di comunicazione con l'impianto: {e}")
                if not alarm_active:
                    trigger_alarm()  # Attiva sempre l'allarme per errore di comunicazione

        # Attendi l'intervallo specificato
        time.sleep(INTERVAL)

def on_closing():
    """Gestisce la chiusura dell'applicazione"""
    if messagebox.askokcancel("Chiusura", "Vuoi davvero chiudere l'applicazione?"):
        # Esegui operazioni di pulizia se necessario
        root.destroy()

def log_message(message):
    """Aggiunge un messaggio all'area di log"""
    log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
    log_text.see(tk.END)

def plot_graph():
    """Aggiorna il grafico con i dati del periodo selezionato"""
    global cursor
    
    try:
        ax.clear()
        
        # Carica i dati dal file XML in base al periodo selezionato
        timestamps, power_values = load_recent_data(days=display_period.get())
        
        if timestamps and power_values and len(timestamps) > 0 and len(power_values) > 0:
            # Plot dei dati
            line, = ax.plot(timestamps, power_values, color=COLOR_PRIMARY, linewidth=2, marker="o", markersize=4)
            
            # Configura il formato dell'asse X in base al periodo
            if display_period.get() <= 1:  # Visualizzazione giornaliera
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.set_xlabel("Ora")
            else:  # Visualizzazione multi-giorno
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
                ax.set_xlabel("Data e Ora")
            
            # Calcola l'energia giornaliera approssimativa (area sotto la curva)
            if timestamps:
                today = datetime.now().strftime('%Y-%m-%d')
                today_timestamps = [ts for ts in timestamps if ts.strftime('%Y-%m-%d') == today]
                today_powers = [power_values[timestamps.index(ts)] for ts in today_timestamps]
                
                if today_powers and len(today_powers) > 0:
                    # Calcolo approssimativo dell'energia (kWh) come media delle potenze * ore
                    avg_power = sum(today_powers) / len(today_powers)
                    hours = (max(today_timestamps) - min(today_timestamps)).total_seconds() / 3600 if len(today_timestamps) > 1 else 0
                    daily_energy = avg_power * hours
                    daily_energy_value_label.config(text=f"{daily_energy:.2f} kWh")
            
            # Aggiunge annotazioni per i valori massimi
            if power_values and len(power_values) > 0:
                max_power = max(power_values)
                max_time = timestamps[power_values.index(max_power)]
                ax.annotate(f"Max: {max_power:.2f} kW", 
                            xy=(max_time, max_power),
                            xytext=(0, 10), textcoords='offset points',
                            ha='center', va='bottom',
                            bbox=dict(boxstyle='round,pad=0.3', fc='#FFC107', alpha=0.7))
            
            # Aggiunge tooltip interattivi sui punti
            if cursor:
                try:
                    cursor.remove()
                except:
                    pass
            
            # Array globali per trovare l'indice corretto
            all_timestamps = timestamps
            all_powers = power_values
            
            cursor = mplcursors.cursor(line, hover=True)
            
            @cursor.connect("add")
            def on_cursor_add(sel):
                try:
                    # Diverso approccio per individuare il punto
                    # Usa le coordinate del target per trovare il punto più vicino
                    target_x, target_y = sel.target
                    
                    # Trova l'indice del punto più vicino
                    # Converti timestamps a numeri per il confronto numerico
                    x_values = mdates.date2num(all_timestamps)
                    x_selected = mdates.date2num(target_x) if isinstance(target_x, datetime) else target_x
                    
                    # Calcola la distanza e trova il punto più vicino
                    distances = [(x - x_selected)**2 + (y - target_y)**2 for x, y in zip(x_values, all_powers)]
                    closest_idx = distances.index(min(distances))
                    
                    # Ottieni il timestamp e la potenza corrispondenti
                    timestamp = all_timestamps[closest_idx].strftime('%Y-%m-%d %H:%M:%S')
                    power = all_powers[closest_idx]
                    
                    # Aggiorna l'annotazione
                    sel.annotation.set_text(f"{timestamp}\n{power:.2f} kW")
                    sel.annotation.get_bbox_patch().set(fc="#4CAF50", alpha=0.7)
                except Exception as e:
                    log_message(f"Errore nel tooltip: {e}")
        else:
            # Nessun dato disponibile
            ax.text(0.5, 0.5, "Nessun dato disponibile per il periodo selezionato", 
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes)

        # Personalizzazione del grafico
        ax.set_title("Produzione Energetica", fontsize=14, color=COLOR_PRIMARY)
        ax.set_ylabel("Potenza (kW)")
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Migliora l'aspetto del grafico
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Imposta i limiti dell'asse y per includere lo zero e avere un margine superiore
        if power_values and len(power_values) > 0:
            ax.set_ylim(0, max(power_values) * 1.1)
        else:
            # Imposta un valore di default se non ci sono dati
            ax.set_ylim(0, 10)
        
        # Assicurati che ci siano almeno due tick sull'asse x
        if not ax.get_xticks().size:
            now = datetime.now()
            ax.set_xlim(now - timedelta(hours=1), now)
        
        fig.tight_layout()
        canvas.draw_idle()  # Usa draw_idle invece di draw per evitare aggiornamenti eccessivi
        
    except Exception as e:
        log_message(f"Errore nell'aggiornamento del grafico: {e}")
        
        # Tenta di ripristinare il grafico
        try:
            ax.clear()
            ax.text(0.5, 0.5, "Errore nell'aggiornamento del grafico", 
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, color='red')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            fig.tight_layout()
            canvas.draw()
        except:
            pass
# ===== INIZIALIZZAZIONE GUI =====

# Creazione della finestra principale
root = tk.Tk()
root.title("SS® | Energy Monitor - FV GIUMENTARE")
root.state('zoomed')
root.configure(bg="#f5f5f5")
root.iconbitmap("icon.ico") if os.path.exists("icon.ico") else None

# Inizializza il file XML
xml_tree = initialize_xml_file()

# Stili e colori
COLOR_PRIMARY = "#1976D2"
COLOR_SECONDARY = "#388E3C"
COLOR_ACCENT = "#FFA000"
COLOR_WARNING = "#F44336"
COLOR_BG = "#f5f5f5"
COLOR_CARD = "#ffffff"

# Stili dei font
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUBTITLE = ("Segoe UI", 14, "bold")
FONT_NORMAL = ("Segoe UI", 12)
FONT_BUTTON = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)

# Configurazione dei ttk style per widget moderni
style = ttk.Style()
style.theme_use('clam')  # Usa un tema base che supporta più personalizzazioni

# Configura stile per i pulsanti
style.configure('TButton', font=FONT_BUTTON, padding=6)
style.configure('Primary.TButton', background=COLOR_PRIMARY, foreground='white')
style.configure('Success.TButton', background=COLOR_SECONDARY, foreground='white')
style.configure('Warning.TButton', background=COLOR_WARNING, foreground='white')
style.configure('Accent.TButton', background=COLOR_ACCENT, foreground='white')

# Configura stile per i frame
style.configure('Card.TFrame', background=COLOR_CARD, relief='raised')
style.configure('BG.TFrame', background=COLOR_BG)

# Configura stile per i label
style.configure('TLabel', background=COLOR_CARD, font=FONT_NORMAL)
style.configure('Title.TLabel', font=FONT_TITLE, foreground=COLOR_PRIMARY)
style.configure('Subtitle.TLabel', font=FONT_SUBTITLE, foreground=COLOR_SECONDARY)
style.configure('Value.TLabel', font=FONT_TITLE, foreground=COLOR_SECONDARY)
style.configure('Warning.TLabel', foreground=COLOR_WARNING)
style.configure('BG.TLabel', background=COLOR_BG)

# Layout principale
main_frame = ttk.Frame(root, style='BG.TFrame')
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Frame sinistro per le informazioni
left_frame = ttk.Frame(main_frame, style='Card.TFrame')
left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")

# Frame destro per il grafico
right_frame = ttk.Frame(main_frame, style='Card.TFrame')
right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
main_frame.grid_columnconfigure(1, weight=1)
main_frame.grid_rowconfigure(0, weight=1)

# ===== CONTENUTO DEL FRAME SINISTRO =====

# Titolo dell'applicazione
title_frame = ttk.Frame(left_frame, style='Card.TFrame')
title_frame.pack(fill="x", pady=(10, 5))
title_label = ttk.Label(title_frame, text="SS® Energy Monitor", style='Title.TLabel')
title_label.pack(pady=5)
plant_label = ttk.Label(title_frame, text="FV GIUMENTARE", style='Subtitle.TLabel')
plant_label.pack(pady=(0, 5))

# Separatore
ttk.Separator(left_frame, orient='horizontal').pack(fill='x', padx=10, pady=5)

# Card per la potenza attuale
power_frame = ttk.Frame(left_frame, style='Card.TFrame')
power_frame.pack(fill="x", padx=10, pady=5)
ttk.Label(power_frame, text="Potenza Attuale", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(5, 0))
power_value_label = ttk.Label(power_frame, text="-- kW", style='Value.TLabel')
power_value_label.pack(pady=(0, 5), padx=10)

# Card per lo stato dell'inverter
status_frame = ttk.Frame(left_frame, style='Card.TFrame')
status_frame.pack(fill="x", padx=10, pady=5)
ttk.Label(status_frame, text="Stato Inverter", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(5, 0))
status_value_label = ttk.Label(status_frame, text="--", style='Value.TLabel')
status_value_label.pack(pady=(0, 5), padx=10)

# Card per l'energia giornaliera
daily_energy_frame = ttk.Frame(left_frame, style='Card.TFrame')
daily_energy_frame.pack(fill="x", padx=10, pady=5)
ttk.Label(daily_energy_frame, text="Energia Giornaliera", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(5, 0))
daily_energy_value_label = ttk.Label(daily_energy_frame, text="-- kWh", style='Value.TLabel')
daily_energy_value_label.pack(pady=(0, 5), padx=10)

# Separatore
ttk.Separator(left_frame, orient='horizontal').pack(fill='x', padx=10, pady=5)

# Area di log con scrollbar
log_frame = ttk.Frame(left_frame, style='Card.TFrame')
log_frame.pack(fill="both", expand=True, padx=10, pady=5)
ttk.Label(log_frame, text="Log Eventi", style='Subtitle.TLabel').pack(anchor="w", padx=10, pady=(5, 0))

log_text = tk.Text(log_frame, height=8, width=40, font=FONT_SMALL, bg="#f8f9fa", fg="#333")
log_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))
log_scrollbar = ttk.Scrollbar(log_text)
log_scrollbar.pack(side="right", fill="y")
log_text.config(yscrollcommand=log_scrollbar.set)
log_scrollbar.config(command=log_text.yview)

# Pulsanti di azione
buttons_frame = ttk.Frame(left_frame, style='Card.TFrame')
buttons_frame.pack(fill="x", padx=10, pady=(5, 10))

# Prima riga di pulsanti
buttons_row1 = ttk.Frame(buttons_frame, style='Card.TFrame')
buttons_row1.pack(fill="x", pady=5)

settings_btn = ttk.Button(buttons_row1, text="IMPOSTAZIONI", style='Primary.TButton', command=open_settings)
settings_btn.pack(side="left", fill="x", expand=True, padx=2)

export_btn = ttk.Button(buttons_row1, text="ESPORTA DATI", style='Success.TButton', command=export_data)
export_btn.pack(side="left", fill="x", expand=True, padx=2)

# Seconda riga di pulsanti
buttons_row2 = ttk.Frame(buttons_frame, style='Card.TFrame')
buttons_row2.pack(fill="x", pady=5)

stats_btn = ttk.Button(buttons_row2, text="STATISTICHE", style='Accent.TButton', command=show_statistics)
stats_btn.pack(side="left", fill="x", expand=True, padx=2)

exit_btn = ttk.Button(buttons_row2, text="ESCI", style='Warning.TButton', command=on_closing)
exit_btn.pack(side="left", fill="x", expand=True, padx=2)

# ===== CONTENUTO DEL FRAME DESTRO (GRAFICO) =====

# Titolo del grafico
graph_title_frame = ttk.Frame(right_frame, style='Card.TFrame')
graph_title_frame.pack(fill="x", pady=5)
graph_title_label = ttk.Label(graph_title_frame, text="Produzione Energetica in Tempo Reale", style='Title.TLabel')
graph_title_label.pack(pady=5)

# Controlli del grafico
graph_controls = ttk.Frame(right_frame, style='Card.TFrame')
graph_controls.pack(fill="x", pady=5, padx=10)

ttk.Label(graph_controls, text="Periodo:", style='TLabel').pack(side="left", padx=5)

# Variabile per il controllo del periodo visualizzato
display_period = tk.IntVar(value=1)  # Default: 1 giorno

def update_period(days):
    display_period.set(days)
    plot_graph()

today_btn = ttk.Button(graph_controls, text="Oggi", style='Primary.TButton', command=lambda: update_period(1))
today_btn.pack(side="left", padx=5)

days3_btn = ttk.Button(graph_controls, text="3 Giorni", style='Primary.TButton', command=lambda: update_period(3))
days3_btn.pack(side="left", padx=5)

days7_btn = ttk.Button(graph_controls, text="7 Giorni", style='Primary.TButton', command=lambda: update_period(7))
days7_btn.pack(side="left", padx=5)

days30_btn = ttk.Button(graph_controls, text="30 Giorni", style='Primary.TButton', command=lambda: update_period(30))
days30_btn.pack(side="left", padx=5)

# Variabile di stato per il refresh dei dati
refresh_paused = False

def toggle_refresh():
    """Funzione per mettere in pausa o riprendere l'aggiornamento dati"""
    global refresh_paused
    refresh_paused = not refresh_paused  # Inverti lo stato
    refresh_button.config(
        text="▶ Riprendi" if refresh_paused else "⏸ Pausa", 
        style='Warning.TButton' if refresh_paused else 'Success.TButton'
    )
    log_message("Aggiornamento dati in pausa" if refresh_paused else "Aggiornamento dati ripreso")

# Pulsante pausa/riprendi
refresh_button = ttk.Button(graph_controls, text="⏸ Pausa", style='Success.TButton', command=toggle_refresh)
refresh_button.pack(side="right", padx=5)

# Grafico
graph_frame = ttk.Frame(right_frame, style='Card.TFrame')
graph_frame.pack(fill="both", expand=True, padx=10, pady=5)

# Creazione del grafico con matplotlib
fig = Figure(figsize=(8, 5), dpi=100)
ax = fig.add_subplot(111)

# Canvas per il grafico
canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas.get_tk_widget().pack(fill="both", expand=True)

# Toolbar per il grafico
toolbar_frame = ttk.Frame(graph_frame)
toolbar_frame.pack(fill="x")
toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
toolbar.update()

# Cursore per i tooltip sui punti del grafico
cursor = None

# Dati per il grafico
times, powers = [], []

# Creazione dell'overlay per l'allarme
alarm_overlay = tk.Frame(root, bg="red", width=1200, height=700)
alarm_label = tk.Label(alarm_overlay, text="!!! ALLARME ATTIVO !!!", font=("Segoe UI", 40, "bold"), fg="white", bg="red")
alarm_label.pack(expand=True)

reset_button = ttk.Button(alarm_overlay, text="RESET ALLARME", style='Warning.TButton', command=reset_alarm)
reset_button.pack(pady=20)

# Menu principale
main_menu = tk.Menu(root)
root.config(menu=main_menu)

# Menu File
file_menu = tk.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Impostazioni", command=open_settings)
file_menu.add_command(label="Esporta XML", command=export_data)
file_menu.add_command(label="Esporta CSV", command=export_csv)
file_menu.add_command(label="Configura Esportazione Automatica", command=setup_auto_export)
file_menu.add_separator()
file_menu.add_command(label="Esci", command=on_closing)

# Menu Visualizza
view_menu = tk.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Visualizza", menu=view_menu)
view_menu.add_command(label="Oggi", command=lambda: update_period(1))
view_menu.add_command(label="3 Giorni", command=lambda: update_period(3))
view_menu.add_command(label="7 Giorni", command=lambda: update_period(7))
view_menu.add_command(label="30 Giorni", command=lambda: update_period(30))
view_menu.add_separator()
view_menu.add_command(label="Pausa/Riprendi Aggiornamento", command=toggle_refresh)

# Menu Strumenti
tools_menu = tk.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Strumenti", menu=tools_menu)
tools_menu.add_command(label="Statistiche", command=show_statistics)
tools_menu.add_command(label="Confronto Mensile", command=show_monthly_comparison)
tools_menu.add_command(label="Simula Allarme", command=trigger_alarm)

# Menu Aiuto
help_menu = tk.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Aiuto", menu=help_menu)
help_menu.add_command(label="Informazioni", command=lambda: messagebox.showinfo("Informazioni", "SS® Energy Monitor\nVersione 2.0\n \n\nSviluppato da Stefano Solidoro <kishosa@me.com> \n\nMonitoraggio impianti fotovoltaici FusionSolar"))

# Registra il gestore di eventi per la chiusura dell'applicazione
root.protocol("WM_DELETE_WINDOW", on_closing)

# Leggi le impostazioni di esportazione automatica
# Leggi le impostazioni di esportazione automatica
if 'EXPORT' in config and config.getboolean('EXPORT', 'AUTO_EXPORT_ENABLED', fallback=False):
    threading.Thread(target=auto_export_thread, daemon=True).start()
    log_message(f"Esportazione automatica abilitata ogni {config.getint('EXPORT', 'AUTO_EXPORT_INTERVAL_HOURS', fallback=24)} ore")

# Carica dati iniziali se disponibili
if os.path.exists(XML_FILE_PATH):
    log_message("Caricamento dati storici...")
    try:
        timestamps, power_values = load_recent_data(days=display_period.get())
        if timestamps:
            log_message(f"Caricati {len(timestamps)} punti dati.")
            plot_graph()
            
            # Calcola l'energia giornaliera
            stats = calculate_statistics(days=1)
            if stats and 'total_energy' in stats:
                daily_energy_value_label.config(text=f"{stats['total_energy']:.2f} kWh")
        else:
            log_message("Nessun dato storico trovato.")
            plot_graph()  # Visualizza il grafico vuoto con il messaggio appropriato
    except Exception as e:
        log_message(f"Errore nel caricamento dati storici: {e}")

# Avvia il thread di aggiornamento dati
update_thread = threading.Thread(target=update_data, daemon=True)
update_thread.start()

# Avvia l'applicazione
root.mainloop()