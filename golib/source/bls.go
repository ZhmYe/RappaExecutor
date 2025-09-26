package main

import (
	"crypto/subtle"
	"errors"
	"io"
	"math/big"

	bls12381 "github.com/consensys/gnark-crypto/ecc/bls12-381"
	ecdsa_bls12381 "github.com/consensys/gnark-crypto/ecc/bls12-381/ecdsa"
	"github.com/consensys/gnark-crypto/ecc/bls12-381/fp"
	"github.com/consensys/gnark-crypto/ecc/bls12-381/fr"
)

const (
	sizeFr         = fr.Bytes
	sizeFrBits     = fr.Bits
	sizeFp         = fp.Bytes
	sizePublicKey  = sizeFp
	sizePrivateKey = sizeFr + sizePublicKey
	sizeSignature  = 2 * sizeFr
)

// BLS12381的bls签名和聚合方式
// 这里密钥的格式是一样的但是不能用ecdsa的算法

type BLS12381PublicKey = ecdsa_bls12381.PublicKey

// BLS12381PrivateKey 私钥
type BLS12381PrivateKey struct {
	PublicKey BLS12381PublicKey // 公钥，[s]g1，一个base field上的点
	scalar    [sizeFr]byte      // [s], scalar filed上的点，一个big.int
}

func (sk *BLS12381PrivateKey) Bytes() []byte {
	// Bytes returns the binary representation of pk,
	// as byte array publicKey||scalar
	// where publicKey is as publicKey.Bytes(), and
	// scalar is in big endian, of size sizeFr.
	var res [sizePrivateKey]byte
	pubkBin := sk.PublicKey.A.Bytes()
	subtle.ConstantTimeCopy(1, res[:sizePublicKey], pubkBin[:])
	subtle.ConstantTimeCopy(1, res[sizePublicKey:sizePrivateKey], sk.scalar[:])
	return res[:]
}

func (sk *BLS12381PrivateKey) SetBytes(buf []byte) (int, error) {
	// SetBytes sets pk from buf, where buf is interpreted
	// as  publicKey||scalar
	// where publicKey is as publicKey.Bytes(), and
	// scalar is in big endian, of size sizeFr.
	// It returns the number byte read.
	n := 0
	if len(buf) < sizePrivateKey {
		return n, io.ErrShortBuffer
	}
	if _, err := sk.PublicKey.A.SetBytes(buf[:sizePublicKey]); err != nil {
		return 0, err
	}
	n += sizePublicKey
	subtle.ConstantTimeCopy(1, sk.scalar[:], buf[sizePublicKey:sizePrivateKey])
	n += sizeFr
	return n, nil
}

// Sign 将msg转化为g2上的点H，然后计算[s]H
func (sk *BLS12381PrivateKey) Sign(msg []byte) ([]byte, error) {
	hashToG2, err := bls12381.HashToG2(msg, []byte("QUUX-V01-CS02-with-BLS12381G1_XMD:SHA-256_SSWU_RO_"))
	if err != nil {
		return nil, err
	}
	var signature bls12381.G2Affine
	s := new(big.Int).SetBytes(sk.scalar[:])
	signature.ScalarMultiplication(&hashToG2, s)

	sBytes := signature.Bytes() // 96byte
	return sBytes[:], nil
}

func VerifySingleSignature(sig []byte, pk *BLS12381PublicKey, msg []byte) error {
	// e(g1, sig=[s]H) = e(pk=[s]g1, H)
	_, _, g1, _ := bls12381.Generators()
	var signature bls12381.G2Affine
	_, err := signature.SetBytes(sig)
	if err != nil {
		return err
	}
	left, err := bls12381.Pair([]bls12381.G1Affine{g1}, []bls12381.G2Affine{signature})
	if err != nil {
		return err
	}
	hashToG2, err := bls12381.HashToG2(msg, []byte("QUUX-V01-CS02-with-BLS12381G1_XMD:SHA-256_SSWU_RO_"))
	if err != nil {
		return err
	}
	right, err := bls12381.Pair([]bls12381.G1Affine{pk.A}, []bls12381.G2Affine{hashToG2})
	if !left.Equal(&right) {
		return errors.New("signature verify failed")
	}
	return nil
}

// AggregateBLS12381Signature 聚合若干个bls12381 signatures
// 每个bls12381 sig都是一个g2点，加法即可
func AggregateBLS12381Signature(sigs [][]byte) ([]byte, error) {
	if len(sigs) == 0 {
		return nil, errors.New("signature can't be empty")
	}
	g2s := make([]bls12381.G2Affine, len(sigs))
	for i := 0; i < len(sigs); i++ {
		var sig bls12381.G2Affine
		_, err := sig.SetBytes(sigs[i])
		if err != nil {
			return nil, err
		}
		g2s[i] = sig
	}
	var aggSig *bls12381.G2Affine
	aggSig = &g2s[0]
	for i := 1; i < len(sigs); i++ {
		aggSig = aggSig.Add(aggSig, &g2s[i])
	}
	aggBytes := aggSig.Bytes()
	return aggBytes[:], nil
}

func VerifyBLS12381AggregateSignature(aggSig []byte, pks []BLS12381PublicKey, msg []byte) error {
	if len(pks) == 0 {
		return errors.New("public keys can't be empty")
	}
	// 每个pk都是一个g1点
	aggPk := &pks[0].A
	for i := 1; i < len(pks); i++ {
		aggPk = aggPk.Add(aggPk, &pks[i].A)
	}
	hashToG2, err := bls12381.HashToG2(msg, []byte("QUUX-V01-CS02-with-BLS12381G1_XMD:SHA-256_SSWU_RO_"))
	if err != nil {
		return err
	}
	// e(g1, aggSig) = e(aggPk, msg)
	_, _, g1, _ := bls12381.Generators()
	var aggG2 bls12381.G2Affine
	_, err = aggG2.SetBytes(aggSig)
	if err != nil {
		return err
	}
	left, err := bls12381.Pair([]bls12381.G1Affine{g1}, []bls12381.G2Affine{aggG2})
	if err != nil {
		return err
	}
	right, err := bls12381.Pair([]bls12381.G1Affine{*aggPk}, []bls12381.G2Affine{hashToG2})
	if !left.Equal(&right) {
		return errors.New("signature verify failed")
	}
	return nil
}
