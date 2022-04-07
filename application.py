import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, twod

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM Holdings WHERE user_id = ? AND qty > 0", session["user_id"])
    for entry in rows:
        symbol = entry['symbol']
        stock = lookup(symbol)
        currentStockPrice = stock['price']
        entry['currentStockPrice'] = currentStockPrice
        qty = entry['qty']
        entry['mktVal'] = currentStockPrice * qty

    funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    funds = funds[0]
    funds = (funds['cash'])
    return render_template("index.html", rows=rows, funds=funds)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        qty = (request.form.get("shares"))
        if (not qty.isnumeric()):
            return apology("bad qty", 400)
        else:
            qty = float(qty)
        symbol = request.form.get("symbol")
        rows = lookup(symbol)
        if(rows is None):
            return apology("invalid ticker symbol", 400)
        if float(qty) < 1.0 or float(qty) != float(int(qty)):
            return apology("qty must be positive integer", 400)
        stockprice = rows["price"]
        money = db.execute("SELECT cash FROM users where id = ?", session["user_id"])
        cash_available = float(money[0]["cash"])
        required_cash = float(qty) * float(stockprice)
        if (cash_available < required_cash):
            return apology("Insufficient Funds")
        else:
            newBalance = cash_available - required_cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newBalance, session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, qty, price, type) VALUES (?,?,?,?,?)",
                       session["user_id"], symbol, qty, stockprice, "buy")
            qtyHeldArr = db.execute("SELECT qty FROM holdings WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
            if(len(qtyHeldArr) == 0):
                newQty = float(qty)
                db.execute("INSERT INTO holdings (user_id, symbol, qty) VALUES (?, ?, ?)", session["user_id"], symbol, newQty)
            else:
                qtyHeld = float(qtyHeldArr[0]["qty"])
                newQty = twod(qtyHeld + qty)
                db.execute("UPDATE holdings SET qty = ? WHERE user_id = ? AND symbol = ?", newQty, session["user_id"], symbol)
            return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("transactions.html", rows=rows)


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
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], (request.form.get("password"))):
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        rows = lookup(symbol)
        if(rows is None):
            return apology("bad ticker symbol", 400)
        company = rows["name"]
        price = usd(rows["price"])
        return render_template("quoted.html", company=company, symbol=symbol, price=price)
    else:
        return render_template("quote.html")


@app.route("/addfunds", methods=["GET", "POST"])
@login_required
def addfunds():
    if request.method == "POST":
        moneyToAdd = float(request.form.get("dollars"))
        currentBalanceArr = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        newBalance = moneyToAdd + float(currentBalanceArr[0]['cash'])
        db.execute("UPDATE users SET cash = ? where id = ?", newBalance, session["user_id"])
        return redirect('/')
    else:
        return render_template("addfunds.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords no match")

        # users = db.execute("INSERT INTO birthdays (name, month, day) VALUES(?, ?, ?)", name, month, day)
        username = request.form.get("username")
        users = db.execute("SELECT * FROM users WHERE username LIKE ?", username)

        if len(users) != 0:
            return apology("user exists", 400)
        else:
            num_existing = db.execute("SELECT * FROM users")
            db.execute("INSERT INTO users (id, username, hash) VALUES(?,?,?)", 1 + len(num_existing),
                       username, generate_password_hash(request.form.get("password")))
        # Remember which user has logged in
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1:
            return apology("Unable to log in", 403)
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page

        return redirect('/')
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        qtySelling = (request.form.get("shares"))
        shares = qtySelling
        if (not qtySelling.isnumeric()):
            return apology("bad qty", 400)
        else:
            qtySelling = float(qtySelling)
        symbol = request.form.get("symbol")
        rows = lookup(symbol)
        stockprice = rows["price"]
        saleAmount = float(stockprice) * float(qtySelling)
        money = db.execute("SELECT cash FROM users where id = ?", session["user_id"])
        userBalance = float(money[0]["cash"])
        sharesHeldArr = db.execute("SELECT qty FROM holdings WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        if (len(sharesHeldArr) == 0):
            return apology("you don't own that stock")

        sharesHeld = float(sharesHeldArr[0]['qty'])

        if (sharesHeld < qtySelling):
            return apology("You don't have that many shares")
        else:
            newBalance = userBalance + saleAmount
            newQty = sharesHeld - qtySelling
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newBalance, session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, qty, price, type) VALUES (?,?,?,?,?)",
                       session["user_id"], symbol, qtySelling, stockprice, "sell")
            db.execute("UPDATE holdings SET qty = ? WHERE user_id = ? AND symbol = ?", newQty, session["user_id"], symbol)
            return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT symbol FROM holdings WHERE user_id = ? AND qty > 0.0", session["user_id"])
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
