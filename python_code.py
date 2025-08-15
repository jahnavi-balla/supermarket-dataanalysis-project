import streamlit as st
import pandas as pd
import mysql.connector
from sqlalchemy import create_engine
from datetime import datetime

# ---------- DB Connection ----------
@st.cache_resource
def connect_to_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password="1234",
            database="supermarket_db"
        )
        engine = create_engine("mysql+mysqlconnector://root:1234@localhost:3306/supermarket_db")
        return conn, engine
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None, None

# ---------- Helpers ----------
def generate_invoice_id(engine):
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"INV-{today_str}"
    query = f"SELECT `Invoice ID` FROM sales WHERE `Invoice ID` LIKE '{prefix}%'"
    result = pd.read_sql(query, con=engine)
    if result.empty:
        return f"{prefix}-001"
    else:
        next_number = result['Invoice ID'].str.extract(r'(\d+)$').astype(int).max()[0] + 1
        return f"{prefix}-{str(next_number).zfill(3)}"

def insert_into_db(engine, df):
    try:
        df.to_sql('sales', engine, if_exists="append", index=False)
        return True
    except Exception as e:
        st.error(f"Data insertion failed: {e}")
        return False

def reset_for_next_customer(engine):
    st.session_state.invoice_id = generate_invoice_id(engine)
    st.session_state.products = pd.DataFrame(columns=["Product line", "Unit price", "Quantity"])
    st.session_state.invoice_submitted = False
    st.rerun()

# ---------- UI ----------
def sales_form(engine):
    # Initialize state
    if "invoice_id" not in st.session_state:
        st.session_state.invoice_id = generate_invoice_id(engine)
    if "products" not in st.session_state:
        st.session_state.products = pd.DataFrame(columns=["Product line", "Unit price", "Quantity"])
    if "invoice_submitted" not in st.session_state:
        st.session_state.invoice_submitted = False

    st.title("🛒 Supermarket Sales Entry")
    st.write("Enter details for one invoice with multiple products.")
    st.markdown(f"**Generated Invoice ID:** `{st.session_state.invoice_id}`")

    # Invoice-level details
    col1, col2, col3 = st.columns(3)
    city = col1.selectbox('City:', ['Yangon', 'Mandalay', 'Naypyitaw', 'Others'])
    customer_type = col2.selectbox('Customer Type:', ['Normal', 'Member'])
    gender = col3.selectbox('Gender:', ['Male', 'Female', 'Other'])

    col4, col5, col6 = st.columns(3)
    date = col4.date_input('Date:', datetime.now())
    time_ = col5.time_input('Time:', datetime.now().time())
    payment = col6.selectbox('Payment Type:', ['Cash', 'Credit card', 'Ewallet'])

    rating = st.slider('Rating (1-10):', 1, 10, 5)

    # Product input
    st.subheader("📦 Add Products")
    colp1, colp2, colp3 = st.columns(3)
    prod_line = colp1.selectbox('Product Line:', [
        'Health and beauty', 'Electronic accessories', 'Home and lifestyle',
        'Sports and travel', 'Food and beverages', 'Fashion accessories'
    ])
    unit_price = colp2.number_input('Unit Price:', min_value=0.01, step=0.01)
    quantity = colp3.number_input('Quantity:', min_value=1, step=1)

    if st.button("➕ Add Product"):
        new_row = pd.DataFrame([[prod_line, unit_price, quantity]],
                               columns=["Product line", "Unit price", "Quantity"])
        st.session_state.products = pd.concat([st.session_state.products, new_row], ignore_index=True)
        st.rerun()

    # Show product list + delete option
    if not st.session_state.products.empty:
        products_df = st.session_state.products.copy()
        products_df["Tax 5%"] = products_df["Unit price"] * products_df["Quantity"] * 0.05
        products_df["Total"] = products_df["Unit price"] * products_df["Quantity"] + products_df["Tax 5%"]

        for idx, row in products_df.iterrows():
            col_a, col_b = st.columns([6, 1])
            col_a.write(f"**{row['Product line']}** — {row['Quantity']} × ₹{row['Unit price']} = ₹{row['Total']:.2f}")
            if col_b.button("🗑 Delete", key=f"del_{idx}"):
                st.session_state.products.drop(idx, inplace=True)
                st.session_state.products.reset_index(drop=True, inplace=True)
                st.rerun()

        invoice_total = round(products_df["Total"].sum(), 2)
        st.markdown(f"### 💰 Final Invoice Total: **₹{invoice_total}**")

        if not st.session_state.invoice_submitted:
            if st.button("✅ Submit Invoice"):
                # Get branch from city
                CITY_TO_BRANCH = {
                    "Yangon": "A",
                    "Mandalay": "B",
                    "Naypyitaw": "C"
                }
                branch = CITY_TO_BRANCH.get(city, None)

                # Prepare DataFrame for DB insert
                db_rows = []
                for _, row in products_df.iterrows():
                    cogs = row["Unit price"] * row["Quantity"]
                    tax = cogs * 0.05
                    gross_margin = round(((row["Total"] - cogs) / row["Total"]) * 100, 2)
                    db_rows.append([
                        st.session_state.invoice_id, branch, city, customer_type, gender, row["Product line"],
                        row["Unit price"], row["Quantity"], round(tax, 2), round(row["Total"], 2),
                        date, time_, payment, round(cogs, 2), gross_margin, round(tax, 2),
                        rating, date.month, date.year
                    ])

                final_df = pd.DataFrame(db_rows, columns=[
                    "Invoice ID", "Branch", "City", "Customer type", "Gender", "Product line",
                    "Unit price", "Quantity", "Tax 5%", "Total", "Date", "Time", "Payment",
                    "cogs", "gross margin percentage", "gross income", "Rating", "Month", "Year"
                ])

                if insert_into_db(engine, final_df):
                    st.success(f"Invoice {st.session_state.invoice_id} submitted successfully!")
                    st.session_state.invoice_submitted = True

        # Show Record Next Customer button only after submission
        if st.session_state.invoice_submitted:
            if st.button("🆕 Record Next Customer"):
                reset_for_next_customer(engine)

# ---------- Main ----------
def main():
    conn, engine = connect_to_db()
    if not conn:
        st.stop()
    sales_form(engine)

if __name__ == "__main__":
    main()
