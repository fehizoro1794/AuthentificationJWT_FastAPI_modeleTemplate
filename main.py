from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, engine
from models import Base
from crud import create_user, authenticate_user
from auth import create_access_token, get_current_user

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    await create_user(db, username, email, password)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response
# @app.post("/login")
# async def login(request: Request, email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
#     user = await authenticate_user(db, email, password)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    
#     # Création du token JWT
#     access_token = create_access_token(data={"sub": user.email})
    
#     # Création de la réponse avec un cookie
#     response = RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)
#     response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
#     return response


@app.get("/home")
async def home_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {"request": request, "username": user.username})

@app.get("/detail")
async def detail_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("detail.html", {"request": request, "user": user})

@app.post("/logout")
async def logout(response: RedirectResponse):
    # Supprimer le cookie 'access_token'
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response
