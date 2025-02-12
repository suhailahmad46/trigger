from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from threading import Timer
import time
import uuid
from collections import deque
import uvicorn
import redis
import json
import requests

app = FastAPI()
security = HTTPBasic()

# Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

triggers = {}
event_logs = deque()

RETENTION_TIME = 2 * 60 * 60  # 2 hours
ARCHIVE_TIME = 48 * 60 * 60  # 48 hours

# Simple authentication
USER_CREDENTIALS = {"admin": "password"}

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if USER_CREDENTIALS.get(credentials.username) == credentials.password:
        return credentials.username
    raise HTTPException(status_code=401, detail="Invalid credentials")

class TriggerRequest(BaseModel):
    type: str
    interval: int = None
    repeat: bool = False
    payload: dict = None

def log_event(trigger_id: str, trigger_type: str, payload: dict = None, test: bool = False):
    timestamp = time.time()
    event_data = {
        "trigger_id": trigger_id,
        "trigger_type": trigger_type,
        "timestamp": timestamp,
        "payload": payload,
        "test": test,
        "archived": False
    }
    
    redis_client.setex(f"event:{timestamp}", RETENTION_TIME, json.dumps(event_data))
    Timer(RETENTION_TIME, archive_event, args=[timestamp]).start()
    Timer(ARCHIVE_TIME, delete_event, args=[timestamp]).start()

def archive_event(timestamp: float):
    event_data = redis_client.get(f"event:{timestamp}")
    if event_data:
        event = json.loads(event_data)
        event["archived"] = True
        redis_client.setex(f"event:{timestamp}", ARCHIVE_TIME - RETENTION_TIME, json.dumps(event))

def delete_event(timestamp: float):
    redis_client.delete(f"event:{timestamp}")

def trigger_event(trigger_id: str):
    trigger = triggers.get(trigger_id)
    if trigger:
        log_event(trigger_id, trigger["type"], trigger.get("payload"))

def schedule_trigger(trigger_id: str, interval: int, repeat: bool):
    if repeat:
        Timer(interval, lambda: [trigger_event(trigger_id), schedule_trigger(trigger_id, interval, repeat)]).start()
    else:
        Timer(interval, lambda: trigger_event(trigger_id)).start()

@app.post("/triggers")
def create_trigger(data: TriggerRequest, username: str = Depends(authenticate)):
    trigger_id = str(uuid.uuid4())

    if data.type == "api":
        if not data.payload or "name" not in data.payload:
            raise HTTPException(status_code=400, detail="API trigger must include a 'name' in the payload")
        
    triggers[trigger_id] = data.model_dump()
    
    if data.type == "scheduled" and data.interval:
        schedule_trigger(trigger_id, data.interval, data.repeat)
    
    return {"trigger_id": trigger_id}

@app.post("/fire/{trigger_id}")
def fire_trigger(trigger_id: str, username: str = Depends(authenticate)):
    trigger = triggers.get(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if trigger["type"] != "api":
        raise HTTPException(status_code=400, detail="Trigger is not an API trigger")
    
    # Expect the payload to include a 'name' key
    name = trigger.get("payload", {}).get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Payload must include 'name'")
    
    # Call the external API with the provided name
    url = f"https://api.agify.io/?name={name}"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error calling external API")
    
    response_data = response.json()
    # Log the event including the external API's response
    log_event(trigger_id, trigger["type"], {"api_response": response_data})
    return {"message": "API trigger fired", "api_response": response_data}

@app.get("/triggers")
def list_triggers(username: str = Depends(authenticate)):
    return triggers

@app.put("/triggers/{trigger_id}")
def edit_trigger(trigger_id: str, data: TriggerRequest, username: str = Depends(authenticate)):
    if trigger_id not in triggers:
        raise HTTPException(status_code=404, detail="Trigger not found")
    
    triggers[trigger_id] = data.dict()
    return {"message": "Trigger updated"}

@app.delete("/triggers/{trigger_id}")
def delete_trigger(trigger_id: str, username: str = Depends(authenticate)):
    if trigger_id in triggers:
        del triggers[trigger_id]
    return {"message": "Trigger deleted"}

@app.post("/test")
def test_trigger(data: TriggerRequest, username: str = Depends(authenticate)):
    trigger_id = str(uuid.uuid4())
    log_event(trigger_id, data.type, data.payload, test=True)
    return {"message": "Test event triggered"}

@app.get("/events")
def get_events(archived: bool = False, username: str = Depends(authenticate)):
    keys = redis_client.keys("event:*")
    events = []
    for key in keys:
        event_data = json.loads(redis_client.get(key))
        if event_data["archived"] == archived:
            events.append(event_data)
    return events

@app.delete("/clear_events")
def clear_events(username: str = Depends(authenticate)):
    keys = redis_client.keys("event:*")
    if keys:
        redis_client.delete(*keys)
    return {"message": "Redis events cleared."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
