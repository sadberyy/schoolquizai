# Quiz Builder

**Quiz Builder** — это веб-приложение для генерации и редактирования викторин для школьников.  
Проект поддерживает создание викторин на основе текстового материала, работу с формулами, просмотр, редактирование и экспорт результатов.

## 🔗 Ссылка на проект

Проект можно запускать локально или открыть по публичной ссылке:

[https://school-quiz-ai.vercel.app/](https://school-quiz-ai.vercel.app/)

---

## 📁 Структура проекта

Проект состоит из двух основных папок:

- **frontend/** — клиентская часть приложения, которая отвечает за отображение сайта и развёртывается через **Vercel**.
- **backend/** — серверная часть приложения на **FastAPI**, которая включает текущую реализацию логики работы с **GigaChat**, а также создание и работу с базой данных.

> Папки **frontend** и **backend** логически разделены и работают независимо:  
> frontend отвечает за интерфейс, backend — за API, генерацию викторин и хранение данных.

---

## ⚙️ Локальный запуск проекта

### 1. Настройка backend

Перейдите в папку `backend` и создайте файл `.env`.

Пример содержимого `./backend/.env`:

```env
GIGACHAT_AUTH_KEY=ваш_ключ_доступа
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat
GIGACHAT_CA_BUNDLE_FILE=название_вашего_сертификата.crt
FRONTEND_ORIGIN=http://localhost:5173
```

### 2. Запуск backend

Откройте терминал в папке `backend` и выполните команды:

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Если вы запускаете проект не в PowerShell, команда активации окружения может отличаться:

```bash
source .venv/Scripts/activate
```

Если нужно, зависимости можно установить и так:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 💻 Настройка frontend

### 3. Создание `.env.local` для frontend

Откройте второй терминал, перейдите в папку `frontend` и создайте файл `./frontend/.env.local`.

Пример содержимого:

```env
VITE_API_URL=http://localhost:8000
VITE_STUDENT_URL=http://localhost:5173/student
```

### 4. Запуск frontend

Выполните команды:

```bash
cd frontend
npm install
npm run dev
```

После запуска frontend откройте в браузере:

[http://localhost:5173](http://localhost:5173)

---

## 🔄 Как это работает локально

При локальном запуске сервисы работают так:

- **frontend** запускается на `http://localhost:5173`
- **backend** запускается на `http://localhost:8000`

Frontend отправляет запросы к backend через переменную:

```env
VITE_API_URL=http://localhost:8000
```

---

## 🚀 Продакшен-версия

В продакшене:

- **frontend** развёрнут на **Vercel**
- **backend** работает отдельно через серверную часть проекта
- публичная версия доступна по ссылке:

[https://school-quiz-ai.vercel.app/](https://school-quiz-ai.vercel.app/)

---

## 🛠 Технологии

### Frontend
- React
- Vite
- TypeScript
- Tailwind CSS

### Backend
- FastAPI
- SQLite
- SQLAlchemy
- GigaChat

---

## ✨ Основные возможности

- генерация викторин на основе текстового материала;
- редактирование вопросов и ответов;
- работа с LaTeX-формулами;
- предпросмотр и экспорт материалов;
- локальный и публичный запуск проекта.

---

## 📌 Примечание

Для корректной работы backend необходимо:
- указать актуальные значения переменных в `.env`;
- иметь сертификат для `GigaChat`, если он используется в текущей конфигурации;
- запускать frontend и backend в двух отдельных терминалах при локальной разработке.
