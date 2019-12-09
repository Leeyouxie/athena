# coding=utf-8
# Copyright (C) ATHENA AUTHORS
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

if [ "athena" != "$current_dir" ]; then
    echo "You should run this script in athena directory!!"
    exit 1
fi

source /tmp-data/tools/env/tf2.0_py3.6_all_luban.env
source tools/env.sh

stage=0
stop_stage=100

if [ ${stage} -le 0 ] && [ ${stop_stage} -ge 0 ]; then
    # pretrain stage
    python athena/main.py examples/asr/hkust/mpc.json
fi

if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then
    # finetuning stage
    python athena/main.py examples/asr/hkust/mtl_transformer.json
fi

if [ ${stage} -le 2 ] && [ ${stop_stage} -ge 2 ]; then
    # decoding stage
    python athena/decode_main.py examples/asr/hkust/mtl_transformer_test.json
fi
