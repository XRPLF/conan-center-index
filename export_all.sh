#!/usr/bin/env bash

set -ex

if ! command -v yq &> /dev/null; then
    echo "yq could not be found. Please install yq to run this script."
    exit 1
fi

function export_recipe() {
    local directory="$1"
    local version="$2"

    # Check the version is available in conandata.yml
    yq --exit-status ".sources | has(\"${version}\")" "${directory}/conandata.yml"
    conan export "${directory}" --version="${version}"
}

DIRECTORY=$(dirname "$0")

pushd "${DIRECTORY}"/recipes/

export_recipe abseil/all 20250127.0
export_recipe ed25519/all 2015.03
export_recipe grpc/all 1.81.1
export_recipe mpt-crypto/all 1.0.0
export_recipe openssl/3.x.x 3.5.7
export_recipe openssl/3.x.x 3.6.3
export_recipe secp256k1/all 0.7.1
export_recipe snappy/all 1.1.10
export_recipe wasm-xrplf/all 2.4.1-xrplf
export_recipe wasmi/all 1.0.6
export_recipe wasmi/all 1.0.9

popd
