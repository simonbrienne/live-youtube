from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=8080)
    print("Access Token:", creds.token)
    print("Refresh Token:", creds.refresh_token)

if __name__ == "__main__":
    main()