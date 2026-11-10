#!/usr/bin/env bash
# Reference build procedure based on the model author's INFERENCE.md. Needs Ubuntu 22.04/24.04.
set -euo pipefail
mkdir -p "$HOME/raj0-runtime"
cd "$HOME/raj0-runtime"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip 'huggingface_hub[cli]' 'cmake>=3.26' ninja
hf download aungzaythant/Raj-0 raj-0-q8_0.gguf native-runtime.patch SHA256SUMS --local-dir model
(cd model && sha256sum -c SHA256SUMS --ignore-missing)
if [ ! -d NeMo-Speech.cpp ]; then git clone https://github.com/NVIDIA/NeMo-Speech.cpp; fi
cd NeMo-Speech.cpp
git checkout 5be7bfb104802131e61fe679b3f1401b27270216
git submodule update --init ggml third_party/cpp-httplib
if ! git apply --reverse --check ../model/native-runtime.patch >/dev/null 2>&1; then
  git apply ../model/native-runtime.patch
fi
cmake --preset cpu-asr -DNEMO_SPEECH_BUILD_HTTP=ON -DGGML_BLAS=OFF -DGGML_METAL=OFF
cmake --build --preset cpu-asr -j2
cat <<'END'
Raj-0 binary is built. Start it with:
cd ~/raj0-runtime/NeMo-Speech.cpp
export NEMO_SPEECH_HTTP_API_KEY='YOUR_LONG_UNIQUE_SERVER_SECRET'
build/cpu-asr/bin/nemo-speech serve --host 127.0.0.1 --port 8080 --device cpu \
  --asr-model "$HOME/raj0-runtime/model/raj-0-q8_0.gguf" \
  --asr.model.name Raj-0-Q8 --asr.streaming.rnnt_right_context 3 --threads 2
END
