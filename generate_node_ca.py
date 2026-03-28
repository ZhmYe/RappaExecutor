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

    # C_GenerateBLS12381Key
    lib.C_GenerateBLS12381Key.argtypes = [
        ctypes.c_char_p, ctypes.c_int,
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)
    ]
    lib.C_GenerateBLS12381Key.restype = ctypes.c_int

    return lib


def main():
    parser = argparse.ArgumentParser(description="Generate node keys (Secp256k1 + BLS) and a CA certificate signed by a host.")
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
            raise Exception("Failed to generate node secp256k1 keys.")

        node_sk_len_val = node_sk_len.value
        node_pk_len_val = node_pk_len.value

        if node_sk_len_val != 96:
            raise Exception(f"Invalid SK length: {node_sk_len_val}, expected 96")
        if node_pk_len_val != 64:
            raise Exception(f"Invalid PK length: {node_pk_len_val}, expected 64")

        # 使用 string_at 而不是 .value，因为 .value 会在遇到 \x00 时截断
        node_sk_bytes = ctypes.string_at(node_sk_ptr, node_sk_len_val)
        node_pk_bytes = ctypes.string_at(node_pk_ptr, node_pk_len_val)

        os.makedirs("certs", exist_ok=True)

        with open("certs/node_spec_sk.key", 'w') as f:
            f.write(base64.b64encode(node_sk_bytes).decode('utf-8'))
        with open("certs/node_spec_pk.key", 'w') as f:
            f.write(base64.b64encode(node_pk_bytes).decode('utf-8'))

        print("Node Secp256k1 keys saved to node_sk.key and node_pk.key")

        # 3. Generate BLS12-381 keys
        print("Generating BLS12-381 key pair for the node...")
        bls_sk_ptr = ctypes.c_char_p()
        bls_sk_len = ctypes.c_int()
        bls_pk_ptr = ctypes.c_char_p()
        bls_pk_len = ctypes.c_int()

        ret = go_lib.C_GenerateBLS12381Key(
            node_seed, len(node_seed),
            ctypes.byref(bls_sk_ptr), ctypes.byref(bls_sk_len),
            ctypes.byref(bls_pk_ptr), ctypes.byref(bls_pk_len)
        )
        if ret != 0:
            raise Exception("Failed to generate BLS keys.")

        bls_sk_len_val = bls_sk_len.value
        bls_pk_len_val = bls_pk_len.value

        # 使用 string_at 而不是 .value，因为 .value 会在遇到 \x00 时截断
        bls_sk_bytes = ctypes.string_at(bls_sk_ptr, bls_sk_len_val)
        bls_pk_bytes = ctypes.string_at(bls_pk_ptr, bls_pk_len_val)

        with open("certs/node_bls_sk.key", 'w') as f:
            f.write(base64.b64encode(bls_sk_bytes).decode('utf-8'))
        with open("certs/node_bls_pk.key", 'w') as f:
            f.write(base64.b64encode(bls_pk_bytes).decode('utf-8'))

        print("BLS keys saved to node_bls_sk.key and node_bls_pk.key")

        # 4. Generate CA certificate (using Secp256k1 PK)
        print("Generating CA certificate for the node...")
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

        ca_json_len_val = ca_json_len.value
        # 使用 string_at 而不是 .value
        ca_json_bytes = ctypes.string_at(ca_json_ptr, ca_json_len_val)
        ca_base64_string = base64.b64encode(ca_json_bytes).decode('utf-8')

        ca_filename = "certs/node.ca"
        with open(ca_filename, 'w') as f:
            f.write(ca_base64_string)

        print(f"CA certificate (Base64 encoded) saved to {ca_filename}")

        # Clean up memory
        free(node_sk_ptr)
        free(node_pk_ptr)
        free(bls_sk_ptr)
        free(bls_pk_ptr)
        free(ca_json_ptr)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()