from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import pytz
import json
import os
import google_auth_httplib2
import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import phonenumbers
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

app = Flask(__name__)
CORS(app) 

# --- Configurações do Negócio ---
WORK_START_HOUR = 9
WORK_END_HOUR = 21
SLOT_INTERVAL_MINUTES = 30
APPOINTMENT_DURATION_MINUTES = 60
CLEANUP_BUFFER_MINUTES = 30
CALENDAR_ID = 'primary'
TATUADOR_WHATSAPP = "5511937244363" 
SPREADSHEET_ID = "1ZhLT0v_a-EsvbkZZpKaxlglUpU3XVNOSHQrySTVcRFs"
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# --- Configurações de E-mail ---
ARTIST_EMAIL = "nunes.lucas1357@gmail.com" 
SENDER_EMAIL = "nunes.lucas1357@gmail.com"
SENDER_NAME = "Estúdio de Tatuagem"

# --- CHAVE DA API INSERIDA DIRETAMENTE (APENAS PARA TESTE LOCAL) ---
def load_brevo_key():
    """Lê a chave da API do Brevo de um arquivo JSON local."""
    try:
        with open('brevo_secret.json', 'r') as f:
            secrets = json.load(f)
            return secrets.get('api_key')
    except FileNotFoundError:
        print("AVISO DE SEGURANÇA: O arquivo 'brevo_secret.json' não foi encontrado. Para deploy, use variáveis de ambiente.")
        return os.environ.get('BREVO_API_KEY') # Mantém a compatibilidade com Render/Replit
    except (json.JSONDecodeError, KeyError):
        print("AVISO: Erro ao ler o arquivo 'brevo_secret.json'. Verifique o formato.")
        return None

BREVO_API_KEY = load_brevo_key()
# -------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_authorized_user_file("token.json", SCOPES)
authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
calendar_service = build("calendar", "v3", http=authorized_http, cache_discovery=False)
sheets_service = build("sheets", "v4", http=authorized_http, cache_discovery=False)

@app.route('/api/horarios', methods=['GET'])
def get_available_slots():
    try:
        date_str = request.args.get('date')
        selected_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        time_min = datetime.datetime.combine(selected_date, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(selected_date, datetime.time.max).isoformat() + 'Z'
        
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime'
        ).execute()
        busy_slots_events = events_result.get('items', [])
        
        available_slots = []
        
        slot_start_naive = datetime.datetime.combine(selected_date, datetime.time(WORK_START_HOUR))
        work_end_naive = datetime.datetime.combine(selected_date, datetime.time(WORK_END_HOUR))

        slot_start = LOCAL_TIMEZONE.localize(slot_start_naive)
        work_end_time = LOCAL_TIMEZONE.localize(work_end_naive)

        while slot_start < work_end_time:
            slot_end = slot_start + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINUTES)
            
            if slot_end > work_end_time:
                break

            is_slot_busy = False
            for event in busy_slots_events:
                event_start_str = event['start'].get('dateTime')
                event_end_str = event['end'].get('dateTime')

                if not event_start_str or not event_end_str:
                    continue

                event_start = datetime.datetime.fromisoformat(event_start_str)
                effective_event_end = datetime.datetime.fromisoformat(event_end_str) + datetime.timedelta(minutes=CLEANUP_BUFFER_MINUTES)

                if slot_start < effective_event_end and slot_end > event_start:
                    is_slot_busy = True
                    break 
            
            if not is_slot_busy:
                available_slots.append(slot_start.strftime('%H:%M'))

            slot_start += datetime.timedelta(minutes=SLOT_INTERVAL_MINUTES)
        
        return jsonify(available_slots)

    except Exception as e:
        print(f"Ocorreu um erro em /api/horarios: {e}")
        return jsonify({"error": "Erro interno no servidor."}), 500

@app.route('/api/agendar', methods=['POST'])
def create_booking():
    try:
        data = request.get_json()
        
        telefone_cliente = data.get('telefone')
        if not telefone_cliente:
            return jsonify({"error": "O número de telefone é obrigatório."}), 400
        
        try:
            parsed_number = phonenumbers.parse(telefone_cliente, "BR")
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValueError("Número de telefone inválido.")
        except (phonenumbers.phonenumberutil.NumberParseException, ValueError) as e:
            print(f"Tentativa de agendamento com telefone inválido: {telefone_cliente} | Erro: {e}")
            return jsonify({"error": "O número de telefone fornecido não parece ser válido."}), 400

        start_dt = datetime.datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M')
        end_dt = start_dt + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINUTES)
        event_body = {
            'summary': f"Tatuagem - {data.get('nome', 'Novo Cliente')}",
            'description': f"Contato: {data.get('telefone', 'Não informado')}\n\nIdeia da tatuagem: {data.get('ideia', 'Não informado')}",
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        }

        created_event = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        print(f"Evento criado no Calendar com ID: {created_event['id']}")
        
        try:
            new_row = [data.get('date'), data.get('time'), data.get('nome'), data.get('telefone'), created_event['id']]
            sheets_service.spreadsheets().values().append(spreadsheetId=SPREADSHEET_ID, range="Registros!A1", valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": [new_row]}).execute()
            print("Linha adicionada na planilha com sucesso.")
        except Exception as e:
            print(f"ERRO: Falha ao escrever na planilha do Google Sheets: {e}")

        # Lógica de Envio de E-mail
        try:
            # A chave agora é lida da variável definida no topo do arquivo
            if BREVO_API_KEY and BREVO_API_KEY != "xkeysib-SUA_CHAVE_COMPLETA_DA_API_DO_BREVO_VAI_AQUI":
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key['api-key'] = BREVO_API_KEY
                api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
                
                subject = f"Novo Agendamento: {data.get('nome')} às {data.get('time')}"
                html_content=f"""
                    <h3>✅ Novo agendamento recebido pelo site!</h3>
                    <p><strong>Cliente:</strong> {data.get('nome')}</p>
                    <p><strong>Contato:</strong> {data.get('telefone')}</p>
                    <p><strong>Data:</strong> {data.get('date')}</p>
                    <p><strong>Hora:</strong> {data.get('time')}</p>
                    <p><strong>Ideia:</strong> {data.get('ideia', 'Não informado')}</p>
                    <br>
                    <p><em>O evento já foi adicionado automaticamente na sua Google Agenda.</em></p>
                """
                sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}
                to = [{"email": ARTIST_EMAIL}]
                
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)
                api_instance.send_transac_email(send_smtp_email)
                print("E-mail de notificação enviado via Brevo com sucesso.")
            else:
                print("AVISO: BREVO_API_KEY não foi definida. E-mail de notificação não enviado.")
        except ApiException as e:
            print(f"ERRO: Falha ao enviar e-mail de notificação via Brevo: {e}")

        return jsonify({
            "message": "Agendamento criado com sucesso!", 
            "eventId": created_event['id'],
            "whatsappNumber": TATUADOR_WHATSAPP
        }), 201

    except Exception as e:
        print(f"Ocorreu um erro CRÍTICO em /api/agendar: {e}")
        return jsonify({"error": "Erro interno no servidor."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)