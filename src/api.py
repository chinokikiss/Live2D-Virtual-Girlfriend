from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from utils.other import wait_send_over
from config import Global
import uvicorn
import logging
import time

app = FastAPI()

class ReturnRequest(BaseModel):
    function_name: str
    function_id: int
    result: str

@app.post("/return")
async def tool_call(request: ReturnRequest):
    try:
        if request.function_name == 'send_audio_text':
            wait_send_over()
            Global.send_audio_text(request.result, tool=False)

        else:
            wait_send_over()

            tool_call_id = f"call_{int(time.time()*1000)}"
            Global.my_agent.messages.append({
                'role': 'assistant', 
                'content': '', 
                'tool_calls': [
                    {
                        'id': tool_call_id,
                        'type': 'function',
                        'function': {
                            'name': request.function_name,
                            'arguments': ''
                        }
                    }
                ]
            })
            Global.my_agent.messages.append({
                'role': 'tool',
                'content': request.result,
                'tool_call_id': tool_call_id
            })
            Global.my_agent.messages.append({'role':'user', 'content':'查看工具返回结果'})

            Global.sounds_player.play('exp.wav')
            Global.bubble_widget.show_bubble("工具调用返回结果~")

            Global.my_agent.send_audio_text(tool=False)

        return {"message": "successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run():
    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    uvicorn.run(app, host="127.0.0.1", port=Global.modelscope['port'], log_level="error")