from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

# Success case (dummy keys; SDK call may still fail if invalid)
resp = client.post('/api/login', json={
	'api_key': 'x',
	'api_secret': 'y',
	'session_key': 'z',
})
print('SUCCESS attempt:', resp.status_code, resp.json())

# Missing field -> should return 422 from Pydantic
resp2 = client.post('/api/login', json={
	'api_key': 'only',
})
print('VALIDATION attempt:', resp2.status_code, resp2.json())
