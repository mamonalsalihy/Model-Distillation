// Paths
local root = '/home/offendo/src/the-count/';

// Training
local context = 256;
local lr = 1e-3;
local decay = 0.0;
local batch_size = 4;
local max_instances = 16;
local max_instances_memory = null;
local epochs = 1000;
local patience = 1000;
local dropout = 0.0;

// Model config
local num_layers = 1;
local embedding_dim = 768;
local hidden_dim = 768 * 4;
local num_attention_heads = 12;
local activation = 'relu';

local cuda_devices = [1, 2];
local cuda_device = 0;

local train_reader = {
  type: 'wikitext-reader',
  context: context,
  tokenizer: {
    type: 'wikitext-tokenizer',
    tokenizer_path: root + 'unigram-tokenizer.json',
    add_special_tokens: true,
  },
  token_indexers: {
    tokens: {
      type: 'single_id',
      namespace: 'tokens',
    },
  },
  exclusive: true,
  split_on: 'paragraph',
  min_context_len: 2,
  max_instances: max_instances,
  manual_multiprocess_sharding: true,
  manual_distributed_sharding: true,
};

local eval_reader = {
  type: 'wikitext-reader',
  context: context,
  tokenizer: {
    type: 'wikitext-tokenizer',
    tokenizer_path: root + 'unigram-tokenizer.json',
    add_special_tokens: true,
  },
  token_indexers: {
    tokens: {
      type: 'single_id',
      namespace: 'tokens',
    },
  },
  exclusive: false,
  eval: true,
  split_on: 'paragraph',
  min_context_len: 2,
  max_instances: max_instances,
  manual_multiprocess_sharding: true,
  manual_distributed_sharding: true,
};

{
  dataset_reader: train_reader,
  vocabulary: {
    type: 'from_files',
    directory: root + 'data/vocab/',
    padding_token: '[PAD]',
    oov_token: '[UNK]',
  },
  model: {
    type: 'simple-transformer-language-model',
    embedding_dim: embedding_dim,
    max_positions: context,
    embedder: {
      type: 'basic',
      token_embedders: {
        tokens: {
          type: 'embedding',
          embedding_dim: embedding_dim,
        },
      },
    },
    decoder: {
      type: 'gpt2-transformer-decoder',
      input_dim: embedding_dim,
      hidden_dim: hidden_dim,
      num_attention_heads: num_attention_heads,
      num_layers: num_layers,
      activation: activation,
      dropout: dropout,
    },
    // initializer: {
    //   regexes: [
    //     ['.*weight', { type: 'xavier_normal' }],
    //   ],
    // },
  },
  train_data_path: root + 'data/wikitext-103-raw/wiki.train.raw',
  validation_data_path: root + 'data/wikitext-103-raw/wiki.valid.raw',
  test_data_path: root + 'data/wikitext-103-raw/wiki.test.raw',
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
    validation_metric: '-perplexity',
    num_epochs: epochs,
    patience: patience,
    optimizer: {
      type: 'adam',
      lr: lr,
      weight_decay: decay,
    },
    // learning_rate_scheduler: {
    //   type: 'cosine',
    //   t_initial: epochs,
    // },
    run_confidence_checks: false,
    cuda_device: cuda_device,
    grad_norm: 0.25,
    callbacks: [
      {
        type: 'tensorboard',
      },
    ],
  },
  // distributed: {
  //   cuda_devices: cuda_devices,
  // },
}