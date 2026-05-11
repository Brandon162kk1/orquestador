# MicrosoftGraph/graph_client.py

import msal
import requests
import sys

class GraphMailClient:

    def __init__(
        self,
        tenant_id,
        client_id,
        client_secret,
        scope,
        email_account
    ):

        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = [scope]

        self.authority = (
            f"https://login.microsoftonline.com/{tenant_id}"
        )

        self.email_account = email_account

        self.graph_url = (
            f"https://graph.microsoft.com/v1.0/users/{email_account}/messages"
        )

    def obtener_token(self):

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

        result = app.acquire_token_for_client(
            scopes=self.scope
        )

        if "access_token" in result:
            return result["access_token"]

        print(
            "Error token:",
            result.get("error"),
            result.get("error_description")
        )

        sys.exit(1)

    def obtener_correos_no_leidos(self):

        token = self.obtener_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            self.graph_url,
            headers=headers,
            params={"$filter": "isRead eq false"}
        )

        if response.status_code != 200:
            print(f"❌ Error obteniendo correos: {response.text}")
            return [], token

        return response.json().get("value", []), token

    def marcar_como_leido(self, message_id, token):

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "isRead": True
        }

        response = requests.patch(
            f"{self.graph_url}/{message_id}",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            print("🟢 Correo marcado como leído")
        else:
            print(f"❌ Error marcando leído: {response.text}")