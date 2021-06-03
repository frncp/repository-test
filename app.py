from flask import Flask, render_template, url_for, request, redirect, send_from_directory, make_response, send_file
import requests
import json
from http import cookies

import pymongo
from pymongo import MongoClient, errors
import base64
import bson
from bson.binary import Binary
from bson.objectid import ObjectId

from datetime import date, datetime
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
import os

from passwords import DB_USER, DB_PASSWORD

# import ssl

import flask_login


# DB Connection
mongo_client_string = "mongodb+srv://" + DB_USER + ":" + DB_PASSWORD + "@cluster0.dfin1.mongodb.net/inQueue?retryWrites=true&w=majority"
client = pymongo.MongoClient(mongo_client_string)
db = client["inQueue"]
businesses_collection = db["businesses"]
bookings_collection = db["bookings"]
PDFs_collection = db["bookings_PDFs"]
# Start app
app = Flask(__name__)
app.secret_key = 'super secret string'
# Start login manager
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
users = {'mattiarip@gmail.com': {'password': 'ciao'},
         'frncp@gmail.com': {'password': 'pollasto'}}
# app.config['SERVER_NAME'] = 'inqueue.it'


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return
    user = User()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    if email not in users:
        return
    user = User()
    user.id = email
    user.is_authenticated = (request.form['password'] == users[email]['password'])
    return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['email']
    if request.form['password'] == users[email]['password']:
        user = User()
        user.id = email
        flask_login.login_user(user)
        return redirect(url_for('protected'))

    return 'Bad login'


@app.route('/protected')
@flask_login.login_required
def protected():
    return 'Logged in as: ' + flask_login.current_user.id


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return 'Logged out'


@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized'


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/select', methods=["POST", "GET"])
def homepage_new():
    if request.method == "GET":
        city_from_cookie = request.cookies.get("city")
        if not city_from_cookie:
            city_from_cookie = ""
        return render_template("home.html", city_from_cookie=city_from_cookie)
    else:
        city = request.form["city"]
        resp = make_response(render_template('index.html', city=city))
        resp.set_cookie("city", value=city, max_age=60 * 60 * 24)
        return resp


@app.route('/')
def homepage():
    city_from_cookie = request.cookies.get("city")
    if not city_from_cookie:
        rendered_template = render_template('index.html', city="clicca")
        return make_response(rendered_template)
    else:
        return render_template('index.html', city=city_from_cookie)


@app.route('/business/<business_name>_<creation_date>_<creation_time>', methods=["POST", "GET"])
def business_page(business_name, creation_date, creation_time):
    if request.method == "POST":
        name = request.form["fname"]
        surname = request.form["lname"]
        email = request.form["email"]
        cellphone = request.form["cellphone"]
        day = request.form["date"]
        time = request.form["slot2"]
        service = request.form["service"]
        operator = request.form["operator"]
        document = {"business_name": business_name, "business_creation_date": creation_date,
                    "business_creation_time": creation_time, "name": name, "surname": surname, "email": email,
                    "cellphone": cellphone, "day": day, "time": time, "service": service, "operator": operator}
        booking_result = bookings_collection.insert_one(document)
        return redirect("/booking_confirmation/"+str(booking_result.inserted_id))
    else:
        return render_template("business-info.html", business_name=business_name, creation_date=creation_date,
                               creation_time=creation_time)


@app.route('/test/')
def book_test():
    return render_template('booked.html')


@app.route('/files/tickets/<booking_id>.pdf')
def send_booking_pdf(booking_id):
    query_result = PDFs_collection.find_one({"_id": booking_id})
    if query_result is None:
        file_name = curr_path + "\\temp\\" + booking_id + ".pdf"
        # PDF creation
        canvas = Canvas(file_name, pagesize=(612.0, 792.0))
        canvas.drawString(72, 72, "Hello, World")
        canvas.save()
        file = open(file_name, "rb")
        # DB insert and retrieval
        document = {"_id": booking_id, "pdf": file.read()}
        PDFs_collection.insert_one(document)
        query_result = PDFs_collection.find_one({"_id": booking_id})
        # temp file deletion
        file.close()
        os.remove(file_name)
    return send_file(BytesIO(query_result["pdf"]), mimetype="application/pdf")


@app.route('/booking_confirmation/<booking_id>')
def bookings_confirmation_page(booking_id):
    try:
        query_result = bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except bson.errors.InvalidId:
        return redirect('/404/')
    if query_result is not None:
        service = query_result["service"]
        business_name = query_result["business_name"]
        business_creation_date = query_result["business_creation_date"]
        business_creation_time = query_result["business_creation_time"]
        operator = query_result["operator"]
        day = query_result["day"]
        time = query_result["time"]
        # Use parameters found from query
        return render_template("booked.html", service=service, business_name=business_name, operator=operator,
                               day=day, time=time)
    else:
        return redirect('/404/')
    # TODO: Add parameters to function


@app.route("/partner", methods=["POST", "GET"])
def partners_page():
    if request.method == "POST":
        img = request.files['img'].read()
        fname = request.form["fname"]
        lname = request.form["lname"]
        email = request.form["email"]
        cellphone = request.form["cellphone"]
        business_name = request.form["bname"]
        open_time = request.form["open-time"]
        close_time = request.form["close-time"]
        service = request.form["service"]
        city = request.form["city"]
        address = request.form["address"]
        lat = request.form["lat"]
        lon = request.form["lon"]
        num_of_services = int(request.form["num_of_services"])
        services = [str(request.form["service"])]
        service_n = 2
        while service_n <= num_of_services:
            service = request.form["service_"+str(service_n)]
            if len(service) > 0:
                services.append(service)
            service_n += 1

        today = str(date.today()).replace("/", "-", 3)
        now = datetime.now().strftime('%H:%M:%S')

        # TODO: document with all services, create account with credentials
        document = {"img": img, "fname": fname, "lname": lname, "email": email, "cellphone": cellphone,
                    "business_name": business_name, "open_time": open_time, "close_time": close_time,
                    "service": service, "creation_date": today, "creation_time": now,
                    "city": city, "address": address, "lat": lat, "lon": lon}
        b_sign_up_result = businesses_collection.insert_one(document)
        return redirect("/newBusiness_confirmation/"+str(b_sign_up_result.inserted_id))
    else:
        return render_template("business-creation.html")


@app.route('/newBusiness_confirmation/<b_sign_up_result>', methods=["GET"])
def partner_confirmation_page(b_sign_up_result):
    business_document = businesses_collection.find_one({"_id": ObjectId(b_sign_up_result)})
    return render_template("signed-up.html")


@app.route('/photos/<business_name>_<creation_date>_<creation_time>.jpg', methods=["GET"])
def send_business_image(business_name, creation_date, creation_time):
    document = businesses_collection.find_one({"business_name": business_name, "creation_date": creation_date,
                                               "creation_time": creation_time})
    photo = BytesIO(document["img"])
    return send_file(photo, mimetype="image/gif")


if __name__ == "__main__":
    curr_path = os.path.dirname(__file__)
    try:
        os.mkdir(curr_path+"\\temp")
    except FileExistsError:
        pass
    https_available = False
    try:
        # SSL cert approach commented out to test the other one
        # context = ssl.SSLContext()
        # context.load_cert_chain(curr_path + '/cert.pem', curr_path + '/privkey.pem')
        context = (curr_path + '/cert.pem', curr_path + '/privkey.pem')
        https_available = False # True = create https page
    except FileNotFoundError:
        print("HTTPs certification files not found")
    # Server starting
    local_only = False  # False = Accessible also from out of intranet
    if local_only:
        if https_available:
            app.run(debug=True, ssl_context=context)
        else:
            app.run(debug=True)
    else:
        # Port forwarding needed on router
        if https_available:
            app.run(host='0.0.0.0', port=8150, debug=True, ssl_context=context)
        else:
            app.run(host='0.0.0.0', port=8150, debug=True)
