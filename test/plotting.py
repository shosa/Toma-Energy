import logging
import threading
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import mplcursors

logger = logging.getLogger(__name__)

# Lock per evitare aggiornamenti simultanei del grafico
plot_lock = threading.Lock()

class PlottingManager:
    """
    Classe per gestire i grafici e le visualizzazioni
    """
    def __init__(self, data_storage, statistics_calculator):
        """
        Inizializza il gestore dei grafici
        
        Args:
            data_storage: Gestore dei dati
            statistics_calculator: Calcolatore delle statistiche
        """
        self.data_storage = data_storage
        self.statistics = statistics_calculator
        
        # Colori dei grafici
        self.colors = {
            'primary': "#1976D2",
            'secondary': "#388E3C",
            'accent': "#FFA000",
            'warning': "#F44336",
            'background': "#f5f5f5",
            'card': "#ffffff"
        }
        
        # Stile di matplotlib
        plt.style.use('ggplot')
        
        # Variabile per il cursore del grafico
        self.cursor = None
    
    def create_main_plot(self, parent_frame):
        """
        Crea il grafico principale nell'interfaccia
        
        Args:
            parent_frame: Frame tkinter in cui inserire il grafico
            
        Returns:
            tuple: (figure, axes, canvas) - Oggetti matplotlib e tkinter
        """
        # Crea figura e assi
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        # Canvas per il grafico
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar per il grafico
        toolbar_frame = parent_frame.winfo_children()[0] if parent_frame.winfo_children() else parent_frame
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()
        
        return fig, ax, canvas
    
    def update_main_plot(self, fig, ax, canvas, days=1):
        """
        Aggiorna il grafico principale con i dati recenti
        
        Args:
            fig: Figura matplotlib
            ax: Assi matplotlib
            canvas: Canvas tkinter
            days: Numero di giorni da visualizzare
            
        Returns:
            bool: True se l'aggiornamento è riuscito, False altrimenti
        """
        with plot_lock:
            try:
                ax.clear()
                
                # Carica i dati recenti
                timestamps, power_values = self.data_storage.load_recent_data(days=days)
                
                if timestamps and power_values and len(timestamps) > 0 and len(power_values) > 0:
                    # Plot dei dati
                    line, = ax.plot(timestamps, power_values, color=self.colors['primary'], linewidth=2, marker="o", markersize=4)
                    
                    # Configura il formato dell'asse X in base al periodo
                    if days <= 1:  # Visualizzazione giornaliera
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                        ax.set_xlabel("Ora")
                    else:  # Visualizzazione multi-giorno
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
                        ax.set_xlabel("Data e Ora")
                    
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
                    if self.cursor:
                        try:
                            self.cursor.remove()
                        except:
                            pass
                    
                    # Array globali per trovare l'indice corretto
                    all_timestamps = timestamps
                    all_powers = power_values
                    
                    self.cursor = mplcursors.cursor(line, hover=True)
                    
                    @self.cursor.connect("add")
                    def on_cursor_add(sel):
                        try:
                            # Diverso approccio per individuare il punto
                            # Usa le coordinate del target per trovare il punto più vicino
                            target_x, target_y = sel.target
                            
                            # Trova l'indice del punto più vicino
                            # Converti timestamps a numeri per il confronto numerico
                            x_values = mdates.date2num(all_timestamps)
                            x_selected = mdates.date2num(target_x) if hasattr(target_x, 'strftime') else target_x
                            
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
                            logger.error(f"Errore nel tooltip: {e}")
                            sel.annotation.set_text("Errore nell'analisi del punto")
                else:
                    # Nessun dato disponibile
                    ax.text(0.5, 0.5, "Nessun dato disponibile per il periodo selezionato", 
                            horizontalalignment='center', verticalalignment='center',
                            transform=ax.transAxes)
    
                # Personalizzazione del grafico
                ax.set_title("Produzione Energetica", fontsize=14, color=self.colors['primary'])
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
                
                fig.tight_layout()
                canvas.draw_idle()  # Usa draw_idle invece di draw per evitare aggiornamenti eccessivi
                return True
                
            except Exception as e:
                logger.error(f"Errore nell'aggiornamento del grafico: {e}")
                
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
                
                return False
    
    def create_statistics_plot(self, parent_frame, days=30):
        """
        Crea un grafico per le statistiche
        
        Args:
            parent_frame: Frame tkinter in cui inserire il grafico
            days: Numero di giorni da visualizzare
            
        Returns:
            tuple: (figure, axes, canvas) - Oggetti matplotlib e tkinter o None in caso di errore
        """
        try:
            # Calcola le statistiche
            stats = self.statistics.calculate_statistics(days)
            
            if not stats or not stats.get('daily_energy'):
                return None, None, None
            
            # Crea figura e assi
            fig = Figure(figsize=(8, 4), dpi=100)
            ax = fig.add_subplot(111)
            
            # Prepara i dati per il grafico
            days = list(stats['daily_energy'].keys())[-30:]  # Ultimi 30 giorni
            energies = [stats['daily_energy'][day] for day in days]
            
            # Converti le date in oggetti datetime per l'ordinamento
            import datetime
            days_dt = [datetime.datetime.strptime(day, '%Y-%m-%d') for day in days]
            days_energies = sorted(zip(days_dt, energies), key=lambda x: x[0])
            days_dt, energies = zip(*days_energies)
            
            # Formatta le date come stringhe
            days_str = [dt.strftime('%d/%m') for dt in days_dt]
            
            # Crea un grafico a barre
            bars = ax.bar(days_str, energies, color=self.colors['secondary'])
            
            # Aggiungi etichette per i valori
            for i, bar in enumerate(bars):
                height = bar.get_height()
                if height > 0:  # Mostra etichette solo per valori positivi
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                            f'{energies[i]:.1f}',
                            ha='center', va='bottom', rotation=0, fontsize=8)
            
            ax.set_title("Produzione Energetica Giornaliera", fontsize=12, color=self.colors['primary'])
            ax.set_xlabel("Data")
            ax.set_ylabel("Energia (kWh)")
            ax.grid(True, linestyle='--', alpha=0.7, axis='y')
            
            # Migliora l'aspetto del grafico
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Ruota le etichette sull'asse x per maggiore leggibilità
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            
            fig.tight_layout()
            
            # Canvas per il grafico
            canvas = FigureCanvasTkAgg(fig, master=parent_frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Toolbar per il grafico
            toolbar = NavigationToolbar2Tk(canvas, parent_frame)
            toolbar.update()
            
            return fig, ax, canvas
        except Exception as e:
            logger.error(f"Errore nella creazione del grafico statistiche: {e}")
            return None, None, None
    
    def create_monthly_plot(self, parent_frame):
        """
        Crea un grafico con confronto mensile
        
        Args:
            parent_frame: Frame tkinter in cui inserire il grafico
            
        Returns:
            tuple: (figure, axes, canvas) - Oggetti matplotlib e tkinter o None in caso di errore
        """
        try:
            # Calcola i dati mensili
            monthly_energy = self.statistics.calculate_monthly_data()
            
            if not monthly_energy:
                return None, None, None
            
            # Crea figura e assi
            fig = Figure(figsize=(8, 4), dpi=100)
            ax = fig.add_subplot(111)
            
            # Prepara i dati per il grafico
            months = sorted(monthly_energy.keys())
            energies = [monthly_energy[month] for month in months]
            
            # Crea etichette più leggibili
            import datetime
            month_labels = [datetime.datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]
            
            # Crea un grafico a barre
            bars = ax.bar(month_labels, energies, color=self.colors['primary'])
            
            # Aggiungi etichette con i valori sopra le barre
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{energies[i]:.1f}',
                        ha='center', va='bottom', rotation=0)
            
            ax.set_title("Produzione Energetica Mensile", fontsize=12, color=self.colors['primary'])
            ax.set_ylabel("Energia (kWh)")
            ax.grid(True, linestyle='--', alpha=0.7, axis='y')
            
            # Migliora l'aspetto del grafico
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Ruota le etichette sull'asse x per maggiore leggibilità
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
            
            fig.tight_layout()
            
            # Canvas per il grafico
            canvas = FigureCanvasTkAgg(fig, master=parent_frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Toolbar per il grafico
            toolbar = NavigationToolbar2Tk(canvas, parent_frame)
            toolbar.update()
            
            return fig, ax, canvas
        except Exception as e:
            logger.error(f"Errore nella creazione del grafico mensile: {e}")
            return None, None, None