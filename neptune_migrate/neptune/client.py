from urllib.parse import urlencode

import requests


class NeptuneClient:
    def __init__(self, auth, config):
        self.auth = auth
        self.config = config

    def update_query(self, query):
        return self.execute_query(query, body_payload="update")

    def execute_query(self, query, body_payload="query"):
        request_params = {
            "url": f"{self.config.get('aws_neptune_url')}/sparql",
            "method": "POST",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Connection": "close",
            },
            "data": urlencode({body_payload: query}),
            "timeout": 60,
        }
        response = requests.request(**request_params, auth=self.auth)
        response.raise_for_status()

        return response.json()
