Pour créer un projet FastAPI avec authentification JWT et un affichage avec Jinja2 pour la base de données PostgreSQL, suivez les étapes ci-dessous. Nous utiliserons FastAPI pour gérer l'API et l'authentification, SQLAlchemy pour l'accès à la base de données, et Jinja2 pour le rendu des templates HTML.

Voici le guide détaillé pour le projet.

### 1. Installer les dépendances

Vous aurez besoin de FastAPI, SQLAlchemy, Jinja2, et PyJWT pour l'authentification JWT, ainsi que d'asyncpg pour la connexion à PostgreSQL :

```bash
pip install fastapi uvicorn sqlalchemy asyncpg psycopg2-binary jinja2 passlib pyjwt
```

### 2. Configuration du Projet

Créez la structure suivante pour le projet :

```
project/
├── main.py
├── database.py
├── models.py
├── auth.py
├── crud.py
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── home.html
│   └── detail.html
└── config.py
```

### 3. Configurer la Base de Données (database.py)

Dans `database.py`, configurez la connexion à PostgreSQL :

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
```

Remplacez `user`, `password`, et `dbname` par vos informations de base de données.

### 4. Définir le Modèle d'Utilisateur (models.py)

Dans `models.py`, définissez le modèle SQLAlchemy pour les utilisateurs :

```python
from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(100), nullable=False)
    role = Column(String(100), default="client")
    is_active = Column(Boolean, default=True)
```

### 5. Créer des Fonctions CRUD (crud.py)

Dans `crud.py`, définissez les fonctions pour manipuler les utilisateurs :

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, username: str, email: str, password: str):
    hashed_password = pwd_context.hash(password)
    user = User(username=username, email=email, password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user_by_email(db, email)
    if user and pwd_context.verify(password, user.password):
        return user
    return None
```

### 6. Authentification JWT (auth.py)

Dans `auth.py`, ajoutez les fonctions pour générer et vérifier les tokens JWT :

```python
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .config import SECRET_KEY
from .crud import get_user_by_email
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = "YOUR_SECRET_KEY"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = await get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
```

### 7. Créer le Contrôleur FastAPI (main.py)

Dans `main.py`, configurez les routes et l'affichage Jinja2 :

```python
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db, engine
from .models import Base
from .crud import create_user, authenticate_user
from .auth import create_access_token, get_current_user

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

@app.get("/home")
async def home_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {"request": request, "username": user.username})

@app.get("/detail")
async def detail_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("detail.html", {"request": request, "user": user})
```

### 8. Templates HTML

Créez les fichiers HTML dans le dossier `templates` pour `login.html`, `register.html`, `home.html`, et `detail.html` :

- **login.html** et **register.html** : formulaires de connexion et d’inscription.
- **home.html** : page d’accueil qui affiche "Bonjour [username de l'user]" et un lien "detail".
- **detail.html** : page de détails avec les informations de l’utilisateur (id, username, email, role, is_active).

Cela donne une base solide pour votre projet, avec des fonctionnalités d'inscription, de connexion avec JWT, et une interface utilisateur simple utilisant Jinja2.

Bien sûr ! Voici les templates HTML que vous pouvez utiliser pour chaque page du projet.

### 1. `login.html`

Formulaire de connexion qui demande l'email et le mot de passe.

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Connexion</title>
</head>
<body>
    <h2>Connexion</h2>
    <form action="/login" method="post">
        <label for="email">Email :</label>
        <input type="email" id="email" name="email" required>
        <br>
        <label for="password">Mot de passe :</label>
        <input type="password" id="password" name="password" required>
        <br>
        <button type="submit">Se connecter</button>
    </form>
    <p>Vous n'avez pas de compte ? <a href="/register">S'inscrire</a></p>
</body>
</html>
```

### 2. `register.html`

Formulaire d'inscription qui demande le nom d'utilisateur, l'email et le mot de passe.

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Inscription</title>
</head>
<body>
    <h2>Inscription</h2>
    <form action="/register" method="post">
        <label for="username">Nom d'utilisateur :</label>
        <input type="text" id="username" name="username" required>
        <br>
        <label for="email">Email :</label>
        <input type="email" id="email" name="email" required>
        <br>
        <label for="password">Mot de passe :</label>
        <input type="password" id="password" name="password" required>
        <br>
        <button type="submit">S'inscrire</button>
    </form>
    <p>Vous avez déjà un compte ? <a href="/login">Se connecter</a></p>
</body>
</html>
```

### 3. `home.html`

Page d'accueil qui s'affiche après la connexion de l'utilisateur et qui affiche "Bonjour [nom d'utilisateur]" avec un lien vers la page des détails.

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Accueil</title>
</head>
<body>
    <h2>Bonjour, {{ username }} !</h2>
    <a href="/detail">Voir les détails de votre compte</a>
</body>
</html>
```

### 4. `detail.html`

Page de détails de l'utilisateur, qui affiche toutes les informations de l'utilisateur (id, username, email, role, et is_active).

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Détails de l'utilisateur</title>
</head>
<body>
    <h2>Détails de l'utilisateur</h2>
    <ul>
        <li><strong>ID :</strong> {{ user.id }}</li>
        <li><strong>Nom d'utilisateur :</strong> {{ user.username }}</li>
        <li><strong>Email :</strong> {{ user.email }}</li>
        <li><strong>Rôle :</strong> {{ user.role }}</li>
        <li><strong>Actif :</strong> {{ user.is_active }}</li>
    </ul>
    <a href="/home">Retour à l'accueil</a>
</body>
</html>
```

Ces templates HTML utilisent la syntaxe Jinja2 pour insérer dynamiquement les données de l'utilisateur fournies par FastAPI. Assurez-vous que les fichiers HTML sont bien placés dans le dossier `templates`, comme indiqué dans la structure du projet.
----------
>>Pourquoi j'ai {"detail":"Not authenticated"} apres le login alors que l'email et mot de passe

Si vous avez déjà vérifié que tout est correctement configuré et que les étapes comme le hashage du mot de passe, la génération du jeton JWT, et l'envoi du jeton dans les cookies sont toutes en place, l'erreur `{"detail": "Not authenticated"}` pourrait provenir d'un autre problème spécifique, probablement lié à la gestion du cookie ou à l'extraction du jeton JWT lors de l'accès aux routes protégées.

### Voici quelques pistes à explorer pour identifier le problème :

### 1. **Vérification des cookies dans le navigateur (ou outils de développement)**

Lorsque vous vous connectez et que vous obtenez un jeton JWT, vérifiez si le cookie `access_token` est bien défini dans le navigateur. Utilisez les outils de développement de votre navigateur (généralement `F12` pour ouvrir les DevTools) et regardez l'onglet **Cookies** pour vérifier si le cookie `access_token` est bien présent après la connexion.

- Si le cookie est présent, il doit contenir un jeton valide.
- Si le cookie est absent ou vide, cela pourrait être un problème au niveau de la réponse de la connexion.

### 2. **Vérification du format du cookie et de la lecture du jeton**

Dans le code de votre route `/login`, vous générez un cookie avec `response.set_cookie`. Assurez-vous que le jeton est bien dans le bon format et qu'il est lisible par FastAPI sur les requêtes suivantes.

```python
response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
```

Cela envoie un cookie HTTP uniquement (qui n'est pas accessible par JavaScript). Cependant, il doit être envoyé dans l'en-tête des requêtes suivantes pour qu'il soit correctement vérifié par FastAPI dans la fonction `get_current_user`.

Si vous utilisez des cookies, assurez-vous que le cookie est envoyé correctement et que le code de récupération du jeton fonctionne comme prévu.

Dans votre fonction `get_current_user`, assurez-vous que le cookie est bien pris en compte. Si vous utilisez un cookie, cela pourrait être comme ceci :

```python
from fastapi import Request

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = token.split(" ")[1]  # Supposons que le jeton est dans le format "Bearer <token>"
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = await get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
```

### 3. **Problèmes liés à la configuration du cookie**

Si vous êtes en développement local, assurez-vous que vous n'avez pas de problème avec les cookies HTTP. Par exemple :

- **Pas de cookie en production si l'API n'est en HTTPS** : Si vous utilisez `secure=True` dans le cookie (ce qui est recommandé en production), le cookie ne sera envoyé que sur une connexion HTTPS. Assurez-vous de bien tester en HTTP si vous êtes en développement local, ou utilisez HTTPS même en développement pour tester.

- **Vérifier les paramètres de cookie (`SameSite`, `Secure`)** : Si vous travaillez avec un front-end séparé (par exemple, un front-end React/Angular), assurez-vous que les cookies sont envoyés avec la requête. Parfois, les paramètres de cookie comme `SameSite=None` ou `Secure=True` peuvent bloquer l'envoi du cookie en développement ou entre différents domaines.

```python
response.set_cookie(
    key="access_token",
    value=f"Bearer {access_token}",
    httponly=True,
    secure=True,  # assurez-vous d'avoir HTTPS si vous utilisez secure=True
    samesite="None"  # pour les cookies entre différents domaines
)
```

### 4. **Problème avec la clé de signature du JWT**

Vérifiez que la clé secrète (`SECRET_KEY`) que vous utilisez pour signer et vérifier les tokens est bien la même partout dans l'application. Si vous avez plusieurs fichiers ou environnements, il se peut qu'il y ait un décalage entre la clé utilisée pour signer et celle utilisée pour vérifier le token.

### 5. **Problèmes de cache ou d'ancien cookie**

Essayez de vider les cookies du navigateur ou de tester dans un autre navigateur pour vous assurer qu'il n'y a pas un problème de cache ou d'ancien cookie qui est utilisé.

### 6. **Test manuel avec un outil comme Postman ou cURL**

Essayez de simuler manuellement les requêtes avec un outil comme Postman ou cURL pour voir si le problème provient de la gestion des cookies dans le navigateur. Cela peut vous aider à déterminer si le problème vient de l'authentification côté client ou de la gestion du jeton côté serveur.

Par exemple, après avoir obtenu un jeton, vous pouvez tester une requête avec cURL en envoyant explicitement le cookie :

```bash
curl -X 'GET' 'http://127.0.0.1:8000/home' -H 'accept: application/json' -H 'Cookie: access_token=Bearer <votre_token>'
```

### Conclusion

Si tout semble correct côté serveur et côté cookie, il est probable que le problème vienne de la manière dont les cookies ou les tokens JWT sont envoyés ou récupérés. Assurez-vous que le cookie est effectivement présent, que le token est envoyé correctement, et que l'extraction du token JWT se fait correctement dans la route protégée. Si vous utilisez des cookies, la méthode `request.cookies.get("access_token")` devrait récupérer correctement le jeton pour chaque requête protégée.

Si le problème persiste, il peut être utile de partager plus de détails spécifiques concernant la manière dont le jeton est envoyé et récupéré, ou d'essayer de reproduire le problème avec un outil comme Postman.