from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import pytz
import json
import os
import io
import google_auth_httplib2
import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
import phonenumbers
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

app = Flask(__name__)
CORS(app) 

# --- Configurações do Negócio (sem alteração) ---
WORK_START_HOUR = 9
WORK_END_HOUR = 21
SLOT_INTERVAL_MINUTES = 30
APPOINTMENT_DURATION_MINUTES = 60
CLEANUP_BUFFER_MINUTES = 30
CALENDAR_ID = 'primary'
TATUADOR_WHATSAPP = "5511937244363" 
SPREADSHEET_ID = "1ZhLT0v_a-EsvbkZZpKaxlglUpU3XVNOSHQrySTVcRFs"
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')
DRIVE_FOLDER_ID = "1dre0bbyyz2jabjVK3fq2hVcGRv-LWE98" 

# --- Configurações de E-mail (sem alteração) ---
ARTIST_EMAIL = "nunes.lucas1357@gmail.com" 
SENDER_EMAIL = "nunes.lucas1357@gmail.com"
SENDER_NAME = "Estúdio de Tatuagem"

def load_brevo_key():
    try:
        with open('brevo_secret.json', 'r') as f:
            secrets = json.load(f)
            return secrets.get('api_key')
    except FileNotFoundError:
        print("AVISO DE SEGURANÇA: O arquivo 'brevo_secret.json' não foi encontrado.")
        return os.environ.get('BREVO_API_KEY')
    except (json.JSONDecodeError, KeyError):
        print("AVISO: Erro ao ler o arquivo 'brevo_secret.json'.")
        return None

BREVO_API_KEY = load_brevo_key()
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

@app.route('/api/horarios', methods=['GET'])
def get_available_slots():
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=30))
        calendar_service = build("calendar", "v3", http=authorized_http, cache_discovery=False)
        
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
            if slot_end > work_end_time: break
            is_slot_busy = False
            for event in busy_slots_events:
                event_start = datetime.datetime.fromisoformat(event['start'].get('dateTime'))
                effective_event_end = datetime.datetime.fromisoformat(event['end'].get('dateTime')) + datetime.timedelta(minutes=CLEANUP_BUFFER_MINUTES)
                if slot_start < effective_event_end and slot_end > event_start:
                    is_slot_busy = True
                    break 
            if not is_slot_busy:
                available_slots.append(slot_start.strftime('%H:%M'))
            slot_start += datetime.timedelta(minutes=SLOT_INTERVAL_MINUTES)
        return jsonify(available_slots)
    except Exception as e:
        print(f"Ocorreu um erro em /api/horarios: {e}")
        return jsonify({"error": "Erro interno no servidor ao buscar horários."}), 500

@app.route('/api/agendar', methods=['POST'])
def create_booking():
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
        calendar_service = build("calendar", "v3", http=authorized_http, cache_discovery=False)
        sheets_service = build("sheets", "v4", http=authorized_http, cache_discovery=False)
        drive_service = build("drive", "v3", http=authorized_http, cache_discovery=False)
        
        data = request.form
        image_file = request.files.get('ideia-imagem')
        telefone_cliente = data.get('telefone')
        if not telefone_cliente: return jsonify({"error": "O número de telefone é obrigatório."}), 400
        
        try:
            if not phonenumbers.is_valid_number(phonenumbers.parse(telefone_cliente, "BR")):
                raise ValueError("Número inválido.")
        except Exception as e:
            return jsonify({"error": "O número de telefone fornecido não parece ser válido."}), 400

        image_link = "Nenhuma imagem enviada."
        if image_file:
            try:
                file_metadata = {'name': f"Ref_{data.get('nome')}_{data.get('date')}.jpg", 'parents': [DRIVE_FOLDER_ID]}
                media = MediaIoBaseUpload(io.BytesIO(image_file.read()), mimetype=image_file.mimetype, resumable=True)
                uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
                drive_service.permissions().create(fileId=uploaded_file.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()
                image_link = uploaded_file.get('webViewLink')
                print(f"Imagem enviada para o Google Drive. Link: {image_link}")
            except HttpError as error:
                print(f"ERRO: Falha ao fazer upload para o Google Drive: {error}")
                image_link = "Erro ao fazer upload da imagem."
        
        description_text = (f"Contato: {data.get('telefone', 'N/A')}\n\nIdeia: {data.get('ideia', 'N/A')}\n\nReferência: {image_link}")
        start_dt = datetime.datetime.strptime(f"{data['date']} {data['time']}", '%Y-%m-%d %H:%M')
        end_dt = start_dt + datetime.timedelta(minutes=APPOINTMENT_DURATION_MINUTES)
        event_body = {
            'summary': f"Tatuagem - {data.get('nome', 'Novo Cliente')}", 'description': description_text,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        }
        created_event = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        
        # --- SEÇÃO DO RELATÓRIO NA PLANILHA (SIMPLIFICADA) ---
        try:
            # 1. Formata a data e hora do agendamento para um formato legível
            agendamento_formatado = start_dt.strftime('%d/%m/%Y %H:%M')

            # 2. Define a nova estrutura da linha com apenas os 3 campos solicitados
            new_row_values = [
                agendamento_formatado,
                data.get('nome'),
                data.get('telefone')
            ]
            
            # 3. Verifica se a planilha está vazia para adicionar o cabeçalho
            range_to_check = 'Registros!A1:A1'
            result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_to_check).execute()
            is_sheet_empty = not result.get('values')

            if is_sheet_empty:
                # 4. Define os novos cabeçalhos simplificados
                headers = [["Agendamento", "Nome do Cliente", "Telefone"]]
                sheets_service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range="Registros!A1",
                    valueInputOption="USER_ENTERED",
                    body={"values": headers}
                ).execute()
                print("Cabeçalhos simplificados adicionados à planilha.")

            # 5. Adiciona a nova linha com os dados do agendamento
            sheets_service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, 
                range="Registros!A1", 
                valueInputOption="USER_ENTERED", 
                insertDataOption="INSERT_ROWS", 
                body={"values": [new_row_values]}
            ).execute()
            print("Relatório simplificado atualizado na planilha com sucesso.")

        except Exception as e:
            print(f"ERRO: Falha ao escrever na planilha do Google Sheets: {e}")
        # --- FIM DA SEÇÃO DO RELATÓRIO ---

        try:
            if BREVO_API_KEY:
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key['api-key'] = BREVO_API_KEY
                api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
                html_content=f"""<h3>✅ Agendamento recebido!</h3><p><strong>Cliente:</strong> {data.get('nome')}</p><p><strong>Contato:</strong> {data.get('telefone')}</p><p><strong>Data:</strong> {data.get('date')} às {data.get('time')}</p><p><strong>Ideia:</strong> {data.get('ideia', 'N/A')}</p><p><strong>Referência:</strong> <a href="{image_link}">{image_link}</a></p>"""
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=[{"email": ARTIST_EMAIL}], html_content=html_content, sender={"name": SENDER_NAME, "email": SENDER_EMAIL}, subject=f"Novo Agendamento: {data.get('nome')}")
                api_instance.send_transac_email(send_smtp_email)
                print("E-mail de notificação enviado via Brevo com sucesso.")
            else:
                print("AVISO: BREVO_API_KEY não definida. E-mail não enviado.")
        except ApiException as e:
            print(f"ERRO: Falha ao enviar e-mail via Brevo: {e}")

        return jsonify({"message": "Agendamento criado!", "eventId": created_event['id'], "whatsappNumber": TATUADOR_WHATSAPP}), 201
    except Exception as e:
        print(f"ERRO CRÍTICO em /api/agendar: {e}")
        return jsonify({"error": "Erro interno no servidor ao agendar."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)