import sys, json, urllib.request
sys.path.insert(0, '.')
from config.settings import settings
token = settings.TELEGRAM_BOT_TOKEN

url = 'https://api.telegram.org/bot' + token + '/getWebhookInfo'
resp = urllib.request.urlopen(url, timeout=5)
data = json.loads(resp.read())
info = data.get('result', {})
print('Webhook URL:', info.get('url', '-'))
print('Pending updates:', info.get('pending_update_count', 0))
print('Last error msg:', info.get('last_error_message', '-'))

url2 = 'https://api.telegram.org/bot' + token + '/getUpdates?limit=3'
resp2 = urllib.request.urlopen(url2, timeout=5)
data2 = json.loads(resp2.read())
updates = data2.get('result', [])
print('Updates:', len(updates))
for u in updates:
    msg = u.get('message', {})
    from_id = msg.get('from', {}).get('id')
    text = msg.get('text', '-')
    print('  Update ' + str(u['update_id']) + ': from=' + str(from_id) + ' text=' + text[:40])
