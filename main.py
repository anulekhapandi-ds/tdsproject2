from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from pydantic import BaseModel
import aiohttp
import aiofiles
import zipfile
import os
import pandas as pd
import uvicorn
from pyngrok import ngrok
import threading

app = FastAPI()
AI_PROXY_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
AIPROXY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjMwMDA4ODBAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.KpMaVgWdPhDF3a3Xy3V8HPM45rxPSZxpzNvyepVqz-4"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class AnswerResponse(BaseModel):
    answer: str

@app.get("/")
def read_root():
    return {"message": "FastAPI server is running!"}

async def get_llm_answer(question: str) -> str:
    """Query GPT-4o-mini via AI Proxy."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": question}]}
        async with session.post(AI_PROXY_URL, json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result["choices"][0]["message"]["content"]
            raise HTTPException(status_code=response.status, detail="AI Proxy Error")

async def extract_csv_answer(zip_path: str) -> str:
    """Extract CSV and return the value in 'answer' column."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(UPLOAD_DIR)
        csv_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".csv")]
        if csv_files:
            df = pd.read_csv(os.path.join(UPLOAD_DIR, csv_files[0]))
            if "answer" in df.columns:
                return str(df["answer"].iloc[0])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV Processing Error: {e}")
    return "No answer found in CSV."

@app.post("/api/", response_model=AnswerResponse)
async def solve_question(question: str = Form(...), file: UploadFile = File(None)):
    """Handles question processing and optional file uploads."""
    if file:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)
        answer = await extract_csv_answer(file_path)
    else:
        answer = await get_llm_answer(question)
    return {"answer": answer}

if __name__ == "__main__":
    # Start ngrok in a separate thread
    def start_ngrok():
        authtoken = "2soV7DjCcAX7D3igQGcwlR0vYPr_7DzL5qthoB7nUEt75UDLC"
        ngrok.set_auth_token(authtoken)
        public_url = ngrok.connect(8000)
        print(f"Public API URL: {public_url}")

    threading.Thread(target=start_ngrok, daemon=True).start()

    # Run FastAPI server in main thread
    uvicorn.run(app, host="0.0.0.0", port=8000)
