import tkinter as tk
import threading
import time
import sys
import winsound
import configparser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from fusion_solar_py.client import FusionSolarClient

# Caricamento configurazioni
config = configparser.ConfigParser()
config.read('config.ini')

USERNAME = config['CREDENTIALS']['USERNAME']
PASSWORD = config['CREDENTIALS']['PASSWORD']
SUBDOMAIN = config['CREDENTIALS']['SUBDOMAIN']
CAPTCHA_MODEL_PATH = config['CREDENTIALS']['CAPTCHA_MODEL_PATH']
ALARM_ENABLED = config.getboolean('SETTINGS', 'ALARM_ENABLED', fallback=True)

def save_config():
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

client = FusionSolarClient(
    USERNAME, PASSWORD,
    captcha_model_path=CAPTCHA_MODEL_PATH,
    huawei_subdomain=SUBDOMAIN
)

# Inizializza la finestra
root = tk.Tk()
root.title("SS® | Energy Monitor")
root.geometry("1000x650")
root.configure(bg="#f4f4f4")

# Stili
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_NORMAL = ("Segoe UI", 12)
FONT_BUTTON = ("Segoe UI", 10, "bold")

# Layout principale
main_frame = tk.Frame(root, bg="#f4f4f4")
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

left_frame = tk.Frame(main_frame, bg="#ffffff", relief="raised", bd=2)
left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")

right_frame = tk.Frame(main_frame, bg="#ffffff", relief="raised", bd=2)
right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
main_frame.grid_columnconfigure(1, weight=1)
main_frame.grid_rowconfigure(0, weight=1)

# Etichette principali
power_label = tk.Label(left_frame, text="Potenza: -- kW", font=FONT_TITLE, fg="#fff", bg="#008000")
power_label.pack(pady=10, fill="x")

status_label = tk.Label(left_frame, text="Stato Inverter: --", font=FONT_NORMAL, fg="#ff8800", bg="#ffffff")
status_label.pack(pady=5)

# Grafico
fig = Figure(figsize=(7, 4), dpi=100)
ax = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=right_frame)
canvas.get_tk_widget().pack(fill="both", expand=True)
toolbar = NavigationToolbar2Tk(canvas, right_frame)
toolbar.update()
canvas.get_tk_widget().pack(fill="both", expand=True)

graph_title = tk.Label(right_frame, text="FV GIUMENTARE • In Diretta", font=("Segoe UI", 16, "bold"), fg="green", bg="#ffffff")
graph_title.pack(pady=5)

# Dati per il grafico
times, powers = [], []

def plot_graph():
    ax.clear()
    ax.plot(times, powers, color="blue", linewidth=2, marker="o", markersize=5)
    ax.set_title("Produzione Energetica", fontsize=12)
    ax.set_xlabel("Tempo")
    ax.set_ylabel("Potenza (kW)")
    ax.grid(True)
    canvas.draw()

# Log
log_text = tk.Text(left_frame, height=5, width=40, bg="#eaeaea", fg="#333", font=FONT_NORMAL, wrap="none")
log_text.pack(fill="both", expand=True, pady=5)

def log_message(message):
    log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
    log_text.see(tk.END)

def open_settings():
    settings_window = tk.Toplevel(root)
    settings_window.title("Impostazioni")
    settings_window.geometry("400x150")
    settings_window.resizable(False, False)
    
    def toggle_alarm():
        global ALARM_ENABLED
        ALARM_ENABLED = not ALARM_ENABLED
        config.set('SETTINGS', 'ALARM_ENABLED', str(ALARM_ENABLED))
        save_config()
        log_message(f"MODIFICATE IMPOSTAZIONI")
        alarm_toggle_btn.config(text="Attivo" if ALARM_ENABLED else "Disattivo", bg="green" if ALARM_ENABLED else "red")
    
    tk.Label(settings_window, text="ALLARME SU PRODUZIONE 0", font=FONT_NORMAL).pack(pady=10)
    alarm_toggle_btn = tk.Button(settings_window, text="Attivo" if ALARM_ENABLED else "Disattivo", bg="green" if ALARM_ENABLED else "red", command=toggle_alarm)
    alarm_toggle_btn.pack(pady=10)
    
    tk.Button(settings_window, text="Simula Allarme", font=FONT_BUTTON, bg="red", fg="white", command=trigger_alarm).pack(pady=10)

# Pulsante Impostazioni
tk.Button(left_frame, text="IMPOSTAZIONI", font=FONT_BUTTON, bg="#0078D7", fg="white", command=open_settings).pack(pady=5, fill="x")

tk.Button(left_frame, text="ESCI", font=FONT_BUTTON, bg="#FF5733", fg="white", command=sys.exit).pack(pady=5, fill="x")

# Allarme
alarm_active = False

def trigger_alarm():
    global alarm_active
    alarm_active = True
    alarm_overlay.pack(fill="both", expand=True)
    threading.Thread(target=alarm_blink, daemon=True).start()

def alarm_blink():
    while alarm_active:
        alarm_overlay.config(bg="red" if alarm_overlay.cget("bg") == "black" else "black")
        winsound.Beep(1000, 500)
        time.sleep(0.5)

def reset_alarm():
    global alarm_active
    alarm_active = False
    alarm_overlay.pack_forget()

alarm_overlay = tk.Frame(root, bg="black", width=900, height=600)
alarm_label = tk.Label(alarm_overlay, text="!!! ALLARME ATTIVO !!!", font=("Segoe UI", 50, "bold"), fg="white", bg="black")
alarm_label.pack(expand=True)

def update_data():
    global alarm_active
    while True:
        try:
            stats = client.get_power_status()
            current_power = stats.current_power_kw
            inverter_status = "✅ Operativo" if current_power > 0 else "⚠️ Nessuna Produzione"
            
            power_label.config(text=f"Potenza: {current_power:.2f} kW", bg="#008000", fg="#fff")
            status_label.config(text=f"Stato Inverter: {inverter_status}", fg="green" if current_power > 0 else "orange")
            
            times.append(time.strftime('%H:%M:%S'))
            powers.append(current_power)
            plot_graph()
            
            log_message(f"Potenza: {current_power:.2f} kW - Stato: {inverter_status}")
            
            if ALARM_ENABLED and (current_power == 0 or 'Errore' in inverter_status):
                if not alarm_active:
                    trigger_alarm()
            else:
                reset_alarm()
        except Exception:
            log_message("Errore di comunicazione con l'impianto!")
            if ALARM_ENABLED and not alarm_active:
                trigger_alarm()
        time.sleep(3)

threading.Thread(target=update_data, daemon=True).start()
root.mainloop()
