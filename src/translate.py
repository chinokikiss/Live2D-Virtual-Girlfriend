import hashlib
import time
import json
import requests
from config import Global

# 百度
def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": Global.baidu_api_key, "client_secret": Global.baidu_secret_key}
    return str(requests.post(url, params=params).json().get("access_token"))

# 小牛
def generate_auth_str(params):
    sorted_params = sorted(list(params.items()) + [('apikey', Global.niutrans_api_key)], key=lambda x: x[0])
    param_str = '&'.join([f'{key}={value}' for key, value in sorted_params])
    md5 = hashlib.md5()
    md5.update(param_str.encode('utf-8'))
    auth_str = md5.hexdigest()
    return auth_str

def translate(from_l, to_l, src_t):
    if Global.baidu_api_key and Global.baidu_secret_key:
        url = "https://aip.baidubce.com/rpc/2.0/mt/texttrans/v1?access_token=" + access_token
        
        payload = json.dumps({
            "from": from_l,
            "to": to_l,
            "q": src_t
        }, ensure_ascii=False)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
        return response.json()["result"]["trans_result"][0]["dst"]
    
    elif Global.niutrans_app_id and Global.niutrans_api_key:
        data = {
            'from': from_l,
            'to': to_l,
            'appId': Global.niutrans_app_id,
            'timestamp': int(time.time()),
            'srcText': src_t
        }

        auth_str = generate_auth_str(data)
        data['authStr'] = auth_str
        response = requests.post("https://api.niutrans.com/v2/text/translate", data=data)
        try:
            return response.json()['tgtText']
        except:
            print(from_l, to_l, [src_t], response.json())
            return ''
        
    else:
        l = {'zh':'ZH_CN', 'en':'EN', 'ja':'JA'}
        from_l = l[from_l]
        to_l = l[to_l]
        response = requests.get(f'https://api.pearktrue.cn/api/translate?text={src_t}&type={from_l}2{to_l}')
        return response.json()['data']['translate']

if Global.baidu_api_key and Global.baidu_secret_key:
    access_token = get_access_token()