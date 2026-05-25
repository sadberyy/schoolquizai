Проект содержит 2 ключевые папки:

- папка **backend** в текущей своей версии уже содержит в себе папку **backend_gigachat** и создание БД;
- папку **frontend** использует Vercel для отображения МАКЕТА будущего сайта (кнопки генерации викторины, копирования ссылки, прикрепления файлов и т.д. не работают).

Папка **frontend** не пересекается с папкой **backend**.   

Папка **backend_gigachat** используется для тестирования взаимодействия с моделью GigaChat через Swagger UI. Чтобы протестировать работу самому, необходимо:  

1. Создать и заполнить **env**-файл (.env) в папке **./backend/** со следующими переменными:
  GIGACHAT_AUTH_KEY=ваш_ключ_доступа  
   GIGACHAT_SCOPE=GIGACHAT_API_PERS  
   GIGACHAT_MODEL=GigaChat  
   GIGACHAT_CA_BUNDLE_FILE=название_вашего_сертификата.crt  
   FRONTEND_ORIGIN=[http://localhost:5173](http://localhost:5173)
2. Выполнить следующие команды в терминале, находясь в папке **backend**:
   cd backend  
   python -m venv .venv  
   .venv\Scripts\Activate.ps1  
   pip install -r requirements.txt (либо .venv\Scripts\python.exe -m pip install -r requirements.txt)  
   uvicorn app.main:app --reload
4. Открыть Swagger UI в браузере по адресу [http://localhost:8000/docs](http://localhost:8000/docs)

