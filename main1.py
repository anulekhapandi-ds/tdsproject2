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
import mimetypes

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

async def get_llm_answer(question: str, context: str = "") -> str:
    """Query GPT-4o-mini via AI Proxy with optional context."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": f"{question}\nContext: {context}"}]}
        async with session.post(AI_PROXY_URL, json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result["choices"][0]["message"]["content"]
            raise HTTPException(status_code=response.status, detail="AI Proxy Error")

async def extract_text_from_file(file_path: str) -> str:
    """Extract text content from supported file formats."""
    mime_type, _ = mimetypes.guess_type(file_path)
    print(f"📂 Processing file: {file_path} (MIME: {mime_type})")  # Debug log

    try:
        if file_path.endswith(".txt"):
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                return await f.read()
        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            return df.to_string()
        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
            return df.to_string()
        elif file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(UPLOAD_DIR)
                extracted_files = [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR)]
                return "\n".join([await extract_text_from_file(f) for f in extracted_files])
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime_type}")
    except Exception as e:
        print(f"❌ File Processing Error: {e}")  # Debug log
        raise HTTPException(status_code=400, detail=f"File Processing Error: {e}")

@app.post("/api/", response_model=AnswerResponse)
async def solve_question(question: str = Form(...), file: UploadFile = File(None)):
    """Handles question processing and optional file uploads."""
    print(f"📥 Received Question: {question}")  # Debug log
    context = ""

    if file:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        try:
            async with aiofiles.open(file_path, "wb") as out_file:
                await out_file.write(await file.read())
            context = await extract_text_from_file(file_path)
        except Exception as e:
            print(f"❌ File Save Error: {e}")  # Debug log
            raise HTTPException(status_code=400, detail=f"File Save Error: {e}")
    else:
        print("⚠️ No file received!")  # Debug log

    answer = await get_llm_answer(question, context)
    return {"answer": answer}

if __name__ == "__main__":
    # Start ngrok in a separate thread
    def start_ngrok():
        authtoken = "2soV7DjCcAX7D3igQGcwlR0vYPr_7DzL5qthoB7nUEt75UDLC"
        ngrok.set_auth_token(authtoken)
        public_url = ngrok.connect(8000)
        print(f"🌍 Public API URL: {public_url}")

    threading.Thread(target=start_ngrok, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
