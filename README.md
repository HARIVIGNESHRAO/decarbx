# DecarbX Environmental Intelligence Platform

React/Vite frontend with FastAPI, MongoDB, JWT authentication, bcrypt passwords, RBAC, REST APIs, and Recharts.

## Local development (existing MongoDB)

Make sure your existing MongoDB service is running at `mongodb://127.0.0.1:27017`, then:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --port 8000
```

In another terminal:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

Development accounts:

```text
ADMIN                   admin@decarbx.com / Admin@123
SUSTAINABILITY_MANAGER  manager@decarbx.com / Manager@123
CARBON_ANALYST          analyst@decarbx.com / Analyst@123
PROCUREMENT_MANAGER     procurement@decarbx.com / Procure@123
FINANCE_USER            finance@decarbx.com / Finance@123
SUPPLIER                supplier@decarbx.com / Supplier@123
AUDITOR                 auditor@decarbx.com / Auditor@123
VIEWER                  viewer@decarbx.com / Viewer@123
```

The explicit seed creates Hyderabad Factory, Bangalore Office, and nine prototype factors. Every seeded factor has `is_demo: true` and source `DEMO — not an official regulatory factor`.

## Local backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
uvicorn main:app --reload --port 8000
```

MongoDB database: `decarbx` at `mongodb://127.0.0.1:27017/decarbx`.

## Main endpoints

- `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST /api/facilities`
- `POST /api/emissions/calculate`
- `GET /api/emissions`, `GET|PUT|DELETE /api/emissions/{id}`
- `GET /api/dashboard/summary`
- `GET /api/analytics/trends`, `/anomalies`, `/forecast`
- `GET /api/reports/summary`
- `GET|POST /api/users`, `PUT|DELETE /api/users/{id}`

Dashboard and analytics values are calculated from `emission_records` stored in MongoDB; they are not hardcoded.
