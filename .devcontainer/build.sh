#!/bin/bash
set -e

echo "[build.sh] Building Detock..."

cd /workspaces/detock-vscode

rm -rf build
mkdir build
cd build

cmake .. -DCMAKE_BUILD_TYPE=release
make -j$(nproc)

echo "[build.sh] Build complete."

echo "[build.sh] Copying binaries to /opt/slog..."

cp janus /opt/slog/janus
cp slog /opt/slog/slog
cp client /opt/slog/client
cp benchmark /opt/slog/benchmark
cp scheduler_benchmark /opt/slog/scheduler_benchmark

echo "[build.sh] Copying examples and tools..."

cp -r /workspaces/detock-vscode/examples/* /opt/slog/
rm -rf /opt/slog/tools
cp -r /workspaces/detock-vscode/tools /opt/slog/

echo "[build.sh] All files copied successfully!"