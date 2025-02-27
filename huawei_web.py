import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
import time
import sys
from fusion_solar_py.client import FusionSolarClient

# Credenziali di accesso
USERNAME = "tomarocco@libero.it"
PASSWORD = "logistica2024"
SUBDOMAIN = "uni005eu5"
CAPTCHA_MODEL_PATH = r"captcha_huawei.onnx"

# Creazione del client con il solver CAPTCHA
client = FusionSolarClient(
    USERNAME, PASSWORD,
    captcha_model_path=CAPTCHA_MODEL_PATH,
    huawei_subdomain=SUBDOMAIN
)

# Inizializza l'app Dash con Bootstrap
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server

# Variabili per il grafico
timestamps = []
power_values = []
log_messages = ["[INFO] Dashboard avviata"]

# **Layout della Dashboard**
app.layout = dbc.Container([
    dcc.Store(id="error-state", data=False),  # Store per lo stato di errore

    # **Schermo di errore ENORME e lampeggiante**
    html.Div(
        html.H1("ERRORE", id="error-text", style={
            "fontSize": "120px",
            "fontWeight": "bold",
            "color": "white",
            "textAlign": "center"
        }),
        id="error-screen",
        style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "backgroundColor": "red",
            "display": "none",
            "justifyContent": "center",
            "alignItems": "center",
            "zIndex": "9999",
            "animation": "flash 1s infinite"
        }
    ),

    # **CSS per il lampeggiamento**
    html.Div([
        dcc.Markdown("""
        <style>
        @keyframes flash {
            0% { background-color: red; }
            50% { background-color: black; }
            100% { background-color: red; }
        }
        </style>
        """, dangerously_allow_html=True)
    ]),

    dbc.Row([
        dbc.Col(html.H1("🌞 Monitoraggio FV GIUMENTARE", className="text-center text-light mt-3"), width=12)
    ]),

    # **Notifica avanzata**
    dbc.Alert(id="notification", is_open=False, duration=5000, className="text-center"),

    dbc.Row([
        dbc.Col([
            dcc.Graph(id='live-graph')
        ], width=8),

        dbc.Col([
            html.Div([
                html.H3("⚡ Dati in Tempo Reale", className="text-center text-light"),
                html.P(id="current-power", className="h3 text-center text-primary"),
                html.P(id="daily-production", className="h5 text-center text-info"),
                html.P(id="total-production", className="h5 text-center text-success"),
            ], className="p-3 border rounded bg-dark"),

            html.Div([
                html.H4("📊 Stato dell'Inverter", className="text-center text-light"),
                html.P(id="inverter-status", className="h5 text-center text-warning")
            ], className="p-3 border rounded bg-secondary mt-3"),

            # **Pulsanti**
            dbc.Button("⚠️ Simula Errore", id="simulate-error-btn", color="danger", className="mt-3 mb-3 w-100"),
            dbc.Button("🛑 TERMINA", id="terminate-button", color="dark", className="mt-3 w-100")
        ], width=4)
    ]),

    dbc.Row([
        dbc.Col(html.H5("📝 Log di Sistema", className="text-center text-light mt-3"), width=12),
        dbc.Col([
            dcc.Textarea(
                id="log-box",
                value="\n".join(log_messages),
                style={"width": "100%", "height": "200px", "backgroundColor": "#222", "color": "white"},
                readOnly=True
            )
        ], width=12)
    ]),

    dcc.Interval(id='interval-component', interval=5000, n_intervals=0)  # **Aggiornamento ogni 5s**
])

# **Callback per aggiornare il grafico e i dati**
@app.callback(
    [Output('live-graph', 'figure'),
     Output('current-power', 'children'),
     Output('daily-production', 'children'),
     Output('total-production', 'children'),
     Output('inverter-status', 'children'),
     Output('notification', 'children'),
     Output('notification', 'is_open'),
     Output('log-box', 'value')],
    [Input('interval-component', 'n_intervals')]
)
def update_data(n_intervals):
    global timestamps, power_values, log_messages

    try:
        # Recupero dati da FusionSolar
        stats = client.get_power_status()
        
        current_power = stats.current_power_kw
        daily_production = stats.energy_today_kwh
        total_production = stats.energy_kwh
        inverter_status = "✅ Operativo" if current_power > 0 else "⚠️ Attenzione: Nessuna Produzione"

        # Aggiorna dati per il grafico
        timestamps.append(time.strftime("%H:%M:%S"))
        power_values.append(current_power)

        if len(timestamps) > 20:
            timestamps.pop(0)
            power_values.pop(0)

        # Crea il grafico
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timestamps, y=power_values, mode='lines+markers', name='Potenza (kW)'))
        fig.update_layout(title="📈 Andamento Potenza Attuale", xaxis_title="Tempo", yaxis_title="Potenza (kW)", template="plotly_dark")

        # Log aggiornato
        log_messages.append(f"[{time.strftime('%H:%M:%S')}] Potenza: {current_power} kW")
        if len(log_messages) > 15:
            log_messages.pop(0)

        # Notifica per bassa produzione
        notification_text = ""
        show_notification = False
        if current_power < 5:
            notification_text = "⚠️ Attenzione: Potenza molto bassa!"
            show_notification = True

        return fig, f"⚡ Potenza attuale: {current_power} kW", f"🌞 Produzione oggi: {daily_production} kWh", f"🔋 Produzione totale: {total_production} kWh", inverter_status, notification_text, show_notification, "\n".join(log_messages)

    except Exception as e:
        return go.Figure(), "Errore nel recupero dati", "", "", "⚠️ Errore", "❌ Errore di comunicazione con l'impianto!", True, "\n".join(log_messages)


# **Callback per la simulazione di errore**
@app.callback(
    Output('error-screen', 'style'),
    Input('simulate-error-btn', 'n_clicks'),
    prevent_initial_call=True
)
def simulate_error(n_clicks):
    return {"display": "flex"} if n_clicks % 2 == 1 else {"display": "none"}

# **Callback per TERMINARE l'app**
@app.callback(
    Output('terminate-button', 'children'),
    Input('terminate-button', 'n_clicks'),
    prevent_initial_call=True
)
def terminate_app(n_clicks):
    client.log_out()
    sys.exit("Chiusura dell'applicazione richiesta.")

# **Avvia il server Dash**
if __name__ == '__main__':
    app.run_server(debug=True)
