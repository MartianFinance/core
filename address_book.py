import json
import os
import time

ADDRESS_FILE = "addresses.json"
LOCK_FILE = "addresses.json.lock"

def acquire_lock(timeout=5):
    """Acquires a file-based lock, waiting up to the timeout."""
    start_time = time.time()
    while True:
        try:
            # Attempt to create the lock file in exclusive mode
            with open(LOCK_FILE, 'x') as f:
                return True # Lock acquired
        except FileExistsError:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Could not acquire lock on {ADDRESS_FILE} within {timeout} seconds.")
            time.sleep(0.1)

def release_lock():
    """Releases the file-based lock."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def save_address(name: str, address: str):
    """Saves an agent's address to the shared address file using a file lock."""
    try:
        acquire_lock()
        addresses = {}
        if os.path.exists(ADDRESS_FILE):
            with open(ADDRESS_FILE, "r") as f:
                try:
                    addresses = json.load(f)
                except json.JSONDecodeError:
                    pass # File is empty or corrupt, will overwrite
        
        addresses[name] = address
        
        with open(ADDRESS_FILE, "w") as f:
            json.dump(addresses, f, indent=4)
    finally:
        release_lock()

def get_address(name: str, retries: int = 5, delay: int = 1) -> str:
    """
    Retrieves an agent's address from the shared address file.
    Retries if the address is not found immediately.
    """
    for i in range(retries):
        if os.path.exists(ADDRESS_FILE):
            with open(ADDRESS_FILE, "r") as f:
                try:
                    addresses = json.load(f)
                    address = addresses.get(name)
                    if address:
                        return address
                except (json.JSONDecodeError, KeyError):
                    pass  # File might be being written to or key doesn't exist yet
        
        if i < retries - 1:
            time.sleep(delay)
            
    raise ValueError(f"Address for '{name}' not found in {ADDRESS_FILE} after {retries} retries.")
