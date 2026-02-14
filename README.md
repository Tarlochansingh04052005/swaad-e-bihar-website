# Swaad-e-Bihar | Cloud Kitchen Web App

A Flask-based website for Swaad-e-Bihar with public pages, customer login, admin portal, menu management, cart flow, and order tracking.

## Features
- Public pages: Home, Menu, Story, Order, Cart, Contact
- Menu portal with add/remove cart controls
- Session cart with totals
- Customer accounts (login, register, profile, order history)
- Admin portal (menu, story, contact, orders, users)
- Admin business dashboard with KPIs and trends

## Tech Stack
- Python 3.11
- Flask
- SQLite (local)

## Local Setup
1) Create and activate a virtual environment

Windows PowerShell:
```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2) Install dependencies
```
pip install -r requirements.txt
```

3) Run the server
```
python app.py
```

Open: http://127.0.0.1:5000/

## Default Admin Login
- URL: http://127.0.0.1:5000/admin/login
- Email: swaadebihar01@gmail.com
- Password: admin123

## Customer Login
- URL: http://127.0.0.1:5000/customer/login
- Register: http://127.0.0.1:5000/customer/register

## Important Routes
- / : Home
- /menu : Menu portal (add/remove items)
- /cart : Cart view + totals
- /order : Order request form
- /story : Story page
- /contact : Contact page

Admin:
- /admin/login
- /admin
- /admin/orders
- /admin/menu
- /admin/story
- /admin/contact
- /admin/users

Customer:
- /dashboard/customer
- /customer/profile

## Data Storage
- SQLite database: swaad.db (local)
- Uploads: uploads/

Note: uploads/ and *.db are ignored by git via .gitignore.

## Deployment (Simple)
You can deploy this on Render or Railway quickly.

### Render
1) Create a new **Web Service** (not Static Site)
2) Connect your GitHub repo
3) Build command: `pip install -r requirements.txt`
4) Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`

### Railway
1) Create a new project
2) Connect your GitHub repo
3) Set Start Command to `gunicorn app:app --bind 0.0.0.0:$PORT`

## Notes
- This project uses a local SQLite database for now.
- For production, use a managed database and set a strong secret key.

## License
All rights reserved.
