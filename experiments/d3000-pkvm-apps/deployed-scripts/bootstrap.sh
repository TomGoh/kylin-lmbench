#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_layout
space_guard
install -m 0644 "$SCRIPT_DIR/SOURCE_REVISION" "$EXP_HOME/SOURCE_REVISION"
mkdir -p "$EXP_HOME/notes"
install -m 0644 "$SCRIPT_DIR/EXPERIMENT_PLAN.zh-CN.md" "$EXP_HOME/notes/EXPERIMENT_PLAN.zh-CN.md"
if [[ ! -s "$EXP_HOME/notes/WORKLOG.md" ]]; then
    printf '# D3000 pKVM application benchmark worklog\n\n' >"$EXP_HOME/notes/WORKLOG.md"
fi
exec > >(tee -a "$LOG_DIR/bootstrap.log") 2>&1
bootstrap_done=no
trap 'rc=$?; record_note bootstrap "exit rc=$rc complete=$bootstrap_done"' EXIT
record_note bootstrap "start dependency installation and pinned tool build"

log "installing build and runtime dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential autoconf automake libtool pkg-config git curl ca-certificates rsync jq bc \
    libevent-dev zlib1g-dev libssl-dev \
    openjdk-17-jre-headless numactl sysstat time \
    flex bison libelf-dev libslang2-dev libnuma-dev

download() {
    local url=$1 out=$2 expected=${3:-}
    if [[ ! -s "$out" ]]; then
        log "download $url"
        curl --fail --location --retry 5 --retry-delay 2 --output "$out.part" "$url"
        mv "$out.part" "$out"
    fi
    if [[ -n "$expected" ]]; then
        printf '%s  %s\n' "$expected" "$out" | sha256sum --check
    fi
    sha256sum "$out" | tee -a "$EXP_HOME/metadata/SHA256SUMS"
}

mkdir -p "$EXP_HOME/downloads" "$TOOLS_DIR/bin"
: >"$EXP_HOME/metadata/SHA256SUMS"

redis_tar="$EXP_HOME/downloads/redis-${REDIS_VERSION}.tar.gz"
memtier_tar="$EXP_HOME/downloads/memtier_benchmark-${MEMTIER_VERSION}.tar.gz"
perftest_jar="$TOOLS_DIR/perf-test-${PERFTEST_VERSION}.jar"

download "https://github.com/redis/redis/archive/refs/tags/${REDIS_VERSION}.tar.gz" "$redis_tar" "$REDIS_SOURCE_SHA256"
download "https://github.com/redis/memtier_benchmark/archive/refs/tags/${MEMTIER_VERSION}.tar.gz" "$memtier_tar" "$MEMTIER_SOURCE_SHA256"
download "https://github.com/rabbitmq/rabbitmq-perf-test/releases/download/v${PERFTEST_VERSION}/perf-test-${PERFTEST_VERSION}.jar" \
    "$perftest_jar" "$PERFTEST_SHA256"
printf '%s  %s\n' "$GEEKBENCH_SHA256" "$GEEKBENCH_ARCHIVE" | sha256sum --check
sha256sum "$GEEKBENCH_ARCHIVE" | tee -a "$EXP_HOME/metadata/SHA256SUMS"

if [[ ! -d "$SRC_DIR/redis-${REDIS_VERSION}" ]]; then
    tar -C "$SRC_DIR" -xzf "$redis_tar"
fi
if [[ ! -d "$SRC_DIR/memtier_benchmark-${MEMTIER_VERSION}" ]]; then
    tar -C "$SRC_DIR" -xzf "$memtier_tar"
fi
if [[ ! -d "$TOOLS_DIR/geekbench-6.7.1" ]]; then
    mkdir -p "$TOOLS_DIR/geekbench-6.7.1"
    tar -C "$TOOLS_DIR/geekbench-6.7.1" --strip-components=1 -xzf "$GEEKBENCH_ARCHIVE"
fi

log "building Redis ${REDIS_VERSION}"
make -C "$SRC_DIR/redis-${REDIS_VERSION}" -j"$(nproc)" CC=gcc CXX=g++ BUILD_TLS=yes MALLOC=jemalloc
install -m 0755 "$SRC_DIR/redis-${REDIS_VERSION}/src/redis-server" "$TOOLS_DIR/bin/redis-server"
install -m 0755 "$SRC_DIR/redis-${REDIS_VERSION}/src/redis-cli" "$TOOLS_DIR/bin/redis-cli"
install -m 0755 "$SRC_DIR/redis-${REDIS_VERSION}/src/redis-benchmark" "$TOOLS_DIR/bin/redis-benchmark"

log "building memtier_benchmark ${MEMTIER_VERSION}"
pushd "$SRC_DIR/memtier_benchmark-${MEMTIER_VERSION}" >/dev/null
autoreconf -ivf
./configure --prefix="$TOOLS_DIR/memtier-${MEMTIER_VERSION}"
make -j"$(nproc)"
popd >/dev/null
mkdir -p "$TOOLS_DIR/memtier-${MEMTIER_VERSION}/bin"
install -m 0755 "$SRC_DIR/memtier_benchmark-${MEMTIER_VERSION}/memtier_benchmark" \
    "$TOOLS_DIR/memtier-${MEMTIER_VERSION}/bin/memtier_benchmark"
ln -sfn "$TOOLS_DIR/memtier-${MEMTIER_VERSION}/bin/memtier_benchmark" "$TOOLS_DIR/bin/memtier_benchmark"

lmbench_src=$(find "$SRC_DIR" -maxdepth 1 -type d -name 'kylin-lmbench-*' | head -n 1)
[[ -n "$lmbench_src" ]] || die "pinned kylin-lmbench source archive was not installed in $SRC_DIR"
log "building pinned kylin-lmbench source: $lmbench_src"
make -C "$lmbench_src" build
make -C "$lmbench_src/experiments/munmap-tlbi" op_sweep
arch_bin=$(find "$lmbench_src/bin" -mindepth 1 -maxdepth 1 -type d | head -n 1)
for bin in lat_mem_rd lmdd; do
    [[ -x "$arch_bin/$bin" ]] || die "lmbench build did not produce $bin"
    ln -sfn "$arch_bin/$bin" "$TOOLS_DIR/bin/$bin"
done
gcc -O2 -Wall -Wextra -o "$TOOLS_DIR/bin/lat_mmap_precise" "$lmbench_src/src/lat_mmap_precise.c"
ln -sfn "$lmbench_src/experiments/munmap-tlbi/op_sweep" "$TOOLS_DIR/bin/op_sweep"
gcc -O2 -Wall -Wextra -o "$TOOLS_DIR/bin/redis-seed-generator" "$SCRIPT_DIR/redis-seed-generator.c"

log "building kernel-matched perf from /home/jose/common"
mkdir -p "$BUILD_DIR/perf"
make -C /home/jose/common/tools/perf O="$BUILD_DIR/perf" -j"$(nproc)" WERROR=0 \
    NO_LIBPERL=1 NO_LIBPYTHON=1 NO_JEVENTS=1 NO_LIBTRACEEVENT=1 \
    NO_LIBAUDIT=1 NO_LIBUNWIND=1 NO_LIBBFD=1 NO_LIBCAP=1
install -m 0755 "$BUILD_DIR/perf/perf" "$TOOLS_DIR/bin/perf-6.6.30"

log "pulling RabbitMQ ${RABBITMQ_VERSION} official image"
sudo docker pull "$RABBITMQ_IMAGE"
sudo docker image inspect "$RABBITMQ_IMAGE" >"$EXP_HOME/metadata/rabbitmq-image-inspect.json"
sudo docker image inspect --format '{{join .RepoDigests "\n"}}' "$RABBITMQ_IMAGE" \
    >"$EXP_HOME/metadata/rabbitmq-image-digests.txt"

{
    gcc --version | head -n 1
    g++ --version | head -n 1
    "$TOOLS_DIR/bin/redis-server" --version
    "$TOOLS_DIR/bin/memtier_benchmark" --version
    java -jar "$perftest_jar" --version
    "$TOOLS_DIR/geekbench-6.7.1/geekbench6" --version || true
    "$TOOLS_DIR/bin/perf-6.6.30" version
} >"$EXP_HOME/metadata/tool-versions.txt" 2>&1

"$TOOLS_DIR/bin/memtier_benchmark" --help >"$EXP_HOME/metadata/memtier-help.txt" 2>&1 || test "$?" -eq 2
java -jar "$perftest_jar" --help >"$EXP_HOME/metadata/perftest-help.txt"

sudo install -m 0644 "$SCRIPT_DIR/d3000-pkvm-campaign.service" /etc/systemd/system/d3000-pkvm-campaign.service
sudo systemctl daemon-reload
sudo systemctl enable d3000-pkvm-campaign.service

touch "$STATE_DIR/bootstrap-complete"
bootstrap_done=yes
record_note bootstrap "complete; versions and hashes saved under metadata"
log "bootstrap complete"
