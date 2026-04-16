#!/usr/bin/env bash

set -ex

DIRECTORY=$(dirname "$0")

pushd "${DIRECTORY}"/recipes/

conan export abseil/all --version=20250127.0
conan export ed25519/all --version=2015.03
conan export m4/all --version=1.4.19
conan export mpt-crypto/all --version=0.3.0-rc1
conan export openssl/3.x.x --version=3.5.5
conan export openssl/3.x.x --version=3.6.1
conan export secp256k1/all --version=0.7.1
conan export snappy/all --version=1.1.10
conan export wasm-xrplf/all --version=2.4.1-xrplf
conan export wasmi/all --version=1.0.6
conan export wasmi/all --version=1.0.9

popd
