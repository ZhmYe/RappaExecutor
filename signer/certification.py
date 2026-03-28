import ctypes
import os
import json
import base64
from pathlib import Path
from utils.function.func import get_project_root
from config.config import BHExecutionNodeGlobalConfig

# C's free function to release memory allocated by Go's C.CString
free = ctypes.CDLL(None).free
free.argtypes = [ctypes.c_void_p]
free.restype = None


class CertificateManager:
    def __init__(self):
        self.cert_path = Path(get_project_root()) / BHExecutionNodeGlobalConfig.CERT_PATH
        self.lib = self._load_go_library(os.path.join(get_project_root(), 'signer/libgo.so'))
        # 这里加载节点的公钥、私钥、CA证书
        self.spec_publicKey = None
        self.spec_privateKey = None
        self.bls_publicKey = None
        self.bls_privateKey = None
        self.ca = None
        self.ca_base64 = None
        self._load_certificates()

    # 加载动态链接库
    def _load_go_library(self, library_path='signer/libgo.so'):
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

        # C_VerifyCA
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

        # C_SignSlot
        lib.C_SignSlot.argtypes = [
            ctypes.c_char_p, ctypes.c_int,  # dataHash, dataHashLen
            ctypes.c_char_p, ctypes.c_int,  # secpSk, secpSkLen
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),  # sig, sigLen
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)  # slotHash, slotHashLen
        ]
        lib.C_SignSlot.restype = ctypes.c_int

        return lib

    def _load_certificates(self):
        """加载公钥、私钥和 CA 证书"""
        # 加载spec公钥（base64 编码）
        public_key_path = os.path.join(self.cert_path, 'node_spec_pk.key')
        if os.path.exists(public_key_path):
            with open(public_key_path, 'r') as f:
                b64_data = f.read()
                self.spec_publicKey = base64.b64decode(b64_data)
        else:
            raise FileNotFoundError(f"Spec public key file not found: {public_key_path}")

        # 加载spec私钥（base64 编码）
        private_key_path = os.path.join(self.cert_path, 'node_spec_sk.key')
        if os.path.exists(private_key_path):
            with open(private_key_path, 'r') as f:
                b64_data = f.read()
                self.spec_privateKey = base64.b64decode(b64_data)
        else:
            raise FileNotFoundError(f"Spec private key file not found: {private_key_path}")

        # 加载bls公钥（base64 编码）
        public_key_path = os.path.join(self.cert_path, 'node_bls_pk.key')
        if os.path.exists(public_key_path):
            with open(public_key_path, 'r') as f:
                b64_data = f.read()
                self.bls_publicKey = base64.b64decode(b64_data)
        else:
            raise FileNotFoundError(f"BLS public key file not found: {public_key_path}")
        # 加载bls私钥（base64 编码）
        private_key_path = os.path.join(self.cert_path, 'node_bls_sk.key')
        if os.path.exists(private_key_path):
            with open(private_key_path, 'r') as f:
                b64_data = f.read()
                self.bls_privateKey = base64.b64decode(b64_data)
        else:
            raise FileNotFoundError(f"BLS private key file not found: {private_key_path}")


        # 加载 CA 证书（JSON 格式）
        ca_path = os.path.join(self.cert_path, 'node.ca')
        if os.path.exists(ca_path):
            with open(ca_path, 'r', encoding='utf-8') as f:
                b64_data = f.read()
                self.ca_base64 = b64_data
                self.ca = json.loads(base64.b64decode(b64_data))
                # 解码 CA 证书中的公钥
                self.ca['public_key'] = base64.b64decode(self.ca['public_key'])
                self.ca['decrypt_key'] = base64.b64decode(self.ca['decrypt_key'])
                # 解码 CA 证书中的签名
                self.ca['signature'] = base64.b64decode(self.ca['signature'])
                # 验证本地证书是否合法
                epoch_lower = self.ca.get('epoch_lower_bound')
                epoch_upper = self.ca.get('epoch_upper_bound')
                if epoch_lower is None or epoch_upper is None:
                    raise ValueError("CA证书缺少epoch_lower或epoch_upper字段")

                # 准备验证参数
                public_key = self.ca['public_key']
                decrypt_key = self.ca['decrypt_key']
                signature = self.ca['signature']

                # 调用C_VerifyCA函数
                verify_result = self.lib.C_VerifyCA(
                    ctypes.c_char_p(public_key), ctypes.c_int(len(public_key)),
                    ctypes.c_char_p(decrypt_key), ctypes.c_int(len(decrypt_key)),
                    ctypes.c_int(epoch_lower), ctypes.c_int(epoch_upper),
                    ctypes.c_char_p(signature), ctypes.c_int(len(signature))
                )
                if verify_result != 0:
                    raise ValueError(f"CA证书验证失败，错误码: {verify_result}")
        else:
            raise FileNotFoundError(f"CA certificate file not found: {ca_path}")

    def sign_data(self, data: bytes):
        # For the output string parameters, we need to create proper pointer variables
        sig = ctypes.c_char_p()
        sigLen = ctypes.c_int(0)
        slotHash = ctypes.c_char_p()
        slotHashLen = ctypes.c_int(0)

        # Call the C_SignSlot function with the correct pointer types
        sign_result = self.lib.C_SignSlot(
            ctypes.c_char_p(data), ctypes.c_int(len(data)),
            ctypes.c_char_p(self.spec_privateKey), ctypes.c_int(len(self.spec_privateKey)),
            ctypes.byref(sig), ctypes.byref(sigLen),
            ctypes.byref(slotHash), ctypes.byref(slotHashLen)
        )

        # Check if the call was successful
        if sign_result != 0:
            raise Exception("Failed to sign slot")

        # Extract the signature data
        signature_data = ctypes.string_at(sig, sigLen)

        # The method only returns the base64-encoded signature data
        return base64.b64encode(signature_data).decode('utf-8')

    def get_ca_base64(self):
        """返回CA证书的base64编码"""
        return self.ca_base64


