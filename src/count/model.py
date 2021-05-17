# STL
from typing import Dict

import numpy

# Utilities
import torch
from allennlp.nn.util import get_text_field_mask, sequence_cross_entropy_with_logits

# AllenNLP
from allennlp.data import Instance, Token, Vocabulary
from allennlp.data.data_loaders import SimpleDataLoader
from allennlp.data.fields import LabelField, TextField
from allennlp.data.fields.text_field import TextFieldTensors
from allennlp.data.token_indexers import SingleIdTokenIndexer, TokenIndexer

# Models
from allennlp.models import Model
from allennlp.modules import Embedding, TextFieldEmbedder

# Inference
from allennlp.predictors.predictor import Predictor

# Training
from allennlp.training.metrics import Perplexity
from allennlp.training.trainer import GradientDescentTrainer, Trainer

# Layers
from allennlp.modules.attention import Attention
from allennlp.modules.transformer import TransformerLayer, TransformerStack
from allennlp.modules import Embedding, TextFieldEmbedder
from allennlp.modules.text_field_embedders import BasicTextFieldEmbedder
from allennlp.nn.activations import Activation

# Local
from data import WikiTextReader
import config


@Model.register("language-model")
class LanguageModel(Model):
    def __init__(
        self,
        vocab: Vocabulary,
        embedder: TextFieldEmbedder,
        num_hidden_layers: int,
        hidden_size: int,
        intermediate_size: int,
        num_attention_heads: int,
        hidden_dropout: float = 0.2,
        activation: str = "relu",
    ) -> None:
        super().__init__(vocab)

        self.embedder = embedder
        self.activation = Activation.by_name(activation)()
        # question: what is intermediate size?
        self.transformer = TransformerStack(
            num_hidden_layers=num_hidden_layers,
            hidden_size=hidden_size,
            intermediate_size=intermediate_size,
            num_attention_heads=num_attention_heads,
            hidden_dropout=hidden_dropout,
            activation=self.activation,
            add_cross_attention=False,
        )

        # linear layer that maps the last last transformer layer to logits for each word
        self.vocab_size = vocab.get_vocab_size()
        self.PAD_IDX = self.vocab.get_token_index(config.PAD)
        self.linear = torch.nn.Linear(hidden_size, self.vocab_size)

        self.normalizer = config.BATCH_SIZE * config.CONTEXT_WINDOW
        self.dif_tokenizers_ratio = config.DIF_TOKENIZERS_RATIO

        self.metric = Perplexity()

    def forward(
        self,
        tokens: TextFieldTensors,
    ) -> Dict[str, torch.Tensor]:
        # shape (batch_size, timesteps)
        token_ids = tokens["tokens"]["tokens"]

        # get source and targets from tokens
        source = token_ids[:, :-1]
        target = token_ids[:, -1]

        # do embedding stuff here
        # shape (batch_size, timesteps, embedding_size)
        embeddings = self.embedder(tokens)

        # get the first part of the window
        source_embeddings = embeddings[:, :-1, :]
        # do processing stuff here
        mask = get_text_field_mask(tokens, padding_id=self.PAD_IDX)[:, :-1]
        # open issue: how are we going to resolve this mask
        # it is currently always true
        # is the behavior we want?
        # answer: this mask is true whenever the item is NOT padding

        # NOTE, need to confirm that this is getting the right output of the transformer
        # calculate logits of the next context
        trans_out = self.transformer(source_embeddings, mask)[0]

        # ==========================================================================================
        # In this scheme, we only care about the next word (e.g., if we got tokens 1-10 as input, we
        # predicted 2-11 but we only care about number 11). If we want to calculate the loss over
        # all 10 new tokens, we'd have to mask the future ones when we run it through prediction,
        # otherwise it's using knowledge that it normally wouldn't have (that is, the current/future
        # tokens).
        # ==========================================================================================

        # last_token should be [batch_size, embedding_dim]
        last_token = trans_out[:, -1]

        # shape (batch_size, vocab_size)
        logits = self.linear(last_token)
        probs = torch.nn.functional.softmax(logits, dim=1)

        # reshape them because they aren't contiguous in memory
        # unsure why this issue exists in AllenNLP
        # https://discuss.pytorch.org/t/contigious-vs-non-contigious-tensor/30107
        preds = logits.reshape(-1, self.vocab_size)
        target = target.reshape(-1)

        # temp = torch.nn.functional.cross_entropy(
        #     preds, target, ignore_index=self.PAD_IDX, reduction="sum"
        # )
        # loss = temp / self.normalizer

        # new_normalized = temp / (self.normalizer * self.dif_tokenizers_ratio)
        # calculates the perplexity for the model w.r.t new normalizer
        # self.metric(new_normalized)

        # Calculates loss without normalizing by length, since we're only predicting the next token each time.
        loss = torch.nn.functional.cross_entropy(
            preds, target, ignore_index=self.PAD_IDX, reduction="mean"
        )
        self.metric(loss)

        return {"logits": logits, "loss": loss, "probs": probs}

    def make_output_human_readable(
        self, output_dict: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:
        """Takes logits from `forward` and computes the corresponding label

        Arguments
        ---------
        output_dict : Dict[str, torch.Tensor]
            Dictionary returned by `forward`. Must contain a key with `logits`.
        Returns
        -------
        Dict[str, torch.Tensor]:
            Same as input dictionary, but with another key `label` indicating the predicted label
        """
        # Take the logits from the forward pass, and compute the label
        # IDs for maximum values
        logits = output_dict["logits"].cpu().data.numpy()
        predicted_id: numpy.ndarray = numpy.argmax(logits, axis=-1)
        # Convert these IDs back to label strings using vocab
        output_dict["label"] = [
            self.vocab.get_token_from_index(x, namespace="tokens") for x in predicted_id
        ]
        return output_dict

    def get_metrics(self, reset: bool = False) -> Dict[str, float]:
        return {"perplexity": self.metric.get_metric(reset)}

    # change parameters to be a more readable format
    def count_parameters(self):
        total = sum(p.numel() for p in self.parameters() if p.requires_grad)
        millions = total // 1_000_000
        thousands = (total - millions * 1_000_000) // 1_000
        string = str(millions) + "." + str(thousands) + "M"
        return string
