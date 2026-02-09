#!/bin/bash

set -e

PREFIX=${1:-"$(pwd)/lib_rnnoise"}

apt update && apt install -y --no-install-recommends \
  git \
  autoconf \
  automake \
  libtool \
  make \
  gcc && \
  rm -rf /var/lib/apt/lists/*

if [ ! -d "rnnoise" ]; then
    git clone https://gitlab.xiph.org/xiph/rnnoise.git
fi

cd rnnoise

./autogen.sh
./configure --prefix="$PREFIX"
make -j$(nproc)
make install

echo "RNNoise library installed to $PREFIX"
