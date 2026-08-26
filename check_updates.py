import sys, json, urllib.request
sys.path.insert(0, '.')
from config.settings import settings
token = settings.TELEGRAM_BOT_TOKEN
url = f'https://api.telegram.org/bot{token}/getUpdates?limit=10&timeout=0'
try:
    resp = urllib.request.urlopen(url, timeout=10)
    data = json.loads(resp.read())
    if data.get('ok'):
        updates = data.get('result', [])
        print(f'Total de updates: {len(updates)}')
        for u in updates[-5:]:
            msg = u.get('message', {})
            from_id = msg.get('from',{}).get('id')
            text = msg.get('text', '(sem texto)')
            print(f'  Update {u["update_id"]}: de {from_id} | texto: {text[:50]}')
    else:
        print(f'Erro API: {data}')
except Exception as e:
    print(f'Erro: {e}')
