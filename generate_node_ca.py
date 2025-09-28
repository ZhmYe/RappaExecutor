# generate_node_ca.py

import os
import base64
import ctypes
import json
import argparse

# C's free function to release memory allocated by Go's C.CString
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

    return lib


def main():
    parser = argparse.ArgumentParser(description="Generate node keys and a CA certificate signed by a host.")
    parser.add_argument("--host-sk-file", required=True, help="Path to the host's Base64 encoded private key file.")
    args = parser.parse_args()

    try:
        go_lib = load_go_library()

        # 1. Load host's private key
        print(f"Loading host private key from: {args.host_sk_file}")
        with open(args.host_sk_file, 'r') as f:
            host_sk_base64 = f.read().strip()
        host_sk_bytes = base64.b64decode(host_sk_base64)

        # 2. Generate new keys for the node
        print("Generating new secp256k1 key pair for the node...")
        node_seed = os.urandom(32)
        node_sk_ptr = ctypes.c_char_p()
        node_sk_len = ctypes.c_int()
        node_pk_ptr = ctypes.c_char_p()
        node_pk_len = ctypes.c_int()

        ret = go_lib.C_GenerateSecp256K1Key(
            node_seed, len(node_seed),
            ctypes.byref(node_sk_ptr), ctypes.byref(node_sk_len),
            ctypes.byref(node_pk_ptr), ctypes.byref(node_pk_len)
        )
        if ret != 0:
            raise Exception("Failed to generate node keys.")

        node_sk_bytes = node_sk_ptr.value[:node_sk_len.value]
        node_pk_bytes = node_pk_ptr.value[:node_pk_len.value]

        with open("certs/node_sk.key", 'w') as f:
            f.write(base64.b64encode(node_sk_bytes).decode('utf-8'))
        with open("certs/node_pk.key", 'w') as f:
            f.write(base64.b64encode(node_pk_bytes).decode('utf-8'))

        print("Node keys saved to node_sk.key and node_pk.key")

        # 3. Generate CA certificate
        print("Generating CA certificate for the node...")
        # 这里暂时假设是永久证书，即两个epoch均为-1
        epoch_lower = -1
        epoch_upper = -1
        ca_json_ptr = ctypes.c_char_p()
        ca_json_len = ctypes.c_int()

        ret = go_lib.C_GenerateCA(
            node_pk_bytes, len(node_pk_bytes),
            host_sk_bytes, len(host_sk_bytes),
            epoch_lower, epoch_upper,
            ctypes.byref(ca_json_ptr), ctypes.byref(ca_json_len)
        )
        if ret != 0:
            raise Exception("Failed to generate CA certificate.")

        # <--- MODIFICATION START --->
        # Get the raw JSON bytes from the Go function
        ca_json_bytes = ca_json_ptr.value[:ca_json_len.value]

        # Encode the entire JSON output to Base64
        ca_base64_string = base64.b64encode(ca_json_bytes).decode('utf-8')

        # Save the Base64 string to a file with a .b64 extension
        ca_filename = "certs/node.ca"
        with open(ca_filename, 'w') as f:
            f.write(ca_base64_string)

        print(f"CA certificate (Base64 encoded) saved to {ca_filename}")
        # <--- MODIFICATION END --->

        # Clean up memory
        free(node_sk_ptr)
        free(node_pk_ptr)
        free(ca_json_ptr)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()