import json
import os
import random
from flask import Flask, request, jsonify, Response, render_template_string

app = Flask(__name__)

DATA_FILE = "hydra_db.json"

DEFAULT_RULES = """1. Запрещено размещать материалы, нарушающие законодательство.
2. Запрещен спам, фишинг и вредоносное ПО.
3. Уважайте других пользователей сети Гидра.
4. Администрация оставляет за собой право заблокировать любой домен при нарушении правил."""


def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "sites": []}


def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def generate_ip(existing_ips):
    while True:
        ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        if ip not in existing_ips:
            return ip


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Гидра Поиск</title>
    <link rel="search" type="application/opensearchdescription+xml" title="Гидра Поиск" href="/opensearch.xml">
</head>
<body style="font-family: Arial; text-align: center; margin-top: 80px;">
    <h1>Гидра Поиск — Сервер работает</h1>
    <form action="/web_search" method="get" style="margin-top: 20px;">
        <input type="text" name="q" placeholder="Поиск в сети Гидра..." style="width: 320px; padding: 10px; font-size: 16px;">
        <button type="submit" style="padding: 10px 20px; font-size: 16px;">Найти</button>
    </form>
</body>
</html>"""


@app.route("/opensearch.xml")
def opensearch():
    host_url = request.host_url.rstrip("/")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>Гидра</ShortName>
  <Description>Поиск в сети Гидра</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <Url type="text/html" method="get" template="{host_url}/web_search?q={{searchTerms}}"/>
</OpenSearchDescription>"""
    return Response(xml, mimetype="application/opensearchdescription+xml")


@app.route("/web_search")
def web_search():
    query = request.args.get("q", "").strip().lower()
    db = load_db()
    results = []
    for s in db["sites"]:
        if s.get("is_banned"):
            continue
        if (
            not query
            or query in s["title"].lower()
            or query in s["domain"].lower()
            or query in s["desc"].lower()
        ):
            results.append(s)

    html = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>{{ query }} — Гидра Поиск</title></head>
<body style="font-family: Arial; max-width: 700px; margin: 40px auto;">
    <form action="/web_search" method="get" style="margin-bottom: 30px;">
        <input type="text" name="q" value="{{ query }}" style="width: 70%; padding: 8px; font-size: 16px;">
        <button type="submit" style="padding: 8px 16px; font-size: 16px;">Найти</button>
    </form>
    {% if not results %}
        <p>Ничего не найдено.</p>
    {% endif %}
    {% for item in results %}
        <div style="margin-bottom: 20px;">
            <div style="color: #5f6368; font-size: 13px;">hydra://{{ item.domain }} ({{ item.ip }})</div>
            <a href="hydra://{{ item.ip }}" style="font-size: 18px; color: #1a0dab; text-decoration: none;">
                <b>{{ item.title }}</b>
            </a>
            <p style="margin: 4px 0; color: #4d5156;">{{ item.desc }}</p>
        </div>
    {% endfor %}
</body>
</html>"""
    return render_template_string(html, query=request.args.get("q", ""), results=results)


@app.route("/rules", methods=["GET"])
def get_rules():
    return jsonify({"rules": DEFAULT_RULES})


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    if not phone or len(password) < 4:
        return jsonify({"error": "Введите номер и пароль (от 4 символов)"}), 400
    db = load_db()
    if phone in db["users"]:
        return jsonify({"error": "Этот номер уже зарегистрирован"}), 400
    db["users"][phone] = {"password": password}
    save_db(db)
    return jsonify({"phone": phone})


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    db = load_db()
    user = db["users"].get(phone)
    if not user or user["password"] != password:
        return jsonify({"error": "Неверный номер телефона или пароль"}), 401
    return jsonify({"phone": phone})


@app.route("/create_site", methods=["POST"])
def create_site():
    data = request.json or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    title = data.get("title", "").strip()
    domain = data.get("domain", "").strip().lower()
    desc = data.get("desc", "").strip()
    content = data.get("content", "").strip()

    db = load_db()
    user = db["users"].get(phone)
    if not user or user["password"] != password:
        return jsonify({"error": "Ошибка авторизации"}), 401
    if not title or not domain or not content:
        return jsonify({"error": "Заполните название, домен и текст"}), 400
    if any(s["domain"] == domain for s in db["sites"]):
        return jsonify({"error": "Такой домен уже занят"}), 400

    existing_ips = {s["ip"] for s in db["sites"]}
    ip = generate_ip(existing_ips)
    new_site = {
        "ip": ip,
        "domain": domain,
        "title": title,
        "desc": desc,
        "content": content,
        "owner": phone,
        "is_banned": False,
        "ban_reason": "",
    }
    db["sites"].append(new_site)
    save_db(db)
    return jsonify({"ip": ip, "domain": domain})


@app.route("/my_sites", methods=["POST"])
def my_sites():
    data = request.json or {}
    phone = data.get("phone", "").strip()
    db = load_db()
    user_sites = [s for s in db["sites"] if s.get("owner") == phone]
    return jsonify(user_sites)


@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip().lower()
    db = load_db()
    results = []
    for s in db["sites"]:
        if s.get("is_banned"):
            continue
        if (
            not query
            or query in s["title"].lower()
            or query in s["domain"].lower()
            or query in s["desc"].lower()
        ):
            results.append(
                {
                    "ip": s["ip"],
                    "domain": s["domain"],
                    "title": s["title"],
                    "desc": s["desc"],
                }
            )
    return jsonify(results)


@app.route("/visit", methods=["GET"])
def visit():
    target = request.args.get("target", "").strip().lower()
    db = load_db()
    for s in db["sites"]:
        if s["ip"] == target or s["domain"] == target:
            return jsonify(s)
    return jsonify({"error": "Сайт не найден"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
