#!/bin/bash
# L0-L3 + Local CI 共享函数库

fail() {
    echo "[FAIL] $1" >&2
    exit 1
}

warn() {
    echo "[WARN] $1"
}

info() {
    echo "[INFO] $1"
}

ok() {
    echo "[OK] $1"
}
