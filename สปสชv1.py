from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from typing import Optional
import uvicorn

USERNAME = "520186617209"
PASSWORD = "h12345"

app = FastAPI(
    title="NHSO API",
    description="ระบบ API สปสช.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NHSOResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None

def perform_login():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    }
    
    try:
        auth_url = "https://iam.nhso.go.th/realms/nhso/protocol/openid-connect/auth"
        params = {
            "response_type": "code",
            "client_id": "authencode",
            "scope": "openid profile",
            "redirect_uri": "https://authenservice.nhso.go.th/authencode/login/oauth2/code/authencode"
        }
        
        # 1. รับ Login Page
        response = session.get(auth_url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        login_form = soup.find('form', id='kc-form-login')
        
        if not login_form:
            return None, "ไม่สามารถโหลดหน้า Login ได้"
            
        login_action_url = login_form.get('action')
        
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "credentialId": ""
        }
        
        form_headers = headers.copy()
        form_headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://iam.nhso.go.th",
            "Referer": response.url
        })
        
        login_response = session.post(
            login_action_url, 
            data=payload, 
            headers=form_headers, 
            allow_redirects=True,
            timeout=15
        )
        
        if "authenservice.nhso.go.th/authencode" in login_response.url:
            session.get(
                "https://authenservice.nhso.go.th/authencode/claimcode",
                headers=headers,
                timeout=15
            )
            return session, "Login Success"
        
        return None, "Login Failed: ชื่อผู้ใช้หรือรหัสผ่านอาจผิดพลาด"
            
    except Exception as e:
        return None, f"Login Error: {str(e)}"

def get_nhso_data_with_fresh_login(pid: str):
    session, msg = perform_login()
    
    if not session:
        return None, msg

    url = f"https://authenservice.nhso.go.th/authencode/api/nch-personal-fund/search-by-pid?pid={pid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://authenservice.nhso.go.th/authencode/claimcode",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = session.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json(), "ดึงข้อมูลสำเร็จ"
        else:
            return None, f"ไม่พบข้อมูล (HTTP {response.status_code})"
            
    except Exception as e:
        return None, f"API Error: {str(e)}"

@app.get("/api/search", response_model=NHSOResponse)
async def search_by_pid(
    pid: str = Query(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก")
):
    if not pid.isdigit():
        raise HTTPException(status_code=400, detail="PID ต้องเป็นตัวเลขเท่านั้น")
    
    data, message = get_nhso_data_with_fresh_login(pid)
    
    if data:
        return NHSOResponse(success=True, message=message, data=data)
    else:
        return NHSOResponse(success=False, message=message, data=None)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
