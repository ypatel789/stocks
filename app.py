import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
import math

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=user_id)

    """ print("printing transactions", transactions) """

    summaries = []
    abbreviation = []
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)[0]['cash']
    total = 0
    total += cash

    for transaction in transactions:
        if transaction['symbol'] not in abbreviation:
            abbreviation.append(transaction['symbol'])

    print("printing abbreviations", abbreviation)

    for symbol in abbreviation:
        print("calculating symbols", symbol)
        lookup_res = lookup(symbol)
        summary = {
            'sym': symbol,
            'name': lookup_res['name'],
            'shares': 0,
            'price': lookup_res['price'],
            'total': 0,
        }
        shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, summary['sym'])
        for share in shares:
            summary['shares'] += share['shares']
        print("summary for symbols", summary['shares'])

        summary['total'] = round((summary['shares'] * summary['price']), 2)

        print("total value of shares", summary['total'])
        total += summary['total']
        summaries.append(summary)

        print("printing summaries", summaries)

    round_total = round(total, 2)
    round_cash = round(cash, 2)

    return render_template("index.html", cash=round_cash, total=round_total, summaries=summaries)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Symbol Required")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol Does Not Exist")

        if shares < 0:
            return apology("Share not allowed")

        transaction_value = shares * stock["price"]

        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        if user_cash < transaction_value:
            return apology("Not Enough Funds")

        updt_cash = user_cash - transaction_value

        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)

        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)",user_id, stock["symbol"], shares, stock["price"], date)

        flash("Bought!")

        return redirect ("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :id ORDER BY date DESC", id=user_id)

    for transaction in transactions:
        lookup_res = lookup(transaction["symbol"])
        transaction["name"] = lookup_res["name"]

    return render_template("history.html", transactions = transactions)




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Symbol Required")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol Does Not Exist")

        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Username Required")

        if not password:
            return apology("Password Required")

        if not confirmation:
            return apology("Confirmation Required")

        if password != confirmation:
            return apology("Passwords Do Not Match")

        hash = generate_password_hash(password)

        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology("Username Already Exists")

        session["user_id"] = new_user

        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        symbols_user = db.execute("SELECT symbol FROM transactions WHERE user_id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in symbols_user])

    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Symbol Required")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol Does Not Exist")

        if shares < 0:
            return apology("Share not allowed")

        transaction_value = shares * stock["price"]

        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        user_shares = db.execute("SELECT shares FROM transactions WHERE user_id= :id AND symbol= :symbol GROUP BY symbol", id=user_id, symbol=symbol)
        user_shares_real = user_shares[0]["shares"]

        if shares > user_shares_real:
            return apology("Not enough stocks available!")

        updt_cash = user_cash + transaction_value

        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)

        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)",user_id, stock["symbol"], (-1)*shares, stock["price"], date)

        flash("Sold!")

        return redirect ("/")

@app.route("/topup", methods=["GET", "POST"])
@login_required
def topup():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("topup.html")

    else:
        user_id = session["user_id"]
        amount = request.form.get("ur_fat_mum")

        if float(amount) <= 0:
            return apology("UR FAT MUM")

        user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)

        updt_cash = user_cash[0]["cash"] + float(amount)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)

        flash("Account Topped Up By {} Your new balance is {}".format(amount, round(updt_cash, 2)))

        return redirect ("/")
