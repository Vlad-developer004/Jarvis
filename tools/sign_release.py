"""Release signing for the self-updater (core/system/app_updater.py).

  python tools/sign_release.py genkey <private_key_file>      one time: creates the key pair, prints the public key line
  python tools/sign_release.py sign <private_key_file> <zip>  writes SHA256SUMS and SHA256SUMS.sig next to the zip

Upload the .zip, SHA256SUMS and SHA256SUMS.sig to the GitHub release. Put the public key (64 hex characters) into
data/update_pubkey.txt before building. Keep the private key file outside the repository and out of cloud-synced folders.
"""
import base64
import hashlib
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def genkey(path: Path) -> None:
    if path.exists():
        sys.exit(f'{path} already exists; refusing to overwrite a key')
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw, encryption_algorithm=serialization.NoEncryption())
    path.write_text(base64.b64encode(seed).decode('ascii'), encoding='ascii')
    pub = key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    print('private key written to', path)
    print('public key for data/update_pubkey.txt:', pub.hex())


def sign(key_file: Path, archive: Path) -> None:
    seed = base64.b64decode(key_file.read_text(encoding='ascii').strip())
    key = Ed25519PrivateKey.from_private_bytes(seed)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = f'{digest}  {archive.name}\n'.encode('utf-8')
    (archive.parent / 'SHA256SUMS').write_bytes(sums)
    (archive.parent / 'SHA256SUMS.sig').write_bytes(base64.b64encode(key.sign(sums)))
    print('signed', archive.name, digest)


def main(argv: list[str]) -> None:
    if len(argv) == 3 and argv[1] == 'genkey':
        genkey(Path(argv[2]))
    elif len(argv) == 4 and argv[1] == 'sign':
        sign(Path(argv[2]), Path(argv[3]))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
