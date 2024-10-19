from flask import Flask

app = Flask(__name__)

@app.route("/") # sends to home page
def home():
    return "Main Page"

def user(name):
    return f"Hello{name}"

if __name__=="__main__":
    app.run()