import sys, json, urllib.request
sys.path.insert(0, '.')
from config.settings import settings
token = settings.TELEGRAM_BOT_TOKEN
if not token or token == 'coloque_aqui_o_token_do_botfather':
    print('TOKEN NAO CONFIGURADO')
    sys.exit(1)
print('Token OK, comprimento:', len(token))
url = f'https://api.telegram.org/bot{token}/getMe'
try:
    resp = urllib.request.urlopen(url, timeout=5)
    data = json.loads(resp.read())
    if data.get('ok'):
        bot_info = data['result']
        print(f"Bot: @{bot_info['username']} (id={bot_info['id']})")
    else:
        print('Erro:', data)
except Exception as e:
    print(f'Erro Telegram API: {e}')
