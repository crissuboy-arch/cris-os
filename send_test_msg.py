import json, urllib.request, sys
sys.path.insert(0, '.')
from config.settings import settings
token = settings.TELEGRAM_BOT_TOKEN
user_id = str(settings.TELEGRAM_ALLOWED_USER_ID or 6460872429)

# Send test message simulating user
msg = "TESTE CRIS 123"
data = json.dumps({"chat_id": user_id, "text": msg}).encode()
url = f'https://api.telegram.org/bot{token}/sendMessage'
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=10)
result = json.loads(resp.read())
if result.get('ok'):
    print('Mensagem enviada:', msg)
    print('Message ID:', result['result']['message_id'])
else:
    print('Erro:', result)
