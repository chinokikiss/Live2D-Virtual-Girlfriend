import base64
import os
from openai import OpenAI
from PIL import Image
from config import Global
client = OpenAI(api_key=Global.modelscope['api_key'], base_url=Global.modelscope['base_url'])

def image_to_base64(image_path):  
    with open(image_path, "rb") as image_file:  
        return "data:image/jpeg;base64," + base64.b64encode(image_file.read()).decode('utf-8')

def VLM(text, imgs, is_path=True):
    messages = [{'role':'user', 'content':[]}]
    if is_path:
        for file in imgs:
            file_name = os.path.basename(file)
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']:
                img = Image.open(file)
                messages[0]['content'].append({'type': 'text', 'text': f'\n*{file}*{img.size}\n'})
                messages[0]['content'].append({'type': 'image_url', 'image_url': {'url': image_to_base64(file)}, 'max_pixels': 50176})
                img.close()
    else:
        for file in imgs:
            messages[0]['content'].append({'type': 'image_url', 'image_url': {'url': f"data:image/png;base64,{file}"}, 'max_pixels': 50176})
    
    messages[0]['content'].append({'type': 'text', 'text': text})

    response = client.chat.completions.create(
        model='Qwen/Qwen2.5-VL-72B-Instruct',
        messages=messages
    )

    return response.choices[0].message.content