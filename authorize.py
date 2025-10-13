from google_auth_oauthlib.flow import InstalledAppFlow

# Permissões completas para Calendário, Planilhas e Google Drive.
SCOPES = [
    "https://www.googleapis.com/auth/calendar", 
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

def main():
    """
    Executa o fluxo de autorização e salva o token.json.
    Este script só precisa ser executado uma vez, ou sempre que
    as permissões (SCOPES) forem alteradas.
    """
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    # Salva as credenciais para o backend usar
    with open("token.json", "w") as token:
        token.write(creds.to_json())
    
    print("O arquivo 'token.json' foi criado/atualizado com sucesso!")
    print("Ele agora contém as permissões para Google Calendar, Sheets e Drive.")
    print("Você já pode rodar o app.py.")

if __name__ == "__main__":
    main()