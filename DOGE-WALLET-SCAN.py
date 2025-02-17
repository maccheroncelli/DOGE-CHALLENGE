#!/usr/bin/env python
import sqlite3
import os
import time
import csv
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from bip32 import BIP32, HARDENED_INDEX
from mnemonic import Mnemonic
from hashlib import sha256, new
import binascii, base58

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants and DB file
DB_FILE = "DOGECOIN.db"  # Updated database name
DOGECOIN_PREFIX = b'\x1e'      # For address generation (P2PKH)
DOGECOIN_WIF_PREFIX = b'\x9e'  # For WIF conversion

# BlockDaemon endpoint (we now prompt for the API key in step 2)
DOGE_BASE_URL = "https://svc.blockdaemon.com/universal/v1/dogecoin/mainnet/account"

# -----------------------------------------------------------
# Common database setup used by multiple functions
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mnemonics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mnemonic TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE NOT NULL,
            derivation_path TEXT NOT NULL,
            transactions INTEGER DEFAULT 0,
            checked INTEGER DEFAULT 0,
            coin_type INTEGER DEFAULT 3,
            balance REAL DEFAULT 0,
            mnemonic_id INTEGER,
            wif TEXT,
            FOREIGN KEY (mnemonic_id) REFERENCES mnemonics(id)
        )
    """)
    conn.commit()
    return conn, cursor

# -----------------------------------------------------------
# 1. Generate DOGE addresses
def pubkey_to_doge_address(pubkey: bytes) -> str:
    pubkey_hash = sha256(pubkey).digest()
    ripemd160 = new('ripemd160')
    ripemd160.update(pubkey_hash)
    hashed_pubkey = ripemd160.digest()
    prefixed_pubkey = DOGECOIN_PREFIX + hashed_pubkey
    checksum = sha256(sha256(prefixed_pubkey).digest()).digest()[:4]
    final_address_bytes = prefixed_pubkey + checksum
    return base58.b58encode(final_address_bytes).decode()

def generate_and_store_addresses(seed_phrase, account_start=0, account_end=0, 
                                 include_change=False, include_hardened=False, 
                                 address_start=0, num_addresses=100,
                                 coin_enum=None, coin_type_str="3", mnemonic_id=None):
    try:
        conn, cursor = setup_database()
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return
    seed = Bip39SeedGenerator(seed_phrase).Generate()
    if coin_type_str == "0":
        bip32_ctx = BIP32.from_seed(seed)
    else:
        bip44_ctx = Bip44.FromSeed(seed, coin_enum)
    address_count = 0
    for hardened in ([False, True] if include_hardened and coin_type_str != "0" else [False]):
        for account in range(account_start, account_end + 1):
            for change in ([0, 1] if include_change else [0]):
                for i in range(address_start, address_start + num_addresses):
                    if coin_type_str != "0":
                        account_index = account + (2**31 if hardened else 0)
                        address_index = i + (2**31 if hardened else 0)
                        path_str = f"m/44'/{coin_type_str}'/{account}{'h' if hardened else ''}/{change}/{i}{'h' if hardened else ''}"
                        address_ctx = (bip44_ctx.Purpose()
                                       .Coin()
                                       .Account(account_index)
                                       .Change(Bip44Changes.CHAIN_EXT if change == 0 else Bip44Changes.CHAIN_INT)
                                       .AddressIndex(address_index))
                        address = address_ctx.PublicKey().ToAddress()
                    else:
                        path_list = [44 | HARDENED_INDEX, 0 | HARDENED_INDEX, account | HARDENED_INDEX, change, i]
                        pubkey = bip32_ctx.get_pubkey_from_path(path_list)
                        address = pubkey_to_doge_address(pubkey)
                        path_str = f"m/44'/0'/{account}'/{change}/{i}"
                    try:
                        cursor.execute(
                            """
                            INSERT INTO addresses (address, derivation_path, transactions, checked, coin_type, balance, mnemonic_id, wif)
                            VALUES (?, ?, 0, 0, ?, 0, ?, NULL)
                            """,
                            (address, path_str, int(coin_type_str), mnemonic_id)
                        )
                    except sqlite3.IntegrityError:
                        pass
                    address_count += 1
                    if address_count % 100 == 0:
                        print(f"Generated and stored {address_count} addresses")
    conn.commit()
    conn.close()
    print(f"Address generation and storage complete. Total addresses: {address_count}")

def generate_addresses():
    print("\n--- Generate DOGE Addresses ---")
    seed_phrase = input("Enter your seed phrase: ").strip()
    transition = input("Generate pre-SLIP0044 (coin type '0') or post-SLIP0044 (coin type '3') addresses? (Default '3'): ").strip().lower()
    if transition == "0":
        coin_enum = None
        coin_type_str = "0"
    else:
        coin_enum = Bip44Coins.DOGECOIN
        coin_type_str = "3"
    try:
        account_start = int(input("Enter starting account (default 0): ") or 0)
        account_end_input = input(f"Enter ending account (default {account_start}): ").strip()
        account_end = int(account_end_input) if account_end_input else account_start
    except ValueError:
        print("Invalid account numbers. Exiting address generation.")
        return
    include_change = input("Generate external and internal (change) addresses? (yes/no, default no): ").strip().lower() == "yes"
    include_hardened = False
    if coin_type_str != "0":
        include_hardened = input("Generate both non-hardened and hardened addresses? (yes/no, default no): ").strip().lower() == "yes"
    try:
        address_start = int(input("Enter starting address index (default 0): ") or 0)
        num_addresses = int(input("Enter number of addresses to generate per combination (default 100): ") or 100)
    except ValueError:
        print("Invalid address index or count. Exiting address generation.")
        return
    num_accounts = account_end - account_start + 1
    multiplier_change = 2 if include_change else 1
    multiplier_hardened = 2 if include_hardened and coin_type_str != "0" else 1
    total_addresses = num_addresses * num_accounts * multiplier_change * multiplier_hardened
    if coin_type_str == "0":
        starting_path = f"m/44'/0'/{account_start}'/0/{address_start}"
    else:
        starting_path = f"m/44'/{coin_type_str}'/{account_start}'/0/{address_start}"
    finishing_index = address_start + num_addresses - 1
    if coin_type_str == "0":
        finishing_path = f"m/44'/0'/{account_end}'/0/{finishing_index}"
    else:
        last_hardened = True if include_hardened and coin_type_str != "0" else False
        last_change = 1 if include_change else 0
        finishing_path = f"m/44'/{coin_type_str}'/{account_end}{'h' if last_hardened else ''}/{last_change}/{finishing_index}{'h' if last_hardened else ''}"
    print(f"\nThe starting derivation path will be: {starting_path}")
    print(f"For each account, addresses {address_start} to {finishing_index} will be generated.")
    print(f"The finishing derivation path will be: {finishing_path}")
    print(f"You are about to generate a total of {total_addresses} addresses.")
    proceed = input("Proceed? (yes/no) [default: yes]: ").strip().lower()
    if proceed not in ("", "yes", "y"):
        print("Address generation cancelled.")
        return
    conn, cursor = setup_database()
    try:
        cursor.execute("INSERT INTO mnemonics (mnemonic) VALUES (?)", (seed_phrase,))
        mnemonic_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM mnemonics WHERE mnemonic = ?", (seed_phrase,))
        mnemonic_id = cursor.fetchone()[0]
    conn.close()
    generate_and_store_addresses(
        seed_phrase, account_start, account_end, include_change, include_hardened,
        address_start, num_addresses, coin_enum=coin_enum, coin_type_str=coin_type_str,
        mnemonic_id=mnemonic_id
    )
    print("Returning to main menu...\n")

# -----------------------------------------------------------
# 2. Check DOGE addresses for transaction activity & funds with BlockDaemon API
def check_addresses(batch_size=5):
    print("\n--- Check DOGE Addresses for Transaction Activity & Funds ---")
    if not os.path.exists(DB_FILE):
        logging.error("Database file not found. Please generate addresses first.")
        return
    # Prompt the user for their unique Blockdaemon API key.
    api_key = input("Enter your Blockdaemon API key: ").strip()
    headers = {
        "accept": "application/json",
        "X-API-Key": api_key
    }
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    def display_upfront_stats(cursor):
        cursor.execute("SELECT COUNT(*) FROM addresses")
        total_addresses = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM addresses WHERE checked = 1")
        processed_addresses = cursor.fetchone()[0]
        unchecked_addresses = total_addresses - processed_addresses
        logging.info("==================================================")
        logging.info("Initial Address Statistics:")
        logging.info(f"Total Addresses: {total_addresses}")
        logging.info(f"Processed Addresses: {processed_addresses}")
        logging.info(f"Unchecked Addresses: {unchecked_addresses}")
        logging.info("==================================================")
        return total_addresses, processed_addresses, unchecked_addresses
    total_addresses, processed_addresses, total_unchecked = display_upfront_stats(cursor)
    if total_unchecked == 0:
        logging.info("All addresses have already been processed.")
        conn.close()
        return
    processed_count = 0
    start_time = time.time()
    def check_transaction_exists(address, coin_type, retries=3, delay=2, session=None):
        session = session or requests.Session()
        url = f"{DOGE_BASE_URL}/{address}/txs?page_size=1&order=desc"
        for attempt in range(retries):
            try:
                response = session.get(url, headers=headers)
                if response.status_code == 429:
                    logging.error(f"429 Too Many Requests for {address} (txs check). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                elif response.status_code == 400:
                    logging.error(f"400 Bad Request for {address} (txs check). Possibly invalid for Dogecoin.")
                    return False
                response.raise_for_status()
                data = response.json()
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    tx_list = data["data"][0]
                    return len(tx_list) > 0
                else:
                    logging.debug(f"No tx data for {address}: {data}")
                    return False
            except Exception as e:
                logging.error(f"Error checking tx existence for {address}: {e}")
                return False
        logging.error(f"Max retries exceeded for tx check on {address}")
        return False
    def fetch_balance(address, coin_type, retries=3, delay=2, session=None):
        session = session or requests.Session()
        asset = "dogecoin/native/doge"
        url = f"{DOGE_BASE_URL}/{address}?assets={asset}"
        for attempt in range(retries):
            try:
                response = session.get(url, headers=headers)
                if response.status_code == 429:
                    logging.error(f"429 Too Many Requests for {address} (balance check). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                elif response.status_code == 400:
                    logging.error(f"400 Bad Request for {address} (balance check).")
                    return 0
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    balance_info = data[0]
                    confirmed = balance_info.get("confirmed_balance", "0")
                    try:
                        return float(confirmed)
                    except:
                        return 0
                else:
                    logging.debug(f"No balance data for {address}: {data}")
                    return 0
            except Exception as e:
                logging.error(f"Error fetching balance for {address}: {e}")
                return 0
        logging.error(f"Max retries exceeded for balance check on {address}")
        return 0
    def process_address(item, session):
        addr, coin_type = item
        has_tx = check_transaction_exists(addr, coin_type, session=session)
        if has_tx:
            tx_flag = 1
            balance = fetch_balance(addr, coin_type, session=session)
        else:
            tx_flag = 0
            balance = 0
        return addr, tx_flag, balance
    with requests.Session() as session:
        while True:
            cursor.execute("SELECT id, address, derivation_path, coin_type FROM addresses WHERE checked = 0 LIMIT ?", (batch_size,))
            rows = cursor.fetchall()
            if not rows:
                logging.info("All addresses have been processed.")
                break
            address_map = {address: (row_id, derivation_path, coin_type) for row_id, address, derivation_path, coin_type in rows}
            items = [(addr, address_map[addr][2]) for addr in address_map]
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                results = list(executor.map(lambda x: process_address(x, session), items))
            for address, tx_flag, balance in results:
                row_id, derivation_path, coin_type = address_map[address]
                cursor.execute(
                    "UPDATE addresses SET transactions = ?, balance = ?, checked = 1 WHERE id = ?",
                    (tx_flag, balance, row_id)
                )
                flag_str = "yes" if tx_flag == 1 else "no"
                if tx_flag:
                    logging.info(f"Address: {address}, Transactions: {flag_str}, Balance: {balance}, Derivation Path: {derivation_path}")
                processed_count += 1
            conn.commit()
            if processed_count % 30 == 0 or processed_count >= (total_addresses - processed_addresses):
                elapsed_time = time.time() - start_time
                remaining = (total_addresses - processed_addresses) - processed_count
                percentage = (processed_count / (total_addresses - processed_addresses)) * 100
                avg_time = elapsed_time / processed_count if processed_count else 0
                est_remaining = avg_time * remaining
                logging.info(f"Progress: {processed_count}/{total_addresses - processed_addresses} ({percentage:.2f}%)")
                logging.info(f"Estimated Time Remaining: {est_remaining:.2f} seconds")
                logging.info("--------------------------------------------------")
            time.sleep(1)
    logging.info(f"Processed all {processed_count} addresses.")
    conn.close()
    print("Returning to main menu...\n")

# -----------------------------------------------------------
# 3. Generate WIF Private Keys for DOGE addresses with transaction history
def parse_derivation_path(path_str: str) -> list:
    if not path_str.startswith("m/"):
        raise ValueError("Invalid derivation path format.")
    segments = path_str.lstrip("m/").split("/")
    indices = []
    for seg in segments:
        if seg.endswith("'"):
            idx = int(seg[:-1]) | HARDENED_INDEX
        else:
            idx = int(seg)
        indices.append(idx)
    return indices

def private_key_to_wif(privkey: bytes) -> str:
    prefixed_key = DOGECOIN_WIF_PREFIX + privkey
    checksum = sha256(sha256(prefixed_key).digest()).digest()[:4]
    final_key = prefixed_key + checksum
    return base58.b58encode(final_key).decode()

def derive_wif_for_row(mnemonic: str, derivation_path: str, coin_type: int) -> str:
    if coin_type == 0:
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(mnemonic)
        bip32_ctx = BIP32.from_seed(seed)
        path_list = parse_derivation_path(derivation_path)
        child_privkey = bip32_ctx.get_privkey_from_path(path_list)
    else:
        seed = Bip39SeedGenerator(mnemonic).Generate()
        bip44_ctx = Bip44.FromSeed(seed, Bip44Coins.DOGECOIN)
        try:
            segments = derivation_path.lstrip("m/").split("/")
            account = int(segments[2].rstrip("'"))
            change = int(segments[3])
            index = int(segments[4])
        except Exception as e:
            raise ValueError(f"Error parsing derivation path: {derivation_path}") from e
        child_privkey = bip44_ctx.Purpose().Coin().Account(account).Change(
            Bip44Changes.CHAIN_EXT if change == 0 else Bip44Changes.CHAIN_INT
        ).AddressIndex(index).PrivateKey().Raw().ToBytes()
    return private_key_to_wif(child_privkey)

def update_wif_for_transactions():
    print("\n--- Generate WIF Private Keys for DOGE Addresses with Transaction History ---")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.derivation_path, a.coin_type, m.mnemonic
        FROM addresses AS a
        JOIN mnemonics AS m ON a.mnemonic_id = m.id
        WHERE a.transactions > 0 AND (a.wif IS NULL OR a.wif = '')
    """)
    rows = cursor.fetchall()
    if not rows:
        print("No rows found that require WIF update.")
        conn.close()
        return
    updated_count = 0
    for row in rows:
        row_id, derivation_path, coin_type, mnemonic = row
        try:
            wif = derive_wif_for_row(mnemonic, derivation_path, coin_type)
            cursor.execute("UPDATE addresses SET wif = ? WHERE id = ?", (wif, row_id))
            updated_count += 1
            print(f"Updated row {row_id} with WIF: {wif}")
        except Exception as e:
            print(f"Error deriving WIF for row {row_id} with derivation path {derivation_path}: {e}")
    conn.commit()
    conn.close()
    print(f"Updated WIF for {updated_count} rows.")
    print("Returning to main menu...\n")

# -----------------------------------------------------------
# 4. Create CSV of database information for WIF generated rows
def export_csv():
    print("\n--- Export Database to CSV ---")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, address, derivation_path, transactions, balance, wif
        FROM addresses
        WHERE wif IS NOT NULL AND wif != ''
    """)
    rows = cursor.fetchall()
    if not rows:
        print("No rows with WIF found in the database.")
        conn.close()
        return
    csv_filename = input("Enter filename for CSV export (default 'doge_addresses.csv'): ").strip() or "doge_addresses.csv"
    try:
        with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Address", "Derivation Path", "Transactions", "Balance", "WIF"])
            writer.writerows(rows)
        print(f"CSV export successful. File saved as '{csv_filename}'.")
    except Exception as e:
        print(f"Error writing CSV file: {e}")
    conn.close()
    print("Returning to main menu...\n")

# -----------------------------------------------------------
# Main menu loop
def main_menu():
    while True:
        print("=" * 50)
        title = "DOGE WALLET SCAN"
        print(title.center(50))
        print("=" * 50)
        print("1. Generate DOGE addresses")
        print("2. Check DOGE addresses (BlockDaemon API)")
        print("3. Generate WIF Private Keys")
        print("4. Export CSV of Addesses with WIF Private Keys")
        print("5. Exit program")
        choice = input("Enter your choice (1-5): ").strip()
        if choice == "1":
            generate_addresses()
        elif choice == "2":
            check_addresses()
        elif choice == "3":
            update_wif_for_transactions()
        elif choice == "4":
            export_csv()
        elif choice == "5":
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please select a number from 1 to 5.\n")

if __name__ == '__main__':
    main_menu()
