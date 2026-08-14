# Railway backend

Railway Variables:
- BOT_TOKEN = yangi BotFather token
- ADMIN_ID = 5203992395

Start command:
uvicorn server:app --host 0.0.0.0 --port $PORT

After deployment, generate a public Railway domain and copy it into Netlify `config.js`.
