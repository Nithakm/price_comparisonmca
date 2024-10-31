from flask import Flask, render_template, request, session, redirect, url_for,flash
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from firebase_admin import credentials, auth, firestore
import firebase_admin
import logging

app = Flask(__name__)

app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Firebase initialization
cred = credentials.Certificate(r"C:\api\price-comparison-c4beb-firebase-adminsdk-oyzi7-eb82aba9dc.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# Function to scrape price from Flipkart
def scrape_flipkart(url):
    driver = webdriver.Chrome()
    driver.get(url)
    wait = WebDriverWait(driver, 20)  # Increase the timeout to 20 seconds
    try:
        price_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.Nx9bqj")))
        price = price_element.text if price_element else "Price not found"
    except TimeoutException:
        try:
            price_element = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="container"]/div[1]/div[3]/div[1]/div[2]/div[2]/div[1]/div[1]/div[1]/a[1]/div[3]/div[2]/div[1]/div[1]/div[1]')))
            price = price_element.text if price_element else "Price not found"
        except TimeoutException:
            price = "Price not found"
    driver.quit()
    return price

# Function to scrape price from Amazon
def scrape_amazon(url):
    driver = webdriver.Chrome()
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    try:
        price_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.a-price-whole, span.a-color-price")))
        price = price_element.text if price_element else "Price not found"
    except TimeoutException:
        try:
            price_element = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="search"]/div[1]/div[1]/div[1]/span[1]/div[1]/div[5]/div[1]/div[1]/span[1]/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/div[1]/div[1]/div[1]/div[1]/a[1]/span[1]/span[2]/span[2]')))
            price = price_element.text if price_element else "Price not found"
        except TimeoutException:
            price = "Price not found"
    driver.quit()
    return price

# Function to scrape price from Croma
def scrape_croma(url):
    driver = webdriver.Chrome()
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    try:
        price_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.amount[data-testid='new-price']")))
        price = price_element.text.strip() if price_element else "Price not found"
    except TimeoutException:
        price = "Price not found"
    driver.quit()
    return price

# Function to compare prices
def compare_prices(flipkart_price, amazon_price, croma_price):
    prices = {'Flipkart': flipkart_price.replace('₹', '').replace(',', ''),
              'Amazon': amazon_price.replace('₹', '').replace(',', ''),
              'Croma': croma_price.replace('₹', '').replace(',', '')}
    best_price = min(prices.values())
    best_deal = [merchant for merchant, price in prices.items() if price == best_price][0]
    return best_price, best_deal

# Function to generate product links, including model ID
def generate_links(product_name, model_id):
    try:
        flipkart_link = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}+{model_id}&otracker=search"
        amazon_link = f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}+{model_id}"
        croma_link = f"https://www.croma.com/searchB?q={product_name.replace(' ', '%20')}+{model_id}"

        return [flipkart_link, amazon_link, croma_link]
    except Exception as e:
        print("An error occurred:", e)
        return []

# Function to register a new user
def register_user(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        session['user_id'] = user.uid  # Store the user_id in the session
        session['user_email'] = email
        return True
    except ValueError as e:
        logging.error(f"Error during user registration: {e}")
        return str(e)
    except Exception as e:
        logging.error(f"Unexpected error during user registration: {e}")
        return "An error occurred during user registration. Please try again."

# Function to log in an existing user
def login_user(email, password):
    try:
        user = auth.get_user_by_email(email)
        session['user_id'] = user.uid  # Store the user_id in the session
        session['user_email'] = email
        logging.debug("User logged in successfully.")
        return True
    except auth.UserNotFoundError:
        logging.error("User not found.")
        return False
    except Exception as e:
        logging.error(f"Error during user login: {e}")
        return False

# Route for login or registration
@app.route('/', methods=['GET', 'POST'])
def login_or_register():
    if 'user_email' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if 'register' in request.form:
            registration_result = register_user(email, password)
            if registration_result is True:
                return redirect(url_for('home'))
            else:
                return render_template('login.html', error=registration_result)

        elif 'login' in request.form:
            login_result = login_user(email, password)
            if login_result:
                return redirect(url_for('home'))
            else:
                return render_template('login.html', error="Invalid email or password. Please try again.")

    return render_template('login.html')

# Route for index page
@app.route('/index', methods=['GET', 'POST'])
def home():
    # Redirect to login if the user is not authenticated
    if 'user_email' not in session:
        return redirect(url_for('login_or_register'))

    product_name = None  # Initialize product_name for GET requests

    if request.method == 'POST':
        product_name = request.form.get('product_name')
        model_id = request.form.get('model_id')

        # Generate links based on product_name and model_id
        product_links = generate_links(product_name, model_id)
        flipkart_link, amazon_link, croma_link = product_links

        # Scrape prices from the generated links
        flipkart_price = scrape_flipkart(flipkart_link)
        amazon_price = scrape_amazon(amazon_link)
        croma_price = scrape_croma(croma_link)

        # Compare prices to find the best deal
        best_price, best_deal = compare_prices(flipkart_price, amazon_price, croma_price)

        # Render with all scraped and calculated information for POST request
        return render_template(
            'index.html',
            product_name=product_name,
            flipkart_price=flipkart_price,
            amazon_price=amazon_price,
            croma_price=croma_price,
            best_price=best_price,
            best_deal=best_deal,
            flipkart_link=flipkart_link,
            amazon_link=amazon_link,
            croma_link=croma_link
        )

    # Render template for GET request
    return render_template('index.html', product_name=product_name)



# Route to handle adding items to the cart
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    user_id = session.get('user_id')
    if not user_id:
        return render_template('error.html', error="User not authenticated"), 403  # Render error page if not authenticated

    product = request.form.get('product')
    price = request.form.get('price')
    product_name = request.form.get('product_name')


    if not product or not price:
        return render_template('error.html', error="Missing product or price"), 400  # Render error page if product/price is missing

    # Prepare product data
    product_data = {
        "product": product,
        "price": price,
        "product_name":product_name
    }

    # Reference to the user's cart in Firestore
    cart_ref = db.collection('carts').document(user_id)
    cart_doc = cart_ref.get()
    if cart_doc.exists:
        cart_ref.update({"items": firestore.ArrayUnion([product_data])})
    else:
        cart_ref.set({"items": [product_data]})

    # Flash notification message
    flash("Item added to cart!")
    return redirect(url_for('cart'))

# Route to display the cart items
@app.route('/cart')
def cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login_or_register'))  # Ensure user is authenticated

    # Reference to the user's cart in Firestore
    cart_ref = db.collection('carts').document(user_id)
    cart_doc = cart_ref.get()

    cart_items = []
    total_price = 0

    if cart_doc.exists:
        cart_items = cart_doc.to_dict().get('items', [])
        # Calculate the total price
        total_price = sum(float(item['price'].replace('₹', '').replace(',', '').strip()) for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)
    
@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login_or_register'))

    product_name = request.form.get('product_name')
    product = request.form.get('product')

    # Reference to the user's cart in Firestore
    cart_ref = db.collection('carts').document(user_id)
    cart_doc = cart_ref.get()

    if cart_doc.exists:
        cart_items = cart_doc.to_dict().get('items', [])
        
        # Filter out the item to be removed, checking if 'product' and 'product_name' are present
        updated_cart_items = [
            item for item in cart_items
            if not (item.get('product') == product and item.get('product_name') == product_name)
        ]
        
        # Update Firestore with the new list
        cart_ref.update({"items": updated_cart_items})

    return redirect(url_for('cart'))

# Logic for Password reset function
def send_password_reset_email(email):
    try:
        link = auth.generate_password_reset_link(email)
        logging.info("Password reset link generated successfully.")
        print("Password reset link:", link)
        return True
    except ValueError as ve:
        logging.error(f"ValueError occurred while generating password reset link: {ve}")
        return False
    except auth.UserNotFoundError as unf:
        logging.error(f"UserNotFoundError: {unf}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending password reset email: {e}")
        return False

# Route for password reset
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        if send_password_reset_email(email):
            return "Password reset email has been sent. Please check your inbox."
        else:
            return "An error occurred while sending the password reset email."
    return render_template('forgot_password.html')

# Route to logout
@app.route('/logout')
def logout():
    # Clear the user's session
    session.clear()
    # Redirect to the login page
    return redirect(url_for('login_or_register'))

if __name__ == '__main__':
    app.run(debug=True)
