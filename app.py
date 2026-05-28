from flask import Flask


app = Flask(__name__)

@app.route("/")
def index():
    return "Hello World!"

@app.route("/about")
def about():
    return "This page is gonna describe this project"

@app.route("/login")
def login():
    return"Please login here"

@app.route("/inventory")
def inventory():
    return "Here is your inventory"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
