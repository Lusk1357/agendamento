from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import google_auth_httplib2
import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)
CORS(app) 

# --- Configurações do Negócio ---
WORK_START_HOUR = 9
WORK_END_HOUR = 21
SLOT_DURATION_MINUTES = 60
CALENDAR_ID = 'primary'
# --- CONFIGURAÇÃO IMPORTANTE ---
# Adicione o número de WhatsApp do tatuador aqui.
# Formato: CódigoDoPaís + DDD + Número (tudo junto, sem espaços ou símbolos)
TATUADOR_WHATSAPP = "5511954480557" 
# -------------------------

# --- Carregar Credenciais do Token ---
SCOPES = ["https://www.googleapis.com/auth/calendar"]
creds = Credentials.from_authorized_user_file("token.json", SCOPES)

# Cliente HTTP autorizado com timeout maior e cache desabilitado para mais estabilidade
authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
service = build("calendar", "v3", http=authorized_http, cache_discovery=False)

@app.route('/api/horarios', methods=['GET'])
def get_available_slots():
    """
    Calcula e retorna os horários disponíveis para uma data específica.
    """
    try:
        date_str = request.args.get('date')
        selected_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        time_min = datetime.datetime.combine(selected_date, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(selected_date, datetime.time.max).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        busy_slots = events_result.get('items', [])
        
        all_slots = set()
        current_time = datetime.datetime.combine(selected_date, datetime.time(WORK_START_HOUR))
        end_time = datetime.datetime.combine(selected_date, datetime.time(WORK_END_HOUR))

        while current_time < end_time:
            all_slots.add(current_time.strftime('%H:%M'))
            current_time += datetime.timedelta(minutes=SLOT_DURATION_MINUTES)
            
        for event in busy_slots:
            start_str = event['start'].get('dateTime')
            if not start_str: continue

            event_start = datetime.datetime.fromisoformat(start_str)
            
            slot_to_remove = event_start.strftime('%H:%M')
            if slot_to_remove in all_slots:
                all_slots.remove(slot_to_remove)

        return jsonify(sorted(list(all_slots)))

    except HttpError as error:
        print(f"Ocorreu um erro na API do Google: {error}")
        return jsonify({"error": "Erro ao acessar a agenda."}), 500
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        return jsonify({"error": "Erro interno no servidor."}), 500

@app.route('/api/agendar', methods=['POST'])
def create_booking():
    """
    Cria um novo evento (agendamento) no Google Calendar.
    """
    try:
        data = request.get_json()
        
        start_dt = datetime.datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M')
        end_dt = start_dt + datetime.timedelta(minutes=SLOT_DURATION_MINUTES)

        event_body = {
            'summary': f"Tatuagem - {data.get('nome', 'Novo Cliente')}",
            'description': f"Contato: {data.get('telefone', 'Não informado')}\n\nIdeia da tatuagem: {data.get('ideia', 'Não informado')}",
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
        }

        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        
        return jsonify({
            "message": "Agendamento criado com sucesso!", 
            "eventId": created_event['id'],
            "whatsappNumber": TATUADOR_WHATSAPP
        }), 201

    except HttpError as error:
        print(f"Ocorreu um erro na API do Google: {error}")
        return jsonify({"error": "Erro ao criar agendamento na agenda."}), 500
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        return jsonify({"error": "Erro interno no servidor."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)