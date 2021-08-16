// Paths
local root = '/data/users/nilay/the-count/';
// local root = '/home/offendo/src/the-count/';

// Training
local lr = 1e-5;
local decay = 1e-4;
local batch_size = 64;
local max_instances = null;
local max_instances_memory = null;
local epochs = 50;
local patience = 20;
local dropout = 0.4;

// Model config
local embed_dim = 768;
local model_path = root + 'saved-experiments/teacher-16-student-2/';
local num_head_layers = 2;

local cuda_devices = [0, 1];
local cuda_device = 0;

local reader = {
  type: 'stsb-reader',
  tokenizer_path: root + 'wordpiece-tokenizer.json',
  max_instances: max_instances,
};

{
  dataset_reader: reader,
  vocabulary: {
    type: 'from_files',
    directory: root + 'data/vocab/',
    padding_token: '[PAD]',
    oov_token: '[UNK]',
  },
  model: {
    type: 'glue-classifier',
    task: 'stsb',
    model: {
      type: 'from_archive',
      archive_file: model_path,
    },
    embedding_dim: embed_dim,
    feedforward: null,
    freeze: false,
    pool_method: 'mean',
  },
  train_data_path: 'train',
  validation_data_path: 'validation',
  test_data_path: 'test',
  data_loader: {
    type: 'multiprocess',
    batch_size: batch_size,
    shuffle: true,
    max_instances_in_memory: max_instances_memory,
    num_workers: 0,
    start_method: 'fork',
  },
  validation_data_loader: {
    type: 'multiprocess',
    batch_size: batch_size,
    shuffle: false,
    max_instances_in_memory: max_instances_memory,
    num_workers: 0,
    start_method: 'fork',
  },
  trainer: {
    type: 'gradient_descent',
    validation_metric: '+spearman',
    num_epochs: epochs,
    patience: patience,
    run_sanity_checks: false,
    optimizer: {
      type: 'adam',
      lr: lr,
      weight_decay: decay,
    },
    cuda_device: cuda_device,
    grad_norm: 0.25,
  },
}
