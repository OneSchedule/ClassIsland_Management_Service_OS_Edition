"""
PGP 密钥管理工具

ClassIsland 客户端使用 BouncyCastle PGP (PgpCore) 进行握手：
- 客户端用服务器公钥加密 challenge token
- 服务端用私钥解密验证

此模块使用 cryptography 库生成 RSA 密钥对，并包装为 ASCII-armored PGP 格式。
简化实现：直接使用 RSA PKCS1v15 加解密 + PEM 格式的密钥。
客户端侧使用 PgpCore 库，因此需要生成兼容的 PGP 密钥。

简化方案：生成 RSA 密钥对，以 PEM 格式存储。
在实际对接时，如果客户端强制要求 PGP ASCII Armor 格式，
可以使用 gpg 命令行工具生成真正的 PGP 密钥并导入。
"""
import base64
import struct
import hashlib
import time
import os

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

from core.models import ServerKeyPair, Organization


def _rsa_pubkey_to_pgp_armored(public_key) -> tuple[str, int]:
    """
    将 RSA 公钥转换为 OpenPGP ASCII Armored 格式（v4 key packet）。
    这是一个简化实现，生成的密钥可被 PgpCore/BouncyCastle 解析。
    """
    pub_numbers = public_key.public_numbers()
    n = pub_numbers.n
    e = pub_numbers.e

    # MPI encoding: 2 bytes bit count + big-endian bytes
    def mpi(value):
        value_bytes = value.to_bytes((value.bit_length() + 7) // 8, 'big')
        bit_count = value.bit_length()
        return struct.pack('>H', bit_count) + value_bytes

    n_mpi = mpi(n)
    e_mpi = mpi(e)

    # Public key packet body (v4)
    creation_time = int(time.time())
    key_body = struct.pack('>B', 4)  # version 4
    key_body += struct.pack('>I', creation_time)  # creation time
    key_body += struct.pack('>B', 1)  # algorithm: RSA (Encrypt or Sign)
    key_body += n_mpi + e_mpi

    # Key ID = lower 8 bytes of SHA1 fingerprint
    fingerprint_data = b'\x99' + struct.pack('>H', len(key_body)) + key_body
    sha1 = hashlib.sha1(fingerprint_data).digest()
    key_id = int.from_bytes(sha1[-8:], 'big')

    # Wrap as old-format packet tag 6 (Public Key)
    packet_tag = 0xC0 | 6  # new format, tag 6
    if len(key_body) < 192:
        packet_header = struct.pack('>BB', packet_tag, len(key_body))
    else:
        packet_header = struct.pack('>B', packet_tag) + _new_format_length(len(key_body))

    packet = packet_header + key_body

    # User ID packet
    uid_str = "ClassIsland Server <server@classisland>"
    uid_tag = 0xC0 | 13  # tag 13 = User ID
    uid_body = uid_str.encode('utf-8')
    if len(uid_body) < 192:
        uid_packet = struct.pack('>BB', uid_tag, len(uid_body)) + uid_body
    else:
        uid_packet = struct.pack('>B', uid_tag) + _new_format_length(len(uid_body)) + uid_body

    pgp_data = packet + uid_packet

    armored = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n"
    b64 = base64.b64encode(pgp_data).decode('ascii')
    for i in range(0, len(b64), 76):
        armored += b64[i:i+76] + "\n"
    # CRC24
    crc = _crc24(pgp_data)
    armored += "=" + base64.b64encode(struct.pack('>I', crc)[1:]).decode('ascii') + "\n"
    armored += "-----END PGP PUBLIC KEY BLOCK-----\n"

    return armored, key_id


def _new_format_length(length):
    if length < 192:
        return struct.pack('>B', length)
    elif length < 8384:
        first = ((length - 192) >> 8) + 192
        second = (length - 192) & 0xFF
        return struct.pack('>BB', first, second)
    else:
        return struct.pack('>BI', 255, length)


def _crc24(data):
    CRC24_INIT = 0xB704CE
    CRC24_POLY = 0x1864CFB
    crc = CRC24_INIT
    for byte in data:
        crc ^= byte << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= CRC24_POLY
    return crc & 0xFFFFFF


def generate_server_keypair(organization: Organization) -> ServerKeyPair:
    """为组织生成 RSA 密钥对并保存"""
    # 停用旧密钥
    ServerKeyPair.objects.filter(
        organization=organization, is_active=True
    ).update(is_active=False)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 私钥 PEM
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    # 公钥 PGP Armored
    pub_armored, key_id = _rsa_pubkey_to_pgp_armored(private_key.public_key())

    kp = ServerKeyPair.objects.create(
        organization=organization,
        key_id=key_id,
        public_key_armored=pub_armored,
        private_key_armored=priv_pem,
        is_active=True,
    )
    return kp


def get_active_keypair(organization: Organization) -> ServerKeyPair | None:
    """获取当前活跃的密钥对"""
    return ServerKeyPair.objects.filter(
        organization=organization, is_active=True
    ).first()


def decrypt_with_private_key(private_key_pem: str, encrypted_text: str) -> str:
    """
    使用私钥解密 PGP 加密的数据。

    ClassIsland 客户端使用 PgpCore 加密 challenge token。
    PgpCore 输出的是 OpenPGP 格式的加密消息。
    这里尝试解析 OpenPGP 格式并使用 RSA 解密。

    简化实现：如果加密数据是 base64 编码的 RSA 密文，直接解密。
    如果是 PGP armored 格式，先提取密文再解密。
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'), password=None,
    )

    # 尝试解析 PGP Armored 格式
    if "-----BEGIN PGP MESSAGE-----" in encrypted_text:
        # 提取 base64 内容
        lines = encrypted_text.strip().split('\n')
        b64_lines = []
        in_body = False
        for line in lines:
            if line.strip() == '':
                in_body = True
                continue
            if line.startswith('-----'):
                in_body = False
                continue
            if line.startswith('='):
                continue  # CRC line
            if in_body:
                b64_lines.append(line.strip())

        pgp_data = base64.b64decode(''.join(b64_lines))
        # 简化：尝试找到 RSA 加密的会话密钥并解密
        # 完整的 OpenPGP 解析非常复杂，这里做最基本的处理
        try:
            plaintext = _decrypt_pgp_message(private_key, pgp_data)
            return plaintext
        except Exception:
            pass

    # Fallback: 尝试 base64 解码后直接 RSA 解密
    try:
        ciphertext = base64.b64decode(encrypted_text)
        plaintext = private_key.decrypt(
            ciphertext,
            padding.PKCS1v15(),
        )
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError(f"无法解密: {e}")


def _decrypt_pgp_message(private_key, pgp_data: bytes) -> str:
    """
    简化的 OpenPGP 消息解密。
    处理 PKESK (tag 1) + SEIP/AEAD 数据包。
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    offset = 0
    session_key = None
    algo = None

    while offset < len(pgp_data):
        # 解析包头
        tag_byte = pgp_data[offset]
        offset += 1

        if tag_byte & 0xC0 == 0xC0:
            # 新格式
            tag = tag_byte & 0x3F
            length_byte = pgp_data[offset]
            offset += 1
            if length_byte < 192:
                pkt_len = length_byte
            elif length_byte < 224:
                second = pgp_data[offset]
                offset += 1
                pkt_len = ((length_byte - 192) << 8) + second + 192
            else:
                pkt_len = struct.unpack('>I', pgp_data[offset:offset+4])[0]
                offset += 4
        else:
            # 旧格式
            tag = (tag_byte & 0x3C) >> 2
            len_type = tag_byte & 0x03
            if len_type == 0:
                pkt_len = pgp_data[offset]
                offset += 1
            elif len_type == 1:
                pkt_len = struct.unpack('>H', pgp_data[offset:offset+2])[0]
                offset += 2
            elif len_type == 2:
                pkt_len = struct.unpack('>I', pgp_data[offset:offset+4])[0]
                offset += 4
            else:
                pkt_len = len(pgp_data) - offset

        pkt_body = pgp_data[offset:offset+pkt_len]
        offset += pkt_len

        if tag == 1:
            # Public-Key Encrypted Session Key Packet
            version = pkt_body[0]
            # key_id = pkt_body[1:9]
            pk_algo = pkt_body[9]
            # RSA encrypted session key MPI
            mpi_offset = 10
            bit_count = struct.unpack('>H', pkt_body[mpi_offset:mpi_offset+2])[0]
            mpi_offset += 2
            byte_count = (bit_count + 7) // 8
            encrypted_mpi = pkt_body[mpi_offset:mpi_offset+byte_count]

            # RSA decrypt
            decrypted = private_key.decrypt(encrypted_mpi, padding.PKCS1v15())
            # Format: algo_byte + session_key + 2-byte checksum
            algo = decrypted[0]
            session_key = decrypted[1:-2]
            checksum = struct.unpack('>H', decrypted[-2:])[0]
            # Verify checksum
            calc_checksum = sum(session_key) & 0xFFFF
            if calc_checksum != checksum:
                raise ValueError("Session key checksum mismatch")

        elif tag == 18:
            # Symmetrically Encrypted Integrity Protected Data
            version = pkt_body[0]
            encrypted_data = pkt_body[1:]

            if session_key is None:
                raise ValueError("No session key found")

            # AES-128/256 CFB mode
            if algo == 7:  # AES-128
                block_size = 16
            elif algo == 8:  # AES-192
                block_size = 16
            elif algo == 9:  # AES-256
                block_size = 16
            else:
                raise ValueError(f"Unsupported symmetric algo: {algo}")

            # OpenPGP CFB: IV is block_size+2 bytes of random prefix
            iv = b'\x00' * block_size
            cipher = Cipher(algorithms.AES(session_key), modes.CFB(iv))
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(encrypted_data) + decryptor.finalize()

            # Skip random prefix (block_size + 2) and strip MDC (22 bytes)
            data = plaintext[block_size + 2:-22]

            # The data contains literal data packet
            # Parse literal data packet to get the actual content
            return _extract_literal_data(data)

    raise ValueError("Could not decrypt PGP message")


def _extract_literal_data(data: bytes) -> str:
    """从 OpenPGP literal data packet 中提取文本"""
    offset = 0
    while offset < len(data):
        tag_byte = data[offset]
        offset += 1

        if tag_byte & 0xC0 == 0xC0:
            tag = tag_byte & 0x3F
            length_byte = data[offset]
            offset += 1
            if length_byte < 192:
                pkt_len = length_byte
            elif length_byte < 224:
                second = data[offset]
                offset += 1
                pkt_len = ((length_byte - 192) << 8) + second + 192
            else:
                pkt_len = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
        else:
            tag = (tag_byte & 0x3C) >> 2
            len_type = tag_byte & 0x03
            if len_type == 0:
                pkt_len = data[offset]
                offset += 1
            elif len_type == 1:
                pkt_len = struct.unpack('>H', data[offset:offset+2])[0]
                offset += 2
            else:
                pkt_len = len(data) - offset

        pkt_body = data[offset:offset+pkt_len]
        offset += pkt_len

        if tag == 11:  # Literal Data Packet
            fmt = pkt_body[0]
            fname_len = pkt_body[1]
            # skip filename and date
            content_offset = 2 + fname_len + 4
            return pkt_body[content_offset:].decode('utf-8')

    # 如果没有找到 literal data packet, 直接返回
    return data.decode('utf-8', errors='replace')
