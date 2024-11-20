from flask import Flask,redirect,url_for,render_template

app = Flask(__name__)

@app.route("/") # sends to home page
def home():
    return render_template("home.html")

@app.route("/contactus") # sends to contact us page
def contact_us():
    return render_template("contactus.html")

@app.route("/<name>")
def user(name):
    return f"Hello{name}"

@app.route("/admin")
def admin():
    return redirect(url_for("home"))

if __name__=="__main__":
    app.run(debug=True)