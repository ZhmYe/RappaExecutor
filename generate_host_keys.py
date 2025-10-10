# generate_host_keys.py

import os
import base64
import ctypes

free = ctypes.CDLL(None).free
free.argtypes = [ctypes.c_void_p]
free.restype = None

# 加载动态链接库
def load_go_library(library_path='./libgo.so'):
    """Loads the Go shared library and sets up the function signatures."""
    if not os.path.exists(library_path):
        raise FileNotFoundError(f"Go shared library not found at {library_path}. Please compile it first.")

    lib = ctypes.CDLL(library_path)

    # C_GenerateSecp256K1Key
    lib.C_GenerateSecp256K1Key.argtypes = [
        ctypes.c_char_p, ctypes.c_int,
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)
    ]
    lib.C_GenerateSecp256K1Key.restype = ctypes.c_int

    # C_GenerateCA
    lib.C_GenerateCA.argtypes = [
        ctypes.c_char_p, ctypes.c_int,  # publicKey
        ctypes.c_char_p, ctypes.c_int,  # sk
        ctypes.c_int, ctypes.c_int,  # epochs
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)  # caJson
    ]
    lib.C_GenerateCA.restype = ctypes.c_int

    lib.C_VerifyCA.argtypes = [
        ctypes.c_char_p, ctypes.c_int,  # publicKey, publicKeyLen
        ctypes.c_char_p, ctypes.c_int,  # decryptKey, decryptKeyLen
        ctypes.c_int, ctypes.c_int,  # epochLower, epochUpper
        ctypes.c_char_p, ctypes.c_int,  # signature, signatureLen
    ]
    lib.C_VerifyCA.restype = ctypes.c_int

    # C_GenerateBLS12381Key
    lib.C_GenerateBLS12381Key.argtypes = [
        ctypes.c_char_p, ctypes.c_int,
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)
    ]
    lib.C_GenerateBLS12381Key.restype = ctypes.c_int

    return lib


def generate_and_save_keys(lib, sk_filename="host_sk.key", pk_filename="host_pk.key"):
    """
    Checks for existing keys. If not found, generates a new secp256k1 key pair
    and saves them to files in Base64 format.
    """

    # <--- MODIFICATION START --->
    # Check if both key files already exist
    if os.path.exists(sk_filename) and os.path.exists(pk_filename):
        print("Host keys already exist. Skipping generation.")
        print(f"  - Using existing Private Key: {sk_filename}")
        print(f"  - Using existing Public Key: {pk_filename}")
        return
    # <--- MODIFICATION END --->

    print("Generating new host keys...")
    seed = os.urandom(32)

    sk_ptr = ctypes.c_char_p()
    sk_len = ctypes.c_int()
    pk_ptr = ctypes.c_char_p()
    pk_len = ctypes.c_int()

    ret = lib.C_GenerateSecp256K1Key(
        seed, len(seed),
        ctypes.byref(sk_ptr), ctypes.byref(sk_len),
        ctypes.byref(pk_ptr), ctypes.byref(pk_len)
    )

    if ret != 0:
        raise Exception("Failed to generate host keys from Go library.")

    sk_bytes = sk_ptr.value[:sk_len.value]
    pk_bytes = pk_ptr.value[:pk_len.value]

    # Encode keys to Base64
    sk_base64 = base64.b64encode(sk_bytes).decode('utf-8')
    pk_base64 = base64.b64encode(pk_bytes).decode('utf-8')

    # Save to files
    with open(sk_filename, 'w') as f:
        f.write(sk_base64)
    with open(pk_filename, 'w') as f:
        f.write(pk_base64)

    print(f"New host keys generated successfully.")
    print(f"  - Private Key (Base64) saved to: {sk_filename}")
    print(f"  - Public Key (Base64) saved to: {pk_filename}")

    # Clean up memory
    free(sk_ptr)
    free(pk_ptr)


if __name__ == "__main__":
    try:
        go_lib = load_go_library()
        generate_and_save_keys(go_lib)
    except Exception as e:
        print(f"An error occurred: {e}")