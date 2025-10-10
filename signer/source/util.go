package main

import (
	"bytes"
	"crypto/subtle"
	"encoding/binary"
	"fmt"
	"io"
	"math/big"

	bls12381 "github.com/consensys/gnark-crypto/ecc/bls12-381"
	fr_bls12381 "github.com/consensys/gnark-crypto/ecc/bls12-381/fr"
	"github.com/consensys/gnark-crypto/ecc/secp256k1"
	ecdsa_secp "github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
	fr_secp "github.com/consensys/gnark-crypto/ecc/secp256k1/fr"
	"golang.org/x/crypto/sha3"
)

// SignSlot 节点合成一个slot以后 计算这个slot的dataHash，然后对其进行签名（secp256k1)
// 后续Master会验签
// 在生成签名后计算这个签名的哈希，用于epoch验证
// 这个签名的哈希也就是SlotHash
func SignSlot(dataHash []byte, secpSk *ecdsa_secp.PrivateKey) (sig, slotHash []byte, err error) {
	sig, err = secpSk.Sign(dataHash, sha3.New256())
	if err != nil {
		return
	}
	hasher := sha3.New256()
	hasher.Write(sig)
	slotHash = hasher.Sum(nil)
	return
}

func SignRootHash(rootHash []byte, blsSk *BLS12381PrivateKey) ([]byte, error) {
	sig, err := blsSk.Sign(rootHash)
	if err != nil {
		return nil, err
	}
	return sig, nil
}

func GenerateCA(publicKey ecdsa_secp.PublicKey, sk *ecdsa_secp.PrivateKey, epochs [2]int32) (CA, error) {
	// 主要是要计算签名
	// 这里不需要zkp，只需要链上直接verify一下即可
	// 这里先对CA已知的内容计算sha256
	hasher := sha3.New256()
	// 将上面的内容转化为bytes
	pubkeyBytes := publicKey.Bytes() // [64]位的bytes，x和y各256位
	hasher.Write(pubkeyBytes[:])
	e1Bytes, err := ConvertIntToBytes(epochs[0])
	if err != nil {
		return CA{}, err
	}
	e2Bytes, err := ConvertIntToBytes(epochs[1])
	if err != nil {
		return CA{}, err
	}
	hasher.Write(e1Bytes)
	hasher.Write(e2Bytes)
	plainText := hasher.Sum(nil) // 要签名的明文

	// 使用DecryptKey对明文进行签名
	signature, err := sk.Sign(plainText, sha3.New256())
	if err != nil {
		return CA{}, err
	}
	return CA{
		PublicKey:       publicKey,
		EpochLowerBound: epochs[0],
		EpochUpperBound: epochs[1],
		Signature:       signature,
		DecryptKey:      sk.PublicKey,
	}, nil
}

// VerifyCA 用来验证这个ca内容
func VerifyCA(publicKey ecdsa_secp.PublicKey, decryptKey ecdsa_secp.PublicKey, epochs [2]int32, signature []byte) error {
	hasher := sha3.New256()

	pubkeyBytes := publicKey.Bytes() // [64]位的bytes，x和y各256位
	hasher.Write(pubkeyBytes[:])
	e1Bytes, err := ConvertIntToBytes(epochs[0])
	if err != nil {
		return err
	}
	e2Bytes, err := ConvertIntToBytes(epochs[1])
	if err != nil {
		return err
	}
	hasher.Write(e1Bytes)
	hasher.Write(e2Bytes)
	plainText := hasher.Sum(nil) // 要签名的明文

	if flag, err := decryptKey.Verify(signature, plainText, sha3.New256()); err != nil {
		return err
	} else {
		if !flag {
			return fmt.Errorf("invalid signature")
		}
	}
	return nil
}

func GenerateSecp256K1Key(k *big.Int) (*ecdsa_secp.PrivateKey, error) {
	const sizePublicKey, sizePrivateKey = 64, 96
	_, g := secp256k1.Generators()

	privateKey := new(ecdsa_secp.PrivateKey)
	// 这里由于我们拿不到privateKey.scalar，所以取巧一下，我们先得到bytes，再转过去
	//k.FillBytes(privateKey.scalar[:sizeFr])
	privateKey.PublicKey.A.ScalarMultiplication(&g, k) // 可以计算得到pk
	var res [sizePrivateKey]byte
	pubkBin := privateKey.PublicKey.A.RawBytes()
	subtle.ConstantTimeCopy(1, res[:sizePublicKey], pubkBin[:])
	subtle.ConstantTimeCopy(1, res[sizePublicKey:sizePrivateKey], k.Bytes()[:sizePrivateKey-sizePublicKey])
	_, err := privateKey.SetBytes(res[:])
	if err != nil {
		return nil, err
	}
	return privateKey, nil
}

func GenerateBLS12381Key(k *big.Int) (*BLS12381PrivateKey, error) {
	const sizePublicKey, sizePrivateKey = 48, 80
	_, _, g1, _ := bls12381.Generators()
	privateKey := new(BLS12381PrivateKey)
	privateKey.PublicKey.A.ScalarMultiplication(&g1, k) // pk
	var res [sizePrivateKey]byte
	pubkBin := privateKey.PublicKey.A.Bytes()
	subtle.ConstantTimeCopy(1, res[:sizePublicKey], pubkBin[:])
	subtle.ConstantTimeCopy(1, res[sizePublicKey:sizePrivateKey], k.Bytes()[:sizePrivateKey-sizePublicKey])
	_, err := privateKey.SetBytes(res[:])
	if err != nil {
		return nil, err
	}
	return privateKey, nil
}

func randFieldElement(rand io.Reader) (b []byte, secpK, blsK *big.Int, err error) {
	nbBits := 256 // 这里bls12381和secp256k1都是256k1
	b = make([]byte, nbBits/8+8)
	_, err = io.ReadFull(rand, b)
	if err != nil {
		return
	}
	one := new(big.Int).SetInt64(1)

	// generate bls12381 field element
	{
		blsK = new(big.Int).SetBytes(b)
		blsN := new(big.Int).Sub(fr_bls12381.Modulus(), one)
		blsK.Mod(blsK, blsN)
		blsK.Add(blsK, one)
	}
	{
		secpK = new(big.Int).SetBytes(b)
		secpN := new(big.Int).Sub(fr_secp.Modulus(), one)
		secpK.Mod(secpK, secpN)
		secpK.Add(secpK, one)
	}
	return
}

func ConvertIntToBytes(num int32) ([]byte, error) {
	buf := new(bytes.Buffer)                        // 使用bytes.Buffer来收集写入的字节
	err := binary.Write(buf, binary.BigEndian, num) // 使用big endian格式写入
	if err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}
