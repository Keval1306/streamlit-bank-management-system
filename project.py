import streamlit as st
import json
import os
import random
import datetime
import pandas as pd
import plotly.express as px
import time
import math

# --- CONFIGURATION & CONSTANTS ---
DATA_FILE = "bank_data.json"
MIN_BALANCE_SAVINGS = 10000
OVERDRAFT_BASE_LIMIT = 50000
OVERDRAFT_FIXED_RATE = 0.10  # 10% Flat Rate
ADMIN_PASSWORD = "admin123"

BRANCH_DATA = {
    "LJ University": {"code": "LJU001", "address": "S.G. Highway", "tel": "079-111111"},
    "Bodakdev": {"code": "BDK002", "address": "Judges Bungalow Rd", "tel": "079-222222"},
    "Gurukul": {"code": "GRK003", "address": "Drive In Rd", "tel": "079-333333"},
    "Vasna": {"code": "VSN004", "address": "Vasna Barrage Rd", "tel": "079-444444"}
}

# --- LOAN CALCULATOR LOGIC ---
class LoanType:
    def __init__(self, name, max_amount, min_tenure, max_tenure, base_rate):
        self.name = name
        self.max_amount = max_amount
        self.min_tenure = min_tenure
        self.max_tenure = max_tenure
        self.base_rate = base_rate

    def calculate_rate(self, cibil_score):
        if cibil_score >= 750: return max(0.01, self.base_rate - 0.01)
        elif 650 <= cibil_score < 750: return self.base_rate
        else: return self.base_rate + 0.02

LOAN_OPTS = {
    "Home Loan": LoanType("Home", 5000000, 5, 30, 0.07),
    "Personal Loan": LoanType("Personal", 500000, 1, 5, 0.10),
    "Credit Line": LoanType("Credit", 200000, 1, 3, 0.15),
    "Vehicle Loan": LoanType("Vehicle", 1000000, 2, 7, 0.08)
}

# --- HELPER FOR RERUN ---
def safe_rerun():
    """Handles rerun compatibility for different Streamlit versions."""
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# --- CORE DATA OPERATIONS ---
def load_data():
    defaults = {
        "bank_balance": 10000000, 
        "pending_loans": [], 
        "reactivation_requests": []
    }
    
    if not os.path.exists(DATA_FILE): 
        return defaults
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Ensure all keys exist
            for key, val in defaults.items():
                if key not in data:
                    data[key] = val
            return data
    except: return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def show_processing(text="Processing..."):
    """Creates a realistic 2-second delay with a progress bar."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    for percent in range(100):
        time.sleep(0.02) # Total 2 seconds
        progress_bar.progress(percent + 1)
        status_text.text(f"{text} {percent+1}%")
    progress_bar.empty()
    status_text.empty()

# --- UTILITY FUNCTIONS ---
def get_current_date(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def verify_pin(user_data, account_index, input_pin):
    return user_data["accounts"][account_index]["pin"] == input_pin

def get_overdraft_limit(cibil):
    if cibil >= 750: return 100000
    elif cibil >= 650: return 75000
    else: return OVERDRAFT_BASE_LIMIT

def calculate_emi(principal, annual_rate, tenure_years):
    if tenure_years == 0: return principal
    monthly_rate = annual_rate / 12
    num_months = tenure_years * 12
    if monthly_rate == 0:
        return principal / num_months
    emi = (principal * monthly_rate * ((1 + monthly_rate)**num_months)) / (((1 + monthly_rate)**num_months) - 1)
    return round(emi, 2)

def add_transaction(user_data, account_index, t_type, amount, description):
    current_bal = user_data["accounts"][account_index]["balance"]
    t = {
        "date": get_current_date(),
        "type": t_type,
        "amount": f"₹{amount:,.2f}",
        "description": description,
        "balance_after": current_bal
    }
    user_data["accounts"][account_index]["transactions"].append(t)

# --- APP PAGES ---

def admin_panel():
    st.title("🏦 Central Bank Administration")
    data = load_data()
    
    col1, col2 = st.columns(2)
    col1.metric("Total Bank Liquidity", f"₹{data.get('bank_balance', 0):,.2f}")
    
    # --- TABS FOR ADMIN ---
    tab1, tab2, tab3 = st.tabs(["Pending Loans", "Account Management", "Reactivation Requests"])

    # 1. LOAN APPROVALS
    with tab1:
        st.subheader("Pending Loan Approvals")
        if not data["pending_loans"]:
            st.info("No active loan requests.")
        else:
            for idx, req in enumerate(data["pending_loans"]):
                with st.expander(f"REQ: {req['id']} | User: {req['username']} | Amount: ₹{req['principal']}"):
                    st.write(f"**Type:** {req['type']} | **Interest:** {req['interest_rate']}")
                    c1, c2 = st.columns(2)
                    
                    if c1.button("Approve", key=f"app_{idx}"):
                        show_processing("Disbursing Loan Funds...")
                        u, acc_idx = req["username"], req["account_index"]
                        rate_val = float(req["interest_rate"].strip('%')) / 100
                        emi = calculate_emi(req["principal"], rate_val, req["tenure_years"])
                        total_p = emi * req["tenure_years"] * 12
                        
                        loan_record = {
                            "id": req["id"], "type": req["type"], "principal": req["principal"],
                            "total_amount_payable": total_p, "total_paid": 0, "remaining_amount": total_p,
                            "total_interest": total_p - req["principal"], "emi_amount": emi, 
                            "status": "Active", "date": get_current_date()
                        }
                        data[u]["accounts"][acc_idx]["loans"].append(loan_record)
                        data[u]["accounts"][acc_idx]["balance"] += req["principal"]
                        data["bank_balance"] -= req["principal"]
                        add_transaction(data[u], acc_idx, "CREDIT", req["principal"], f"Loan Disbursed: {req['id']}")
                        del data["pending_loans"][idx]
                        save_data(data)
                        safe_rerun()
                    
                    if c2.button("Reject", key=f"rej_{idx}", type="secondary"):
                        show_processing("Processing Rejection...")
                        u, acc_idx = req["username"], req["account_index"]
                        rej_record = {"id": req["id"], "type": req["type"], "status": "Rejected", "date": get_current_date()}
                        data[u]["accounts"][acc_idx]["loans"].append(rej_record)
                        del data["pending_loans"][idx]
                        save_data(data)
                        safe_rerun()

    # 2. ACCOUNT MANAGEMENT (DEACTIVATE / REMOVE)
    with tab2:
        st.subheader("Manage User Accounts")
        usernames = [u for u in data if isinstance(data[u], dict) and "accounts" in data[u]]
        
        if usernames:
            selected_user = st.selectbox("Select User", usernames)
            # Show all accounts for the user
            user_accounts = data[selected_user]["accounts"]
            
            if user_accounts:
                account_options = []
                for i, acc in enumerate(user_accounts):
                    status_icon = "🟢" if acc.get("status", "active") == "active" else "🔴"
                    account_options.append(f"{status_icon} {acc['account_number']} ({acc['account_type']}) - {acc.get('status', 'active').upper()}")

                selected_acc_str = st.selectbox("Select Account", account_options)
                
                # Find index based on selection
                acc_idx = account_options.index(selected_acc_str)
                target_acc = user_accounts[acc_idx]

                st.divider()
                st.write(f"**Current Status:** {target_acc.get('status', 'active')}")
                st.write(f"**Balance:** ₹{target_acc['balance']:,.2f}")

                # Use a Form for Admin Action
                with st.form("admin_action_form"):
                    action = st.radio("Choose Action", ["Deactivate Account", "Remove Account"])
                    reason = st.text_area("Reason (Required for audit)")
                    submit_admin = st.form_submit_button("Execute Action")

                if submit_admin:
                    if not reason.strip():
                        st.error("Please provide a reason.")
                    else:
                        if action == "Deactivate Account":
                            if target_acc.get("status") == "deactivated":
                                st.warning("Account is already deactivated.")
                            else:
                                show_processing("Deactivating Account...")
                                data[selected_user]["accounts"][acc_idx]["status"] = "deactivated"
                                data[selected_user]["accounts"][acc_idx]["admin_note"] = reason
                                save_data(data)
                                st.success("Account Deactivated Successfully.")
                                safe_rerun()

                        elif action == "Remove Account":
                            show_processing("Permanently Deleting Data...")
                            del data[selected_user]["accounts"][acc_idx]
                            
                            # If user has no more accounts, remove user entry entirely
                            if not data[selected_user]["accounts"]:
                                del data[selected_user]
                            
                            save_data(data)
                            st.success("Account and Data Removed Permanently.")
                            safe_rerun()
            else:
                st.warning("User has no accounts.")
        else:
            st.info("No users found in database.")

    # 3. REACTIVATION REQUESTS
    with tab3:
        st.subheader("User Reactivation Requests")
        if not data.get("reactivation_requests"):
            st.info("No pending requests.")
        else:
            for idx, req in enumerate(data["reactivation_requests"]):
                with st.container():
                    st.error(f"Request from: **{req['username']}**")
                    st.write(f"**Account:** {req['account_number']}")
                    st.write(f"**Reason:** {req['message']}")
                    st.caption(f"Date: {req['date']}")
                    
                    if st.button("Approve Reactivation", key=f"react_{idx}"):
                        show_processing("Reactivating Account...")
                        u = req['username']
                        if u in data:
                            for acc in data[u]["accounts"]:
                                if acc["account_number"] == req["account_number"]:
                                    acc["status"] = "active"
                                    if "admin_note" in acc: del acc["admin_note"]
                            
                            del data["reactivation_requests"][idx]
                            save_data(data)
                            st.success(f"Account for {u} is now Active.")
                            safe_rerun()
                        else:
                            st.error("User data no longer exists.")
                    st.markdown("---")
    
    st.divider()
    if st.button("Logout (Admin)"):
        st.session_state["logged_in"] = False
        safe_rerun()

def main_banking_interface():
    data = load_data()
    user = st.session_state["username"]
    
    if user not in data:
        st.session_state["logged_in"] = False
        safe_rerun()
    
    user_accounts = data[user]["accounts"]
    
    if not user_accounts:
        st.error("No accounts found linked to this user.")
        if st.button("Logout"):
            st.session_state["logged_in"] = False
            safe_rerun()
        return

    # Automatically select the first account
    account_index = 0
    acc = user_accounts[account_index]
    
    # --- CHECK STATUS (Active vs Deactivated) ---
    if acc.get("status", "active") == "deactivated":
        st.title("⛔ Account Deactivated")
        st.error(f"This account ({acc['account_number']}) has been deactivated by the Admin.")
        
        if "admin_note" in acc:
            st.info(f"**Admin Reason:** {acc['admin_note']}")
            
        st.subheader("Request Reactivation")
        
        with st.form("reactivation_form"):
            req_msg = st.text_area("Application Message", placeholder="Please explain why your account should be reactivated...")
            submit_req = st.form_submit_button("Send Request to Admin")
        
        if submit_req:
            if req_msg.strip():
                show_processing("Sending Application...")
                existing = any(r['username'] == user and r['account_number'] == acc['account_number'] for r in data.get("reactivation_requests", []))
                
                if not existing:
                    new_req = {
                        "username": user,
                        "account_number": acc["account_number"],
                        "message": req_msg,
                        "date": get_current_date()
                    }
                    data["reactivation_requests"].append(new_req)
                    save_data(data)
                    st.success("Application sent successfully! Wait for Admin approval.")
                else:
                    st.warning("A request is already pending for this account.")
            else:
                st.error("Message cannot be empty.")
                
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            safe_rerun()
        return

    # --- NORMAL BANKING FLOW ---
    acc_type = acc["account_type"]
    base_choices = ["Dashboard", "Deposit", "Withdraw", "Check Balance", "Transfer Money", "CIBIL Score" , "History", "Logout"]
    choices = base_choices + ["Loans"] if acc_type == "Savings" else base_choices + ["Overdraft"]
    
    st.sidebar.title(f"Welcome, {acc['account_name']}")
    choice = st.sidebar.radio("Navigation", choices)

    if choice == "Dashboard":
        st.title("Account Overview")
        c1, c2, c3 = st.columns(3)
        c1.metric("Account Holder", acc['account_name'])
        c2.metric("Type", acc["account_type"])
        c3.metric("CIBIL Score", acc.get("cibil", 550))
        
        st.info(f"**Account Number:** {acc['account_number']} | **IFSC:** {acc['ifsc']}")
        st.write(f"**Branch:** {acc['branch_name']} - {acc['branch_addr']}")
        st.write(f"**Branch Telephone:** {BRANCH_DATA[acc['branch_name']]['tel']}")

    elif choice == "Deposit":
        st.header("Cash Deposit")
        # Use Form to avoid session state errors on clear
        with st.form("deposit_form"):
            amt = st.number_input("Enter Amount", min_value=100.0)
            pin = st.text_input("Enter PIN", type="password")
            submit_dep = st.form_submit_button("Deposit Funds")
            
        if submit_dep:
            if verify_pin(data[user], account_index, pin):
                show_processing("Safe-locking deposit...")
                acc["balance"] += amt
                data["bank_balance"] += amt
                add_transaction(data[user], account_index, "CREDIT", amt, "Cash Deposit")
                save_data(data)
                st.success("Successfully Deposited!")
            else: st.error("Incorrect PIN")

    elif choice == "Withdraw":
        st.header("Withdrawal")
        with st.form("withdraw_form"):
            amt = st.number_input("Enter Amount", min_value=100.0)
            pin = st.text_input("Enter PIN", type="password")
            submit_with = st.form_submit_button("Withdraw Funds")
            
        if submit_with:
            if verify_pin(data[user], account_index, pin):
                if acc_type == "Savings" and acc["balance"] - amt < MIN_BALANCE_SAVINGS:
                    st.error(f"Cannot withdraw. Minimum balance ₹{MIN_BALANCE_SAVINGS} required.")
                elif acc_type == "Current" and acc["balance"] - amt < -get_overdraft_limit(acc["cibil"]):
                    st.error(f"Exceeds overdraft limit.")
                else:
                    show_processing("Dispensing Cash...")
                    acc["balance"] -= amt
                    data["bank_balance"] -= amt
                    add_transaction(data[user], account_index, "DEBIT", amt, "Cash Withdrawal")
                    save_data(data)
                    st.success("Withdrawal Complete!")
            else: st.error("Incorrect PIN")

    elif choice == "Check Balance":
        st.header("Secure Balance Check")
        with st.form("balance_form"):
            pin = st.text_input("Enter PIN", type="password")
            submit_bal = st.form_submit_button("Check")
            
        if submit_bal:
            if verify_pin(data[user], account_index, pin):
                show_processing("Communicating with Server...")
                st.metric("Available Balance", f"₹{acc['balance']:,.2f}")
            else: st.error("Wrong PIN")
                
    elif choice == "CIBIL Score":
        st.header("📊 Credit Information Report")
        current_score = acc.get("cibil", 700)
        st.metric("Current CIBIL Score", current_score)

        st.divider()
        st.subheader("Update Your Credit Record")
        new_cibil = st.slider("Simulate/Update Score", 300, 900, current_score)

        if st.button("Update CIBIL Record"):
            # Progress bar animation as requested
            show_processing("Connecting to Credit Bureau...")
            acc["cibil"] = new_cibil
            save_data(data)
            st.success(f"CIBIL Score successfully updated to {new_cibil}!")
            time.sleep(1)
            safe_rerun()

    elif choice == "Transfer Money":
        st.header("Transfer to Another Account")
        with st.form("transfer_form"):
            recipient_username = st.text_input("Recipient Username")
            recipient_acc_no = st.text_input("Recipient Account Number")
            amt = st.number_input("Amount to Transfer", min_value=100.0)
            pin = st.text_input("Your PIN", type="password")
            submit_trans = st.form_submit_button("Transfer")
        
        if submit_trans:
            if verify_pin(data[user], account_index, pin):
                if recipient_username not in data or not data[recipient_username].get("accounts"):
                    st.error("Recipient not found.")
                else:
                    recipient_accounts = data[recipient_username]["accounts"]
                    recipient_acc = next((acc for acc in recipient_accounts if acc["account_number"] == recipient_acc_no and acc.get("status", "active") == "active"), None)
                    if not recipient_acc:
                        st.error("Recipient account not found or inactive.")
                    else:
                        balance_after_transfer = acc["balance"] - amt
                        
                        if acc_type == "Savings" and balance_after_transfer < MIN_BALANCE_SAVINGS:
                            st.error(f"Cannot withdraw. Minimum balance ₹{MIN_BALANCE_SAVINGS} required.")
                        elif acc_type == "Current" and balance_after_transfer < -get_overdraft_limit(acc["cibil"]):
                            st.error(f"Insufficient funds. Exceeds overdraft limit.")
                        elif acc["balance"] < amt and acc_type == "Savings":
                             st.error("Insufficient balance.")
                        else:
                            show_processing("Transferring Funds...")
                            acc["balance"] -= amt
                            recipient_acc["balance"] += amt
                            add_transaction(data[user], account_index, "DEBIT", amt, f"Transfer to {recipient_username} ({recipient_acc_no})")
                            rec_acc_index = data[recipient_username]["accounts"].index(recipient_acc)
                            add_transaction(data[recipient_username], rec_acc_index, "CREDIT", amt, f"Transfer from {user} ({acc['account_number']})")
                            save_data(data)
                            st.success("Transfer Successful!")
            else: st.error("Incorrect PIN")
               

    elif choice == "Overdraft":
        st.header("Overdraft Facility")
        if acc_type != "Current":
            st.warning("Only Current Accounts have Overdraft access.")
        else:
            used = abs(acc["balance"]) if acc["balance"] < 0 else 0
            limit = get_overdraft_limit(acc["cibil"])
            interest = used * OVERDRAFT_FIXED_RATE
            st.metric("Overdraft Limit", f"₹{limit:,.2f}")
            st.metric("Utilized Limit", f"₹{used:,.2f}")
            st.metric("Fixed Interest (10%)", f"₹{interest:,.2f}")
            
            if acc["balance"] < 0:
                st.warning("Account is in overdraft. You must repay principal and interest.")
            else:
                st.success("No overdraft used.")

    elif choice == "Loans":
        st.header("Loan Services")
        tab1, tab2 = st.tabs(["Apply for Loan", "My Loan Portfolio"])
        
        with tab1:
            st.subheader("Loan Application Calculator")
            # --- MOVED INPUTS OUTSIDE FORM FOR REAL-TIME CALCULATION ---
            l_type = st.selectbox("Select Loan Type", list(LOAN_OPTS.keys()))
            obj = LOAN_OPTS[l_type]
            rate = obj.calculate_rate(acc["cibil"])
            
            col_a, col_b = st.columns(2)
            with col_a:
                amt = st.number_input("Loan Amount (₹)", 10000, obj.max_amount)
            with col_b:
                tenure = st.slider("Tenure (Years)", obj.min_tenure, obj.max_tenure)

            # --- REAL TIME CALCULATION DISPLAY ---
            calc_emi = calculate_emi(amt, rate, tenure)
            total_pay = calc_emi * tenure * 12
            
            st.info(f"**Interest Rate:** {rate*100:.2f}%")
            
            m1, m2 = st.columns(2)
            m1.metric("Estimated Monthly EMI", f"₹{calc_emi:,.2f}")
            m2.metric("Total Repayment Amount", f"₹{total_pay:,.2f}")
            
            st.divider()
            
            # --- FINAL SUBMISSION FORM ---
            with st.form("loan_apply_form"):
                st.write("Confirm your application details above.")
                pin = st.text_input("Enter PIN to Apply", type="password")
                submit_loan = st.form_submit_button("Submit Application")

            if submit_loan:
                if verify_pin(data[user], account_index, pin):
                    show_processing("Sending application to Admin...")
                    req_id = f"LN{random.randint(1000,9999)}"
                    data["pending_loans"].append({
                        "id": req_id, "username": user, "account_index": account_index,
                        "type": l_type, "principal": amt, "interest_rate": f"{rate*100}%",
                        "tenure_years": tenure
                    })
                    save_data(data)
                    st.success("Application Submitted for Approval!")
                else: st.error("Incorrect PIN")

        with tab2:
            if not acc["loans"]:
                st.info("No active or rejected loans.")
            else:
                for l in acc["loans"]:
                    with st.container():
                        st.subheader(f"{l['type']} - {l['id']}")
                        if l["status"] == "Rejected":
                            st.error(f"Status: Rejected (on {l.get('date', 'N/A')})")
                        elif l["status"] == "Active":
                            st.success("Status: Active")
                            st.write(f"**Principal:** ₹{l['principal']:,.2f} | **Total Interest:** ₹{l['total_interest']:,.2f}")
                            st.write(f"**Total Outstanding:** ₹{l['remaining_amount']:,.2f}")
                            
                            emi_val = l['emi_amount']
                            max_possible = math.ceil(l['remaining_amount'] / emi_val)
                            
                            st.divider()
                            st.write(f"**EMI Amount:** ₹{emi_val:,.2f}")
                            
                            # Unique keys for form widgets
                            with st.form(f"emi_form_{l['id']}"):
                                num_emis = st.number_input(f"Number of EMIs to pay", 1, max_possible, step=1, key=f"num_{l['id']}")
                                total_emi_pay = num_emis * emi_val
                                st.info(f"Total Repayment: ₹{total_emi_pay:,.2f}")
                                p_emi = st.text_input(f"PIN", type="password", key=f"pin_{l['id']}")
                                submit_emi = st.form_submit_button("Confirm EMI Payment")
                            
                            if submit_emi:
                                if verify_pin(data[user], account_index, p_emi):
                                    if acc["balance"] >= total_emi_pay:
                                        show_processing("Processing Loan Repayment...")
                                        acc["balance"] -= total_emi_pay
                                        l["remaining_amount"] -= total_emi_pay
                                        l["total_paid"] += total_emi_pay
                                        if l["remaining_amount"] <= 10: l["status"] = "Closed"
                                        add_transaction(data[user], account_index, "DEBIT", total_emi_pay, f"Loan EMI Payment {l['id']}")
                                        save_data(data)
                                        safe_rerun()
                                    else: st.error("Insufficient Funds")
                                else: st.error("Incorrect PIN")
                        st.markdown("---")

    elif choice == "History":
        st.header("Transaction Intelligence")
        if acc["transactions"]:
            df = pd.DataFrame(acc["transactions"])
            fig = px.line(df, x="date", y="balance_after", title="Balance Trend Analysis")
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("Statement")
            st.table(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Transaction History (CSV)",
                data=csv,
                file_name=f"statement_{acc['account_number']}.csv",
                mime="text/csv",
            )
        else: st.info("No transaction history available.")

    if choice == "Logout":
        st.session_state["logged_in"] = False
        safe_rerun()

# --- AUTH SYSTEM ---
def auth_page():
    st.title("🏦 Secure Digital Banking")
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    data = load_data()
    
    with tab1:
        u = st.text_input("Username", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Login"):
            if u == "admin" and p == ADMIN_PASSWORD:
                st.session_state.update({"logged_in": True, "is_admin": True})
                safe_rerun()
            elif u in data and data[u]["password"] == p:
                st.session_state.update({"logged_in": True, "is_admin": False, "username": u})
                safe_rerun()
            else: st.error("Invalid credentials")

    with tab2:
        # --- FIX: Moved Account Type Selection OUTSIDE the form ---
        # This ensures the script reruns and updates min_dep BEFORE the form renders
        acc_type_choice = st.selectbox("Select Account Type", ["Savings", "Current"], key="reg_acc_type")
        
        # Calculate minimum deposit based on the SELECTION immediately
        min_dep_val = MIN_BALANCE_SAVINGS if acc_type_choice == "Savings" else 0.0
        
        with st.form("register_form"):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            
            branch = st.selectbox("Branch", list(BRANCH_DATA.keys()))
            
            # Use the calculated min_dep_val here
            init_dep = st.number_input(f"Initial Deposit (Min: ₹{min_dep_val})", min_value=min_dep_val)
            
            new_pin = st.text_input("Set 4-Digit PIN", type="password", max_chars=4)
            submit_reg = st.form_submit_button("Register & Open Account")
        
        if submit_reg:
            if new_u in data: st.error("User exists")
            elif not new_pin.isdigit(): st.error("PIN must be numeric")
            else:
                show_processing("Creating Account...")
                b_info = BRANCH_DATA[branch]
                data[new_u] = {
                    "password": new_p,
                    "accounts": [{
                        "account_name": new_u, "account_number": str(random.randint(10**9, 10**10-1)),
                        "account_type": acc_type_choice, "balance": init_dep, "pin": new_pin,
                        "branch_name": branch, "branch_addr": b_info["address"],
                        "ifsc": "BANK" + b_info["code"], "cibil": 550,
                        "transactions": [], "loans": [], "status": "active"
                    }]
                }
                data["bank_balance"] += init_dep
                save_data(data)
                st.success("Account Created! Please Login.")

def main():
    if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
    
    if st.session_state["logged_in"]:
        if st.session_state.get("is_admin"): admin_panel()
        else: main_banking_interface()
    else: auth_page()

if __name__ == "__main__":
    st.set_page_config(page_title="Pro-Bank", page_icon="🏦", layout="wide")
    main()