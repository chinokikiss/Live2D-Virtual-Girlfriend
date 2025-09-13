import requests

def identify_role(base64):
    url = "https://api.animetrace.com/v1/search"
    data = {
        'base64': base64,
        'is_multi': "0",
        'model': 'pre_stable',
        'ai_detect': "0"
    }
    response = requests.post(url, data=data).json()
    if response['data']:
        return response['data'][0]['character'][0]
    else:
        return '识别不到动漫角色'