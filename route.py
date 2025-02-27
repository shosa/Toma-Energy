import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import re

# Funzione per ottenere la tabella di routing
def ottieni_tabella_routing():
    try:
        output = subprocess.check_output("route print", shell=True, text=True)
        righe = output.split("\n")
        dati = []
        ipv4_section = False  # Flag per individuare la sezione giusta

        for riga in righe:
            if "IPv4 Route Table" in riga:
                ipv4_section = True
                continue
            if ipv4_section and "===" in riga:  # Fine della tabella IPv4
                break
            if ipv4_section and re.match(r"^\s*\d+\.\d+\.\d+\.\d+", riga):
                colonne = riga.split()
                if len(colonne) >= 4:
                    dati.append((colonne[0], colonne[1], colonne[2], colonne[3]))

        return dati
    except Exception as e:
        messagebox.showerror("Errore", f"Impossibile ottenere la tabella di routing:\n{e}")
        return []
# Funzione per ottenere le interfacce di rete
def ottieni_interfacce():
    try:
        output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
        righe = output.split("\n")
        interfacce = []

        for riga in righe:
            colonne = riga.split()
            if len(colonne) > 3 and colonne[-1] != "Name":
                interfacce.append(colonne[-1])

        return interfacce
    except Exception as e:
        messagebox.showerror("Errore", f"Impossibile ottenere le interfacce di rete:\n{e}")
        return []

# Aggiorna la tabella
def aggiorna_tabella():
    for r in tabella.get_children():
        tabella.delete(r)

    dati = ottieni_tabella_routing()
    for riga in dati:
        tabella.insert("", "end", values=riga)

# Aggiunge una rotta
def aggiungi_rotta():
    destinazione = simpledialog.askstring("Aggiungi Rotta", "Inserisci destinazione:")
    maschera = simpledialog.askstring("Aggiungi Rotta", "Inserisci maschera:")
    gateway = simpledialog.askstring("Aggiungi Rotta", "Inserisci gateway:")
    metrica = simpledialog.askstring("Aggiungi Rotta", "Inserisci metrica (opzionale):")

    if destinazione and maschera and gateway:
        comando = f"route add {destinazione} mask {maschera} {gateway}"
        if metrica:
            comando += f" metric {metrica}"
        subprocess.run(comando, shell=True)
        aggiorna_tabella()

# Modifica una rotta esistente
def modifica_rotta():
    selezione = tabella.selection()
    if not selezione:
        messagebox.showwarning("Attenzione", "Seleziona una rotta da modificare.")
        return

    item = tabella.item(selezione)["values"]
    nuova_gateway = simpledialog.askstring("Modifica Rotta", f"Nuovo gateway per {item[0]}:")
    nuova_metrica = simpledialog.askstring("Modifica Rotta", "Nuova metrica (opzionale):")

    if nuova_gateway:
        comando = f"route change {item[0]} {nuova_gateway}"
        if nuova_metrica:
            comando += f" metric {nuova_metrica}"
        subprocess.run(comando, shell=True)
        aggiorna_tabella()

# Cancella una rotta
def cancella_rotta():
    selezione = tabella.selection()
    if not selezione:
        messagebox.showwarning("Attenzione", "Seleziona una rotta da eliminare.")
        return

    item = tabella.item(selezione)["values"]
    risposta = messagebox.askyesno("Conferma", f"Sei sicuro di eliminare la rotta {item[0]}?")
    if risposta:
        subprocess.run(f"route delete {item[0]}", shell=True)
        aggiorna_tabella()

# Creazione della GUI
root = tk.Tk()
root.title("Gestione Routing Windows")
root.geometry("800x500")

# Frame principale
frame = ttk.Frame(root, padding=10)
frame.pack(fill="both", expand=True)

# Tabella di routing
colonne = ("Destinazione", "Maschera", "Gateway", "Interfaccia")
tabella = ttk.Treeview(frame, columns=colonne, show="headings", height=15)

for col in colonne:
    tabella.heading(col, text=col)
    tabella.column(col, width=150)

tabella.pack(fill="both", expand=True, padx=10, pady=5)

# Bottoni
pannello_bottoni = ttk.Frame(root)
pannello_bottoni.pack(fill="x", padx=10, pady=5)

ttk.Button(pannello_bottoni, text="Aggiorna", command=aggiorna_tabella).pack(side="left", padx=5)
ttk.Button(pannello_bottoni, text="Aggiungi Rotta", command=aggiungi_rotta).pack(side="left", padx=5)
ttk.Button(pannello_bottoni, text="Modifica Rotta", command=modifica_rotta).pack(side="left", padx=5)
ttk.Button(pannello_bottoni, text="Cancella Rotta", command=cancella_rotta).pack(side="left", padx=5)
ttk.Button(pannello_bottoni, text="Esci", command=root.quit).pack(side="right", padx=5)

# Sezione interfacce
frame_interfacce = ttk.LabelFrame(root, text="Interfacce di Rete")
frame_interfacce.pack(fill="both", expand=True, padx=10, pady=10)

lista_interfacce = tk.Listbox(frame_interfacce, height=5)
lista_interfacce.pack(fill="both", expand=True, padx=10, pady=5)

# Aggiornamento iniziale
def carica_dati():
    ottieni_tabella_routing()
    aggiorna_tabella()
    interfacce = ottieni_interfacce()
    for i in interfacce:
        lista_interfacce.insert("end", i)

carica_dati()

root.mainloop()
