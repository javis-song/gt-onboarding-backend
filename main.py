from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file
from google.cloud import datastore, storage
from google.oauth2 import id_token
# from werkzeug import secure_filename
import datetime
import sys
import requests
import re
import io
import os
import hashlib

datastore_client = datastore.Client()
storage_client = storage.Client()
bucket_name = os.getenv('bucket_name')
bucket = storage_client.bucket(bucket_name)

app = Flask(__name__)

app.secret_key = b'lkjadfsj009(*02347@!$&'

def list_blobs(bucket_name):
    """Lists all the blobs in the bucket."""
    # bucket_name = "your-bucket-name"

    storage_client = storage.Client()

    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket_name)

    for blob in blobs:
        print(blob.name)

def fetch_all(kn):
    query = datastore_client.query(kind=kn)
    res = list(query.fetch())
    return res

def fetch_qnas(kn):
    query = datastore_client.query(kind=kn)
    query.order = ['-dt']
    qnas = list(query.fetch())
    return qnas

# return a list
def fetch_one(kn, question):
    key = datastore_client.key(kn, question)
    query = datastore_client.query(kind=kn)
    query.key_filter(key, '=')
    qna = list(query.fetch())
    return qna

def store_qna(kn, question, description, category, id, dt):
    completeKey = datastore_client.key(kn, question)
    entity = datastore.Entity(key=completeKey)
    entity.update({
        'question': question,
        'id': id,
        'description': description,
        'category': category,
        'dt': dt,
        'replies': []
    })
    datastore_client.put(entity)

def store_reply(kn, question, id, comment, dt):
    qnas = fetch_one(kn, question)
    for qna in qnas:
        qna["replies"].append({
            "id": id,
            "comment": comment,
            "dt": dt
        })
        datastore_client.put(qna)

def username_exist(username):
    users = fetch_all("users")
    for user in users:
        if user["username"] == username:
            return True
    return False

def store_user(username, password, id):
    if username_exist(username):
        return
    completeKey = datastore_client.key("users", username)
    entity = datastore.Entity(key=completeKey)
    entity.update({
        'username': username,
        'password': password,
        'id': id
    })
    datastore_client.put(entity)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data["username"]
    password = data["password"]
    id = data["id"]
    m = hashlib.sha256(password.encode())
    password = m.digest()
    store_user(username, password, id)
    return "register successfully"

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    username = data["username"]
    password = data["password"]
    m = hashlib.sha256(password.encode())
    password = m.digest()

    users = fetch_all("users")
    for user in users:
        if user["username"] == username and user["password"] == password:
            res = {"username": user["username"], "id": user["id"]}
            return redirect(url_for('advisor_discuss'))
    return redirect(url_for('login'))

@app.route('/qna', methods=['GET', 'POST'])
def qna():
    if request.method == 'POST':
        data = request.get_json()
        question = data["question"]
        description = data["description"]
        category = data["category"]
        id = data["id"]
        store_qna("qna", question, description, category, id, datetime.datetime.now())
        return "get question"
    qnas = fetch_qnas("qna")
    return jsonify(qnas)
    
@app.route('/reply', methods=['POST'])
def reply():
    data = request.get_json()
    question = data["question"]
    id = data["id"]
    comment = data["comment"]
    store_reply("qna", question, id, comment, datetime.datetime.now())
    return "get reply"

@app.route('/fetch_reply', methods=['POST'])
def fetch_reply():
    data = request.get_json()
    question = data["question"]
    q = fetch_one("qna", question)
    return jsonify(q[0]["replies"])

# main page HTTP request processing
@app.route('/', methods=['GET', 'POST'])
def root():
    return render_template("index.html")

@app.route('/advisor/login', methods=['GET', 'POST'])
def advisor_login():
    if request.method == 'POST':
        data = request.form
        username = data["username"]
        password = data["password"]
        m = hashlib.sha256(password.encode())
        password = m.digest()

        users = fetch_all("users")
        for user in users:
            if user["username"] == username and user["password"] == password:
                res = {"username": user["username"], "id": user["id"]}
                return redirect(url_for('advisor_discuss'))
        return redirect(url_for('advisor_discuss'))
    return render_template("advisor.html")

UPLOAD_FOLDER = 'upload'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = set(['txt', 'png', 'jpg', 'xls', 'JPG', 'PNG', 'xlsx', 'gif', 'GIF'])  # 允许上传的文件后缀

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            blob = bucket.blob(file.filename)
            blob.upload_from_file(file)
            return ""
    return render_template("post_picture.html")

@app.route('/download', methods=['GET', 'POST'])
def download():
    blob = bucket.get_blob("picture.png")
    file = blob.download_as_string()
    return send_file(io.BytesIO(file), mimetype='image/png')

@app.route('/advisor/discuss', methods=['GET', 'POST'])
def advisor_discuss():
    return render_template("dashboard.html")

@app.route('/advisor/discussForAndroid', methods=['GET', 'POST'])
def advisor_discussForAndroid():
    return render_template("dashboardForAndroid.html")
    
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)