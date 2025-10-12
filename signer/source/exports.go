package main

/*
#include <stdlib.h>
*/
import "C"
import (
	"encoding/json"
	"math/big"
	"unsafe"

	ecdsa_secp "github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
)

// C_SignSlot
//export C_SignSlot
func C_SignSlot(dataHash *C.char, dataHashLen C.int, secpSk *C.char, secpSkLen C.int, sig **C.char, sigLen *C.int, slotHash **C.char, slotHashLen *C.int) C.int {
	dataHashBytes := C.GoBytes(unsafe.Pointer(dataHash), dataHashLen)
	secpSkBytes := C.GoBytes(unsafe.Pointer(secpSk), secpSkLen)

	var sk ecdsa_secp.PrivateKey
	if _, err := sk.SetBytes(secpSkBytes); err != nil {
		return -1
	}

	// Calling the original Go function
	sigBytes, slotHashBytes, err := SignSlot(dataHashBytes, &sk)
	if err != nil {
		return -1
	}

    // Note: C.CString allocates memory that C must free. Python's ctypes will handle this.
	*sig = C.CString(string(sigBytes))
	*sigLen = C.int(len(sigBytes))
	*slotHash = C.CString(string(slotHashBytes))
	*slotHashLen = C.int(len(slotHashBytes))

	return 0
}

// C_SignRootHash 导出版本 (Renamed from SignRootHash)
//export C_SignRootHash
func C_SignRootHash(rootHash *C.char, rootHashLen C.int, blsSk *C.char, blsSkLen C.int, sig **C.char, sigLen *C.int) C.int {
	rootHashBytes := C.GoBytes(unsafe.Pointer(rootHash), rootHashLen)
	blsSkBytes := C.GoBytes(unsafe.Pointer(blsSk), blsSkLen)

	var sk BLS12381PrivateKey
	if _, err := sk.SetBytes(blsSkBytes); err != nil {
		return -1
	}

	sigBytes, err := SignRootHash(rootHashBytes, &sk)
	if err != nil {
		return -1
	}

	*sig = C.CString(string(sigBytes))
	*sigLen = C.int(len(sigBytes))

	return 0
}

// C_GenerateCA 导出版本 (Renamed from GenerateCA)
//export C_GenerateCA
func C_GenerateCA(publicKey *C.char, publicKeyLen C.int, sk *C.char, skLen C.int, epochLower C.int, epochUpper C.int, caJson **C.char, caJsonLen *C.int) C.int {
	pubKeyBytes := C.GoBytes(unsafe.Pointer(publicKey), publicKeyLen)
	skBytes := C.GoBytes(unsafe.Pointer(sk), skLen)

	var pk ecdsa_secp.PublicKey
	if _, err := pk.SetBytes(pubKeyBytes); err != nil {
		return -1
	}

	var privateKey ecdsa_secp.PrivateKey
	if _, err := privateKey.SetBytes(skBytes); err != nil {
		return -1
	}

	epochs := [2]int32{int32(epochLower), int32(epochUpper)}

	ca, err := GenerateCA(pk, &privateKey, epochs)
	if err != nil {
		return -1
	}

	serializableCA := ca.Marshal()
	jsonBytes, err := json.Marshal(serializableCA)
	if err != nil {
		return -1
	}

	*caJson = C.CString(string(jsonBytes))
	*caJsonLen = C.int(len(jsonBytes))

	return 0
}

// C_VerifyCA 导出版本
//export C_VerifyCA
func C_VerifyCA(publicKey *C.char, publicKeyLen C.int, decryptKey *C.char, decryptKeyLen C.int, epochLower C.int, epochUpper C.int, signature *C.char, signatureLen C.int) C.int {
	pubKeyBytes := C.GoBytes(unsafe.Pointer(publicKey), publicKeyLen)
	decryptKeyBytes := C.GoBytes(unsafe.Pointer(decryptKey), decryptKeyLen)
	signatureBytes := C.GoBytes(unsafe.Pointer(signature), signatureLen)

	var pk ecdsa_secp.PublicKey
	if _, err := pk.SetBytes(pubKeyBytes); err != nil {
		return -1
	}

	var dk ecdsa_secp.PublicKey
	if _, err := dk.SetBytes(decryptKeyBytes); err != nil {
		return -1
	}

	epochs := [2]int32{int32(epochLower), int32(epochUpper)}

	if err := VerifyCA(pk, dk, epochs, signatureBytes); err != nil {
		return -1
	}

	return 0
}

// C_GenerateSecp256K1Key 导出版本 (Renamed from GenerateSecp256K1Key)
//export C_GenerateSecp256K1Key
func C_GenerateSecp256K1Key(k *C.char, kLen C.int, privateKey **C.char, privateKeyLen *C.int, publicKey **C.char, publicKeyLen *C.int) C.int {
	kBytes := C.GoBytes(unsafe.Pointer(k), kLen)
	bigIntK := new(big.Int).SetBytes(kBytes)

	sk, err := GenerateSecp256K1Key(bigIntK)
	if err != nil {
		return -1
	}

	skBytes := sk.Bytes()
	pkBytes := sk.PublicKey.Bytes()

	*privateKey = C.CString(string(skBytes))
	*privateKeyLen = C.int(len(skBytes))
	*publicKey = C.CString(string(pkBytes[:]))
	*publicKeyLen = C.int(len(pkBytes))

	return 0
}

// C_GenerateBLS12381Key 导出版本 (Renamed from GenerateBLS12381Key)
//export C_GenerateBLS12381Key
func C_GenerateBLS12381Key(k *C.char, kLen C.int, privateKey **C.char, privateKeyLen *C.int, publicKey **C.char, publicKeyLen *C.int) C.int {
	kBytes := C.GoBytes(unsafe.Pointer(k), kLen)
	bigIntK := new(big.Int).SetBytes(kBytes)

	sk, err := GenerateBLS12381Key(bigIntK)
	if err != nil {
		return -1
	}

	skBytes := sk.Bytes()
	pkBytes := sk.PublicKey.A.Bytes()

	*privateKey = C.CString(string(skBytes))
	*privateKeyLen = C.int(len(skBytes))
	*publicKey = C.CString(string(pkBytes[:]))
	*publicKeyLen = C.int(len(pkBytes))

	return 0
}

// main 函数是必须的，但在这里它什么也不做。
func main() {}