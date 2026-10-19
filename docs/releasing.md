# Releasing and update trust

The self-updater (`core/system/app_updater.py`) installs a release only when all of this holds:

1. The GitHub release has three assets: the `.zip`, `SHA256SUMS` and `SHA256SUMS.sig`.
2. `SHA256SUMS.sig` is a valid ed25519 signature (base64) of `SHA256SUMS`, made with the owner's private key. The matching public key
   (64 hex characters) is in `data/update_pubkey.txt` of the installed build.
3. The downloaded zip has the SHA-256 listed in the signed `SHA256SUMS`.
4. The archive has no absolute paths, `..`, drive letters, device names, or an absurd size.

A build without `data/update_pubkey.txt` still announces new versions but never installs one.

## One-time setup

```
python tools/sign_release.py genkey C:\secure\jarvis_release.key
```

Keep the key file outside the repository and outside cloud-synced folders (OneDrive); back it up. Put the printed public key line
into `data/update_pubkey.txt` and build.

## Each release

```
python tools/sign_release.py sign C:\secure\jarvis_release.key dist\Jarvis-1.2.3.zip
```

Upload `Jarvis-1.2.3.zip`, `SHA256SUMS` and `SHA256SUMS.sig` to the release. The tag must look like `v1.2.3`.

## Downloaded models

Models and helper files (speech models, face detector, chat model, telemetry plugin) are fetched over HTTPS only. To pin one, add its
file name and SHA-256 to `data/model_hashes.json` (`{"model.int8.onnx": "<64 hex>"}`); a pinned file that does not match is deleted. Files
without a pin are accepted as before.
