# Copyright (C) 2017 Beijing Didi Infinity Technology and Development Co.,Ltd.
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

import numpy as np

import tensorflow as tf

from athena.utils.hparam import HParams
from athena.transform.feats.base_frontend import BaseFrontend


class CMVN(BaseFrontend):
    def __init__(self, config: dict):
        super().__init__(config)

        self.global_cmvn = False
        if len(config.global_mean) > 1:
            self.global_cmvn = True

    @classmethod
    def params(cls, config=None):
        """ set params """

        hparams = HParams(cls=cls)
        hparams.add_hparam("type", "CMVN")
        hparams.add_hparam("global_mean", [0.0])
        hparams.add_hparam("global_variance", [1.0])
        hparams.add_hparam("local_cmvn", False)

        if config is not None:
            hparams.parse(config, True)

        assert len(hparams.global_mean) == len(
            hparams.global_variance
        ), "Error, global_mean length {} is not equals to global_variance length {}".format(
            len(hparams.global_mean), len(hparams.global_variance)
        )

        hparams.global_variance = (np.sqrt(hparams.global_variance) + 1e-6).tolist()
        return hparams

    def call(self, audio_feature, speed=1.0):
        params = self.config
        if self.global_cmvn:
            audio_feature = (
                audio_feature - params.global_mean
            ) / params.global_variance

        if params.local_cmvn:
            mean, var = tf.compat.v1.nn.moments(audio_feature, axes=0)
            audio_feature = (audio_feature - mean) / (
                tf.compat.v1.math.sqrt(var) + 1e-6
            )

        return audio_feature

        def dim(self):
            params = self.config
            return len(params.global_mean)


def compute_cmvn(audio_feature, mean=None, variance=None, local_cmvn=False):
    if mean is not None:
        assert variance is not None
        audio_feature = (audio_feature - mean) / variance
    if local_cmvn:
        mean, var = tf.compat.v1.nn.moments(audio_feature, axes=0)
        audio_feature = (audio_feature - mean) / (tf.compat.v1.math.sqrt(var) + 1e-6)
    return audio_feature
