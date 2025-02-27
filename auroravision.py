import dash
from dash import dcc, html
import plotly.graph_objs as go
import requests
import datetime
from dash.dependencies import Input, Output
import pandas as pd

# Configurazione dell'app Flask
USERNAME = "tomacarburanti"
PASSWORD = "Riccardo@01"
ENTITY_IDS = ["14370648", "14354021", "14349631"]
BASE_URL = "https://easyview.auroravision.net/easyview/services/gmi/summary/GenerationEnergy.json"

# Funzione per ottenere i dati di produzione
def get_production():
    session = requests.Session()
    login_url = "https://www.auroravision.net/ums/v1/login?setCookie=true"
    
    # Effettua login
    response = session.get(login_url, auth=requests.auth.HTTPBasicAuth(USERNAME, PASSWORD))
    print(f"Login response: {response.status_code}")  # Log di risposta per il login
    
    # Gestione date
    start_date = datetime.date.today().strftime("%Y%m%d")
    end_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    
    production_data = {}
    
    for entity in ENTITY_IDS:
        url = f"{BASE_URL}?type=GenerationEnergy&eids={entity}&tz=US%2FPacific&start={start_date}&end={end_date}&binSize=Hour"
        response = session.get(url)
        
        # Log della risposta dell'API
        print(f"API Response for {entity}: {response.status_code}")
        
        if response.status_code == 200:
            production_data[entity] = response.json()
        else:
            production_data[entity] = {"error": "Failed to retrieve data"}
    
    print("Production data received:", production_data)  # Log dei dati ricevuti
    return production_data

# Inizializzazione dell'app Dash
app = dash.Dash(__name__)

# Layout dell'app
app.layout = html.Div([
    html.H1("Monitoraggio Impianti"),
    dcc.Interval(
        id="interval-update",
        interval=3 * 1000,  # Aggiorna ogni 3 secondi
        n_intervals=0
    ),
    html.Div(id="live-graphs")
])

# Callback per aggiornare i grafici
@app.callback(
    Output("live-graphs", "children"),
    Input("interval-update", "n_intervals")
)
def update_graph(n_intervals):
    data = get_production()  # Ottieni i dati di produzione
    graphs = []

    # Verifica se i dati sono nel formato corretto
    if not data:
        return [html.Div("No data available at the moment")]

    for entity_id, entity_data in data.items():
        print(f"Entity data for {entity_id}: {entity_data}")  # Log dei dati per ogni entità
        
        # Verifica se 'fields' è presente nei dati
        if 'fields' in entity_data:
            for field in entity_data['fields']:
                # Verifica se 'values' è presente nel campo
                if 'values' in field:
                    values = [entry.get('value', None) for entry in field['values']]  # Usa get() per evitare KeyError
                    labels = [entry.get('startLabel', '') for entry in field['values']]  # Usa get() per evitare KeyError
                    
                    # Crea il grafico con i dati di valori e etichette
                    graphs.append(dcc.Graph(
                        id=f'graph-{entity_id}',
                        figure={
                            'data': [
                                {'x': labels, 'y': values, 'type': 'line', 'name': field['entityName']}
                            ],
                            'layout': {
                                'title': field['entityName'],
                                'xaxis': {'title': 'Time'},
                                'yaxis': {'title': 'Generation Energy (kWh)'},
                            }
                        }
                    ))
        else:
            graphs.append(html.Div(f"Error: No fields found for {entity_id}"))

    if not graphs:
        return [html.Div("No data to display")]

    return graphs

# Avvio dell'app
if __name__ == '__main__':
    app.run_server(debug=True)
