import ctypes
import os

# C's free function to release memory allocated by Go's C.CString
free = ctypes.CDLL(None).free
free.argtypes = [ctypes.c_void_p]
free.restype = None

# 加载动态链接库
def load_go_library(library_path='../golib/libgo.so'):
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

    return lib