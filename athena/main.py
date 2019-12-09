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
# Only support tensorflow 2.0
# pylint: disable=invalid-name, no-member
""" a sample implementation of LAS for HKUST """
import sys
import json
import tensorflow as tf
from absl import logging
from athena import SpeechRecognitionDatasetBuilder
from athena import SpeechDatasetBuilder
from athena import HParams
from athena import BaseSolver
from athena import WarmUpAdam
from athena import ExponentialDecayAdam
from athena import Checkpoint
from athena import (
    DeepSpeechModel,
    SpeechTransformer,
    SpeechTransformer2,
    MtlTransformerCtc,
    MaskedPredictCoding,
)

SUPPORTED_DATASET_BUILDER = {
    "speech_recognition_dataset": SpeechRecognitionDatasetBuilder,
    "speech_dataset": SpeechDatasetBuilder,
}

SUPPORTED_MODEL = {
    "deep_speech": DeepSpeechModel,
    "speech_transformer": SpeechTransformer,
    "speech_transformer2": SpeechTransformer2,
    "mtl_transformer_ctc": MtlTransformerCtc,
    "mpc": MaskedPredictCoding,
}

SUPPORTED_OPTIMIZER = {
    "warmup_adam": WarmUpAdam,
    "expdecay_adam": ExponentialDecayAdam,
    "adam": tf.keras.optimizers.Adam,
}

DEFAULT_CONFIGS = {
    "batch_size": 32,
    "num_epochs": 20,
    "sorta_epoch": 1,
    "ckpt": None,
    "summary_dir": None,
    "solver_gpu": [0],
    "solver_config": None,
    "model": "speech_transformer",
    "num_classes": None,
    "model_config": None,
    "pretrained_model": None,
    "optimizer": "warmup_adam",
    "optimizer_config": None,
    "dataset_builder": "speech_recognition_dataset",
    "dataset_config": None,
    "force_recompute_cmvn": False,
    "train_csv": None,
    "dev_csv": None,
    "test_csv": None,
    "decode_config": None,
}


def parse_config(config=None):
    """ parse json config, use HParams to manage configurations
    """
    hparams = HParams()
    print(config)
    for keys in DEFAULT_CONFIGS:
        hparams.add_hparam(keys, DEFAULT_CONFIGS[keys])
    if config is not None:
        hparams.override_from_dict(config)
    return hparams


def load_model_from_jsonfile(jsonfile, rank=0, pre_run=True):
    """ creates model using configurations in json, load from checkpoint
    if previous models exist in checkpoint dir
    """
    config = None
    with open(jsonfile) as file:
        config = json.load(file)
    p = parse_config(config)
    dataset_builder = SUPPORTED_DATASET_BUILDER[p.dataset_builder](p.dataset_config)

    # models
    model = SUPPORTED_MODEL[p.model](
        num_classes=p.num_classes
        if p.num_classes is not None
        else dataset_builder.num_class,
        sample_shape=dataset_builder.sample_shape,
        config=p.model_config,
    )
    optimizer = SUPPORTED_OPTIMIZER[p.optimizer](p.optimizer_config)
    checkpointer = Checkpoint(
        checkpoint_directory=p.ckpt,
        summary_directory=p.summary_dir,
        rank=rank,
        model=model,
        optimizer=optimizer,
    )
    if pre_run or p.pretrained_model is not None:
        # pre_run for lazy initilize in keras
        solver = BaseSolver(
            model,
            optimizer,
            sample_signature=dataset_builder.sample_signature
        )
        if p.dev_csv is None:
            raise ValueError("we currently need a dev_csv for pre-load")
        dataset = dataset_builder.load_csv(p.dev_csv).as_dataset(p.batch_size)
        solver.evaluate_step(iter(dataset).next())
    return p, model, optimizer, checkpointer, dataset_builder


def train(jsonfile, Solver, rank_size=1, rank=0):
    """ entry point for model training, implements train loop

	:param jsonfile: json file to read configuration from
	:param Solver: an abstract class that implements high-level logic of train, evaluate, decode, etc
	:param rank_size: total number of workers, 1 if using single gpu
	:param rank: rank of current worker, 0 if using single gpu
	"""
    p, model, optimizer, checkpointer, dataset_builder \
        = load_model_from_jsonfile(jsonfile, rank)
    if p.pretrained_model is not None:
        p2, pretrained_model, _, _, _ \
            = load_model_from_jsonfile(p.pretrained_model, rank)
        model.restore_from_pretrained_model(pretrained_model, p2.model)

    # for cmvn
    dataset_builder.load_csv(p.train_csv).compute_cmvn_if_necessary(rank == 0)

    # train
    solver = Solver(
        model,
        optimizer,
        sample_signature=dataset_builder.sample_signature,
        config=p.solver_config,
    )
    for epoch in range(p.num_epochs):
        if rank == 0:
            logging.info(f">>>>> start training in epoch {epoch}")
        dataset_builder.load_csv(p.train_csv).shard(rank_size, rank)
        if epoch >= p.sorta_epoch:
            dataset_builder.batch_wise_shuffle(p.batch_size)
        dataset = dataset_builder.as_dataset(p.batch_size)
        solver.train(dataset)

        if rank == 0:
            logging.info(f">>>>> start evaluate in epoch {epoch}")
        dataset = dataset_builder.load_csv(p.dev_csv).as_dataset(p.batch_size)
        loss = solver.evaluate(dataset, epoch)
        checkpointer(loss)


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    tf.random.set_seed(1)

    JSON_FILE = sys.argv[1]
    CONFIG = None
    with open(JSON_FILE) as f:
        CONFIG = json.load(f)
    PARAMS = parse_config(CONFIG)
    BaseSolver.initialize_devices(PARAMS.solver_gpu)
    train(JSON_FILE, BaseSolver, 1, 0)
