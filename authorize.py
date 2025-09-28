from google_auth_oauthlib.flow import InstalledAppFlow

# Permissões completas de leitura e escrita no calendário
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    """
    Executa o fluxo de autorização e salva o token.json.
    Este script só precisa ser executado uma vez.
    """
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    # Salva as credenciais para o backend usar
    with open("token.json", "w") as token:
        token.write(creds.to_json())
    
    print("O arquivo 'token.json' foi criado com sucesso! Agora você pode rodar o app.py.")

if __name__ == "__main__":
    main()