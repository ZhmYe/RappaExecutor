from binascii import hexlify
from typing import List
from .bls12381 import n
from .ec import G1Generator, G2Generator
from utils.cryptography.commitment.kzg.pairing import ate_pairing
from utils.cryptography.commitment.kzg.polynomial import lagrange_polynomial, evaluate_polynomial, polynomial_division
from utils.cryptography.commitment.kzg.util import rand_int


class KZGSetupParams:
    def __init__(self, G1, G2):
        self.G1 = G1
        self.G2 = G2
        self.g1, self.g2 = self.setup()
    def setup(self, length=16):
        s = rand_int(n)
        s_powers = [s**i%n for i in range(length)]
        return [j*self.G1 for j in s_powers], s*self.G2
class KZGProof:
    def __init__(self, commitment, pi, point, params: KZGSetupParams):
        self.commitment = commitment
        self.pi = pi
        self.point = point
        self.params = params
    def verify(self, data: bytes)->bool:
        s_minus_x=(n-self.point[0])*self.params.G2+self.params.g2
        result=ate_pairing(self.pi, s_minus_x)
        c_minus_y=(n-self.point[1])*self.params.G1+self.commitment
        return result==ate_pairing(c_minus_y, self.params.G2) and int(hexlify(data).decode(), 16) # 还要验证数据
class KZGCommitment:
    def __init__(self):
        # 首先setup TODO:@YZM 这里拿到外面统一setup
        G1 = G1Generator()
        G2 = G2Generator()
        self._setup_params = KZGSetupParams(G1, G2)
        # self.points = []
        self.data: List[bytes] = []
        self.commitment = None
        self.poly = None
    def commit(self, vec: List[bytes]):
        # 首先要把数据poly
        self.data = vec # 用于查找
        self.poly = self._encode_vec_to_poly()
        # assert len(self.poly)-1<=len(self._setup_params.g1), "polynomial too large"
        assert len(self.poly) == len(self._setup_params.g1), "polynomial too large"
        self.commitment = sum([i1*i2 for i1, i2 in zip(self.poly, self._setup_params.g1)])
        # self.commitment = kzg.commit(self.poly, self._setup_params.g1)
    # 这里其实没有和EC结合在一起，先这样写 TODO
    def _encode_vec_to_poly(self):
        points = [(i, int(hexlify(self.data[i]).decode(), 16)) for i in range(len(self.data))]
        return lagrange_polynomial(points=points)
    # 这里的承诺打开设置为，将某个chunk传入，open会给出它在向量中的位置，然后给出这个chunk的point表示
    def open(self, data: bytes):
        index = None
        for i, item in enumerate(self.data):
            if item == data:
                index = i
                break
        if index is None:
            raise ValueError("Data not found in kzg vector...")
        # point = self.points[index]
        point = (index, evaluate_polynomial(self.poly,index))
        # assert self.points[index][0] == point[0], "xs should be equal"
        # assert self.points[index][1] == point[1], "ys should be equal"
        px_minus_y = [((n-1)*point[1]+self.poly[0])%n]+self.poly[1:]
        qx, remainder = polynomial_division(px_minus_y,(n-1)*point[0])
        assert remainder==0, "point not on polynomial"
        pi =  sum([i1*i2 for i1, i2 in zip(qx, self._setup_params.g1[:len(qx)])])
        return KZGProof(commitment=self.commitment, pi=pi, point=point, params=self._setup_params)

    @staticmethod
    def verify(proof: KZGProof, data: bytes) -> bool:
        return proof.verify(data)