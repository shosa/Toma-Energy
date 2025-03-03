import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
import requests
from zipfile import ZipFile
from io import BytesIO

# URL del repository GitHub (ZIP)
REPO_URL = "https://github.com/shosa/release_TOMAENERGY/archive/refs/heads/main.zip"

# Percorso della cartella di destinazione
DEST_DIR = r"C:\EnergyMonitor"

class UpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Updater - EnergyMonitor")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # Titolo
        ttk.Label(root, text="Aggiornamento Energy Monitor", font=("Arial", 14, "bold")).pack(pady=10)

        # Log box
        self.log_box = scrolledtext.ScrolledText(root, height=10, state='disabled')
        self.log_box.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Progress bar
        self.progress = ttk.Progressbar(root, mode="determinate", length=400)
        self.progress.pack(pady=10)

        # Bottone di avvio
        self.update_button = ttk.Button(root, text="AVVIA AGGIORNAMENTO", command=self.start_update)
        self.update_button.pack(pady=10)

    def log_message(self, message):
        """Scrive un messaggio nel log testuale."""
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.config(state='disabled')
        self.log_box.yview(tk.END)  # Scorri fino in fondo

    def download_and_extract_repo(self):
        """Scarica e estrae i file dalla repository GitHub."""
        self.progress["value"] = 0
        self.log_message("Inizio aggiornamento...\n")

        if not os.path.exists(DEST_DIR):
            self.log_message(f"Creazione cartella: {DEST_DIR}")
            os.makedirs(DEST_DIR)

        # Scarica il contenuto del repository come file ZIP
        self.log_message("Scarico la repository...")
        response = requests.get(REPO_URL)
        if response.status_code == 200:
            zip_file = ZipFile(BytesIO(response.content))
            
            # Estrai i file ZIP in una cartella temporanea
            temp_dir = os.path.join(DEST_DIR, "temp_extract")
            zip_file.extractall(temp_dir)
            self.log_message("Repository scaricata ed estratta temporaneamente!")

            # Sposta tutti i file dalla cartella temporanea nella cartella di destinazione
            extracted_folder = os.path.join(temp_dir, "release_TOMAENERGY-main")
            for item in os.listdir(extracted_folder):
                s = os.path.join(extracted_folder, item)
                d = os.path.join(DEST_DIR, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            # Rimuovi la cartella temporanea
            shutil.rmtree(temp_dir)
            self.log_message("Repository estratta e aggiornata!")
        else:
            self.log_message("Errore nel download del repository.")
            return

        self.progress["value"] = 100
        self.log_message("\nAggiornamento completato!")

    def start_update(self):
        """Avvia l'aggiornamento in un thread separato."""
        self.update_button.config(state="disabled")  # Disabilita il bottone durante l'aggiornamento
        thread = threading.Thread(target=self.download_and_extract_repo, daemon=True)
        thread.start()
        self.root.after(100, self.check_thread, thread)

    def check_thread(self, thread):
        """Controlla se il thread è terminato e riabilita il bottone."""
        if thread.is_alive():
            self.root.after(100, self.check_thread, thread)
        else:
            self.update_button.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
