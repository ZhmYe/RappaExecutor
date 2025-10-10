package main

import (
	ecdsa_secp "github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
)

// CA 表示一个数字信任证书
// 由可信第三方生成
// 可信第三方有一个公开的公钥pk，和一个私有的私钥sk
// 公钥要上链
// 签名：对sha256(PublicKey, EpochLowerBound, EpochUpperBound)
// 这里没有包含bls12381，因为对于用户来说没有用
type CA struct {
	PublicKey       ecdsa_secp.PublicKey // 签名的公钥 todo 其实这个pk不用加，因为证书是配合公钥发过去，这里为了方便展示证书，就写成这样吧
	EpochLowerBound int32                // epoch的范围下界
	EpochUpperBound int32                // epoch的范围上界
	Signature       []byte               // 签名结果
	DecryptKey      ecdsa_secp.PublicKey // 第三方的pk，用于解密签名得到明文（即PublicKey, EpochLowerBound, EpochUpperBound)
}

// SerializableCA 用于JSON序列化的中间结构体
// 将 ecdsa.PublicKey 替换为 []byte
type SerializableCA struct {
	PublicKey       []byte `json:"public_key"`
	EpochLowerBound int32  `json:"epoch_lower_bound"`
	EpochUpperBound int32  `json:"epoch_upper_bound"`
	Signature       []byte `json:"signature"`
	DecryptKey      []byte `json:"decrypt_key"`
}

func (ca *CA) Marshal() SerializableCA {

	pubkeyBytes := ca.PublicKey.Bytes() // [64]位的bytes，x和y各256位

	decryptKeyBytes := ca.DecryptKey.Bytes()
	return SerializableCA{
		// 使用 elliptic.Marshal 将公钥转换为标准的字节格式
		PublicKey:       pubkeyBytes[:],
		EpochLowerBound: ca.EpochLowerBound,
		EpochUpperBound: ca.EpochUpperBound,
		Signature:       ca.Signature,
		DecryptKey:      decryptKeyBytes[:],
	}
}
