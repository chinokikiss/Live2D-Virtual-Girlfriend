from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from utils.other import wait_send_over
from config import Global
import uvicorn
import logging

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
            Global.Agent_return[request.function_id] = request.result
        return {"message": "successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run():
    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    uvicorn.run(app, host="127.0.0.1", port=Global.modelscope['port'], log_level="error")