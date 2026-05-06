#!/usr/bin/env bash

set -ex

function export_recipe() {
    local directory="$1"
    local version="$2"

    # Check the version is available in conandata.yml
    if ! grep -q "${version}" "${directory}/conandata.yml"; then
        echo "Version ${version} not found in conandata.yml for ${directory}"
        exit 1
    fi

    conan export "${directory}" --version="${version}"
}

DIRECTORY=$(dirname "$0")

pushd "${DIRECTORY}"/recipes/

export_recipe abseil/all 20250127
export_recipe ed25519/all 2015.03
export_recipe mpt-crypto/all 0.3.0-rc1
export_recipe openssl/3.x.x 3.5.5
export_recipe openssl/3.x.x 3.6.2
export_recipe secp256k1/all 0.7.1
export_recipe snappy/all 1.1.10
export_recipe wasm-xrplf/all 2.4.1-xrplf
export_recipe wasmi/all 1.0.6
export_recipe wasmi/all 1.0.9
