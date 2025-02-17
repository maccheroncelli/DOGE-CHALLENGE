# CHAINALYSIS DOGE-CHALLENGE
<img src="https://github.com/user-attachments/assets/b623f5b6-6ae4-40d7-bc92-adc70d3dcb27" alt="Image 1" width="200" />
<img src="https://github.com/user-attachments/assets/4882a1ba-46d3-45fc-a531-8252ef12053d" alt="Image 2" width="200" />
<img src="https://github.com/user-attachments/assets/3644d99a-ca7a-4262-8e90-74997b2a4a23" alt="Image 3" width="200" />

---
# SOLUTION

**DOGE WALLET SCAN** is a Python tool that helps you locate and access your funds. With this suite you can:

- **Generate DOGE Addresses:** Create a set of Dogecoin addresses using either pre‑SLIP0044 (coin type 0) or post‑SLIP0044 (coin type 3) derivation paths.
- **Check Address Activity & Funds:** Query the BlockDaemon API to check for transaction activity and confirmed balances on your generated addresses.
- **Generate WIF Private Keys:** Derive WIF (Wallet Import Format) private keys for addresses with transaction activity so you can sweep your funds.
- **Export Data to CSV:** Export database rows with WIF keys and associated data to a CSV file.
- **Exit the Program:** Close the tool when finished.

After each operation, the tool returns you to the main menu so you can perform multiple actions in one session.

---

## Features

- **Address Generation:**  
  - Supports both pre‑SLIP0044 (using the `bip32` library) and post‑SLIP0044 (using `bip44` from `bip_utils`) derivation methods.
  - Custom Dogecoin address conversion ensures the proper Dogecoin prefix (0x1E) is used.
  - Flexible parameters allow you to specify account ranges, address indexes, and generation quantities.

- **Online Address Check:**  
  - Uses BlockDaemon’s Dogecoin endpoint to check for transaction activity and fetch confirmed balances.
  - Prompts you to enter your unique BlockDaemon API key at runtime for secure access.

- **WIF Private Key Generation:**  
  - Derives private keys using the stored mnemonic and derivation paths.
  - Converts private keys into Dogecoin WIF format (with the 0x9E prefix) so that funds can be swept.

- **CSV Export:**  
  - Exports database rows (addresses, derivation paths, transaction status, balances, and WIF keys) into a CSV file for external analysis.

- **Unified Menu System:**  
  - A polished, centered menu displays all options.
  - After each step, you are returned to the main menu to choose further operations.

---

## Requirements

### Python Version

- **Python 3.7 or higher**

### Python Packages

Install the required packages via pip:

```bash
pip install bip_utils bip32 mnemonic requests
```

### API Requirements

- **BlockDaemon API Key:**  
  To check address activity and fetch balances, you must obtain an API key from [BlockDaemon](https://www.blockdaemon.com/).  
  The tool will prompt you to enter your unique API key during the funds check operation.

---

## Usage

Run the main script with:

```bash
python DOGE_WALLET_SCAN.py
```

You will see a menu similar to:

```
==================================================
                 DOGE WALLET SCAN
==================================================
1. Generate DOGE addresses
2. Check DOGE addresses (BlockDaemon API)
3. Generate WIF Private Keys
4. Export CSV of Addresses with WIF Private Keys
5. Exit program
Enter your choice (1-5):
```

Enter the number corresponding to your desired operation. After each step, you’ll be returned to the main menu.

---

## How It Works

### 1. Generate DOGE Addresses

- **Inputs:**  
  - Seed phrase  
  - Choice of derivation method: pre‑SLIP0044 (coin type 0) or post‑SLIP0044 (coin type 3)  
  - Account range, address index, and number of addresses per combination  
  - Options for external/internal (change) addresses and hardened/non-hardened derivations (where applicable)
  
- **Process:**  
  - Uses either `bip32` (for pre‑SLIP0044) or `bip44` from `bip_utils` (for post‑SLIP0044) to derive addresses.
  - A custom function converts public keys to Dogecoin addresses with the correct prefix.
  - Stores addresses, derivation paths, and a reference to the mnemonic in a SQLite database.

- **Output:**  
  - Summary details (starting & finishing derivation paths, total addresses generated) are displayed.
  - Database is created with generated addresses, and stores the entered Private Key.
  - The tool returns to the main menu upon completion.

### 2. Check DOGE Addresses for Funds

- **Inputs:**  
  - Your unique BlockDaemon API key (entered at runtime).
  
- **Process:**  
  - The tool queries each unchecked address in the database.
  - It checks for transaction activity and fetches confirmed balances using the Dogecoin endpoint.
  - Updates the database with transaction flags and balance information.

- **Output:**  
  - Progress updates are logged to the console.
  - The tool returns to the main menu upon completion.

### 3. Generate WIF Private Keys

- **Inputs:**  
  - The tool scans for database rows with transaction activity and missing WIF keys.
  
- **Process:**  
  - Uses the stored mnemonic and derivation paths to derive private keys.
  - Converts private keys to WIF format using Dogecoin’s WIF prefix.
  - Updates the database with the generated WIF keys.

- **Output:**  
  - Confirmation messages for updated rows.
  - Returns to the main menu upon completion.

### 4. Export CSV

- **Inputs:**  
  - Filename for the CSV export (default: `doge_addresses.csv`).
  
- **Process:**  
  - The tool queries the database for rows with generated WIF keys.
  - Exports selected columns (ID, address, derivation path, transaction status, balance, WIF) to a CSV file.

- **Output:**  
  - A CSV file is created and saved.
  - Returns to the main menu upon completion.

### 5. Exit

- The program terminates.

---
